"""Pure schema-v1 validation. No path creation, registration or synchronization."""
from pathlib import Path
import re
import tomllib

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('invalid scope identifier')
    return value


def path_value(value):
    if not isinstance(value, str) or not value or not (value.startswith('/') or value.startswith('~/')):
        raise ValueError('expected absolute or home-relative path')
    if '..' in Path(value).parts:
        raise ValueError('parent traversal is not supported')
    return Path(value).expanduser()


def table(value, keys):
    if not isinstance(value, dict) or set(value) - set(keys):
        raise ValueError('unsupported table or field')


def strings(value):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value) or len(set(value)) != len(value):
        raise ValueError('expected unique string array')
    return value


def validate(data):
    table(data, ['schema_version', 'roots', 'projects', 'groups', 'common', 'knowledge', 'documents', 'sync_targets'])
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('unsupported common config version')
    targets = data.get('sync_targets', {})
    if not isinstance(targets, dict):
        raise ValueError('expected sync target table')
    for key, target in targets.items():
        identifier(key)
        table(target, ['repository', 'remote'])
        if set(target) != {'repository', 'remote'}:
            raise ValueError('incomplete sync target')
        path_value(target['repository'])
        # A remote name, never a URL/credential. Git registration is a separate check.
        remote = target['remote']
        if not isinstance(remote, str) or not remote or any(c.isspace() for c in remote) or any(c in remote for c in ':@\\'):
            raise ValueError('expected existing remote name')

    def sync(value):
        table(value, ['enabled', 'targets', 'exclude'])
        if type(value.get('enabled', False)) is not bool:
            raise ValueError('expected sync boolean')
        selected = strings(value.get('targets', []))
        for key in selected:
            identifier(key)
            if key not in targets:
                raise ValueError('undefined sync target')
        if value.get('enabled', False) and not selected:
            raise ValueError('enabled sync requires a target')
        for entry in strings(value.get('exclude', [])):
            if not entry or entry.startswith('/') or any(p in ('', '.', '..') for p in entry.split('/')) or any(c in entry for c in '\\*?[]'):
                raise ValueError('expected literal relative exclusion')

    def scope(value, code=False):
        table(value, ['documents', 'assets', 'sync'] + (['code'] if code else []))
        for key, item in value.items():
            if key == 'sync': sync(item)
            else: path_value(item)

    roots = data.get('roots', {})
    table(roots, ['code', 'documents', 'assets'])
    for value in roots.values(): path_value(value)
    for kind in ['projects', 'groups']:
        entries = data.get(kind, {})
        if not isinstance(entries, dict): raise ValueError('expected scope table')
        for key, value in entries.items():
            identifier(key)
            scope(value, kind == 'projects')
    for kind in ['common', 'knowledge']:
        scope(data.get(kind, {}))
    documents = data.get('documents', {})
    table(documents, ['sync'])
    if 'sync' in documents: sync(documents['sync'])
    return data


def load(path):
    # Caller distinguishes explicitly missing config from an absent optional default.
    return validate(tomllib.loads(Path(path).expanduser().read_text()))
