# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Module provenance and dependencies, separate from the userbot environment."""
import ast
import hashlib
from importlib import metadata
import re
import time
try:
    import tomllib
except ImportError:
    import tomli as tomllib


def validate_requirements(requirements):
    result = set()
    for value in requirements:
        if not isinstance(value, str) or not re.fullmatch(
            r'[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?(?:[<>=!~][A-Za-z0-9*.,!<>=~+_-]+)?', value
        ):
            raise ValueError('Module dependencies must be package names with version constraints; URLs and installer options are not allowed')
        result.add(value)
    return sorted(result)


def declared(source):
    return [item for match in re.finditer(r'^\s*#\s*(?:scope:\s*)?requires(?:\s*:\s*|\s+)(.+)$', source, re.M)
            for item in match[1].split()]


def requirements_for_sources(sources, lock_text):
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    graph = {}
    for package in tomllib.loads(lock_text)['package']:
        graph.setdefault(normalize(package['name']), set()).update(
            normalize(item['name']) for item in package.get('dependencies', [])
        )
    core, todo = set(), ['astralix']
    while todo:
        name = todo.pop()
        if name not in core:
            core.add(name)
            todo.extend(graph.get(name, ()))
    mapping = metadata.packages_distributions()
    requirements = set()
    for source in sources:
        requirements.update(declared(source))
        for node in ast.walk(ast.parse(source)):
            imports = [alias.name for alias in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and not node.level and node.module else []
            )
            for name in imports:
                for distribution in mapping.get(name.split('.')[0], []):
                    if normalize(distribution) not in core:
                        requirements.add(f'{distribution}=={metadata.version(distribution)}')
    # Core constraints are authoritative even when a module imports core libraries.
    return validate_requirements(requirements)


def record(previous, source, origin, version):
    digest = hashlib.sha256(source.encode()).hexdigest()
    history = list(previous.get('history', [])) if previous else []
    if not previous or previous.get('sha256') != digest:
        history.append({'time': int(time.time()), 'sha256': digest, 'origin': origin,
                        'version': str(version)})
    return {'sha256': digest, 'origin': origin, 'version': str(version),
            'requirements': declared(source), 'history': history[-20:]}
