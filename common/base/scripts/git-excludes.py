#!/usr/bin/env python3
"""Plan/apply exact global directory ignores and a persistent backup-repo exception."""
import argparse
import json
from pathlib import Path
import subprocess

RULES = ['_bmad/', '_bmad-output/', '_tr-assets/']


def git(*args):
    return subprocess.run(['git', *map(str, args)], check=True, capture_output=True, text=True).stdout.strip()


def setup(excludes=None, backup=None, apply=False):
    if excludes is None:
        current = subprocess.run(['git', 'config', '--global', '--path', '--get', 'core.excludesFile'], capture_output=True, text=True)
        excludes = current.stdout.strip() or str(Path.home() / '.config/git/ignore')
    path = Path(excludes).expanduser().absolute()
    text = path.read_text() if path.exists() else ''
    additions = [r for r in RULES if r not in text.splitlines()]
    backup_root = Path(backup).resolve() if backup else None
    exception = None
    if backup_root:
        if backup_root.name != 'tr-local-docs':
            raise ValueError('backup exception requires the explicit tr-local-docs repository')
        if Path(git('-C', backup_root, 'rev-parse', '--show-toplevel')).resolve() != backup_root:
            raise ValueError('backup must be a repository root')
        exception = backup_root / '.gitignore'
        if exception.is_symlink():
            raise ValueError('backup .gitignore must not be a symlink')
    report = {'status': 'applied' if apply else 'planned', 'global_excludes': str(path),
              'append': additions, 'backup': str(backup_root) if backup_root else None,
              'backup_rule': '!_bmad-output/' if backup_root else None}
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + ('\n' if text and not text.endswith('\n') else '') + ''.join(r + '\n' for r in additions))
        git('config', '--global', 'core.excludesFile', path)
        if exception:
            # Repository rules override global excludes and remain persistent in backup history.
            existing = exception.read_text() if exception.exists() else ''
            rules = ['!_bmad-output/']
            missing = [rule for rule in rules if rule not in existing.splitlines()]
            exception.write_text(existing + ('\n' if existing and not existing.endswith('\n') else '') + ''.join(rule+'\n' for rule in missing))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--excludes'); p.add_argument('--backup'); p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    print(json.dumps(setup(a.excludes, a.backup, a.apply), indent=2))


if __name__ == '__main__': main()
