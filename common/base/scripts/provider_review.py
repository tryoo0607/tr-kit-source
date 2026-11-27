"""Read-only installation review and update comparison, not an installer or signer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

from provider_links import LinkError, MAX_CLI_BYTES, resolve
import runtime_config

MAX_FILES = 8192
MAX_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_PACKAGE_FILES = 32768
MAX_PACKAGE_BYTES = 2 * 1024 * 1024 * 1024
MAX_REVIEW_BYTES = 12 * 1024 * 1024
LAYOUT_METHODS = {'standalone-cli': ('official-release',), 'appimage': ('official-release',),
                  'cli-package': ('npm', 'uv')}
LAYOUTS = ('directory', *LAYOUT_METHODS)
INTERNAL_LINK_LAYOUTS = ('appimage', 'cli-package')
METHODS = ('native-plugin', 'system-skill', 'npm', 'uv', 'official-release', 'skills-cli')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise LinkError('canonical non-symlink path required')
    return path


def bounded(path, limit=4_000_000):
    path = canonical(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise LinkError('bounded regular evidence required')
    data = path.read_bytes()
    if len(data) > limit:
        raise LinkError('evidence limit exceeded')
    return data


def file_record(item, root, limit):
    fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise LinkError('installation exceeds review limits')
        remaining = before.st_size
        pin = hashlib.sha256()
        while remaining:
            chunk = stream.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise LinkError('installation changed during review')
            pin.update(chunk)
            remaining -= len(chunk)
        after = os.fstat(stream.fileno())
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if stream.read(1) or signature(before) != signature(after) or signature(after) != signature(item.lstat()):
            raise LinkError('installation changed during review')
    return {'path': str(item.relative_to(root)), 'size': before.st_size, 'sha256': pin.hexdigest()}


def file_limit(layout):
    if layout == 'appimage':
        return MAX_EXPANDED_BYTES
    if layout in ('standalone-cli', 'cli-package'):
        return MAX_CLI_BYTES
    return 64_000_000


def tree_limits(layout):
    if layout == 'cli-package':
        return MAX_PACKAGE_FILES, MAX_PACKAGE_BYTES
    if layout == 'appimage':
        return MAX_FILES, MAX_EXPANDED_BYTES
    return MAX_FILES, MAX_BYTES


def tree(path, layout='directory', entry=None):
    """Inventory a reviewed installation without traversing directory symlinks."""
    path = canonical(path)
    if not path.is_dir():
        raise LinkError('installation directory required')
    if layout == 'standalone-cli':
        if entry is None or entry.parent != path:
            raise LinkError('standalone CLI must be in the declared installation directory')
        return [file_record(entry, path, MAX_CLI_BYTES)]
    node_limit, byte_limit = tree_limits(layout)
    result = []
    total = nodes = 0
    for item in path.rglob('*'):
        nodes += 1
        if nodes > node_limit * 2:
            raise LinkError('unsupported installation tree')
        if item.is_symlink():
            target = os.readlink(item)
            lexical_target = Path(os.path.normpath(item.parent / target))
            if (layout not in INTERNAL_LINK_LAYOUTS or Path(target).is_absolute()
                    or not lexical_target.is_relative_to(path)
                    or not item.resolve(strict=True).is_relative_to(path) or len(result) >= node_limit):
                raise LinkError('unsupported installation link')
            result.append({'path': str(item.relative_to(path)), 'symlink': target})
            continue
        if item.is_dir():
            continue
        if not item.is_file() or len(result) >= node_limit:
            raise LinkError('unsupported installation node')
        record = file_record(item, path, min(file_limit(layout), byte_limit - total))
        total += record['size']
        result.append(record)
    if not result:
        raise LinkError('empty installation')
    return sorted(result, key=lambda record: Path(record['path']))


def identity(entry):
    return {k: entry[k] for k in ('id', 'kind', 'entry', 'sha256', 'version')}


def snapshot(root, declaration, product, provider_id, kind, installation, method, source, evidence, layout='directory'):
    selected = resolve(root, declaration, product, provider_id, kind)
    installation = canonical(installation)
    root = Path(root).resolve(strict=True)
    if installation == root or root in installation.parents or not Path(selected['entry']).is_relative_to(installation):
        raise LinkError('external installation must contain selected entry')
    if method not in METHODS or not source.startswith('https://') or not evidence:
        raise LinkError('explicit official source, method and installation evidence required')
    if layout not in LAYOUTS or (layout != 'directory' and
                                (kind != 'cli' or method not in LAYOUT_METHODS[layout])):
        raise LinkError('CLI layout incompatible with installation method')
    receipts = []
    for p in evidence:
        p = canonical(p)
        if p == root or root in p.parents or str(p) in [x['path'] for x in receipts]:
            raise LinkError('distinct external installation evidence required')
        receipts.append({'path': str(p), 'sha256': digest(bounded(p))})
    entry = Path(selected['entry'])
    files = tree(installation, layout, entry)
    if not any(record['path'] == str(entry.relative_to(installation))
               and record.get('sha256') == selected['sha256'] for record in files):
        raise LinkError('review inventory does not contain pinned entry')
    # Recheck identity and resource bytes. This is drift detection, not OS locking.
    if resolve(root, declaration, product, provider_id, kind) != selected or tree(installation, layout, entry) != files:
        raise LinkError('installation changed during review')
    install = {'root': str(installation), 'method': method, 'source': source}
    if layout != 'directory':
        install['layout'] = layout
    return {'schema_version': 1, 'provider': identity(selected),
            'installation': install,
            'files': files, 'evidence': receipts, 'review_status': 'pending',
            'products': {product: {'status': 'unverified', 'basis': ''}},
            'unresolved': ['Review official installation evidence, required external resources and product contract.']}


def read_review(path):
    raw = bounded(path, MAX_REVIEW_BYTES)
    doc = json.loads(raw)
    expected = {'schema_version', 'provider', 'installation', 'files', 'evidence', 'review_status', 'products', 'unresolved'}
    if not isinstance(doc, dict) or set(doc) != expected or type(doc['schema_version']) is not int or doc['schema_version'] != 1:
        raise LinkError('unsupported review record')
    if doc['review_status'] not in ('pending', 'reviewed') or not isinstance(doc['unresolved'], list):
        raise LinkError('invalid review state')
    if any(not isinstance(x, str) or not x for x in doc['unresolved']):
        raise LinkError('invalid unresolved resource')
    if not isinstance(doc['products'], dict) or not doc['products'] or set(doc['products']) - {'codex', 'claude'}:
        raise LinkError('invalid product review')
    for value in doc['products'].values():
        if (not isinstance(value, dict) or set(value) != {'status', 'basis'} or
                value['status'] not in ('unverified', 'supported', 'unsupported') or not isinstance(value['basis'], str)):
            raise LinkError('invalid product review')
    install = doc['installation']
    if (not isinstance(install, dict) or set(install) - {'layout'} != {'root', 'method', 'source'} or
            install['method'] not in METHODS or not isinstance(install['source'], str) or not install['source'].startswith('https://')):
        raise LinkError('invalid installation identity')
    layout = install.get('layout', 'directory')
    if layout not in LAYOUTS:
        raise LinkError('invalid installation layout')
    canonical(install['root'])
    if not isinstance(doc['provider'], dict) or set(doc['provider']) != {'id', 'kind', 'entry', 'sha256', 'version'}:
        raise LinkError('invalid provider identity')
    node_limit, byte_limit = tree_limits(layout)
    if not isinstance(doc['files'], list) or not 1 <= len(doc['files']) <= node_limit:
        raise LinkError('invalid closure')
    paths = set()
    total = 0
    for item in doc['files']:
        if not isinstance(item, dict) or set(item) not in ({'path', 'size', 'sha256'}, {'path', 'symlink'}):
            raise LinkError('invalid closure entry')
        p = Path(item['path'])
        if p.is_absolute() or '..' in p.parts or not p.parts or str(p) != item['path'] or item['path'] in paths:
            raise LinkError('invalid closure path')
        paths.add(item['path'])
        if 'symlink' in item:
            if layout not in INTERNAL_LINK_LAYOUTS or not isinstance(item['symlink'], str) or not item['symlink'] or Path(item['symlink']).is_absolute():
                raise LinkError('invalid closure link')
            continue
        if type(item['size']) is not int or not 0 <= item['size'] <= file_limit(layout):
            raise LinkError('invalid closure size')
        total += item['size']
        if layout != 'standalone-cli' and total > byte_limit:
            raise LinkError('invalid closure total size')
        if not isinstance(item['sha256'], str) or len(item['sha256']) != 64 or any(c not in '0123456789abcdef' for c in item['sha256']):
            raise LinkError('invalid closure pin')
    if not isinstance(doc['evidence'], list) or not doc['evidence']:
        raise LinkError('installation evidence missing')
    for item in doc['evidence']:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise LinkError('invalid evidence identity')
        canonical(item['path'])
    return doc, digest(raw)


def verify(root, declaration, product, provider_id, kind, review):
    doc, review_hash = read_review(review)
    selected = resolve(root, declaration, product, provider_id, kind)
    if doc['provider'] != identity(selected):
        raise LinkError('review is for different entry or version')
    status = doc['products'].get(product, {})
    if doc['review_status'] != 'reviewed' or status.get('status') != 'supported' or not status.get('basis', '').strip() or doc['unresolved']:
        raise LinkError('official installation or product resources remain unreviewed')
    current = snapshot(root, declaration, product, provider_id, kind,
                       doc['installation']['root'], doc['installation']['method'], doc['installation']['source'],
                       [x['path'] for x in doc['evidence']], doc['installation'].get('layout', 'directory'))
    if current['files'] != doc['files'] or current['evidence'] != doc['evidence']:
        raise LinkError('installation resources or evidence changed; review update')
    return {'status': 'review-record-verified', 'id': provider_id, 'product': product,
            'entry': selected['entry'], 'review_sha256': review_hash, 'files': len(doc['files']),
            'native_verified': False, 'provenance_authenticated': False,
            'limits': 'Fresh bytes match an explicit local review. Does not authenticate its author, prove provenance, execute workflows or test native integration.'}


def verify_configured(root, provider_id, kind, product=None):
    product = product or runtime_config.product_for_root(root)
    _, config = runtime_config.load(product)
    path = config['provider_reviews'].get(provider_id)
    if not path:
        raise LinkError('external installation review missing')
    return verify(root, config['providers'], product, provider_id, kind, path)


def compare(before, after):
    old, old_hash = read_review(before)
    new, new_hash = read_review(after)
    if old['provider']['id'] != new['provider']['id'] or old['provider']['kind'] != new['provider']['kind']:
        raise LinkError('different provider comparison')
    a = {x['path']: x for x in old['files']}
    b = {x['path']: x for x in new['files']}
    return {'status': 'comparison-only', 'before_sha256': old_hash, 'after_sha256': new_hash,
            'added': sorted(b.keys() - a.keys()), 'removed': sorted(a.keys() - b.keys()),
            'changed': sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
            'identity_changed': old['provider'] != new['provider'] or old['installation'] != new['installation'],
            'evidence_changed': old['evidence'] != new['evidence'],
            'product_contract_changed': old['products'] != new['products'],
            'limits': 'Recorded snapshots only; inspect official old/new instructions and behavior. This never approves or repins an update.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    for action in ('snapshot', 'verify'):
        p = subs.add_parser(action)
        for name in ('root', 'declaration'):
            p.add_argument('--' + name, type=Path, required=True)
        p.add_argument('--product', choices=('codex', 'claude'), required=True)
        p.add_argument('--id', required=True)
        p.add_argument('--kind', choices=('skill', 'cli'), required=True)
        if action == 'verify':
            p.add_argument('--review', type=Path, required=True)
        else:
            p.add_argument('--installation', type=Path, required=True)
            p.add_argument('--layout', choices=LAYOUTS, default='directory')
            p.add_argument('--method', choices=METHODS, required=True)
            p.add_argument('--source', required=True)
            p.add_argument('--evidence', type=Path, action='append', required=True)
    p = subs.add_parser('compare')
    p.add_argument('--before', type=Path, required=True)
    p.add_argument('--after', type=Path, required=True)
    p = subs.add_parser('configured')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--product', choices=('codex', 'claude'))
    p.add_argument('--id', required=True)
    p.add_argument('--kind', choices=('skill', 'cli'), required=True)
    a = parser.parse_args(argv)
    try:
        if a.action == 'compare':
            result = compare(a.before, a.after)
        elif a.action == 'configured':
            result = verify_configured(a.root, a.id, a.kind, a.product)
        elif a.action == 'verify':
            result = verify(a.root, a.declaration, a.product, a.id, a.kind, a.review)
        else:
            result = snapshot(a.root, a.declaration, a.product, a.id, a.kind, a.installation, a.method, a.source,
                              a.evidence, a.layout)
    except Exception:
        print(json.dumps({'status': 'unavailable', 'message': 'selected installation review is incomplete'}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
