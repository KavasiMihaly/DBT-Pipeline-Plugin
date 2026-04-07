#!/usr/bin/env python3
"""
dbt Documentation Generator

Generate and serve dbt documentation with model lineage and descriptions.

Usage:
    python generate_docs.py <command> [options]

Commands:
    generate    Generate dbt documentation (manifest.json, catalog.json, index.html)
    serve       Serve documentation locally in browser
    all         Generate and serve (convenience command)
    export      Export static documentation site to directory

Options:
    --project-dir <path>    Path to dbt project (default: current directory)
    --port <port>           Port for docs server (default: 8080)
    --no-catalog            Skip catalog generation (faster, no column info)
    --output-dir <path>     Output directory for export (default: ./docs-export)
    --target <target>       dbt target to use (default: from profiles.yml)
    --no-browser            Don't automatically open browser when serving

Examples:
    python generate_docs.py generate
    python generate_docs.py serve --port 8081
    python generate_docs.py all
    python generate_docs.py export --output-dir ./public-docs
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional


class DBTDocsGenerator:
    """Generate and serve dbt documentation."""

    def __init__(self, project_dir: str = ".", target: Optional[str] = None):
        self.project_dir = Path(project_dir).resolve()
        self.target_dir = self.project_dir / "target"
        self.target = target

        # Validate dbt project
        self._validate_project()

    def _validate_project(self):
        """Validate that this is a dbt project."""
        dbt_project_file = self.project_dir / "dbt_project.yml"

        if not dbt_project_file.exists():
            print(f"Error: Not a dbt project. Could not find dbt_project.yml in {self.project_dir}", file=sys.stderr)
            print("Please run this command from a dbt project directory.", file=sys.stderr)
            sys.exit(1)

    def generate(self, skip_catalog: bool = False) -> bool:
        """Generate dbt documentation."""
        print("Generating dbt documentation...")
        print(f"Project directory: {self.project_dir}")
        print("")

        # Build command
        cmd = ["dbt", "docs", "generate"]

        if self.target:
            cmd.extend(["--target", self.target])

        if skip_catalog:
            print("Skipping catalog generation (--no-catalog)")
            # Note: dbt doesn't have a native --no-catalog flag
            # We'll handle this by checking catalog.json after generation
            print("Warning: dbt will still attempt to generate catalog. To truly skip, disconnect database.")
            print("")

        # Run command
        try:
            print(f"Running: {' '.join(cmd)}")
            print("")

            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # Print output
            if result.stdout:
                print(result.stdout)

            if result.stderr:
                print(result.stderr, file=sys.stderr)

            if result.returncode != 0:
                print("")
                print("ERROR: Documentation generation failed", file=sys.stderr)
                print(f"Exit code: {result.returncode}", file=sys.stderr)
                return False

            # Check what was generated
            self._report_generated_files()

            print("")
            print("SUCCESS: Documentation generated")
            print("")
            print("Next steps:")
            print("  View docs: python scripts/generate_docs.py serve")
            print("  Or open:   target/index.html")

            return True

        except FileNotFoundError:
            print("ERROR: dbt command not found", file=sys.stderr)
            print("Please ensure dbt is installed and in your PATH", file=sys.stderr)
            print("Install: pip install dbt-core dbt-sqlserver", file=sys.stderr)
            return False

        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return False

    def serve(self, port: int = 8080, open_browser: bool = True) -> bool:
        """Serve dbt documentation locally."""
        print("Starting dbt documentation server...")
        print(f"Project directory: {self.project_dir}")
        print(f"Port: {port}")
        print("")

        # Check if docs exist
        if not self._docs_exist():
            print("ERROR: Documentation not found", file=sys.stderr)
            print("Please run 'generate' command first", file=sys.stderr)
            print("  python scripts/generate_docs.py generate", file=sys.stderr)
            return False

        # Build command
        cmd = ["dbt", "docs", "serve", "--port", str(port)]

        if self.target:
            cmd.extend(["--target", self.target])

        # Open browser
        if open_browser:
            # Give server time to start
            def open_browser_delayed():
                time.sleep(2)
                url = f"http://localhost:{port}"
                print(f"Opening browser: {url}")
                try:
                    webbrowser.open(url)
                except Exception as e:
                    print(f"Could not open browser: {e}", file=sys.stderr)

            import threading
            browser_thread = threading.Thread(target=open_browser_delayed)
            browser_thread.daemon = True
            browser_thread.start()

        # Run server
        try:
            print(f"Running: {' '.join(cmd)}")
            print("")
            print(f"Documentation available at: http://localhost:{port}")
            print("Press Ctrl+C to stop the server")
            print("")

            # Run with stdout/stderr visible
            subprocess.run(
                cmd,
                cwd=self.project_dir,
                encoding='utf-8',
                errors='replace'
            )

            return True

        except KeyboardInterrupt:
            print("")
            print("Server stopped")
            return True

        except FileNotFoundError:
            print("ERROR: dbt command not found", file=sys.stderr)
            print("Please ensure dbt is installed and in your PATH", file=sys.stderr)
            return False

        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return False

    def export(self, output_dir: str = "./docs-export") -> bool:
        """Export static documentation site."""
        print("Exporting dbt documentation as static site...")
        print(f"Project directory: {self.project_dir}")
        print(f"Output directory: {output_dir}")
        print("")

        # Check if docs exist
        if not self._docs_exist():
            print("ERROR: Documentation not found", file=sys.stderr)
            print("Please run 'generate' command first", file=sys.stderr)
            return False

        output_path = Path(output_dir).resolve()

        # Create output directory
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"ERROR: Could not create output directory: {e}", file=sys.stderr)
            return False

        # Files to copy
        files_to_copy = [
            "manifest.json",
            "catalog.json",
            "index.html"
        ]

        # Copy files
        copied = []
        missing = []

        for filename in files_to_copy:
            source = self.target_dir / filename
            dest = output_path / filename

            if source.exists():
                try:
                    shutil.copy2(source, dest)
                    copied.append(filename)
                    print(f"  Copied: {filename}")
                except Exception as e:
                    print(f"  ERROR copying {filename}: {e}", file=sys.stderr)
                    return False
            else:
                missing.append(filename)
                print(f"  Warning: {filename} not found (skipping)")

        print("")
        print(f"SUCCESS: Documentation exported to {output_path}")
        print("")
        print("Exported files:")
        for filename in copied:
            file_path = output_path / filename
            size = file_path.stat().st_size / 1024  # KB
            print(f"  - {filename} ({size:.1f} KB)")

        if missing:
            print("")
            print("Missing files (not exported):")
            for filename in missing:
                print(f"  - {filename}")

        print("")
        print("To view exported docs:")
        print(f"  1. Open {output_path / 'index.html'} in browser")
        print(f"  2. Or serve with: python -m http.server --directory {output_path}")

        return True

    def _docs_exist(self) -> bool:
        """Check if documentation has been generated."""
        return (self.target_dir / "manifest.json").exists()

    def _report_generated_files(self):
        """Report what files were generated."""
        print("")
        print("Files created:")

        files_to_check = [
            "manifest.json",
            "catalog.json",
            "index.html"
        ]

        for filename in files_to_check:
            file_path = self.target_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size / 1024  # KB
                print(f"  - target/{filename} ({size:.1f} KB)")
            else:
                print(f"  - target/{filename} (NOT FOUND)")

    def get_stats(self) -> Optional[Dict]:
        """Get statistics about the documentation."""
        manifest_path = self.target_dir / "manifest.json"

        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            nodes = manifest.get('nodes', {})
            sources = manifest.get('sources', {})

            # Count by type
            models = [n for n in nodes.values() if n.get('resource_type') == 'model']
            tests = [n for n in nodes.values() if n.get('resource_type') == 'test']
            snapshots = [n for n in nodes.values() if n.get('resource_type') == 'snapshot']

            return {
                'models': len(models),
                'tests': len(tests),
                'sources': len(sources),
                'snapshots': len(snapshots)
            }

        except Exception as e:
            print(f"Warning: Could not read manifest.json: {e}", file=sys.stderr)
            return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate and serve dbt documentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate documentation')
    generate_parser.add_argument('--project-dir', default='.', help='Path to dbt project')
    generate_parser.add_argument('--target', help='dbt target to use')
    generate_parser.add_argument('--no-catalog', action='store_true', help='Skip catalog generation')

    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Serve documentation locally')
    serve_parser.add_argument('--project-dir', default='.', help='Path to dbt project')
    serve_parser.add_argument('--target', help='dbt target to use')
    serve_parser.add_argument('--port', type=int, default=8080, help='Port for docs server')
    serve_parser.add_argument('--no-browser', action='store_true', help='Do not open browser')

    # All command (generate + serve)
    all_parser = subparsers.add_parser('all', help='Generate and serve documentation')
    all_parser.add_argument('--project-dir', default='.', help='Path to dbt project')
    all_parser.add_argument('--target', help='dbt target to use')
    all_parser.add_argument('--port', type=int, default=8080, help='Port for docs server')
    all_parser.add_argument('--no-browser', action='store_true', help='Do not open browser')
    all_parser.add_argument('--no-catalog', action='store_true', help='Skip catalog generation')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export static documentation site')
    export_parser.add_argument('--project-dir', default='.', help='Path to dbt project')
    export_parser.add_argument('--output-dir', default='./docs-export', help='Output directory')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Create generator
    generator = DBTDocsGenerator(args.project_dir, getattr(args, 'target', None))

    # Execute command
    if args.command == 'generate':
        success = generator.generate(skip_catalog=args.no_catalog)

    elif args.command == 'serve':
        success = generator.serve(port=args.port, open_browser=not args.no_browser)

    elif args.command == 'all':
        # Generate first
        success = generator.generate(skip_catalog=args.no_catalog)
        if success:
            print("")
            print("-" * 60)
            print("")
            # Then serve
            success = generator.serve(port=args.port, open_browser=not args.no_browser)

    elif args.command == 'export':
        success = generator.export(output_dir=args.output_dir)

    else:
        print(f"ERROR: Unknown command: {args.command}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
