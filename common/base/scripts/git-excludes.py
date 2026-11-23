#!/usr/bin/env python3
"""Plan/apply exact ignores; only the explicit backup repo receives an exception."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from assets import fixed

RULES = ['_bmad/', '_bmad-output/', '_tr-assets/']


def git(*args):
    return subprocess.run(['git', *map(str, args)], check=True, capture_output=True, text=True, timeout=30).stdout.strip()


def append_rules(text, rules):
    missing = [r for r in rules if r not in text.splitlines()]
    return text + ('\n' if text and not text.endswith('\n') and missing else '') + ''.join(r + '\n' for r in missing)


def setup(excludes=None, backup=None, apply=False):
    if excludes is None:
        current = subprocess.run(['git', 'config', '--global', '--path', '--get', 'core.excludesFile'], capture_output=True, text=True, timeout=30)
        if current.returncode not in (0, 1):
            raise ValueError('global Git config lookup failed')
        excludes = current.stdout.strip() or str(Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'git/ignore')
    path = fixed(excludes)
    text = path.read_text() if path.exists() else ''
    additions = [r for r in RULES if r not in text.splitlines()]
    backup_root = fixed(backup) if backup else None
    exception = None
    existing = ''
    if backup_root:
        if backup_root.name != 'tr-local-docs':
            raise ValueError('backup exception requires the explicit tr-local-docs repository')
        if Path(git('-C', backup_root, 'rev-parse', '--show-toplevel')).resolve() != backup_root:
            raise ValueError('backup must be a repository root')
        exception = fixed(backup_root / '.gitignore')
        existing = exception.read_text() if exception.exists() else ''
    report = {'status': 'planned', 'global_excludes': str(path), 'append': additions,
              'backup': str(backup_root) if backup_root else None,
              'backup_rule': '!_bmad-output/' if backup_root else None}
    if apply:
        # Preflight both targets before mutation. This is not an atomic multi-file transaction.
        fixed(path)
        if (path.read_text() if path.exists() else '') != text:
            raise ValueError('global exclude changed since planning')
        if exception:
            fixed(exception)
            if (exception.read_text() if exception.exists() else '') != existing:
                raise ValueError('backup ignore changed since planning')
        path.parent.mkdir(parents=True, exist_ok=True)
        updated = append_rules(text, RULES)
        if updated != text or not path.exists(): path.write_text(updated)
        git('config', '--global', 'core.excludesFile', path)
        if exception:
            updated_exception = append_rules(existing, ['!_bmad-output/'])
            if updated_exception != existing or not exception.exists(): exception.write_text(updated_exception)
        report['status'] = 'applied'
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--excludes'); p.add_argument('--backup'); p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    try:
        print(json.dumps(setup(a.excludes, a.backup, a.apply), indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'failed', 'error': type(exc).__name__, 'partial_changes_possible': a.apply}))
        raise SystemExit(2)


if __name__ == '__main__': main()
