#!/usr/bin/env python3
"""
pbip-from-dbt — Build an openable Power BI Project (PBIP) from a completed dbt pipeline.

Reads pipeline-design.md Section 11 (Created Objects Registry) to discover dim_*/fct_*
tables, reads project-config.yml for SQL Server connection details, and generates a
PBIP folder with:
  * One M-partition table per dimension/fact (columns auto-detected on first refresh)
  * Parameterised connection: SqlEndpoint + Database expressions
  * Blank report shell (one empty page) so the .pbip opens in Power BI Desktop

No measures, relationships, or visuals are pre-defined — user builds those in Desktop.

Usage:
    python build_pbip.py --output "5 - Reports/sales-analytics" --name "Sales Analytics"
"""

import argparse
import fnmatch
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"

INVALID_NAME_CHARS = set('/\\:*?"<>|')


def log(msg: str, verbose: bool) -> None:
    if verbose:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


# ---------- CLI ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a PBIP folder from a completed dbt pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output", required=True,
                   help="Output directory (project folder will be created inside).")
    p.add_argument("--name", required=True,
                   help="Project display name (also used for folder names).")
    p.add_argument("--design-file", default="1 - Documentation/pipeline-design.md",
                   help="Path to pipeline-design.md (relative to --project-root or cwd).")
    p.add_argument("--config-file", default="project-config.yml",
                   help="Path to project-config.yml (relative to --project-root or cwd).")
    p.add_argument("--project-root", default=".",
                   help="Project root. Used to resolve --design-file and --config-file.")
    p.add_argument("--server", default=None,
                   help="SQL Server endpoint. Overrides project-config.yml database.server.")
    p.add_argument("--database", default=None,
                   help="Database name. Overrides project-config.yml database.name.")
    p.add_argument("--schema", default="dbo_analytics",
                   help="Schema containing dim_*/fct_* tables.")
    p.add_argument("--culture", default="en-GB",
                   help="Default culture for the semantic model.")
    p.add_argument("--include", default="dim_*,fct_*",
                   help="Comma-separated glob patterns. Only tables matching these are included.")
    p.add_argument("--exclude", default="stg_*,raw_*",
                   help="Comma-separated glob patterns. Tables matching these are excluded.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing output directory.")
    p.add_argument("--verbose", action="store_true",
                   help="Show detailed progress.")
    return p.parse_args()


# ---------- Input parsing ----------

def parse_design_file(path: Path) -> dict:
    """Extract table names from Section 11 (Created Objects Registry)."""
    if not path.exists():
        raise FileNotFoundError(f"pipeline-design.md not found at: {path}")

    text = path.read_text(encoding="utf-8")

    section_11_match = re.search(
        r"^##\s*11\.\s*Created\s*Objects\s*Registry.*?(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not section_11_match:
        raise ValueError("Section 11 (Created Objects Registry) not found in design file.")
    section_11 = section_11_match.group(0)

    def extract_tables(heading_pattern: str) -> list[str]:
        m = re.search(
            rf"^###\s*{heading_pattern}.*?\n(.*?)(?=^###\s|\Z)",
            section_11, re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if not m:
            return []
        block = m.group(1)
        names: list[str] = []
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith("|--") or line.startswith("|-"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells or not cells[0] or cells[0].lower() in ("object name", "name"):
                continue
            # Skip separator rows and HTML comments
            if cells[0].startswith("<!--"):
                continue
            names.append(cells[0])
        return names

    return {
        "dimensions": extract_tables(r"Dimensions?"),
        "facts": extract_tables(r"Facts?"),
    }


def parse_config_file(path: Path) -> dict:
    """Extract {server, database, schema} from project-config.yml.

    Understands three schema shapes, tried in priority order:

      1. `dbt.database.*` — produced by `dbt-project-initializer` skill in
         this plugin. Keys: `target` (db name), `server`, `dbt_schema`.
      2. `sql_server.default_*` — also written by the initializer. Keys:
         `default_server`, `default_database`, `source_schema`.
      3. `database.*` top-level — legacy shape from the original pbip-from-dbt
         design doc. Keys: `server`, `name`/`database`, `schema`.

    First non-empty value for each field wins. Returns empty dict if file
    missing or unparseable.
    """
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    except ImportError:
        return _parse_config_fallback(path)
    except Exception:
        return {}

    if not isinstance(cfg, dict):
        return {}

    dbt_db = (cfg.get("dbt") or {}).get("database") or {}
    sql_srv = cfg.get("sql_server") or {}
    legacy_db = cfg.get("database") or {}

    def _first(*candidates):
        for v in candidates:
            if v:
                return v
        return None

    return {
        "server": _first(
            dbt_db.get("server"),
            sql_srv.get("default_server"),
            legacy_db.get("server"),
        ),
        "database": _first(
            dbt_db.get("target"),
            sql_srv.get("default_database"),
            legacy_db.get("name"),
            legacy_db.get("database"),
        ),
        "schema": _first(
            # Note: dbt_schema is the profile default schema (e.g. "dbo"),
            # not the mart schema. We don't map it — --schema defaults to
            # "dbo_analytics" at CLI level, which matches the initializer's
            # dbt_project.yml marts config.
            legacy_db.get("schema"),
        ),
    }


def _parse_config_fallback(path: Path) -> dict:
    """Regex-based fallback for when PyYAML is not installed.

    Handles the same three schema shapes as parse_config_file but via line
    scanning. Less robust — e.g. does not handle multi-line YAML strings —
    but sufficient for the keys we need.
    """
    text = path.read_text(encoding="utf-8")
    result: dict = {}

    def _set_once(key: str, value: str):
        if key not in result and value:
            result[key] = value

    # 1) dbt.database.* — look for a `  database:` line indented under `dbt:`
    #    We walk the file with a simple indent tracker.
    lines = text.splitlines()
    path_stack: list[tuple[int, str]] = []  # (indent, key)
    for raw in lines:
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)
        # Pop deeper-or-equal indents off the stack
        while path_stack and indent <= path_stack[-1][0]:
            path_stack.pop()
        m = re.match(r"([A-Za-z_][\w\-]*)\s*:\s*(.*)$", stripped)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
        dotted = ".".join([k for _, k in path_stack] + [key])
        if not val:
            path_stack.append((indent, key))
            continue
        # Map known paths
        if dotted == "dbt.database.server":
            _set_once("server", val)
        elif dotted == "dbt.database.target":
            _set_once("database", val)
        elif dotted == "sql_server.default_server":
            _set_once("server", val)
        elif dotted == "sql_server.default_database":
            _set_once("database", val)
        elif dotted == "database.server":
            _set_once("server", val)
        elif dotted in ("database.name", "database.database"):
            _set_once("database", val)
        elif dotted == "database.schema":
            _set_once("schema", val)

    return result


def read_plugin_settings_local(project_root: Path) -> dict:
    """Fallback connection source: .claude/settings.local.json.

    `configure.py` (sql-connection skill) writes SQL connection options here
    under `pluginConfigs.dbt-pipeline-toolkit.options.{sql_server,sql_database}`.
    If the orchestrator ran its Pre-Stage connection test before invoking this
    skill, those keys are populated and we can fall back to them when
    project-config.yml lacks a server/database value.
    """
    import json as _json
    try:
        settings_path = project_root / ".claude" / "settings.local.json"
        if not settings_path.exists():
            return {}
        data = _json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        opts = (
            data.get("pluginConfigs", {})
                .get("dbt-pipeline-toolkit", {})
                .get("options", {})
        )
        if not isinstance(opts, dict):
            return {}
        return {
            "server": opts.get("sql_server"),
            "database": opts.get("sql_database"),
        }
    except (OSError, ValueError):
        return {}


def filter_tables(names: list[str], include: str, exclude: str) -> list[str]:
    inc_patterns = [p.strip() for p in include.split(",") if p.strip()]
    exc_patterns = [p.strip() for p in exclude.split(",") if p.strip()]
    out: list[str] = []
    for n in names:
        if any(fnmatch.fnmatch(n, p) for p in exc_patterns):
            continue
        if inc_patterns and not any(fnmatch.fnmatch(n, p) for p in inc_patterns):
            continue
        out.append(n)
    return out


# ---------- Validation ----------

def validate_name(name: str) -> None:
    if not name or not name.strip():
        raise ValueError("Project name cannot be empty.")
    invalid = [c for c in name if c in INVALID_NAME_CHARS]
    if invalid:
        raise ValueError(f"Project name contains invalid chars: {sorted(set(invalid))}")


def validate_output(output_dir: Path, force: bool) -> None:
    if output_dir.exists():
        if not force:
            raise FileExistsError(
                f"Output directory already exists: {output_dir}. Use --force to overwrite."
            )


# ---------- Template rendering ----------

def write_utf8(path: Path, content: str, crlf: bool = False) -> None:
    """Write content as UTF-8 without BOM. Use CRLF for .json files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if crlf:
        content = content.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)


def render_tpl(src: Path, dst: Path, subs: dict[str, str], crlf: bool = False) -> None:
    content = src.read_text(encoding="utf-8")
    for key, val in subs.items():
        content = content.replace("{{" + key + "}}", val)
    write_utf8(dst, content, crlf=crlf)


def copy_verbatim(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# ---------- Generators ----------

def gen_expressions_tmdl(server: str, database: str) -> str:
    sql_lineage = str(uuid.uuid4())
    db_lineage = str(uuid.uuid4())
    return (
        f'expression SqlEndpoint = "{server}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {sql_lineage}\n"
        f"\tqueryGroup: Parameters\n"
        f"\n"
        f"\tannotation PBI_NavigationStepName = Navigation\n"
        f"\n"
        f"\tannotation PBI_ResultType = Text\n"
        f"\n"
        f'expression Database = "{database}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {db_lineage}\n"
        f"\tqueryGroup: Parameters\n"
        f"\n"
        f"\tannotation PBI_NavigationStepName = Navigation\n"
        f"\n"
        f"\tannotation PBI_ResultType = Text\n"
        f"\n"
    )


def gen_table_tmdl(table_name: str, schema: str) -> str:
    """Generate a table TMDL with only a partition (no columns).

    Columns are populated by Power BI Desktop on first refresh.
    """
    lineage = str(uuid.uuid4())
    return (
        f"table {table_name}\n"
        f"\tlineageTag: {lineage}\n"
        f"\n"
        f"\tpartition {table_name} = m\n"
        f"\t\tmode: import\n"
        f"\t\tqueryGroup: Tables\n"
        f"\t\tsource = ```\n"
        f"\t\t\t\tlet\n"
        f"\t\t\t\t  Source = Sql.Database(\n"
        f'\t\t\t\t    #"SqlEndpoint",\n'
        f'\t\t\t\t    #"Database"\n'
        f"\t\t\t\t  ),\n"
        f"\t\t\t\t  Data = Source\n"
        f"\t\t\t\t    {{\n"
        f"\t\t\t\t      [\n"
        f'\t\t\t\t        Schema = "{schema}",\n'
        f'\t\t\t\t        Item   = "{table_name}"\n'
        f"\t\t\t\t      ]\n"
        f"\t\t\t\t    }}\n"
        f"\t\t\t\t    [Data]\n"
        f"\t\t\t\tin\n"
        f"\t\t\t\t  Data\n"
        f"\t\t\t\t```\n"
        f"\n"
        f"\tannotation PBI_NavigationStepName = Navigation\n"
        f"\n"
        f"\tannotation PBI_ResultType = Table\n"
        f"\n"
    )


def gen_model_tmdl(culture: str, tables: list[str]) -> str:
    ref_lines = "\n".join(f"ref table {t}" for t in tables)
    return (
        f"model Model\n"
        f"\tculture: {culture}\n"
        f"\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        f"\tsourceQueryCulture: {culture}\n"
        f"\tdataAccessOptions\n"
        f"\t\tlegacyRedirects\n"
        f"\t\treturnErrorValuesAsNull\n"
        f"\n"
        f"annotation __PBI_TimeIntelligenceEnabled = 1\n"
        f"\n"
        f'annotation PBI_ProTooling = ["DevMode"]\n'
        f"\n"
        f"queryGroup Parameters\n"
        f"\n"
        f"queryGroup Tables\n"
        f"\n"
        f"ref cultureInfo {culture}\n"
        f"\n"
        + (ref_lines + "\n\n" if ref_lines else "")
    )


# ---------- Build ----------

def build_pbip(args: argparse.Namespace) -> int:
    verbose = args.verbose

    # 1. Validate name
    validate_name(args.name)

    # 2. Resolve paths
    root = Path(args.project_root).resolve()
    design_path = (root / args.design_file).resolve()
    config_path = (root / args.config_file).resolve()
    output_parent = Path(args.output).resolve()

    # 3. Parse pipeline-design.md
    log(f"Reading {design_path}", verbose)
    registry = parse_design_file(design_path)
    all_tables = registry["dimensions"] + registry["facts"]
    tables = filter_tables(all_tables, args.include, args.exclude)
    if not tables:
        err(f"No tables matched after filtering. Found in registry: {all_tables}")
        return 2
    log(f"Tables: {tables}", verbose)

    # 4. Resolve connection. Priority:
    #    CLI flag > project-config.yml > .claude/settings.local.json
    cfg = parse_config_file(config_path)
    settings_fallback = read_plugin_settings_local(root)
    server = args.server or cfg.get("server") or settings_fallback.get("server")
    database = args.database or cfg.get("database") or settings_fallback.get("database")
    schema = args.schema or cfg.get("schema") or "dbo_analytics"
    if not server:
        err(
            "SQL server not specified. Tried: --server flag, project-config.yml "
            "(dbt.database.server / sql_server.default_server / database.server), "
            "and .claude/settings.local.json pluginConfigs. Pass --server explicitly "
            "or run `configure.py` to populate settings.local.json."
        )
        return 2
    if not database:
        err(
            "Database not specified. Tried: --database flag, project-config.yml "
            "(dbt.database.target / sql_server.default_database / database.name), "
            "and .claude/settings.local.json pluginConfigs. Pass --database "
            "explicitly or run `configure.py` to populate settings.local.json."
        )
        return 2
    log(f"Connection: {server} / {database} / {schema}", verbose)

    # 5. Plan output paths
    project_name = args.name.strip()
    project_dir = output_parent / project_name
    validate_output(project_dir, args.force)
    if project_dir.exists() and args.force:
        log(f"Removing existing {project_dir}", verbose)
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=False)

    report_dir = project_dir / f"{project_name}.Report"
    sm_dir = project_dir / f"{project_name}.SemanticModel"

    # 6. Common placeholders
    common_subs = {
        "PROJECT_NAME": project_name,
        "DISPLAY_NAME": project_name,
        "CULTURE": args.culture,
    }

    # 7. .pbip entry file
    render_tpl(
        TEMPLATES_DIR / "pbip.tpl",
        project_dir / f"{project_name}.pbip",
        common_subs,
        crlf=True,
    )

    # 8. Report folder
    report_subs = {**common_subs, "LOGICAL_ID": str(uuid.uuid4())}
    render_tpl(TEMPLATES_DIR / "Report" / ".platform.tpl", report_dir / ".platform", report_subs, crlf=True)
    render_tpl(TEMPLATES_DIR / "Report" / "definition.pbir.tpl", report_dir / "definition.pbir", report_subs, crlf=True)
    copy_verbatim(TEMPLATES_DIR / "Report" / "definition" / "report.json", report_dir / "definition" / "report.json")
    copy_verbatim(TEMPLATES_DIR / "Report" / "definition" / "version.json", report_dir / "definition" / "version.json")
    copy_verbatim(TEMPLATES_DIR / "Report" / "definition" / "pages" / "pages.json", report_dir / "definition" / "pages" / "pages.json")
    copy_verbatim(
        TEMPLATES_DIR / "Report" / "definition" / "pages" / "895a4d3c5c2b505a42a5" / "page.json",
        report_dir / "definition" / "pages" / "895a4d3c5c2b505a42a5" / "page.json",
    )
    copy_verbatim(
        TEMPLATES_DIR / "Report" / "StaticResources" / "SharedResources" / "BaseThemes" / "CY26SU02.json",
        report_dir / "StaticResources" / "SharedResources" / "BaseThemes" / "CY26SU02.json",
    )

    # 9. SemanticModel folder
    sm_subs = {**common_subs, "LOGICAL_ID": str(uuid.uuid4())}
    render_tpl(TEMPLATES_DIR / "SemanticModel" / ".platform.tpl", sm_dir / ".platform", sm_subs, crlf=True)
    copy_verbatim(TEMPLATES_DIR / "SemanticModel" / "definition.pbism", sm_dir / "definition.pbism")
    copy_verbatim(TEMPLATES_DIR / "SemanticModel" / ".pbi" / "editorSettings.json", sm_dir / ".pbi" / "editorSettings.json")
    copy_verbatim(TEMPLATES_DIR / "SemanticModel" / "definition" / "database.tmdl", sm_dir / "definition" / "database.tmdl")
    render_tpl(
        TEMPLATES_DIR / "SemanticModel" / "definition" / "cultures" / "culture.tmdl.tpl",
        sm_dir / "definition" / "cultures" / f"{args.culture}.tmdl",
        sm_subs,
    )

    # 10. Generated TMDL — model, expressions, tables
    write_utf8(sm_dir / "definition" / "model.tmdl", gen_model_tmdl(args.culture, tables))
    write_utf8(sm_dir / "definition" / "expressions.tmdl", gen_expressions_tmdl(server, database))
    tables_dir = sm_dir / "definition" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for t in tables:
        write_utf8(tables_dir / f"{t}.tmdl", gen_table_tmdl(t, schema))

    # 11. .gitignore (project-level)
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        render_tpl(TEMPLATES_DIR / ".gitignore.tpl", gitignore_path, {})

    # 12. Post-build validation
    validation_errors = validate_build(project_dir, project_name, tables)
    if validation_errors:
        err("Post-build validation failed:")
        for e in validation_errors:
            err(f"  - {e}")
        return 3

    # 13. Summary
    print()
    print(f"[OK] PBIP project created: {project_dir}")
    print(f"  Connection:   {server} / {database} / schema={schema}")
    print(f"  Culture:      {args.culture}")
    print(f"  Tables ({len(tables)}):")
    for t in tables:
        print(f"    - {t}")
    print()
    print("Next steps:")
    print(f"  1. Open: {project_dir / (project_name + '.pbip')}")
    print("  2. Click Refresh to load column metadata from SQL Server.")
    print("  3. Set up relationships and add measures as needed.")
    return 0


# ---------- Post-build validation ----------

GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def validate_build(project_dir: Path, project_name: str, tables: list[str]) -> list[str]:
    errors: list[str] = []
    pbip = project_dir / f"{project_name}.pbip"
    report_dir = project_dir / f"{project_name}.Report"
    sm_dir = project_dir / f"{project_name}.SemanticModel"

    for p in (pbip, report_dir, sm_dir):
        if not p.exists():
            errors.append(f"Missing required path: {p}")

    for marker in (
        report_dir / ".platform",
        report_dir / "definition.pbir",
        report_dir / "definition" / "report.json",
        sm_dir / ".platform",
        sm_dir / "definition.pbism",
        sm_dir / "definition" / "model.tmdl",
        sm_dir / "definition" / "database.tmdl",
        sm_dir / "definition" / "expressions.tmdl",
    ):
        if not marker.exists():
            errors.append(f"Missing file: {marker}")

    for t in tables:
        path = sm_dir / "definition" / "tables" / f"{t}.tmdl"
        if not path.exists():
            errors.append(f"Missing table TMDL: {path}")
            continue
        content = path.read_text(encoding="utf-8")
        if f"partition {t}" not in content:
            errors.append(f"Table {t} has no partition block.")

    model_tmdl = sm_dir / "definition" / "model.tmdl"
    if model_tmdl.exists():
        model_text = model_tmdl.read_text(encoding="utf-8")
        for t in tables:
            if f"ref table {t}" not in model_text:
                errors.append(f"model.tmdl missing ref table for {t}")

    # GUID sanity on .platform files
    import json
    for platform_file in (report_dir / ".platform", sm_dir / ".platform"):
        if platform_file.exists():
            try:
                data = json.loads(platform_file.read_text(encoding="utf-8"))
                lid = data.get("config", {}).get("logicalId", "")
                if not GUID_RE.match(lid):
                    errors.append(f"{platform_file}: logicalId is not a valid GUID: {lid!r}")
            except json.JSONDecodeError as e:
                errors.append(f"{platform_file}: invalid JSON ({e})")

    return errors


# ---------- Entry point ----------

def main() -> int:
    args = parse_args()
    try:
        return build_pbip(args)
    except (FileNotFoundError, ValueError, FileExistsError) as e:
        err(str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
