"""Reset a dbt pipeline project to its pre-build state.

Performs a total reset:
1. Drops all pipeline-created tables from the database
2. Removes all numbered project folders (0-6)
3. Removes Python virtual environment and dbt installation
4. Removes .git directory entirely
5. Preserves only the original source CSV files

Usage:
    python reset_project.py --database MyDatabase
    python reset_project.py --database MyDatabase --schemas raw,dbo_staging,dbo_analytics
    python reset_project.py --database MyDatabase --dry-run
    python reset_project.py --database MyDatabase --keep-raw

Schema detection order (first match wins):
    1. --schemas CLI override
    2. dbt_project.yml (+schema suffixes) combined with profiles.yml (target schema)
    3. Defaults: raw=raw, staging=dbo_staging, marts=dbo_analytics
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Walk up from cwd to find project root (has dbt_project.yml or numbered folders)."""
    current = Path.cwd()
    for _ in range(10):
        if (current / "dbt_project.yml").exists() or (current / "3 - Data Pipeline").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()


def normalize_object_name(name: str, raw_schema: str = "raw") -> str:
    """Strip schema-qualified prefix the orchestrator may have written in the registry.

    The actual SQL tables are bare names (e.g. `epraccur`) in the `raw` schema —
    load_data.py documents this at line 378 ("Target table name without schema
    prefix"). But in practice LLMs sometimes write `raw.epraccur` (schema-qualified
    dot form) in the Section 11 registry, and the reset script would then wrap
    that as `[raw].[raw.epraccur]` — a non-existent table.

    Rule: if `.` is present, keep only the part after the LAST dot. Handles
    `db.schema.table`, `schema.table`, and plain `table` forms uniformly.

    NOTE: we deliberately do NOT strip an underscore prefix like `raw_epraccur`,
    even though the orchestrator's Stage 6 template says `| raw_{source_name} |`.
    Tables can legitimately be named `raw_*` (e.g. when a CSV is named
    `raw_events.csv`), and over-stripping those would break the drop for
    legitimate cases. The underscore template inconsistency is tracked
    separately as an orchestrator fix — see Issues.md.

    `raw_schema` parameter is kept for future use and API compatibility but is
    not currently consulted.
    """
    if not name:
        return name
    # Strip schema-qualified dot prefix (schema.table → table)
    if "." in name:
        name = name.rsplit(".", 1)[-1]
    return name


def detect_schemas_from_dbt_project(project_root: Path) -> dict:
    """Best-effort schema detection from dbt_project.yml + profiles.yml.

    Returns dict with keys: raw, staging, marts. Any missing key signals
    "couldn't detect, fall back to default". Uses regex parsing to avoid a
    PyYAML dependency — matches the approach used in pbip-from-dbt/build_pbip.py.

    dbt-sqlserver resolves final schemas as `{profile_target_schema}_{+schema_suffix}`.
    So we read:
      - profiles.yml → schema under the default target
      - dbt_project.yml → `+schema:` under models.<project>.staging and models.<project>.marts
    """
    result = {}

    # Read profiles.yml for target schema
    profile_target_schema = None
    profiles_yml = project_root / "profiles.yml"
    if profiles_yml.exists():
        profile_text = profiles_yml.read_text(encoding="utf-8", errors="ignore")
        # Look for `schema: <value>` under outputs — first match wins
        m = re.search(r"^\s*schema:\s*([A-Za-z0-9_]+)\s*$", profile_text, re.MULTILINE)
        if m:
            profile_target_schema = m.group(1)

    # Read dbt_project.yml for +schema suffixes.
    # Use `[ \t]` (not `\s`) so whitespace classes don't eat newlines and cross
    # into the next block; use `\+(?!schema:)` to skip sibling +config lines
    # like `+materialized:` without skipping the `+schema:` we're looking for.
    staging_suffix = None
    marts_suffix = None
    dbt_project_yml = project_root / "dbt_project.yml"
    if dbt_project_yml.exists():
        project_text = dbt_project_yml.read_text(encoding="utf-8", errors="ignore")
        m_stg = re.search(
            r"\bstaging:[ \t]*(?:\r?\n[ \t]+\+(?!schema:)[^\r\n]*)*\r?\n[ \t]+\+schema:[ \t]*([A-Za-z0-9_]+)",
            project_text,
        )
        if m_stg:
            staging_suffix = m_stg.group(1)
        m_marts = re.search(
            r"\bmarts:[ \t]*(?:\r?\n[ \t]+\+(?!schema:)[^\r\n]*)*\r?\n[ \t]+\+schema:[ \t]*([A-Za-z0-9_]+)",
            project_text,
        )
        if m_marts:
            marts_suffix = m_marts.group(1)

    if profile_target_schema and staging_suffix:
        result["staging"] = f"{profile_target_schema}_{staging_suffix}"
    if profile_target_schema and marts_suffix:
        result["marts"] = f"{profile_target_schema}_{marts_suffix}"

    # Raw schema is conventional — always `raw` unless overridden
    result["raw"] = "raw"

    return result


def parse_pipeline_design(project_root: Path, raw_schema: str = "raw") -> dict:
    """Parse the Created Objects Registry from pipeline-design.md (Section 11).

    The registry is bounded by RESET_REGISTRY_START / RESET_REGISTRY_END markers
    and contains markdown tables with | Object Name | Type | Created At Stage | rows.

    Every parsed name is normalized via `normalize_object_name()` to strip any
    schema prefix the orchestrator may have written (e.g. `raw.epraccur` →
    `epraccur`). Pass the actual raw schema name so underscore-prefixed entries
    like `raw_epraccur` are also normalized correctly.

    Returns dict with keys:
      - raw_tables: list of raw source table names
      - staging_views: list of staging view names (stg_*)
      - dimensions: list of dimension table names (dim_*)
      - facts: list of fact table names (fct_*)
    """
    design_file = project_root / "1 - Documentation" / "pipeline-design.md"
    if not design_file.exists():
        print(f"  Warning: {design_file} not found — cannot determine which objects to drop.")
        return {"raw_tables": [], "staging_views": [], "dimensions": [], "facts": []}

    content = design_file.read_text(encoding="utf-8")

    # Extract the registry block between markers
    match = re.search(
        r'<!-- RESET_REGISTRY_START.*?-->(.*?)<!-- RESET_REGISTRY_END',
        content, re.DOTALL
    )
    if not match:
        print("  Warning: No RESET_REGISTRY markers found in pipeline-design.md.")
        print("  Falling back to pattern matching across entire file...")
        # Fallback: scan entire file for known prefixes
        return _fallback_parse(content, raw_schema)

    registry = match.group(1)
    result = {"raw_tables": [], "staging_views": [], "dimensions": [], "facts": []}

    # Parse current section context and table rows
    current_section = None
    for line in registry.splitlines():
        line = line.strip()

        # Detect section headers
        if "Raw Tables" in line:
            current_section = "raw_tables"
        elif "Staging Models" in line:
            current_section = "staging_views"
        elif "Dimensions" in line:
            current_section = "dimensions"
        elif "Facts" in line:
            current_section = "facts"

        # Parse table rows: | object_name | TYPE | Stage N |
        if current_section and line.startswith("|") and "Object Name" not in line and "---" not in line:
            cells = [c.strip() for c in line.split("|")]
            # cells[0] is empty (before first |), cells[1] is object name
            if len(cells) >= 3 and cells[1]:
                obj_name = normalize_object_name(cells[1], raw_schema=raw_schema)
                if obj_name and obj_name not in result[current_section]:
                    result[current_section].append(obj_name)

    return result


def _fallback_parse(content: str, raw_schema: str = "raw") -> dict:
    """Fallback: regex-scan for known prefixes if registry markers are missing.

    Patterns match both underscore (`raw_epraccur`) and dot (`raw.epraccur`)
    conventions so the normalizer can collapse either form to the bare table
    name. `stg_`, `dim_`, `fct_` are model-type prefixes (not schema prefixes)
    and remain on the name after normalization.
    """
    result = {"raw_tables": [], "staging_views": [], "dimensions": [], "facts": []}

    # Raw: match `raw_<name>` (underscore) OR `raw.<name>` (dot-qualified).
    # Build the raw pattern from the actual raw schema name.
    escaped_raw = re.escape(raw_schema)
    raw_pattern = rf'\b(?:{escaped_raw}[._])(\w+)\b'
    for match in re.finditer(raw_pattern, content):
        name = match.group(1)
        if name not in result["raw_tables"]:
            result["raw_tables"].append(name)

    for match in re.finditer(r'\b(stg_\w+)\b', content):
        name = match.group(1)
        if name not in result["staging_views"]:
            result["staging_views"].append(name)

    for match in re.finditer(r'\b(dim_\w+)\b', content):
        name = match.group(1)
        if name not in result["dimensions"]:
            result["dimensions"].append(name)

    for match in re.finditer(r'\b(fct_\w+)\b', content):
        name = match.group(1)
        if name not in result["facts"]:
            result["facts"].append(name)

    return result


def generate_drop_sql(
    pipeline_objects: dict,
    database: str,
    raw_schema: str,
    staging_schema: str,
    marts_schema: str,
    keep_raw: bool,
) -> str:
    """Generate DROP statements for only the objects created by this pipeline.

    Schemas differ by object type on dbt-sqlserver:
      - staging views → `{target}_staging` (e.g. `dbo_staging`)
      - dim/fact tables → `{target}_analytics` (e.g. `dbo_analytics`)
      - raw source tables → `raw`
    """
    lines = [f"USE [{database}];", ""]

    # Drop views first (staging models are views, in staging schema)
    view_count = 0
    for view_name in pipeline_objects["staging_views"]:
        lines.append(f"DROP VIEW IF EXISTS [{staging_schema}].[{view_name}];")
        view_count += 1

    if view_count > 0:
        lines.append("")

    # Drop fact tables (before dims, in case of FK constraints) — marts schema
    table_count = 0
    for fact_name in pipeline_objects["facts"]:
        lines.append(f"DROP TABLE IF EXISTS [{marts_schema}].[{fact_name}];")
        table_count += 1

    # Drop dimension tables — marts schema
    for dim_name in pipeline_objects["dimensions"]:
        lines.append(f"DROP TABLE IF EXISTS [{marts_schema}].[{dim_name}];")
        table_count += 1

    # Drop raw source tables (unless --keep-raw)
    raw_count = 0
    if not keep_raw:
        if table_count > 0 or view_count > 0:
            lines.append("")
        for raw_name in pipeline_objects["raw_tables"]:
            lines.append(f"DROP TABLE IF EXISTS [{raw_schema}].[{raw_name}];")
            raw_count += 1

    lines.append("")
    lines.append(f"-- {view_count} views + {table_count} tables + {raw_count} raw tables to drop")
    return "\n".join(lines)


def execute_sql(sql: str, database: str, server: str = "localhost") -> bool:
    """Execute SQL via sqlcmd."""
    try:
        result = subprocess.run(
            ["sqlcmd", "-S", server, "-d", database, "-Q", sql],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"  SQL error: {result.stderr}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"  SQL execution failed: {e}", file=sys.stderr)
        return False


def get_initial_commit() -> str | None:
    """Find the initial scaffold commit (first commit in repo)."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().splitlines()
            return commits[0]  # earliest commit
    except Exception:
        pass
    return None


def get_csv_files(project_root: Path) -> list[Path]:
    """Find all CSV source files in the project."""
    csvs = []
    for pattern_dir in [project_root / "2 - Source Files", project_root]:
        if pattern_dir.exists():
            csvs.extend(pattern_dir.glob("*.csv"))
    return list(set(csvs))


def backup_csv_files(project_root: Path) -> dict[str, bytes]:
    """Find and back up all CSV files before wiping."""
    csv_backup = {}
    # Check numbered source folder
    source_dir = project_root / "2 - Source Files"
    if source_dir.exists():
        for csv in source_dir.glob("*.csv"):
            csv_backup[csv.name] = csv.read_bytes()
            print(f"  Backed up: {csv.name} (from 2 - Source Files/)")
    # Check root
    for csv in project_root.glob("*.csv"):
        if csv.name not in csv_backup:
            csv_backup[csv.name] = csv.read_bytes()
            print(f"  Backed up: {csv.name} (from root)")
    return csv_backup


def reset_filesystem(project_root: Path, dry_run: bool) -> None:
    """Remove all pipeline-created folders, venv, git, and generated files."""

    # Numbered project folders created by dbt-architecture-setup.
    # Includes legacy "6 - Agentic Resources" and old "7 - Data Exports" so
    # older scaffolds reset cleanly even after the 2026-04-19 renumbering.
    numbered_folders = [
        "0 - Architecture Setup",
        "1 - Documentation",
        "2 - Source Files",
        "3 - Data Pipeline",
        "4 - Semantic Layer",
        "5 - Report Building",
        "6 - Data Exports",
        "6 - Agentic Resources",
        "7 - Data Exports",
    ]

    # Virtual environment and dbt artifacts
    extra_targets = [
        ".venv",
        "venv",
        "dbt_packages",
        "dbt_modules",
        "logs",
        "target",
        ".git",
        ".claude",
        ".user.yml",
        "dbt_project.yml",
        "packages.yml",
        "profiles.yml",
        "project-config.yml",
        "CLAUDE.md",
        "requirements.txt",
    ]

    all_targets = numbered_folders + extra_targets

    for target_name in all_targets:
        target_path = project_root / target_name
        if not target_path.exists():
            continue

        if target_path.is_dir():
            if dry_run:
                print(f"    [DRY RUN] Would remove folder: {target_name}/")
            else:
                shutil.rmtree(target_path, ignore_errors=True)
                print(f"    Removed folder: {target_name}/")
        else:
            if dry_run:
                print(f"    [DRY RUN] Would remove file: {target_name}")
            else:
                target_path.unlink(missing_ok=True)
                print(f"    Removed file: {target_name}")

    # Clean up any remaining tmpclaude files
    for tmp in project_root.glob("tmpclaude-*"):
        if dry_run:
            print(f"    [DRY RUN] Would remove: {tmp.name}")
        else:
            tmp.unlink(missing_ok=True)
            print(f"    Removed: {tmp.name}")


def restore_csv_files(project_root: Path, csv_backup: dict[str, bytes]) -> None:
    """Restore CSV files to the project root."""
    for name, data in csv_backup.items():
        target = project_root / name
        target.write_bytes(data)
        print(f"  Restored: {name}")


def resolve_schemas(project_root: Path, cli_schemas: str | None) -> tuple[str, str, str]:
    """Return (raw_schema, staging_schema, marts_schema).

    Priority:
      1. --schemas CLI override (1, 2, or 3 comma-separated values)
      2. Auto-detected from dbt_project.yml + profiles.yml
      3. Defaults: raw=raw, staging=dbo_staging, marts=dbo_analytics

    For backward compat, 2-value CLI input (`raw,dbo`) is accepted with a
    warning — it's rewritten as (`raw`, `dbo_staging`, `dbo_analytics`) since
    a single dbt schema doesn't match the actual dbt-sqlserver layout.
    """
    defaults = {"raw": "raw", "staging": "dbo_staging", "marts": "dbo_analytics"}

    # Auto-detect first — we use it for any values the CLI doesn't override
    detected = detect_schemas_from_dbt_project(project_root)
    merged = {**defaults, **{k: v for k, v in detected.items() if v}}

    if cli_schemas:
        parts = [s.strip() for s in cli_schemas.split(",") if s.strip()]
        if len(parts) == 1:
            # Only raw given; use detected/default for staging+marts
            merged["raw"] = parts[0]
        elif len(parts) == 2:
            # Legacy 2-value form: raw,dbt — the "dbt" part is ambiguous
            # because marts actually live in a different schema. Warn loudly.
            print(
                f"  Warning: --schemas with 2 values ('{parts[0]},{parts[1]}') is legacy form. "
                f"dbt-sqlserver puts staging and marts in different schemas. "
                f"Using raw={parts[0]}, staging={merged['staging']}, marts={merged['marts']}. "
                f"Pass 3 values (e.g. `--schemas {parts[0]},{merged['staging']},{merged['marts']}`) to override."
            )
            merged["raw"] = parts[0]
        elif len(parts) >= 3:
            merged["raw"] = parts[0]
            merged["staging"] = parts[1]
            merged["marts"] = parts[2]

    return merged["raw"], merged["staging"], merged["marts"]


def main():
    parser = argparse.ArgumentParser(description="Total reset of pipeline project to pre-build state")
    parser.add_argument("--database", "-d", required=True, help="SQL Server database name (e.g., SalesDB, AnalyticsDB)")
    parser.add_argument(
        "--schemas",
        "-s",
        default=None,
        help=(
            "Comma-separated schemas: raw,staging,marts (default: auto-detected "
            "from dbt_project.yml + profiles.yml, falling back to raw,dbo_staging,dbo_analytics). "
            "Legacy 2-value form `raw,dbo` is accepted with a warning."
        ),
    )
    parser.add_argument("--keep-raw", action="store_true", help="Keep raw schema tables (only drop dbt models)")
    parser.add_argument("--server", default="localhost", help="SQL Server hostname (default: localhost)")
    parser.add_argument("--db-only", action="store_true", help="Only reset database, skip filesystem reset")
    parser.add_argument("--files-only", action="store_true", help="Only reset filesystem, skip database cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    args = parser.parse_args()

    project_root = find_project_root()
    raw_schema, staging_schema, marts_schema = resolve_schemas(project_root, args.schemas)

    print(f"=== Pipeline Total Reset ===")
    print(f"  Project: {project_root}")
    print(f"  Database: {args.database}")
    print(f"  Schemas: raw={raw_schema}, staging={staging_schema}, marts={marts_schema}")
    if args.keep_raw:
        print(f"  Keeping raw tables")
    if args.dry_run:
        print(f"  *** DRY RUN — no changes will be made ***")
    print()

    # Step 1: Back up CSV source files before anything gets deleted
    print("[1/3] Backing up source CSV files...")
    csv_backup = backup_csv_files(project_root)
    if not csv_backup:
        print("  Warning: No CSV files found to preserve!")
    print()

    # Step 2: Database cleanup — only drop objects listed in pipeline-design.md
    if not args.files_only:
        print("[2/3] Database cleanup (from pipeline-design.md manifest)...")
        pipeline_objects = parse_pipeline_design(project_root, raw_schema=raw_schema)

        total = (len(pipeline_objects["staging_views"]) + len(pipeline_objects["dimensions"])
                 + len(pipeline_objects["facts"]) + (0 if args.keep_raw else len(pipeline_objects["raw_tables"])))

        if total == 0:
            print("  No pipeline objects found in pipeline-design.md.")
        else:
            drop_sql = generate_drop_sql(
                pipeline_objects,
                args.database,
                raw_schema,
                staging_schema,
                marts_schema,
                args.keep_raw,
            )

            # Display what will be dropped
            if pipeline_objects["staging_views"]:
                print(f"  Staging views ({len(pipeline_objects['staging_views'])}):")
                for v in pipeline_objects["staging_views"]:
                    print(f"    DROP VIEW  [{staging_schema}].[{v}]")
            if pipeline_objects["facts"]:
                print(f"  Fact tables ({len(pipeline_objects['facts'])}):")
                for f in pipeline_objects["facts"]:
                    print(f"    DROP TABLE [{marts_schema}].[{f}]")
            if pipeline_objects["dimensions"]:
                print(f"  Dimension tables ({len(pipeline_objects['dimensions'])}):")
                for d in pipeline_objects["dimensions"]:
                    print(f"    DROP TABLE [{marts_schema}].[{d}]")
            if pipeline_objects["raw_tables"] and not args.keep_raw:
                print(f"  Raw tables ({len(pipeline_objects['raw_tables'])}):")
                for r in pipeline_objects["raw_tables"]:
                    print(f"    DROP TABLE [{raw_schema}].[{r}]")
            elif pipeline_objects["raw_tables"] and args.keep_raw:
                print(f"  Raw tables ({len(pipeline_objects['raw_tables'])}): KEEPING (--keep-raw)")

            if not args.dry_run:
                if execute_sql(drop_sql, args.database, args.server):
                    print(f"  Database cleanup complete — {total} objects dropped.")
                else:
                    print("  Some drops failed — check errors above.")
        print()

    # Step 3: Filesystem reset (folders, venv, git, dbt artifacts)
    if not args.db_only:
        print("[3/3] Filesystem reset...")
        # Prune git worktrees before removing .git
        subprocess.run(["git", "worktree", "prune"], capture_output=True, cwd=project_root)
        reset_filesystem(project_root, args.dry_run)
        print()

        # Restore CSV files to project root
        if csv_backup:
            print("Restoring source CSV files...")
            if not args.dry_run:
                restore_csv_files(project_root, csv_backup)
            else:
                for name in csv_backup:
                    print(f"    [DRY RUN] Would restore: {name}")
            print()

    print("=== Reset complete ===")
    if not args.dry_run:
        print(f"Project root now contains only: {', '.join(csv_backup.keys()) or '(no CSVs found)'}")
        print("Ready to re-run: claude --agent dbt-pipeline-orchestrator \"Build a pipeline\"")


if __name__ == "__main__":
    main()
