#!/usr/bin/env python3
"""
dbt Test Coverage Analyzer

Analyzes test coverage across dbt models and identifies gaps.

Usage:
    python analyze_coverage.py [options]

Options:
    --detailed              Show detailed report with recommendations
    --format <format>       Output format: text (default), json, markdown
    --layer <layer>         Filter by layer: staging, marts, intermediate
    --project-dir <path>    Path to dbt project (default: current directory)
    --target <percentage>   Target coverage percentage (default: 80)

Examples:
    python analyze_coverage.py
    python analyze_coverage.py --detailed
    python analyze_coverage.py --format json
    python analyze_coverage.py --layer marts
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import yaml


class TestCoverageAnalyzer:
    """Analyze dbt test coverage across models."""

    def __init__(self, project_dir: str = ".", target_coverage: float = 80.0):
        self.project_dir = Path(project_dir)
        self.models_dir = self.project_dir / "models"
        self.target_coverage = target_coverage

        # Storage for analysis results
        self.models: Dict[str, Dict] = {}
        self.tests: Dict[str, List[Dict]] = {}

    def analyze(self, layer_filter: str = None) -> Dict:
        """Run complete coverage analysis."""
        # Find all models
        self._find_models()

        # Find all tests
        self._find_tests()

        # Calculate coverage
        results = self._calculate_coverage(layer_filter)

        # Identify gaps
        results['gaps'] = self._identify_gaps(layer_filter)

        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results)

        return results

    def _find_models(self):
        """Find all SQL model files in the project."""
        if not self.models_dir.exists():
            print(f"Error: Models directory not found: {self.models_dir}", file=sys.stderr)
            sys.exit(1)

        for sql_file in self.models_dir.rglob("*.sql"):
            # Skip snapshots and tests
            if 'snapshots' in sql_file.parts or 'tests' in sql_file.parts:
                continue

            model_name = sql_file.stem
            relative_path = sql_file.relative_to(self.models_dir)

            # Determine layer
            layer = self._determine_layer(relative_path)

            # Determine model type
            model_type = self._determine_model_type(model_name)

            self.models[model_name] = {
                'name': model_name,
                'path': str(relative_path),
                'layer': layer,
                'type': model_type,
                'has_tests': False,
                'test_types': set()
            }

    def _determine_layer(self, path: Path) -> str:
        """Determine which layer a model belongs to."""
        parts = path.parts

        if 'staging' in parts:
            return 'staging'
        elif 'intermediate' in parts:
            return 'intermediate'
        elif 'marts' in parts:
            return 'marts'
        else:
            return 'other'

    def _determine_model_type(self, model_name: str) -> str:
        """Determine model type from name prefix."""
        if model_name.startswith('stg_'):
            return 'staging'
        elif model_name.startswith('int_'):
            return 'intermediate'
        elif model_name.startswith('fct_'):
            return 'fact'
        elif model_name.startswith('dim_'):
            return 'dimension'
        else:
            return 'other'

    def _find_tests(self):
        """Find all tests defined in schema.yml files."""
        for yml_file in self.models_dir.rglob("*.yml"):
            self._parse_schema_file(yml_file)

        # Also check .yaml extension
        for yaml_file in self.models_dir.rglob("*.yaml"):
            self._parse_schema_file(yaml_file)

    def _parse_schema_file(self, yml_file: Path):
        """Parse a schema.yml file to extract tests."""
        try:
            with open(yml_file, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)

            if not content or 'models' not in content:
                return

            for model in content['models']:
                model_name = model.get('name')
                if not model_name or model_name not in self.models:
                    continue

                # Check for model-level tests
                if 'tests' in model:
                    self.models[model_name]['has_tests'] = True
                    for test in model['tests']:
                        test_name = self._get_test_name(test)
                        self.models[model_name]['test_types'].add(test_name)

                # Check for column-level tests
                if 'columns' in model:
                    for column in model['columns']:
                        if 'tests' in column:
                            self.models[model_name]['has_tests'] = True
                            for test in column['tests']:
                                test_name = self._get_test_name(test)
                                self.models[model_name]['test_types'].add(test_name)

                                # Track specific test types
                                column_name = column.get('name', '')
                                self._track_test_type(model_name, column_name, test_name)

        except Exception as e:
            print(f"Warning: Could not parse {yml_file}: {e}", file=sys.stderr)

    def _get_test_name(self, test) -> str:
        """Extract test name from test definition."""
        if isinstance(test, str):
            return test
        elif isinstance(test, dict):
            return list(test.keys())[0]
        return 'unknown'

    def _track_test_type(self, model_name: str, column_name: str, test_name: str):
        """Track specific test types for gap analysis."""
        if model_name not in self.tests:
            self.tests[model_name] = []

        self.tests[model_name].append({
            'column': column_name,
            'test': test_name
        })

    def _calculate_coverage(self, layer_filter: str = None) -> Dict:
        """Calculate coverage statistics."""
        models = self.models.values()

        # Apply layer filter
        if layer_filter:
            models = [m for m in models if m['layer'] == layer_filter]

        total_models = len(models)
        tested_models = len([m for m in models if m['has_tests']])

        overall_percentage = (tested_models / total_models * 100) if total_models > 0 else 0

        # Calculate by layer
        by_layer = {}
        for layer in ['staging', 'intermediate', 'marts']:
            layer_models = [m for m in self.models.values() if m['layer'] == layer]
            layer_tested = len([m for m in layer_models if m['has_tests']])
            layer_total = len(layer_models)

            if layer_total > 0:
                by_layer[layer] = {
                    'percentage': round(layer_tested / layer_total * 100, 1),
                    'tested': layer_tested,
                    'total': layer_total
                }

        # Calculate by model type within marts
        marts_models = [m for m in self.models.values() if m['layer'] == 'marts']
        by_type = {}
        for model_type in ['fact', 'dimension']:
            type_models = [m for m in marts_models if m['type'] == model_type]
            type_tested = len([m for m in type_models if m['has_tests']])
            type_total = len(type_models)

            if type_total > 0:
                by_type[model_type] = {
                    'percentage': round(type_tested / type_total * 100, 1),
                    'tested': type_tested,
                    'total': type_total
                }

        return {
            'overall_percentage': round(overall_percentage, 1),
            'target_percentage': self.target_coverage,
            'total_models': total_models,
            'tested_models': tested_models,
            'untested_models': total_models - tested_models,
            'by_layer': by_layer,
            'by_type': by_type,
            'meets_target': overall_percentage >= self.target_coverage
        }

    def _identify_gaps(self, layer_filter: str = None) -> List[Dict]:
        """Identify models with missing tests."""
        gaps = []

        for model_name, model_info in self.models.items():
            # Apply layer filter
            if layer_filter and model_info['layer'] != layer_filter:
                continue

            if not model_info['has_tests']:
                gaps.append({
                    'model': model_name,
                    'layer': model_info['layer'],
                    'type': model_info['type'],
                    'missing': ['all_tests'],
                    'priority': self._determine_priority(model_info)
                })
            else:
                # Check for specific missing test types
                missing = self._check_required_tests(model_name, model_info)
                if missing:
                    gaps.append({
                        'model': model_name,
                        'layer': model_info['layer'],
                        'type': model_info['type'],
                        'missing': missing,
                        'priority': self._determine_priority(model_info, missing)
                    })

        # Sort by priority
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        gaps.sort(key=lambda x: priority_order.get(x['priority'], 4))

        return gaps

    def _check_required_tests(self, model_name: str, model_info: Dict) -> List[str]:
        """Check if model has required tests based on type."""
        missing = []
        model_tests = self.tests.get(model_name, [])
        test_types = {t['test'] for t in model_tests}

        # Check for primary key tests
        has_unique = 'unique' in test_types
        has_not_null_pk = any(t['test'] == 'not_null' for t in model_tests)

        if not has_unique:
            missing.append('pk_unique')
        if not has_not_null_pk:
            missing.append('pk_not_null')

        # For facts and dimensions, check for foreign key tests
        if model_info['type'] in ['fact', 'dimension']:
            has_relationships = 'relationships' in test_types
            if not has_relationships and model_info['type'] == 'fact':
                missing.append('fk_relationships')

        return missing

    def _determine_priority(self, model_info: Dict, missing: List[str] = None) -> str:
        """Determine priority level for missing tests."""
        model_type = model_info['type']
        layer = model_info['layer']

        # Critical: Facts and dimensions without tests
        if model_type in ['fact', 'dimension'] and (not missing or 'all_tests' in missing):
            return 'critical'

        # Critical: Any model in marts without PK tests
        if layer == 'marts' and missing and ('pk_unique' in missing or 'pk_not_null' in missing):
            return 'critical'

        # High: Facts missing FK tests
        if model_type == 'fact' and missing and 'fk_relationships' in missing:
            return 'high'

        # High: Staging models without tests
        if model_type == 'staging' and (not missing or 'all_tests' in missing):
            return 'high'

        # Medium: Other marts models
        if layer == 'marts':
            return 'medium'

        return 'low'

    def _generate_recommendations(self, results: Dict) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        gaps = results.get('gaps', [])

        # Count missing test types
        missing_pk = len([g for g in gaps if 'pk_unique' in g['missing'] or 'pk_not_null' in g['missing']])
        missing_fk = len([g for g in gaps if 'fk_relationships' in g['missing']])
        untested = len([g for g in gaps if 'all_tests' in g['missing']])

        if untested > 0:
            recommendations.append(f"Add tests to {untested} completely untested model(s)")

        if missing_pk > 0:
            recommendations.append(f"Add primary key tests (unique + not_null) to {missing_pk} model(s)")

        if missing_fk > 0:
            recommendations.append(f"Add foreign key tests (relationships) to {missing_fk} model(s)")

        # Calculate gap to target
        current = results['overall_percentage']
        target = results['target_percentage']
        if current < target:
            total = results['total_models']
            needed = int((target / 100 * total) - results['tested_models']) + 1
            recommendations.append(f"Current coverage: {current}% -> Target: {target}% (Need {needed} more model(s) tested)")

        if not recommendations:
            recommendations.append("All coverage targets met!")

        return recommendations


def format_text_report(results: Dict, detailed: bool = False) -> str:
    """Format results as human-readable text."""
    lines = []

    lines.append("=== dbt Test Coverage Report ===")
    lines.append("")

    # Overall stats
    lines.append(f"Overall Coverage: {results['overall_percentage']}% ({results['tested_models']}/{results['total_models']} models)")
    status_text = "PASS" if results['meets_target'] else "BELOW TARGET"
    lines.append(f"Target: {results['target_percentage']}% {status_text}")
    lines.append("")

    # By layer
    if results['by_layer']:
        lines.append("Coverage by Layer:")
        for layer, stats in results['by_layer'].items():
            status = 'PASS' if stats['percentage'] >= 80 else 'WARN'
            lines.append(f"  +- {layer:<12}: {stats['percentage']:>5}% ({stats['tested']}/{stats['total']}) [{status}]")

            # Show by type for marts
            if layer == 'marts' and results.get('by_type'):
                for model_type, type_stats in results['by_type'].items():
                    lines.append(f"  |  +- {model_type:<10}: {type_stats['percentage']:>5}% ({type_stats['tested']}/{type_stats['total']})")
        lines.append("")

    # Gaps
    if results.get('gaps'):
        lines.append(f"UNTESTED/INCOMPLETE MODELS ({len(results['gaps'])}):")

        # Group by priority
        by_priority = {}
        for gap in results['gaps']:
            priority = gap['priority']
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append(gap)

        for priority in ['critical', 'high', 'medium', 'low']:
            if priority in by_priority:
                lines.append(f"  {priority.capitalize()} ({len(by_priority[priority])}):")

                # Limit display to first 5 per priority in non-detailed mode
                items = by_priority[priority][:5] if not detailed else by_priority[priority]

                for gap in items:
                    missing_str = ', '.join(gap['missing'])
                    lines.append(f"    >> {gap['model']} - Missing: {missing_str}")

                if not detailed and len(by_priority[priority]) > 5:
                    lines.append(f"    ... ({len(by_priority[priority]) - 5} more)")
                lines.append("")

    # Recommendations
    if results.get('recommendations'):
        lines.append("RECOMMENDATIONS:")
        for i, rec in enumerate(results['recommendations'], 1):
            lines.append(f"{i}. {rec}")

    return '\n'.join(lines)


def format_json_report(results: Dict) -> str:
    """Format results as JSON."""
    return json.dumps(results, indent=2, default=str)


def format_markdown_report(results: Dict) -> str:
    """Format results as Markdown."""
    lines = []

    lines.append("# dbt Test Coverage Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Overall Coverage**: {results['overall_percentage']}% ({results['tested_models']}/{results['total_models']} models)")
    lines.append(f"- **Target**: {results['target_percentage']}%")
    lines.append(f"- **Status**: {'✅ Meets Target' if results['meets_target'] else '⚠️ Below Target'}")
    lines.append("")

    # By layer
    if results['by_layer']:
        lines.append("## Coverage by Layer")
        lines.append("")
        lines.append("| Layer | Coverage | Tested | Total | Status |")
        lines.append("|-------|----------|--------|-------|--------|")

        for layer, stats in results['by_layer'].items():
            status = '✅' if stats['percentage'] >= 80 else '⚠️'
            lines.append(f"| {layer} | {stats['percentage']}% | {stats['tested']} | {stats['total']} | {status} |")
        lines.append("")

    # Gaps
    if results.get('gaps'):
        lines.append("## Models Needing Tests")
        lines.append("")
        lines.append("| Priority | Model | Layer | Type | Missing Tests |")
        lines.append("|----------|-------|-------|------|---------------|")

        for gap in results['gaps'][:20]:  # Limit to top 20 in markdown
            missing = ', '.join(gap['missing'])
            lines.append(f"| {gap['priority']} | `{gap['model']}` | {gap['layer']} | {gap['type']} | {missing} |")

        if len(results['gaps']) > 20:
            lines.append(f"\n*... and {len(results['gaps']) - 20} more models*\n")
        lines.append("")

    # Recommendations
    if results.get('recommendations'):
        lines.append("## Recommendations")
        lines.append("")
        for rec in results['recommendations']:
            lines.append(f"- {rec}")

    return '\n'.join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze dbt test coverage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--detailed', action='store_true',
                        help='Show detailed report with all gaps')
    parser.add_argument('--format', choices=['text', 'json', 'markdown'],
                        default='text', help='Output format (default: text)')
    parser.add_argument('--layer', choices=['staging', 'intermediate', 'marts'],
                        help='Filter by layer')
    parser.add_argument('--project-dir', default='.',
                        help='Path to dbt project (default: current directory)')
    parser.add_argument('--target', type=float, default=80.0,
                        help='Target coverage percentage (default: 80)')

    args = parser.parse_args()

    # Run analysis
    analyzer = TestCoverageAnalyzer(args.project_dir, args.target)
    results = analyzer.analyze(args.layer)

    # Format output
    if args.format == 'json':
        output = format_json_report(results)
    elif args.format == 'markdown':
        output = format_markdown_report(results)
    else:
        output = format_text_report(results, args.detailed)

    print(output)

    # Exit with error code if below target (but only if there are models to test)
    if not results['meets_target'] and results['total_models'] > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
