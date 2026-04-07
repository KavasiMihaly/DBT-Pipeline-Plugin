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


def run_dbt_command(args):
    """
    Execute dbt command with provided arguments.

    Args:
        args: List of command arguments (e.g., ['run', '--select', 'my_model'])

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    # Find dbt project root
    project_root = find_dbt_project_root()

    if project_root is None:
        print("ERROR: No dbt project found (dbt_project.yml not found)")
        print("Please run this script from within a dbt project directory")
        return 1

    print(f"dbt project root: {project_root}")

    # Build dbt command
    dbt_cmd = ["dbt"] + args

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

        print("-" * 80)

        if result.returncode == 0:
            print(f"✓ dbt {args[0]} completed successfully")
            return 0
        else:
            print(f"✗ dbt {args[0]} failed with exit code {result.returncode}")
            return 1

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
        return 1

    # Get dbt command and arguments (everything after script name)
    dbt_args = sys.argv[1:]

    # Execute dbt command
    exit_code = run_dbt_command(dbt_args)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
