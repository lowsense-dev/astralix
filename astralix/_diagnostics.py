# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Shareable diagnostics from an allowlist; never copy configs, logs or sessions."""
import platform
from . import version


def report(state, modules):
    state = state or {}
    return {
        'version': '.'.join(map(str, version.__version__)),
        'python': platform.python_version(), 'system': platform.system(),
        'release': {key: state.get('active', {}).get(key) for key in ('commit', 'channel')},
        'pending': bool(state.get('pending')),
        'history': [{key: item.get(key) for key in ('time', 'status', 'commit', 'channel')}
                    for item in state.get('history', [])[-12:]],
        'modules': [{'name': module.__class__.__name__, 'ready': bool(getattr(module, '__ready__', False)),
                     'core': str(getattr(module, '__origin__', '')).startswith('<core')}
                    for module in modules],
    }
