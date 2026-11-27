"""Select and verify the host's Orca CLI without executing the launcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

import provider_review
from provider_links import LinkError
import runtime_config


ROOT = Path(__file__).resolve().parents[3]
IDS = {'orca': 'orca-cli', 'orca-ide': 'orca-ide-cli', 'orca-dev': 'orca-dev-cli'}


def select_command():
    configured = os.environ.get('ORCA_CLI_COMMAND', '').strip()
    if configured:
        return configured
    if os.environ.get('ORCA_DEV_REPO_ROOT'):
        return 'orca-dev'
    return 'orca-ide' if sys.platform == 'linux' and not os.environ.get('ORCA_PANE_KEY') else 'orca'


def file_identity(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class OrcaConnection:
    def __init__(self, command, product=None):
        self.command = command
        product = product or runtime_config.product_for_root(ROOT)
        _, config = runtime_config.load(product)
        connection_id = IDS.get(Path(command).name, 'orca-cli')
        review = config['provider_reviews'].get(connection_id)
        if not review:
            raise LinkError('Orca installation review missing')
        result = provider_review.verify(ROOT, config['providers'], product, connection_id, 'cli', review)
        self.entry = Path(result['entry'])
        self.entry_identity = file_identity(self.entry)
        self.review = Path(review)
        self.review_identity = file_identity(self.review)
        record, review_hash = provider_review.read_review(self.review)
        if review_hash != result['review_sha256']:
            raise LinkError('Orca installation review changed')
        entry_pin = provider_review.file_record(self.entry, self.entry.parent, 64_000_000)
        if entry_pin['sha256'] != record['provider']['sha256']:
            raise LinkError('Orca executable changed')
        self.selector = None
        self.launchers = {}
        selected = self.current_command()
        if selected != self.entry:
            self.read_launcher_binding(record, selected)
        self.checked_entry()

    def current_command(self):
        candidate = shutil.which(self.command)
        if candidate is None:
            raise LinkError('Orca executable unavailable')
        return Path(candidate).resolve(strict=True)

    def read_launcher_binding(self, record, selected):
        if record['installation'].get('layout') != 'appimage':
            raise LinkError('selected Orca executable differs from review')
        for evidence in record['evidence']:
            path = Path(evidence['path'])
            if path.name != 'orca-launcher.json':
                continue
            raw = provider_review.bounded(path)
            if hashlib.sha256(raw).hexdigest() != evidence['sha256']:
                raise LinkError('Orca launcher evidence changed')
            doc = json.loads(raw)
            if not isinstance(doc, dict) or set(doc) != {'selector', 'launchers'}:
                raise LinkError('invalid Orca launcher evidence')
            selector = Path(doc['selector'])
            provider_review.canonical(selector.parent)
            launchers = doc['launchers']
            if not isinstance(launchers, dict) or not 1 <= len(launchers) <= 4:
                raise LinkError('invalid Orca launchers')
            self.selector = selector
            self.launchers = {provider_review.canonical(name): pin for name, pin in launchers.items()}
            if selected not in self.launchers:
                raise LinkError('selected Orca launcher not reviewed')
            return
        raise LinkError('Orca launcher evidence missing')

    def checked_entry(self):
        if (self.entry.resolve(strict=True) != self.entry or file_identity(self.entry) != self.entry_identity
                or self.review.resolve(strict=True) != self.review
                or file_identity(self.review) != self.review_identity):
            raise LinkError('Orca executable or review changed')
        selected = self.current_command()
        if self.selector is None:
            if selected != self.entry:
                raise LinkError('selected Orca executable changed')
        else:
            if (selected not in self.launchers or not self.selector.is_symlink()
                    or self.selector.resolve(strict=True) != self.entry):
                raise LinkError('Orca launcher target changed')
            for path, pin in self.launchers.items():
                if hashlib.sha256(provider_review.bounded(path, 64_000)).hexdigest() != pin:
                    raise LinkError('Orca launcher bytes changed')
        return str(self.entry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product', choices=('codex', 'claude'))
    args = parser.parse_args()
    try:
        connection = OrcaConnection(select_command(), args.product)
        print(json.dumps({'status': 'verified', 'entry': connection.checked_entry()}))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'deferred', 'reason': 'orca-external-connection-unverified'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
