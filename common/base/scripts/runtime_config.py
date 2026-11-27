"""Host-local pointers only; no discovery, installation or source-policy bypass."""
import json
import os
from pathlib import Path
import re
import stat


def canonical(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('explicit runtime path required')
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path or path.is_symlink():
        raise ValueError('canonical runtime path required')
    return path


def product_for_root(root):
    return 'claude' if (Path(root) / '.claude-plugin/plugin.json').is_file() else 'codex'


def load(product):
    if product not in ('codex', 'claude'):
        raise ValueError('unsupported runtime product')
    selected = os.environ.get('TR_KIT_RUNTIME_CONFIG')
    path = canonical(selected if selected is not None else
                     str(Path.home()/'.config/tr-kit'/('runtime-'+product+'.json')))
    # Open the selected file once and compare its identity after the read.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                before.st_mode & 0o022 or before.st_size > 1_000_000):
            raise ValueError('runtime config must be bounded, owned and not group/world writable')
        raw = stream.read(1_000_001)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    if len(raw) > 1_000_000 or identity(before) != identity(after) or identity(after) != identity(current):
        raise ValueError('runtime config changed during read')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate runtime key')
            result[key] = value
        return result

    data = json.loads(raw, object_pairs_hook=unique)
    expected = ['product', 'provider_reviews', 'providers', 'schema_version', 'upstream_binding']
    if (not isinstance(data, dict) or sorted(data) != expected or
            type(data['schema_version']) is not int or data['schema_version'] != 1 or
            data['product'] != product):
        raise ValueError('runtime schema/product mismatch')
    for key in ('providers', 'upstream_binding'):
        canonical(data[key])
    reviews = data['provider_reviews']
    if not isinstance(reviews, dict) or not 1 <= len(reviews) <= 128:
        raise ValueError('explicit provider reviews required')
    for key, value in reviews.items():
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,95}', key):
            raise ValueError('invalid runtime provider id')
        canonical(value)
    # Resource/evidence validation belongs to the selected provider's existing
    # verifier. Missing unselected providers must not expand the current request.
    return path, data


def note(path, data):
    return ('\n호스트 runtime 설정: '+str(path)+'\n'
            '현재 제품: '+data['product']+'\n'
            '명시 외부 연결 선언: '+data['providers']+'\n'
            '선택한 외부 연결의 검수 기록은 위 runtime 설정의 provider_reviews[ID]를 사용한다. '
            '선언 경로나 파일 존재는 공식 설치·실행 성공의 증거가 아니다. '
            '선택한 진입 파일과 필수 리소스는 외부 연결 및 설치본 검수 절차를 따른다.\n'
            '원문 보호 binding: '+data['upstream_binding']+'\n'
            '실제 보호 대상은 binding이 참조한 scope의 등록 component/artifact다. '
            'kit 소스가 아닌 프로젝트를 자동 편입하거나 설정을 자동 변경하지 않는다.\n')
