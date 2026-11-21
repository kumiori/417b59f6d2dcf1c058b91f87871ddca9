"""Measure production Python review thresholds and reject new or worsened exceptions."""

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

SOURCES = ('game', 'game_gamer_semantics', 'hube_tag', 'tools')
LIMITS = {
    'module_lines': 500,
    'class_lines': 300,
    'function_lines': 50,
    'cyclomatic_complexity': 15,
    'conditional_depth': 3,
}
SCOPES = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
BRANCHES = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.Match)
BASELINE = Path('docs/complexity-baseline.json')
RUFF_VERSION = '0.9.7'


def conditional_depth(node):
    """Count nested conditionals and loops. An elif shares its if's level."""
    if isinstance(node, SCOPES):
        return 0
    if isinstance(node, ast.If):
        body = max(map(conditional_depth, node.body), default=0)
        condition = conditional_depth(node.test)
        if (
            len(node.orelse) == 1
            and isinstance(node.orelse[0], ast.If)
            and node.orelse[0].col_offset == node.col_offset
        ):
            return max(1 + max(body, condition), conditional_depth(node.orelse[0]))
        alternate = max(map(conditional_depth, node.orelse), default=0)
        return 1 + max(body, condition, alternate)
    inner = max(map(conditional_depth, ast.iter_child_nodes(node)), default=0)
    return inner + isinstance(node, BRANCHES)


def definitions(node, parent=''):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SCOPES):
            name = f'{parent}.{child.name}' if parent else child.name
            yield name, child
            yield from definitions(child, name)
        else:
            yield from definitions(child, parent)


def ruff_complexities(root):
    version = subprocess.check_output(['ruff', '--version'], text=True).strip()
    if version != f'ruff {RUFF_VERSION}':
        raise SystemExit(f'Expected Ruff {RUFF_VERSION}, found {version}')
    result = subprocess.run(
        [
            'ruff',
            'check',
            '--isolated',
            '--no-cache',
            '--target-version',
            'py311',
            '--select',
            'C901',
            '--config',
            'lint.mccabe.max-complexity=0',
            '--output-format',
            'json',
            *SOURCES,
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise SystemExit(result.stderr)
    return {
        (
            Path(item['filename']).relative_to(root).as_posix(),
            item['location']['row'],
        ): int(re.search(r'\((\d+) > 0\)', item['message'])[1])
        for item in json.loads(result.stdout)
    }


def measure_definitions(source, name, complexity):
    for symbol, node in definitions(ast.parse(source)):
        lines = node.end_lineno - node.lineno + 1
        if isinstance(node, ast.ClassDef):
            metrics = {'class_lines': lines}
        else:
            metrics = {
                'function_lines': lines,
                'cyclomatic_complexity': complexity.get((name, node.lineno), 1),
                'conditional_depth': max(map(conditional_depth, node.body), default=0),
            }
        yield f'{name}::{symbol}', metrics


def measure(root):
    complexity = ruff_complexities(root)
    for directory in SOURCES:
        for path in sorted((root / directory).rglob('*.py')):
            name = path.relative_to(root).as_posix()
            source = path.read_text(encoding='utf-8')
            yield name, {'module_lines': len(source.splitlines())}
            yield from measure_definitions(source, name, complexity)


def exceptions(report):
    return {
        key: {
            metric: count for metric, count in values.items() if count > LIMITS[metric]
        }
        for key, values in report.items()
        if any(count > LIMITS[metric] for metric, count in values.items())
    }


def gate(current, baseline):
    breaches = [
        f'{key} {metric}: {count} (approved maximum {allowed})'
        for key, values in current.items()
        for metric, count in values.items()
        if count > (allowed := baseline.get(key, {}).get(metric, LIMITS[metric]))
    ]
    if breaches:
        print('\n'.join(breaches))
        return 1
    count = sum(map(len, current.values()))
    print(f'Complexity gate passed with {count} documented threshold exceptions.')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--root', type=Path, default=Path(__file__).resolve().parents[1]
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--report', action='store_true', help='Print all metrics as JSON')
    mode.add_argument(
        '--exceptions', action='store_true', help='Print threshold exceptions as JSON'
    )
    args = parser.parse_args()
    root = args.root.resolve()
    report = dict(measure(root))
    current = exceptions(report)
    if args.report or args.exceptions:
        print(json.dumps(report if args.report else current, indent=2, sort_keys=True))
        return 0
    return gate(current, json.loads((root / BASELINE).read_text(encoding='utf-8')))


if __name__ == '__main__':
    raise SystemExit(main())
