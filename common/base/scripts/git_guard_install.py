"""Own enrollment glue; official scanner remains external, never bundled.

Reuses the previous own installer's snapshots/chaining concepts. Cooperative
local control is not OS write isolation or protection against a malicious owner.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys

import secret_guard as guard

EVENTS = ('pre-commit', 'pre-push')
MARKER = b'# tr-kit managed git guard v2'
RUNTIME = ('common/base/scripts/secret_guard.py', 'common/base/scripts/secret-tools.toml',
           'common/base/scripts/git_guard_install.py', 'scripts/check-git-secrets.py')


class InstallError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(path):
    if path.is_symlink() or path.resolve() != path.absolute():
        raise InstallError('symlink file is unsupported')
    if not path.exists():
        return None
    if not path.is_file():
        raise InstallError('expected a regular file')
    return {'bytes': base64.b64encode(path.read_bytes()).decode(),
            'mode': stat.S_IMODE(path.stat().st_mode)}


def encoded(data, mode=0o600):
    return {'bytes': base64.b64encode(data).decode(), 'mode': mode}


def save(path, value):
    if value is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.tr-kit-write')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(base64.b64decode(value['bytes'], validate=True))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(value['mode'])
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inspection_env():
    # Enrollment targets the explicit repo, not an invoking hook's Git variables.
    return {k: v for k, v in os.environ.items() if k not in {
        'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
        'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'}}


def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                       timeout=30, env=inspection_env())
    if p.returncode:
        raise InstallError('Git enrollment inspection failed')
    return os.fsdecode(p.stdout).strip()


def context(repo):
    repo = Path(repo)
    if not repo.is_absolute():
        raise InstallError('explicit absolute repository required')
    root = Path(git(repo, 'rev-parse', '--show-toplevel')).resolve(strict=True)
    hooks = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks')).resolve()
    p = subprocess.run(['git', '-C', str(root), 'config', '--show-origin',
                        '--show-scope', '--get-all', 'core.hooksPath'],
                       capture_output=True, timeout=30, env=inspection_env())
    if p.returncode not in (0, 1):
        raise InstallError('Git configuration inspection failed')
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    return {'repository': str(root), 'hooks': str(hooks), 'hooks_config': os.fsdecode(p.stdout),
            'common_dir': str(common)}


def scanner_identity(scanner):
    scanner = guard.verify_scanner(Path(scanner))
    p = subprocess.run([str(scanner), 'version'], capture_output=True, timeout=10)
    import tomllib
    pin = tomllib.loads(Path(guard.__file__).with_name('secret-tools.toml').read_text())['gitleaks']['version']
    if p.returncode or p.stdout.decode().strip().lstrip('v') != pin:
        raise InstallError('scanner executable version does not match pin')
    return digest(scanner.read_bytes())


def wrapper(state, event, python):
    command = [str(python), '-B', '-c',
               'import sys; sys.path.insert(0, ' + repr(str(state/'common/base/scripts')) +
               '); import git_guard_install as m; sys.exit(m.run_hook(' +
               repr(str(state)) + ', ' + repr(event) + ', sys.argv[1:]))']
    return b'#!/bin/sh\n' + MARKER + b'\nexec ' + shlex.join(command).encode() + b' "$@"\n'


def plan(repo, state, scanner, local_only=(), allow_artifacts=(), python=None):
    ctx = context(repo)
    root, hooks = Path(ctx['repository']), Path(ctx['hooks'])
    state = Path(state)
    if (not state.is_absolute() or state.resolve() != state or state.is_symlink() or
            not state.parent.is_dir()):
        raise InstallError('state requires an absolute non-symlink path and an existing parent')
    if any(state == p or state.is_relative_to(p) for p in (root, hooks, Path(ctx['common_dir']))):
        raise InstallError('stable state must be outside worktree, Git directory and hooks')
    if state.exists():
        raise InstallError('state must be new; inspect the existing receipt with status')
    if not hooks.parent.is_dir() or (hooks.exists() and not hooks.is_dir()):
        raise InstallError('hooks parent must exist and hooks must be a directory')
    if (hooks/'.tr-kit-guard.lock').exists():
        raise InstallError('another enrollment operation holds the hooks lock')
    scanner = Path(scanner)
    scanner_hash = scanner_identity(scanner)
    python = Path(python or sys.executable).resolve(strict=True)
    if not python.is_absolute() or not os.access(python, os.X_OK):
        raise InstallError('Python executable unavailable')
    entry = {'path': str(root), 'local_only': list(local_only), 'allow_artifacts': list(allow_artifacts)}
    guard.validate_artifact_policy(root, entry)
    policy = {'schema_version': 1, 'gitleaks': str(scanner), 'scanner_sha256': scanner_hash,
              'repositories': [entry]}
    files = []
    source = Path(__file__).resolve().parents[3]
    for name in RUNTIME:
        snap = snapshot(source/name)
        if snap is None:
            raise InstallError('required own runtime source missing')
        files.append({'path': str(state/name), 'before': None, 'after': snap})
    files.append({'path': str(state/'policy.json'), 'before': None,
                  'after': encoded((json.dumps(policy, indent=2)+'\n').encode())})
    wrappers = []
    for event in EVENTS:
        target = hooks/event
        before = snapshot(target)
        if before and any(word in base64.b64decode(before['bytes']).lower() for word in (
                b'tr-kit managed', b'husky', b'lefthook', b'generated by pre-commit', b'commit-guard.py')):
            raise InstallError('already managed or unsupported hook; no overwrite')
        original = hooks/(event+'.tr-kit-original')
        if original.exists() or original.is_symlink():
            raise InstallError('original hook backup path is occupied')
        if before is not None:
            files.append({'path': str(original), 'before': None, 'after': before})
        wrappers.append({'path': str(target), 'before': before,
                         'after': encoded(wrapper(state,event,python),0o755)})
    files.extend(wrappers)
    return dict(ctx, schema_version=2, state=str(state), scanner=str(scanner),
                scanner_sha256=scanner_hash, python=str(python), hooks_existed=hooks.exists(), files=files)


def plan_id(report):
    return digest(json.dumps(report, sort_keys=True, separators=(',', ':')).encode())


def public(report):
    return {k: report[k] for k in ('schema_version','repository','state','hooks','scanner','scanner_sha256')} | {
        'plan_id': plan_id(report), 'files': [
            {'path':f['path'], 'preserves_original':f['before'] is not None,
             'sha256':digest(base64.b64decode(f['after']['bytes']))} for f in report['files']]}


def write_receipt(state, receipt):
    save(state/'receipt.json', encoded((json.dumps(receipt,indent=2)+'\n').encode()))


def changed_context(report):
    return context(Path(report['repository'])) != {k:report[k] for k in
            ('repository','hooks','hooks_config','common_dir')}


def lock_hooks(hooks):
    path = hooks/'.tr-kit-guard.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise InstallError('another enrollment operation holds the hooks lock') from None
    os.close(fd)
    return path


def restore_installed(receipt, state):
    report = receipt['plan']
    installed = receipt['installed']
    conflicts = [i for i in installed if snapshot(Path(report['files'][i]['path'])) != report['files'][i]['after']]
    if conflicts:
        raise InstallError('recovery conflict; no files changed')
    for i in reversed(installed[:]):
        item = report['files'][i]
        save(Path(item['path']),item['before'])
        installed.remove(i)
        write_receipt(state,receipt)
    for directory in sorted((p for p in state.rglob('*') if p.is_dir() and not p.is_symlink()),
                            key=lambda p:len(p.parts), reverse=True):
        try: directory.rmdir()
        except OSError: pass


def apply(report, expected_plan=None):
    if expected_plan is not None and plan_id(report) != expected_plan:
        raise InstallError('reviewed plan changed; no files changed')
    state, hooks = Path(report['state']),Path(report['hooks'])
    if changed_context(report) or hooks.exists() != report['hooks_existed']:
        raise InstallError('pre-apply hooks configuration/path conflict')
    if scanner_identity(Path(report['scanner'])) != report['scanner_sha256']:
        raise InstallError('pre-apply scanner conflict')
    for item in report['files']:
        if snapshot(Path(item['path'])) != item['before']:
            raise InstallError('pre-apply file conflict')
    state.mkdir(mode=0o700)
    receipt={'plan':report,'phase':'installing','installed':[]}
    lock = None
    try:
        if not hooks.exists(): hooks.mkdir(mode=0o700)
        lock=lock_hooks(hooks)
        if changed_context(report): raise InstallError('pre-apply hooks configuration/path conflict')
        write_receipt(state,receipt)
        for index,item in enumerate(report['files']):
            target=Path(item['path'])
            if snapshot(target) != item['before']: raise InstallError('concurrent file conflict')
            save(target,item['after'])
            receipt['installed'].append(index)
            write_receipt(state,receipt)
        receipt['phase']='active';write_receipt(state,receipt)
    except BaseException:
        try:
            restore_installed(receipt,state)
            receipt['phase']='rolled-back';write_receipt(state,receipt)
        except BaseException:
            receipt['phase']='recovery-required'
            try:write_receipt(state,receipt)
            except OSError:pass
        raise
    finally:
        if lock:lock.unlink()
        if not report['hooks_existed'] and receipt['phase']=='rolled-back':
            try:hooks.rmdir()
            except OSError:pass
    return public(report) | {'status':'active'}


def read_receipt(state):
    state=Path(state)
    if not state.is_absolute() or state.resolve()!=state or (state/'receipt.json').is_symlink():
        raise InstallError('invalid receipt path')
    receipt=json.loads((state/'receipt.json').read_text())
    report=receipt['plan'];hooks=Path(report['hooks'])
    if report.get('schema_version')!=2 or report['state']!=str(state):
        raise InstallError('unsupported receipt')
    expected={str(state/n) for n in (*RUNTIME,'policy.json')} | {str(hooks/e) for e in EVENTS}
    allowed=expected | {str(hooks/(e+'.tr-kit-original')) for e in EVENTS}
    paths=[f['path'] for f in report['files']]
    if not expected.issubset(paths) or not set(paths).issubset(allowed) or len(paths)!=len(set(paths)):
        raise InstallError('invalid receipt file scope')
    if (not isinstance(receipt['installed'],list) or
            any(type(i) is not int or not 0<=i<len(paths) for i in receipt['installed']) or
            len(set(receipt['installed']))!=len(receipt['installed'])):
        raise InstallError('invalid receipt journal')
    return state,receipt


def status(state, rollback=False):
    state,receipt=read_receipt(state);report=receipt['plan'];hooks=Path(report['hooks'])
    if receipt['phase']=='rolled-back':
        return {'status':'rolled-back','repository':report['repository']}
    conflicts=[]
    try:
        if changed_context(report):conflicts.append('hooks configuration/path changed')
        for i in receipt['installed']:
            f=report['files'][i]
            if snapshot(Path(f['path']))!=f['after']:conflicts.append(f['path'])
    except (OSError,ValueError,subprocess.SubprocessError):
        conflicts.append('inspection unavailable')
    if conflicts:
        if rollback:raise InstallError('rollback conflict; no files changed')
        return {'status':'conflict','conflicts':conflicts}
    if not rollback:
        try:
            scanner=guard.verify_scanner(Path(report['scanner']))
            if digest(scanner.read_bytes())!=report['scanner_sha256']:
                raise InstallError('scanner changed')
        except (OSError,ValueError,KeyError,TypeError):
            return {'status':'unavailable','reason':'registered scanner unavailable'}
        return {'status':receipt['phase'],'repository':report['repository']}
    lock=lock_hooks(hooks)
    try:
        if changed_context(report):raise InstallError('rollback hooks conflict')
        restore_installed(receipt,state)
        receipt['phase']='rolled-back';write_receipt(state,receipt)
    except BaseException:
        receipt['phase']='recovery-required';write_receipt(state,receipt)
        raise
    finally:lock.unlink()
    if not report['hooks_existed']:
        try:hooks.rmdir()
        except OSError:pass
    return {'status':'rolled-back','repository':report['repository']}


def run_hook(state,event,argv):
    """Shared hooks preserve unenrolled worktrees and original arguments/stdin."""
    try:
        state,receipt=read_receipt(state);report=receipt['plan']
        if event not in EVENTS or receipt['phase']!='active':raise InstallError('guard not ready')
        p=subprocess.run(['git','rev-parse','--show-toplevel'],capture_output=True,timeout=30)
        if p.returncode:raise InstallError('cannot identify hook repository')
        root=Path(os.fsdecode(p.stdout).strip()).resolve()
        enrolled=str(root)==report['repository']
        payload=sys.stdin.buffer.read() if event=='pre-push' else None
        command=[report['python'],'-B',str(state/'scripts/check-git-secrets.py'),
                 'push' if event=='pre-push' else 'index','--repo',str(root),
                 '--policy',str(state/'policy.json')]
        def inspect():
            return subprocess.run(command,input=payload).returncode
        if enrolled:
            code=inspect()
            if code:return code
        original=Path(report['hooks'])/(event+'.tr-kit-original')
        expected=next((f['after'] for f in report['files'] if f['path']==str(original)),None)
        if snapshot(original)!=expected:raise InstallError('original hook changed')
        if expected is not None and expected['mode'] & 0o111:
            code=subprocess.run([str(original),*argv],input=payload).returncode
            if code:return code
            if enrolled:return inspect()
        return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print('tr-kit: Git guard unavailable; operation blocked',file=sys.stderr)
        return 2
