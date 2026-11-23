"""Explicit isolated official-tool preparation; no host activation or vendoring.

Adapts the previous own setup_dev_tools/setup_git_guard glue. npm, uv, official
release archives and the Playwright browser installer retain installation work.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import tarfile
import tomllib
import urllib.request

PIN_FILES = ('dev-tools.toml','security-tools.toml','secret-tools.toml')
MAX_ARCHIVE = 256 * 1024 * 1024


class ToolError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_root():
    return Path(__file__).resolve().parents[3]


def pins(root,kind='development'):
    root=Path(root).resolve(strict=True)
    configs={};hashes=[]
    needed=PIN_FILES[:2] if kind=='development' else PIN_FILES[2:]
    for name in needed:
        p=root/'common/base/scripts'/name
        if p.is_symlink() or not p.is_file():raise ToolError('pin file is not regular')
        data=p.read_bytes();configs[name]=tomllib.loads(data.decode())
        hashes.append({'path':name,'sha256':digest(data)})
    if kind=='development':
        dev,security=(configs[name] for name in PIN_FILES[:2])
        values={'development':dev,'security':security}
        versions=[dev['context7']['version'],dev['playwright']['cli'],dev['playwright']['engine'],
                  dev['playwright']['python'],security['semgrep']['version'],security['trivy']['version'],
                  dev['runtime']['node_minimum'],dev['runtime']['python_minimum']]
        checksums=[security['trivy']['linux_x86_64_sha256']]
    else:
        secret=configs['secret-tools.toml'];values={'secret':secret}
        versions=[secret['gitleaks']['version']];checksums=[secret['gitleaks']['linux_x64_sha256']]
    if any(not isinstance(v,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+(?:-[0-9A-Za-z.-]+)?',v) for v in versions):
        raise ToolError('invalid pinned version')
    for value in checksums:
        if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value):raise ToolError('invalid archive checksum')
    return values,hashes


def release(kind,config):
    if kind=='gitleaks':
        c=config['secret']['gitleaks'];v=c['version']
        return f'https://github.com/gitleaks/gitleaks/releases/download/v{v}/gitleaks_{v}_linux_x64.tar.gz',c['linux_x64_sha256'],'gitleaks'
    c=config['security']['trivy'];v=c['version']
    return f'https://github.com/aquasecurity/trivy/releases/download/v{v}/trivy_{v}_Linux-64bit.tar.gz',c['linux_x86_64_sha256'],'trivy'


def executable(path):
    path=Path(path)
    if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK):
        raise ToolError('explicit existing absolute executable required')
    path=path.resolve(strict=True)
    return {'path':str(path),'sha256':digest(path.read_bytes())}


def plan(kind,prefix,root=None,node=None,npm=None,uv=None,python=None):
    if kind not in ('development','gitleaks'):raise ToolError('unsupported tool group')
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):
        raise ToolError('preparation currently supports Linux x86_64 only')
    prefix=Path(prefix);root=Path(root or source_root()).resolve(strict=True)
    if not prefix.is_absolute() or prefix.resolve()!=prefix or not prefix.parent.is_dir():
        raise ToolError('new absolute canonical prefix with an existing parent required')
    if prefix.exists() or prefix.is_symlink():raise ToolError('existing prefix is never overwritten; use status')
    if prefix==root or prefix.is_relative_to(root):raise ToolError('official installation must be outside kit source')
    config,hashes=pins(root,kind)
    prerequisites={'python':executable(python or sys.executable)}
    if kind=='gitleaks' and any((node,npm,uv)):
        raise ToolError('Gitleaks-only preparation does not accept development prerequisites')
    if kind=='development':
        if not all((node,npm,uv)):raise ToolError('development requires explicit node, npm and uv executables')
        prerequisites.update({name:executable(p) for name,p in [('node',node),('npm',npm),('uv',uv)]})
    url,sha,member=release(kind,config)
    return {'schema_version':1,'kind':kind,'prefix':str(prefix),'source_root':str(root),
            'pins':config,'pin_hashes':hashes,'prerequisites':prerequisites,
            'implementation_sha256':digest(Path(__file__).read_bytes()),
            'release':{'url':url,'sha256':sha,'member':member},
            'effects':(['official npm/PyPI packages, Chromium and Trivy release'] if kind=='development' else
                       ['official Gitleaks release'])+['new prefix only; no hooks, shell profile, provider registration or services']}


def plan_id(report):
    return digest(json.dumps(report,sort_keys=True,separators=(',',':')).encode())


def public(report):
    return report | {'plan_id':plan_id(report)}


def environment(prefix,prerequisites=None):
    prefix=Path(prefix)
    paths=[str(prefix/'bin')]
    if prerequisites and 'node' in prerequisites:paths.append(str(Path(prerequisites['node']['path']).parent))
    paths.extend(['/usr/local/bin','/usr/bin','/bin'])
    # No inherited credentials, proxy/registry/config overrides or host profiles.
    return {'PATH':os.pathsep.join(paths),'LANG':'C.UTF-8','CI':'1','PYTHONDONTWRITEBYTECODE':'1',
            'TMPDIR':str(prefix/'tmp'),'XDG_CACHE_HOME':str(prefix/'cache'),
            'XDG_CONFIG_HOME':str(prefix/'state/config'),'XDG_STATE_HOME':str(prefix/'state'),
            'npm_config_cache':str(prefix/'npm-cache'),'UV_CACHE_DIR':str(prefix/'uv-cache'),
            'UV_PYTHON_DOWNLOADS':'never','UV_KEYRING_PROVIDER':'disabled',
            'NETRC':str(prefix/'empty.netrc'),
            'PLAYWRIGHT_BROWSERS_PATH':str(prefix/'browsers'),
            'SEMGREP_SETTINGS_FILE':str(prefix/'state/semgrep-settings.yml'),
            'SEMGREP_LOG_FILE':str(prefix/'state/semgrep.log'),
            'SEMGREP_ENABLE_VERSION_CHECK':'0','SEMGREP_SEND_METRICS':'off',
            'TRIVY_CACHE_DIR':str(prefix/'trivy-cache'),'CONTEXT7_API_KEY':''}


def write_environment(prefix):
    values=environment(prefix)
    # Explicit source only; preserve the user's PATH, never change startup files.
    text='# Apply explicitly in the selected shell; no automatic host activation.\n'
    for key in ('PLAYWRIGHT_BROWSERS_PATH','SEMGREP_SETTINGS_FILE','SEMGREP_LOG_FILE',
                'SEMGREP_ENABLE_VERSION_CHECK','SEMGREP_SEND_METRICS','TRIVY_CACHE_DIR'):
        text+=f'export {key}={shlex.quote(values[key])}\n'
    text+=f'export TR_DEVTOOLS_ROOT={shlex.quote(str(prefix))}\n'
    text+=f'export PATH={shlex.quote(str(prefix/"bin"))}:"$PATH"\n'
    (prefix/'env.sh').write_text(text)


def run(args,prefix,env,expected=(0,),timeout=180):
    result=subprocess.run([str(a) for a in args],cwd=prefix,env=env,stdin=subprocess.DEVNULL,
                          capture_output=True,timeout=timeout)
    if result.returncode not in expected:raise ToolError('official tool command failed; partial prefix retained')
    return result.stdout


def download(url):
    with urllib.request.urlopen(url,timeout=60) as response:
        data=response.read(MAX_ARCHIVE+1)
    if len(data)>MAX_ARCHIVE:raise ToolError('archive exceeds download limit')
    return data


def install_release(report,prefix,env):
    release=report['release'];data=download(release['url'])
    if digest(data)!=release['sha256']:raise ToolError('official archive checksum mismatch')
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        members=[m for m in archive.getmembers() if m.name==release['member']]
        if len(members)!=1 or not members[0].isfile() or not 0<members[0].size<=MAX_ARCHIVE:
            raise ToolError('expected exactly one regular executable archive member')
        with archive.extractfile(members[0]) as stream:binary=stream.read(MAX_ARCHIVE+1)
    if not 0<len(binary)<=MAX_ARCHIVE:raise ToolError('invalid executable archive size')
    target=prefix/'bin'/release['member'];target.write_bytes(binary);target.chmod(0o755)
    observed=run([target,'version' if release['member']=='gitleaks' else '--version'],prefix,env).decode().strip()
    version=(report['pins']['secret']['gitleaks'] if report['kind']=='gitleaks' else report['pins']['security']['trivy'])['version']
    pattern=(r'v?'+re.escape(version) if report['kind']=='gitleaks' else r'Version: v?'+re.escape(version))
    if not observed or not re.fullmatch(pattern,observed.splitlines()[0]):
        raise ToolError('release executable version mismatch')
    return {'version':version,'url':release['url'],'archive_sha256':release['sha256'],
            'binary_sha256':digest(binary)}


def semver(value):
    match=re.fullmatch(r'v?([0-9]+(?:\.[0-9]+)+)',value.strip())
    if not match:raise ToolError('unexpected runtime version output')
    return tuple(map(int,match[1].split('.')))


def prepare_development(report,prefix,env):
    config=report['pins'];dev=config['development'];commands=report['prerequisites']
    node,npm,uv,python=(commands[n]['path'] for n in ('node','npm','uv','python'))
    node_version=run([node,'--version'],prefix,env).decode().strip()
    python_version=run([python,'-c','import platform; print(platform.python_version())'],prefix,env).decode().strip()
    if semver(node_version)<semver(dev['runtime']['node_minimum']) or semver(python_version)<semver(dev['runtime']['python_minimum']):
        raise ToolError('selected runtime below declared minimum')
    observed={'node':node_version,'python':python_version,
              'npm':run([npm,'--version'],prefix,env).decode().strip(),
              'uv':run([uv,'--version'],prefix,env).decode().strip()}
    node_root=prefix/'node';node_root.mkdir()
    (node_root/'package.json').write_text(json.dumps({'name':'tr-development-tools','version':'0.0.0',
        'private':True,'dependencies':{'ctx7':dev['context7']['version'],'@playwright/cli':dev['playwright']['cli']}},indent=2)+'\n')
    for name in ('empty.npmrc','empty-global.npmrc'):(prefix/name).write_text('')
    run([npm,'install','--prefix',node_root,'--ignore-scripts','--no-audit','--no-fund',
         '--registry=https://registry.npmjs.org','--userconfig',prefix/'empty.npmrc',
         '--globalconfig',prefix/'empty-global.npmrc'],prefix,env,timeout=600)
    packages={'ctx7':dev['context7']['version'],'@playwright/cli':dev['playwright']['cli'],
              'playwright':dev['playwright']['engine']}
    for name,version in packages.items():
        if json.loads((node_root/'node_modules'/name/'package.json').read_text())['version']!=version:
            raise ToolError('npm package/Playwright engine pin drift')
    venv=prefix/'python'
    run([uv,'--no-config','--no-managed-python','--no-python-downloads','venv','--python',python,venv],prefix,env)
    vpython=venv/'bin/python'
    run([uv,'--no-config','--no-python-downloads','pip','install','--python',vpython,
         '--default-index','https://pypi.org/simple','--keyring-provider','disabled','--only-binary',':all:',
         f"semgrep=={config['security']['semgrep']['version']}",f"playwright=={dev['playwright']['python']}"],prefix,env,timeout=600)
    packages=json.loads(run([vpython,'-c','import importlib.metadata,json; print(json.dumps('
        '{n:importlib.metadata.version(n) for n in ("semgrep","playwright")}))'],prefix,env))
    if packages!={'semgrep':config['security']['semgrep']['version'],'playwright':dev['playwright']['python']}:
        raise ToolError('installed Python package pin drift')
    frozen=run([uv,'--no-config','pip','freeze','--python',vpython],prefix,env)
    (prefix/'python-freeze.txt').write_bytes(frozen)
    run([vpython,'-m','playwright','install','chromium'],prefix,env,timeout=600)
    browser=run([vpython,'-c','from playwright.sync_api import sync_playwright; '
        'p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()'],prefix,env).decode().strip()
    browser=Path(browser)
    if not browser.is_absolute() or not browser.resolve().is_relative_to(prefix/'browsers') or not browser.is_file():
        raise ToolError('expected isolated installed Chromium executable')
    (prefix/'playwright.json').write_text(json.dumps({'browser':{'browserName':'chromium',
        'launchOptions':{'executablePath':str(browser),'headless':True}}},indent=2)+'\n')
    for name,target in {'ctx7':node_root/'node_modules/.bin/ctx7',
                        'playwright-cli':node_root/'node_modules/.bin/playwright-cli',
                        'semgrep':venv/'bin/semgrep'}.items():
        if not target.is_file() or not target.resolve().is_relative_to(prefix):raise ToolError('installed CLI entry missing or outside prefix')
        (prefix/'bin'/name).symlink_to(target)
    write_environment(prefix)
    return observed | {'browser':str(browser),'playwright_engine':dev['playwright']['engine']}


def artifact(prefix,name):
    p=prefix/name
    if not p.is_file() or not p.resolve().is_relative_to(prefix):raise ToolError('receipt artifact is missing or outside prefix')
    return {'path':name,'sha256':digest(p.read_bytes()),'target':str(p.resolve().relative_to(prefix)),
            'mode':p.stat().st_mode & 0o777}


def artifact_names(report,receipt):
    names=['bin/'+report['release']['member']]
    if report['kind']=='development':
        prefix=Path(report['prefix']);browser=Path(receipt['observed']['browser'])
        if not browser.is_absolute() or not browser.resolve().is_relative_to(prefix/'browsers'):
            raise ToolError('receipt browser outside isolated browser directory')
        names+=['bin/ctx7','bin/playwright-cli','bin/semgrep','node/package.json','node/package-lock.json',
                'node/node_modules/ctx7/package.json','node/node_modules/@playwright/cli/package.json',
                'node/node_modules/playwright/package.json','python-freeze.txt','playwright.json','env.sh',
                str(browser.relative_to(prefix))]
    return names


def receipt_write(prefix,receipt):
    temporary=prefix/'provisioned.json.new'
    with temporary.open('x') as stream:
        temporary.chmod(0o600);json.dump(receipt,stream,indent=2);stream.write('\n')
    os.replace(temporary,prefix/'provisioned.json')


def apply(report,expected_plan):
    if plan_id(report)!=expected_plan:raise ToolError('reviewed preparation plan changed')
    fresh=plan(report['kind'],Path(report['prefix']),Path(report['source_root']),
               **{name:Path(info['path']) for name,info in report['prerequisites'].items()})
    if fresh!=report:raise ToolError('preparation inputs changed; no overwrite')
    prefix=Path(report['prefix']);prefix.mkdir(mode=0o700)
    receipt={'schema_version':1,'phase':'installing','plan':report,'artifacts':[],
             'scope':'isolated official tools; no host activation or enrollment'}
    try:
        receipt_write(prefix,receipt)
        for name in ('bin','state','state/config','cache','tmp'):(prefix/name).mkdir(mode=0o700,parents=True,exist_ok=True)
        (prefix/'empty.netrc').write_text('')
        env=environment(prefix,report['prerequisites'])
        if report['kind']=='development':receipt['observed']=prepare_development(report,prefix,env)
        receipt.update(install_release(report,prefix,env))
        receipt['artifacts']=[artifact(prefix,name) for name in artifact_names(report,receipt)]
        receipt['phase']='ready';receipt_write(prefix,receipt)
    except BaseException:
        receipt['phase']='failed'
        try:receipt_write(prefix,receipt)
        except OSError:pass
        raise
    return {'status':'ready','prefix':str(prefix),'kind':report['kind'],
            'activation':'none','semantic_verification':'not run'}


def status(prefix,root=None):
    prefix=Path(prefix)
    if not prefix.is_absolute() or prefix.resolve()!=prefix or (prefix/'provisioned.json').is_symlink():
        raise ToolError('invalid explicit receipt path')
    receipt=json.loads((prefix/'provisioned.json').read_text())
    if receipt.get('schema_version')!=1 or not isinstance(receipt.get('plan'),dict):
        raise ToolError('unrecognized legacy/unmanaged receipt; no adoption or overwrite')
    report=receipt['plan']
    if report.get('prefix')!=str(prefix) or report.get('kind') not in ('development','gitleaks'):
        raise ToolError('receipt identity mismatch')
    config,hashes=pins(root or Path(report['source_root']),report['kind'])
    if report['pin_hashes']!=hashes or report['pins']!=config:return {'status':'pin-drift','kind':report['kind']}
    if receipt.get('phase')!='ready':return {'status':receipt.get('phase','unavailable'),'kind':report['kind'],'recovery':'retain prefix; plan a new explicit prefix'}
    if not isinstance(receipt.get('artifacts'),list) or not receipt['artifacts']:
        raise ToolError('missing installed artifact receipt')
    names=[item['path'] for item in receipt['artifacts']]
    if sorted(names)!=sorted(artifact_names(report,receipt)):
        raise ToolError('installed artifact receipt inventory incomplete or unexpected')
    for item in receipt['artifacts']:
        name=item['path']
        if not isinstance(name,str) or Path(name).is_absolute() or any(p in ('','..','.') for p in name.split('/')):
            raise ToolError('invalid receipt artifact path')
        if artifact(prefix,name)!=item:return {'status':'conflict','kind':report['kind']}
    return {'status':'ready','kind':report['kind'],'semantic_verification':'not run'}


def setup_cli(kind):
    p=argparse.ArgumentParser(description='Explicit plan/apply/status; no hooks or host activation')
    p.add_argument('action',choices=['plan','apply','status']);p.add_argument('--prefix',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=source_root());p.add_argument('--expect-plan')
    for name in ('node','npm','uv','python'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    try:
        if a.action=='status':
            if any((a.node,a.npm,a.uv,a.python,a.expect_plan)):p.error('status accepts only prefix/source-root')
            result=status(a.prefix,a.source_root)
        else:
            report=plan(kind,a.prefix,a.source_root,a.node,a.npm,a.uv,a.python)
            if a.action=='apply' and not a.expect_plan:p.error('apply requires reviewed --expect-plan')
            result=apply(report,a.expect_plan) if a.action=='apply' else public(report)
        print(json.dumps(result,indent=2));return 0 if result.get('status','ready')=='ready' else 2
    except ToolError as error:
        print(json.dumps({'status':'unavailable','reason':str(error)}));return 2
    except (OSError,ValueError,KeyError,TypeError,tarfile.TarError,subprocess.SubprocessError):
        print(json.dumps({'status':'unavailable','reason':'preparation failed; partial prefix retained if created'}));return 2
