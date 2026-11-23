"""Pinned external Claude-Mem connection/lifecycle glue, never a memory engine.

No discovery, installation, transcript import, SQL, search proxy or worker
autostart. Actual external installation provenance is a separate prerequisite.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request

from provider_links import resolve
import provider_review
from toolchain import executable, environment, semver

# Keep Popen handles while this controller is alive; never discover/adopt others.
_launched = {}

class ConnectionError(ValueError):
    pass


def sha(data):return hashlib.sha256(data).hexdigest()


def root_path():return Path(__file__).resolve().parents[3]


def canonical(value):
    p=Path(value)
    if not p.is_absolute() or p.resolve()!=p or p.is_symlink():raise ConnectionError('explicit canonical absolute path required')
    return p


def plan(root,binding,product):
    root=Path(root).resolve(strict=True);binding=canonical(binding)
    raw=binding.read_bytes();cfg=json.loads(raw)
    required={'schema_version','providers','node','bun','data_dir','state_dir','port','profile'}
    if (not isinstance(cfg,dict) or type(cfg.get('schema_version')) is not int or
            cfg['schema_version'] not in (1,2) or
            set(cfg)-( {'claude_bin'} if cfg['schema_version']==2 else set() )!=(required if cfg['schema_version']==1 else required|{'reviews'}) or
            cfg['profile']!='manual-local-worker'):
        raise ConnectionError('unsupported explicit manual-local-worker binding')
    if type(cfg['port']) is not int or not 1024<=cfg['port']<=65535:raise ConnectionError('explicit unprivileged loopback port required')
    declaration=canonical(cfg['providers'])
    providers=[resolve(root,declaration,product,name,'cli') for name in ('claude-mem-mcp','claude-mem-worker')]
    reviews={}
    if cfg['schema_version']==2:
        if not isinstance(cfg['reviews'],dict) or set(cfg['reviews'])!={'claude-mem-mcp','claude-mem-worker'}:
            raise ConnectionError('explicit installation review for both official entries required')
        for name,path in cfg['reviews'].items():
            path=canonical(path)
            # Missing review blocks new execution, not inspection/owned stop.
            try:review_hash=sha(provider_review.bounded(path))
            except (OSError,ValueError):review_hash=None
            reviews[name]={'path':str(path),'sha256':review_hash}
    mcp,worker=[Path(p['entry']) for p in providers]
    if mcp.name!='mcp-server.cjs' or worker.name!='worker-service.cjs' or mcp.parent!=worker.parent or worker.parent.name!='scripts':
        raise ConnectionError('unsupported official entry layout')
    installation=worker.parent.parent
    pin=tomllib.loads(Path(__file__).with_name('claude-mem.toml').read_text())['upstream']
    meta=installation/'.claude-plugin/plugin.json'
    if meta.is_symlink():raise ConnectionError('plugin metadata must be regular')
    manifest=json.loads(meta.read_bytes())
    if manifest.get('name')!='claude-mem' or manifest.get('version')!=pin['version'] or any(p['version']!=pin['version'] for p in providers):
        raise ConnectionError('external version differs; review before use')
    data,state=canonical(cfg['data_dir']),canonical(cfg['state_dir'])
    if data==state or data.is_relative_to(state) or state.is_relative_to(data):raise ConnectionError('separate data and controller state required')
    for path in (data,state):
        if not path.parent.is_dir() or path==root or path.is_relative_to(root) or path==installation or path.is_relative_to(installation):
            raise ConnectionError('data/state require existing parents outside source and official installation')
    runtimes={name:executable(canonical(cfg[name])) for name in ('node','bun')}
    if 'claude_bin' in cfg:
        directory=canonical(cfg['claude_bin'])
        if not directory.is_dir():raise ConnectionError('explicit Claude CLI directory required')
        # Official npm supplies a `claude` launcher alias. Pin the resolved
        # executable and admit only the explicitly selected directory to PATH.
        runtimes['claude']=executable(directory/'claude')|{'bin_dir':str(directory)}
    identity={'data_dir':str(data),'state_dir':str(state),'port':cfg['port'],'profile':cfg['profile'],
              'installation':str(installation),'version':pin['version'],
              'mcp':str(mcp),'mcp_sha256':providers[0]['sha256'],
              'worker':str(worker),'worker_sha256':providers[1]['sha256'],'runtimes':runtimes}
    connection_id=sha(json.dumps(identity,sort_keys=True).encode())
    report={'schema_version':1,**identity,'connection_id':connection_id,'kit_root':str(root),
            'product':product,'binding':str(binding),'binding_sha256':sha(raw),
            'providers':str(declaration),'reviews':reviews,
            'metadata_sha256':sha(meta.read_bytes()),'implementation_sha256':sha(Path(__file__).read_bytes()),
            'policy_sha256':{name:sha(Path(__file__).with_name(name).read_bytes())
                             for name in ('claude-mem.toml','provider_links.py','provider_review.py','toolchain.py')},
            'limits':'Entry pins/layout/version only. Confirm official install provenance/resources before execution; no native registration certified.',
            'effects':['manual profile disables worker autostart and transcript watchers; existing profiles are not edited',
                       'MCP/start create selected data/controller metadata and official logs/settings',
                       'explicit worker start may initialize/migrate its DB and run upstream background work',
                       'unmanaged existing data/worker is never automatically adopted or stopped']}
    report['plan_id']=sha(json.dumps(report,sort_keys=True).encode())
    return report


def marker(path,identity):
    target=path/'.tr-kit-claude-mem.json'
    if path.exists():
        if not path.is_dir() or target.is_symlink() or not target.is_file():raise ConnectionError('unmanaged data/state; no automatic adoption')
        if json.loads(target.read_text())!={'schema_version':1,'connection_id':identity}:raise ConnectionError('data/state belongs to another connection')
    else:
        path.mkdir(mode=0o700)
        with target.open('x') as stream:
            target.chmod(0o600);json.dump({'schema_version':1,'connection_id':identity},stream)


def prepare_dirs(p):
    for key in ('state_dir','data_dir'):marker(Path(p[key]),p['connection_id'])
    state=Path(p['state_dir'])
    for name in ('tmp','claude','cache','config','state'):
        path=state/name
        if path.is_symlink() or (path.exists() and not path.is_dir()):raise ConnectionError('controller subdirectory is not owned')
        path.mkdir(mode=0o700,exist_ok=True)


def env_for(p):
    state=Path(p['state_dir']);env=environment(state,{'node':p['runtimes']['node']})
    env['PATH']=str(Path(p['runtimes']['bun']['path']).parent)+os.pathsep+env['PATH']
    if 'claude' in p['runtimes']:
        env['PATH']=p['runtimes']['claude']['bin_dir']+os.pathsep+env['PATH']
    env.update(CLAUDE_MEM_DATA_DIR=p['data_dir'],CLAUDE_MEM_WORKER_PORT=str(p['port']),
               CLAUDE_MEM_WORKER_HOST='127.0.0.1',CLAUDE_CONFIG_DIR=str(state/'claude'),
               CLAUDE_PLUGIN_ROOT=p['installation'],PLUGIN_ROOT=p['installation'],
               CLAUDE_MEM_RUNTIME='worker',CLAUDE_MEM_WORKER_AUTOSTART='false',
               CLAUDE_MEM_TRANSCRIPTS_ENABLED='false',CLAUDE_MEM_CODEX_TRANSCRIPT_INGESTION='false')
    # Chroma/cloud/observer feature settings are not silently rewritten here.
    return env


def check_runtimes(p):
    env=env_for(p)
    versions={}
    for name in ('node','bun'):
        r=subprocess.run([p['runtimes'][name]['path'],'--version'],capture_output=True,
                         stdin=subprocess.DEVNULL,timeout=10,env=env)
        value=r.stdout.decode().strip()
        if r.returncode or (name=='node')!=value.startswith('v'):raise ConnectionError('selected runtime identity/version unavailable')
        version=semver(value)
        if name=='node' and not ((version[0]==20 and version>=(20,19,0)) or version>=(22,12,0)):
            raise ConnectionError('unsupported Node version')
        if name=='bun' and version<(1,1,31):raise ConnectionError('unsupported Bun version')
        versions[name]=value
    if 'claude' in p['runtimes']:
        selected=p['runtimes']['claude'];alias=Path(selected['bin_dir'])/'claude'
        if executable(alias)['sha256']!=selected['sha256'] or str(alias.resolve())!=selected['path']:
            raise ConnectionError('selected Claude CLI changed after plan')
        r=subprocess.run([str(alias),'--version'],capture_output=True,stdin=subprocess.DEVNULL,timeout=15,env=env)
        value=r.stdout.decode().strip()
        if r.returncode or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)? \(Claude Code\)',value):
            raise ConnectionError('selected Claude CLI identity unavailable')
        versions['claude']=value
    return versions


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def http(p,endpoint):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:response=opener.open(f'http://127.0.0.1:{p["port"]}'+endpoint,timeout=1)
    except urllib.error.HTTPError as error:response=error
    with response:
        data=response.read(65537)
        if len(data)>65536:raise ConnectionError('health response exceeds inspection limit')
        return response.status,json.loads(data)


def port_open(p):
    with socket.socket() as sock:
        sock.settimeout(.2);return sock.connect_ex(('127.0.0.1',p['port']))==0


def process_identity(pid,worker):
    if sys.platform!='linux' or type(pid) is not int or pid<=0:raise ConnectionError('owned lifecycle currently requires Linux process metadata')
    proc=Path('/proc')/str(pid)
    fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
    if fields[0]=='Z':raise ConnectionError('worker process is a zombie')
    command=(proc/'cmdline').read_bytes();args=command.split(b'\0')
    if os.fsencode(worker) not in args or b'--daemon' not in args:raise ConnectionError('worker process command is not owned')
    return {'pid':pid,'started_ticks':fields[19],'command_sha256':sha(command)}


def receipt(p):
    path=Path(p['state_dir'])/'worker.json'
    if path.is_symlink():raise ConnectionError('receipt must be regular')
    value=json.loads(path.read_text())
    if value.get('connection_id')!=p['connection_id']:raise ConnectionError('worker receipt belongs to another connection')
    return value


def write_receipt(p,value):
    path=Path(p['state_dir'])/'worker.json';temporary=path.with_suffix('.new')
    with temporary.open('x') as stream:
        temporary.chmod(0o600);json.dump(value,stream,indent=2);stream.write('\n')
    os.replace(temporary,path)


def owned(p):
    try:
        r=receipt(p)
        child=_launched.get(r.get('identity',{}).get('pid'))
        if child is not None:child.poll()
        return r.get('phase') in ('starting','running','failed-running') and process_identity(r['identity']['pid'],p['worker'])==r['identity']
    except (OSError,ValueError,KeyError,TypeError,IndexError):return False


def health(p):
    if not port_open(p):return {'status':'absent','owned':owned(p)}
    try:
        code,body=http(p,'/api/health')
        if (code not in (200,503) or not isinstance(body,dict) or body.get('version')!=p['version'] or
                body.get('status') not in ('ok','degraded') or body.get('workerPath')!=p['worker'] or type(body.get('pid')) is not int):
            return {'status':'unverified','owned':False}
        is_owned=owned(p) and receipt(p)['identity']['pid']==body['pid']
        ready_code,ready=http(p,'/api/readiness')
        ready_ok=(body.get('initialized') is True and body.get('mcpReady') is True and ready_code==200 and
                  isinstance(ready,dict) and ready.get('status')=='ready' and ready.get('mcpReady') is True)
        degraded=code==503 or (isinstance(body.get('dependencies'),dict) and body['dependencies'].get('degraded') is True)
        return {'status':('degraded' if degraded else 'ready') if ready_ok else 'warming',
                'owned':is_owned,'pid':body['pid'],'version':body['version']}
    except (OSError,ValueError,TypeError,KeyError):return {'status':'unverified','owned':False}


def acquire(p):
    path=Path(p['state_dir'])/'.operation.lock'
    try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ConnectionError('another lifecycle operation holds this connection lock') from None
    os.close(fd);return path


def start(p,timeout=30):
    require_review(p)
    prepare_dirs(p);lock=acquire(p)
    try:
        current=health(p)
        if current['owned'] and current['status'] in ('ready','degraded'):return current|{'action':'already-running'}
        if current['status']!='absent' or current['owned']:raise ConnectionError('existing listener/process is not adopted or replaced')
        check_runtimes(p)
        state=Path(p['state_dir']);log=state/'worker.log'
        if log.is_symlink() or (log.exists() and not log.is_file()):raise ConnectionError('worker log must be regular')
        with log.open('ab') as output:
            log.chmod(0o600)
            child=subprocess.Popen([p['runtimes']['bun']['path'],p['worker'],'--daemon'],
                cwd=state,env=env_for(p),stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True)
        _launched[child.pid]=child
        identity=None;deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and child.poll() is None:
            try:identity=process_identity(child.pid,p['worker']);break
            except (OSError,ValueError,IndexError):time.sleep(.02)
        if identity is None:
            write_receipt(p,{'connection_id':p['connection_id'],'launched_pid':child.pid,
                             'phase':'unverified-running' if child.poll() is None else 'failed-exited'})
            raise ConnectionError('worker process identity unavailable; launch PID/log retained, no adoption or automatic cleanup')
        record={'connection_id':p['connection_id'],'identity':identity,'phase':'starting'};write_receipt(p,record)
        while time.monotonic()<deadline:
            # The newly launched executable may exec its interpreter before
            # readiness. Bind the final command only for this same PID/birth;
            # never refresh an already running worker's identity this way.
            try:
                latest=process_identity(child.pid,p['worker'])
                if latest['started_ticks']!=identity['started_ticks']:break
                record['identity']=latest;write_receipt(p,record)
            except (OSError,ValueError,IndexError):
                if child.poll() is not None:break
            current=health(p)
            if current['owned'] and current['status'] in ('ready','degraded'):
                record['phase']='running';write_receipt(p,record);return current|{'action':'started'}
            if child.poll() is not None:break
            time.sleep(.1)
        record['phase']='failed-running' if child.poll() is None else 'failed-exited';write_receipt(p,record)
        raise ConnectionError('worker readiness failed; owned receipt/log retained, no foreign cleanup')
    finally:lock.unlink()


def stop(p,timeout=20):
    # Never claim a directory or adopt an existing process during a stop.
    if not owned(p):raise ConnectionError('no live owned worker receipt; stop refused')
    lock=acquire(p)
    try:
        current=health(p)
        if not current['owned']:raise ConnectionError('worker endpoint ownership unverified; stop refused')
        check_runtimes(p)
        r=subprocess.run([p['runtimes']['bun']['path'],p['worker'],'stop'],cwd=p['state_dir'],env=env_for(p),
                         stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if not port_open(p) and not owned(p):
                record=receipt(p);record['phase']='stopped';write_receipt(p,record)
                return {'status':'stopped','upstream_exit_code':r.returncode}
            time.sleep(.1)
        raise ConnectionError('upstream stop did not verify; no force-kill or success claim')
    finally:lock.unlink()


def mcp(p):
    require_review(p)
    prepare_dirs(p);current=health(p)
    if current['status']!='absent' and not current['owned']:raise ConnectionError('MCP endpoint is not the owned connection')
    check_runtimes(p)
    # Exec official stdio server directly. No protocol/DB proxy or tool rewriting.
    os.execve(p['runtimes']['node']['path'],[p['runtimes']['node']['path'],p['mcp']],env_for(p))


def require_review(p):
    # A v1 binding remains inspectable, but is never an execution approval.
    # Stop keeps its existing ownership checks so drift cannot strand a worker.
    if set(p.get('reviews',{}))!={'claude-mem-mcp','claude-mem-worker'}:
        raise ConnectionError('installation review required before official execution')
    for name,record in p['reviews'].items():
        if sha(provider_review.bounded(record['path']))!=record['sha256']:
            raise ConnectionError('installation review changed after lifecycle plan')
        provider_review.verify(p['kit_root'],p['providers'],p['product'],name,'cli',record['path'])


def render(p):
    # Emit inert source fragments only; never edit a native config or register MCP.
    command={'command':str(Path(sys.executable).resolve()),
             'args':[str(Path(p['kit_root'])/'scripts/claude-mem.py'),'mcp',
                     '--root',p['kit_root'],'--binding',p['binding'],'--product',p['product']],
             'env':{'CLAUDE_MEM_WORKER_AUTOSTART':'false'}}
    directory=Path(p['kit_root'])/f'adapters/{p["product"]}/mcp'
    if p['product']=='claude':
        template=(directory/'claude-mem.json.in').read_text()
        return template.replace('{{SERVER_JSON}}',json.dumps({'type':'stdio',**command},indent=2))
    template=(directory/'claude-mem.toml.in').read_text()
    return template.replace('{{COMMAND}}',json.dumps(command['command'])).replace('{{ARGS}}',json.dumps(command['args']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','doctor','health','start','stop','mcp','render'])
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--product',choices=['codex','claude'],required=True);parser.add_argument('--expect-plan')
    a=parser.parse_args()
    try:
        p=plan(a.root,a.binding,a.product)
        if a.action=='render':print(render(p),end='');return 0
        if a.action=='plan':result=p
        elif a.action=='doctor':result={'status':'entry-pinned','version':p['version'],'connection_id':p['connection_id'],'limits':p['limits']}
        elif a.action=='health':result=health(p)
        elif a.action=='mcp':return mcp(p)
        else:
            if a.expect_plan!=p['plan_id']:raise ConnectionError('explicit reviewed lifecycle plan required')
            result=start(p) if a.action=='start' else stop(p)
        print(json.dumps(result,indent=2))
        if a.action=='health' and not (result['status']=='ready' and result['owned']):return 2
        return 0
    except (OSError,ValueError,KeyError,TypeError,IndexError,subprocess.SubprocessError) as error:
        message=str(error) if isinstance(error,ConnectionError) else 'connection inspection/execution unavailable; no automatic fallback'
        print(json.dumps({'status':'unavailable','reason':message}),file=sys.stderr if a.action=='mcp' else sys.stdout)
        return 2


if __name__=='__main__':raise SystemExit(main())
