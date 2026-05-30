#!/usr/bin/env python3
"""
dbt Runner Script

Executes dbt commands and captures output for Claude Code integration.
Usage: python run_dbt.py <dbt_command> [args...]

Examples:
    python run_dbt.py run
    python run_dbt.py run --select my_model+
    python run_dbt.py test
    python run_dbt.py compile --select stg_*
    python run_dbt.py docs generate
    python run_dbt.py build --select my_model+
    python run_dbt.py snapshot
    python run_dbt.py seed
    python run_dbt.py source freshness
    python run_dbt.py deps
    python run_dbt.py debug
    python run_dbt.py list --select tag:daily
    python run_dbt.py clean
    python run_dbt.py run --select state:modified+ (Slim CI)
    python run_dbt.py run --vars '{"start_date": "2024-01-01"}'
"""

import sys
import subprocess
import os
from pathlib import Path

# Windows consoles default to a non-UTF-8 code page (cp1252), so printing a
# status glyph like the check mark raises UnicodeEncodeError. That exception
# used to be caught below and turned a SUCCESSFUL dbt run into exit code 1.
# Force UTF-8 with replacement so wrapper output can never flip the exit code.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def find_dbt_project_root():
    """
    Find the dbt project root by looking for dbt_project.yml
    starting from current directory and moving up.
    """
    current = Path.cwd()

    # Check current directory and parents
    for path in [current] + list(current.parents):
        dbt_project = path / "dbt_project.yml"
        if dbt_project.exists():
            return path

    return None


def find_venv_dbt(project_root):
    """
    Find dbt executable inside a virtual environment.

    Searches for venv directories in common locations relative to the project root
    and its parents (e.g., venv/, .venv/, 3 - Data Pipeline/venv/).
    Returns the path to the dbt executable if found, None otherwise.
    """
    # On Windows, Scripts/dbt.exe; on Unix, bin/dbt
    if os.name == 'nt':
        dbt_rel = os.path.join("Scripts", "dbt.exe")
    else:
        dbt_rel = os.path.join("bin", "dbt")

    # Search locations relative to project root
    venv_candidates = [
        project_root / "venv",
        project_root / ".venv",
        project_root / "3 - Data Pipeline" / "venv",
        project_root / "3 - Data Pipeline" / ".venv",
    ]

    # Also walk up from project_root to check parent directories
    current = project_root.parent
    for _ in range(3):
        venv_candidates.append(current / "venv")
        venv_candidates.append(current / ".venv")
        if current.parent == current:
            break
        current = current.parent

    for venv_dir in venv_candidates:
        dbt_path = venv_dir / dbt_rel
        if dbt_path.exists():
            return str(dbt_path)

    return None


def _extract_opt(args, name):
    """Pull `--name value` or `--name=value` out of an args list.

    Returns (value_or_None, remaining_args). This lets run_dbt.py accept
    `--project-dir` / `--profiles-dir` so it is CWD-independent — the wrapper can
    be invoked from anywhere (e.g. the repo root) without `cd`-ing into the dbt
    project first, which the harness CWD does not always point at.
    """
    remaining = []
    value = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == name:
            if i + 1 < len(args):
                value = args[i + 1]
                i += 2
            else:
                i += 1
            continue
        if a.startswith(name + "="):
            value = a.split("=", 1)[1]
            i += 1
            continue
        remaining.append(a)
        i += 1
    return value, remaining


def run_dbt_command(args):
    """
    Execute dbt command with provided arguments.

    Args:
        args: List of command arguments (e.g., ['run', '--select', 'my_model'])

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    # CWD-independence: honor an explicit --project-dir / --profiles-dir so the
    # wrapper can run from anywhere (the harness CWD is not always the dbt
    # project). --project-dir sets the subprocess cwd; --profiles-dir is
    # forwarded to dbt as an absolute path. Both are stripped from the args
    # passed through to dbt so they cannot be double-applied.
    project_dir_opt, args = _extract_opt(args, "--project-dir")
    profiles_dir_opt, args = _extract_opt(args, "--profiles-dir")

    if not args:
        print("ERROR: no dbt subcommand provided (e.g. run, test, build, compile)")
        return 1

    # Find dbt project root
    if project_dir_opt:
        project_root = Path(project_dir_opt).resolve()
        if not (project_root / "dbt_project.yml").exists():
            print(f"ERROR: --project-dir has no dbt_project.yml: {project_root}")
            return 1
    else:
        project_root = find_dbt_project_root()
        if project_root is None:
            print("ERROR: No dbt project found (dbt_project.yml not found)")
            print("Please run from within a dbt project directory, or pass --project-dir <path>")
            return 1

    print(f"dbt project root: {project_root}")

    # Try to find dbt in a virtual environment first, fall back to PATH
    venv_dbt = find_venv_dbt(project_root)
    if venv_dbt:
        dbt_executable = venv_dbt
        print(f"Using venv dbt: {venv_dbt}")
    else:
        dbt_executable = "dbt"

    # Build dbt command. Forward --profiles-dir to dbt as an absolute path if the
    # caller supplied one (run_dbt consumed it above so it wasn't passed twice).
    dbt_cmd = [dbt_executable] + args
    if profiles_dir_opt:
        dbt_cmd += ["--profiles-dir", str(Path(profiles_dir_opt).resolve())]

    print(f"Executing: {' '.join(dbt_cmd)}")
    print("-" * 80)

    try:
        # Execute dbt command
        result = subprocess.run(
            dbt_cmd,
            cwd=str(project_root),
            capture_output=False,  # Stream output to console
            text=True
        )

        # Capture dbt's real return code BEFORE printing anything. The wrapper's
        # own status line must never be able to change the exit code we propagate.
        rc = result.returncode
        try:
            print("-" * 80)
            if rc == 0:
                print(f"[OK] dbt {args[0]} completed successfully")
            else:
                print(f"[FAILED] dbt {args[0]} failed with exit code {rc}")
        except Exception:
            pass  # never let a console-encoding error mask dbt's real result
        return rc

    except FileNotFoundError:
        print("ERROR: dbt command not found")
        print("Please ensure dbt is installed and available in your PATH")
        print("Install with: pip install dbt-core dbt-sqlserver")
        return 1

    except Exception as e:
        print(f"ERROR: Unexpected error running dbt command: {e}")
        return 1


def main():
    """Main entry point for the script."""

    # Check if arguments provided
    if len(sys.argv) < 2:
        print("Usage: python run_dbt.py <dbt_command> [args...]")
        print("")
        print("Common Commands:")
        print("  python run_dbt.py run")
        print("  python run_dbt.py run --select my_model+")
        print("  python run_dbt.py test")
        print("  python run_dbt.py test --select my_model")
        print("  python run_dbt.py build --select my_model+")
        print("  python run_dbt.py compile")
        print("  python run_dbt.py docs generate")
        print("")
        print("Additional Commands:")
        print("  python run_dbt.py snapshot")
        print("  python run_dbt.py seed")
        print("  python run_dbt.py source freshness")
        print("  python run_dbt.py deps")
        print("  python run_dbt.py debug")
        print("  python run_dbt.py list --select tag:daily")
        print("  python run_dbt.py clean")
        print("")
        print("Advanced Examples:")
        print("  python run_dbt.py run --full-refresh")
        print("  python run_dbt.py run --select state:modified+")
        print("  python run_dbt.py run --vars '{\"start_date\": \"2024-01-01\"}'")
        print("  python run_dbt.py run --threads 8 --target prod")
        print("")
        print("CWD-independent (run from anywhere):")
        print("  python run_dbt.py run --project-dir \"3 - Data Pipeline\"")
        print("  python run_dbt.py test --project-dir /abs/path/to/project --profiles-dir /abs/path")
        return 1

    # Get dbt command and arguments (everything after script name)
    dbt_args = sys.argv[1:]

    # Execute dbt command
    exit_code = run_dbt_command(dbt_args)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
