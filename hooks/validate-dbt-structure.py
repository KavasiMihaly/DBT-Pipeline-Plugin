"""PostToolUse hook — validates dbt file structure conventions after Write/Edit.

Checks:
1. SQL model naming: stg_*, dim_*, fct_* with correct prefixes
2. SQL model placement: staging/ vs marts/ folder
3. Schema YAML: one per model, correct naming convention
4. SQL content: CTE pattern, no SELECT *, source() usage in staging
5. YAML content: version key, required tests on primary keys
6. No shared schema.yml files (must be per-model)

Returns JSON with 'decision': 'block'/'warn' and 'reason' on violations.
"""

import json
import os
import re
import sys


def main():
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only validate Write and Edit on dbt model files
    if tool_name not in ("Write", "Edit"):
        print(json.dumps({"decision": "approve"}))
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        print(json.dumps({"decision": "approve"}))
        return

    # Normalize path separators
    file_path = file_path.replace("\\", "/")

    # Only validate files inside a dbt models directory
    if "/models/" not in file_path:
        print(json.dumps({"decision": "approve"}))
        return

    warnings = []
    blocks = []

    filename = os.path.basename(file_path)
    dirname = os.path.dirname(file_path)

    # Determine file type
    is_sql = filename.endswith(".sql")
    is_yaml = filename.endswith(".yml") or filename.endswith(".yaml")

    # ── SQL Model Validations ──
    if is_sql:
        model_name = filename[:-4]  # strip .sql

        # Rule 1: Naming convention
        if "/staging/" in file_path:
            if not model_name.startswith("stg_"):
                blocks.append(
                    f"Staging model '{filename}' must start with 'stg_'. "
                    f"Expected: stg_<source>__<entity>.sql"
                )
            elif "__" not in model_name:
                warnings.append(
                    f"Staging model '{model_name}' should use double underscore: "
                    f"stg_<source>__<entity>"
                )

        elif "/marts/" in file_path or "/mart/" in file_path:
            if not (model_name.startswith("dim_") or model_name.startswith("fct_")):
                warnings.append(
                    f"Mart model '{filename}' should start with 'dim_' or 'fct_'. "
                    f"Got: {model_name}"
                )

        # Rule 2: Placement validation
        if model_name.startswith("stg_") and "/staging/" not in file_path:
            blocks.append(
                f"Staging model '{filename}' must be in models/staging/<source>/. "
                f"Found in: {dirname}"
            )

        if model_name.startswith("dim_") and "/marts/" not in file_path:
            blocks.append(
                f"Dimension '{filename}' must be in models/marts/. Found in: {dirname}"
            )

        if model_name.startswith("fct_") and "/marts/" not in file_path:
            blocks.append(
                f"Fact '{filename}' must be in models/marts/. Found in: {dirname}"
            )

        # Rule 3: SQL content checks (only for Write, where we have full content)
        content = tool_input.get("content", "")
        if content:
            # No SELECT * in staging models
            if model_name.startswith("stg_"):
                # Check for SELECT * that isn't inside a CTE (allow `select * from renamed`)
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    stripped = line.strip().lower()
                    if "select *" in stripped or "select  *" in stripped:
                        # Allow "select * from source" or "select * from renamed" in CTE
                        if re.match(r"select\s+\*\s+from\s+(source|renamed|final|filtered)", stripped):
                            continue
                        # Block raw SELECT * at the top level
                        if stripped.startswith("select"):
                            warnings.append(
                                f"Line {i}: Avoid SELECT * — explicitly list columns "
                                f"for staging models"
                            )

                # Must use source() macro in staging
                if "{{ source(" not in content and "{{source(" not in content:
                    blocks.append(
                        f"Staging model '{model_name}' must use "
                        f"{{{{ source('name', 'table') }}}} macro, not ref() or direct table references"
                    )

                # Should have CTE pattern
                if "with" not in content.lower().split("select")[0] if "select" in content.lower() else "":
                    warnings.append(
                        f"Staging model '{model_name}' should use CTE pattern "
                        f"(WITH source AS ...)"
                    )

            # Dims and facts must use ref(), not source()
            if model_name.startswith(("dim_", "fct_")):
                if "{{ source(" in content or "{{source(" in content:
                    blocks.append(
                        f"Mart model '{model_name}' must use ref() not source(). "
                        f"Only staging models reference sources directly."
                    )

    # ── YAML Schema Validations ──
    if is_yaml:
        # Rule 4: Schema file naming convention
        if "/staging/" in file_path:
            # Must be _stg_<source>__<entity>__schema.yml (per-model)
            if filename == "schema.yml" or filename == "_schema.yml":
                blocks.append(
                    f"Shared 'schema.yml' not allowed in staging. "
                    f"Use per-model files: _stg_<source>__<entity>__schema.yml"
                )
            elif filename.startswith("_stg_") and not filename.endswith("__schema.yml"):
                warnings.append(
                    f"Staging schema '{filename}' should end with '__schema.yml'. "
                    f"Expected: _stg_<source>__<entity>__schema.yml"
                )

        elif "/marts/" in file_path:
            # Must be _dim_*__schema.yml or _fct_*__schema.yml (per-model)
            if filename == "schema.yml" or filename == "_schema.yml":
                blocks.append(
                    f"Shared 'schema.yml' not allowed in marts. "
                    f"Use per-model files: _dim_<entity>__schema.yml or _fct_<entity>__schema.yml"
                )

        # Rule 5: YAML content checks (only for Write)
        content = tool_input.get("content", "")
        if content:
            if "version:" not in content:
                warnings.append(
                    f"Schema file '{filename}' missing 'version: 2' declaration"
                )

            # Check for primary key tests
            if ("_stg_" in filename or "_dim_" in filename or "_fct_" in filename):
                if "unique" not in content or "not_null" not in content:
                    blocks.append(
                        f"Schema '{filename}' must have unique + not_null tests "
                        f"on primary key column"
                    )

    # ── Build response ──
    if blocks:
        reason = "dbt structure violations (BLOCKING):\n" + "\n".join(f"  - {b}" for b in blocks)
        if warnings:
            reason += "\n\nAdditional warnings:\n" + "\n".join(f"  - {w}" for w in warnings)
        print(json.dumps({"decision": "block", "reason": reason}))
    elif warnings:
        reason = "dbt structure warnings:\n" + "\n".join(f"  - {w}" for w in warnings)
        print(json.dumps({"decision": "approve", "reason": reason}))
    else:
        print(json.dumps({"decision": "approve"}))


if __name__ == "__main__":
    main()
