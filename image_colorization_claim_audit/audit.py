"""Offline prose matching and conservative per-module AST evidence."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys
from . import __version__, phrases


def claims(text):
    lines = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith('```'):
            fenced = not fenced
        elif not fenced:
            lines.append(line.replace('`', ''))
    text = '\n'.join(lines).lower()

    def consume(words):
        nonlocal text
        found = []
        for word in sorted(words, key=len, reverse=True):
            while word in text:
                start = text.index(word)
                found.append(word)
                text = text[:start] + ' ' * len(word) + text[start + len(word):]
        return found

    negative = consume(phrases.NOCOLORIZATION)
    return consume(phrases.COLORIZATION), negative


def evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    imports = {}
    shadows = {n.name for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module or '') + '.' + alias.name

    def resolve(node):
        if isinstance(node, ast.Name):
            if node.id in shadows:
                return ''
            return imports.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            if not base or node.attr in shadows:
                return ''
            return base + '.' + node.attr
        return ''

    def call_name(node):
        name = resolve(node)
        if isinstance(node, ast.Name) and node.id not in imports:
            return ''
        return name.rsplit('.', 1)[-1] if name else ''

    bindings = {}
    # Assignment propagation supports aliases independent of textual order.
    assignments = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]

    def instance(node, seen=None):
        seen = set() if seen is None else seen
        if isinstance(node, ast.Name):
            if node.id in seen or node.id in shadows:
                return ''
            return instance(bindings.get(node.id), seen | {node.id})
        if not isinstance(node, ast.Call):
            return ''
        name = call_name(node.func)
        resolved = resolve(node.func)
        if name in phrases.GET_IMAGE_COLORIZER_NAMES and resolved.rsplit('.', 1)[0] in phrases.GET_IMAGE_COLORIZER_SOURCES:
            return 'transform'
        # Direct constructors are permitted without an import, unlike generic calls.
        if isinstance(node.func, ast.Name) and node.func.id not in shadows:
            name = imports.get(node.func.id, node.func.id).rsplit('.', 1)[-1]
        if name in phrases.PIPELINE_CLASSES:
            return 'pipeline'
        if name in phrases.MODEL_CLASSES:
            return 'model'
        if call_name(node.func) in phrases.READ_NET_NAMES and any(
                isinstance(arg, ast.Constant) and isinstance(arg.value, str) and 'colorization' in arg.value.lower()
                for arg in list(node.args) + [kw.value for kw in node.keywords]):
            return 'net'
        if isinstance(node.func, ast.Attribute) and node.func.attr in ('eval', 'to', 'cpu', 'cuda'):
            return instance(node.func.value, seen)
        return ''

    for node in assignments:
        for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
            if isinstance(target, ast.Name):
                bindings[target.id] = node.value
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if call_name(node.func) in phrases.GENERIC_NAMES:
            return True
        if instance(node.func) == 'model':
            return True
        if isinstance(node.func, ast.Attribute):
            kind = instance(node.func.value)
            if (kind == 'pipeline' and node.func.attr == 'process' or
                kind == 'net' and node.func.attr == 'forward' or
                kind == 'transform' and node.func.attr in ('get_transformed_image', 'plot_transformed_image', 'plot_transformed_image_from_url')):
                return True
    return False


SKIP = {'.git', '__pycache__', '.venv', 'venv', 'env', '.env', 'virtualenv', 'build', 'dist'}


def audit(repo='.', ignore=(), verbose=False):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository must be an existing directory')
    positive, negative, test_claim = False, False, False
    has_evidence = False
    if verbose:
        print('Scope: README.md, docs/**/*.md, tests fixtures, Python sources in ' + str(root), file=sys.stderr)
    for directory, dirs, files in os.walk(root, onerror=lambda error: (_ for _ in ()).throw(error)):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(directory) / d / 'pyvenv.cfg').exists())
        for filename in sorted(files):
            path = Path(directory) / filename
            rel = path.relative_to(root).as_posix()
            if any(rel.startswith(prefix) for prefix in ignore):
                continue
            doc = rel == 'README.md' or (rel.startswith('docs/') and path.suffix == '.md')
            test = 'tests' in path.relative_to(root).parts[:-1]
            py = path.suffix == '.py'
            if not (doc or test or py):
                continue
            text = path.read_text(encoding='utf-8')
            pos, neg = claims(text) if doc or test else ([], [])
            if doc:
                positive |= bool(pos)
                negative |= bool(neg)
            elif test:
                test_claim |= bool(pos)
            found = evidence(text) if py else False
            has_evidence |= found
            if verbose:
                print('{}: positive={} denial={} evidence={}'.format(rel, len(pos), len(neg), found), file=sys.stderr)
    findings = []
    def finding(rule, severity, message):
        findings.append(dict(rule=rule, severity=severity, verdict='FAIL', message=message))
    if not has_evidence and (positive or test_claim):
        finding('documented-image-colorization-claim-false', 'HIGH' if positive else 'MEDIUM', 'Claim has no recognized source evidence.' if positive else 'Test fixture claim has no recognized source evidence.')
    if negative and has_evidence:
        finding('documented-no-image-colorization-claim-false', 'HIGH', 'Denial conflicts with recognized source evidence.')
    return findings


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    parser = Parser(description='Offline documentation claim auditor')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    scan = sub.add_parser('audit')
    scan.add_argument('repo', nargs='?', default='.')
    scan.add_argument('--json', action='store_true')
    scan.add_argument('--verbose', action='store_true')
    scan.add_argument('--ignore', action='append', default=[])
    scan.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    try:
        args = parser.parse_args(argv)
        findings = audit(args.repo, args.ignore, args.verbose)
        failed = any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in findings)
        verdict = 'FAIL' if failed else 'PASS'
        if args.json:
            print(json.dumps(dict(verdict=verdict, findings=findings)))
        else:
            print(verdict)
            for finding in findings:
                print('{rule} {severity}: {message}'.format(**finding))
        return 2 if failed else 0
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
