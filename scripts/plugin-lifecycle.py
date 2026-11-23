#!/usr/bin/env python3
"""Official plugin CLI glue in an explicitly isolated prefix, never host install."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from package import verify,encoded,digest


def canonical(path):
    p=Path(path)
    if not p.is_absolute() or p.resolve()!=p or p.is_symlink():raise ValueError('canonical absolute path required')
    return p


def read_state(prefix):
    path=prefix/'lifecycle.json'
    if path.is_symlink():raise ValueError('regular receipt required')
    return json.loads(path.read_bytes()) if path.is_file() else None


def commands(product,cli,action,package,*,name=None):
    name=name or f'tr-{product}';selector=name+'@'+name
    remove=[str(cli),'plugin','remove' if product=='codex' else 'uninstall',selector]
    if product=='claude':remove+=['--scope','user','--keep-data']
    remove+=['--json']
    install=[str(cli),'plugin','add' if product=='codex' else 'install',selector]
    if product=='claude':install+=['--scope','user']
    install+=['--json']
    remove_market=[str(cli),'plugin','marketplace','remove',name,'--json']
    add_market=[str(cli),'plugin','marketplace','add',str(package),'--json']
    return ([remove,remove_market] if action!='install' else [])+([] if action=='remove' else [add_market,install])


def plan(action,package,product,prefix,cli,*,expected_name=None):
    prefix=canonical(prefix);package=canonical(package);cli=canonical(cli)
    if not cli.is_file() or not os.access(cli,os.X_OK):raise ValueError('explicit native CLI required')
    if not prefix.parent.is_dir() or prefix==package or prefix.is_relative_to(package) or package.is_relative_to(prefix):
        raise ValueError('separate isolated prefix required')
    release=verify(package,product,scan=False,expected_name=expected_name);state=read_state(prefix)
    name=release['name']
    if state:
        for folder in ('home','codex','claude','config','cache'):
            path=prefix/folder
            if path.is_symlink() or not path.is_dir():raise ValueError('isolated config directory changed')
    if action=='install':
        if prefix.exists():raise ValueError('install requires a new isolated prefix')
    else:
        if not state or state.get('schema_version')!=1 or state.get('product')!=product or state.get('phase')!='installed':
            raise ValueError('no managed installed state; partial state needs inspection')
        current=state['current'];actual=verify(Path(current['package']),product,scan=False,expected_name=name)
        if actual['package_sha256']!=current['sha256']:raise ValueError('previous package drift')
        if action=='remove' and release['package_sha256']!=current['sha256']:raise ValueError('remove must name the installed release')
        if action=='rollback' and (not state.get('previous') or state['previous']['sha256']!=release['package_sha256']):
            raise ValueError('rollback must select the retained previous package')
        if action=='update' and release['package_sha256']==current['sha256']:raise ValueError('already installed; no update')
    value={'schema_version':1,'action':action,'product':product,'name':name,'prefix':str(prefix),'package':str(package),
           'package_sha256':release['package_sha256'],'cli':str(cli),'cli_sha256':digest(cli.read_bytes()),
           'state_sha256':digest(encoded(state)),'version':release['version'],
           'implementation_sha256':digest(Path(__file__).read_bytes()),
           'validator_sha256':digest(Path(__file__).with_name('package.py').read_bytes()),
           'scan':'not executed in plan; mandatory fresh Gitleaks before apply',
           'commands':commands(product,cli,action,package,name=name),
           'removal_verification':[str(cli),'plugin','list','--json'] if action=='remove' else None,
           'effects':'Only isolated home/config and native cache; no trust approval, data/worker/timer changes or host installation.'}
    value['plan_id']=digest(encoded(value));return value


def isolated_environment(prefix):
    # Product variables retain their documented purpose in this test subprocess.
    return {'HOME':str(prefix/'home'),'CODEX_HOME':str(prefix/'codex'),'CLAUDE_CONFIG_DIR':str(prefix/'claude'),
            'XDG_CONFIG_HOME':str(prefix/'config'),'XDG_CACHE_HOME':str(prefix/'cache'),
            'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1',
            'DISABLE_AUTOUPDATER':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}


def cached_payload(prefix,product,release):
    base=prefix/('codex' if product=='codex' else 'claude')/'plugins/cache'
    directory='.codex-plugin' if product=='codex' else '.claude-plugin'
    candidates=[]
    for p in base.glob(f'**/{directory}/plugin.json'):
        if p.is_symlink() or p.resolve()!=p:raise ValueError('native cache link unsupported')
        doc=json.loads(p.read_text())
        if doc.get('name')==release['name'] and doc.get('version')==release['version']:candidates.append(p.parent.parent)
    if len(candidates)!=1:raise ValueError('native cache identity not uniquely verified')
    source=Path(release['payload']);cache=candidates[0]
    expected={str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()}
    import assemble
    assemble.output_bytes(cache,expected);return str(cache)


def write_state(prefix,state):
    path=prefix/'lifecycle.json';temp=prefix/'lifecycle.new'
    with temp.open('xb') as f:f.write(encoded(state))
    os.replace(temp,path)


def uninstall_status(prefix,product,cli,name,cli_sha256):
    """Verify registration absence; native managers may retain version caches."""
    if digest(Path(cli).read_bytes())!=cli_sha256:raise ValueError('native CLI changed before verification')
    result=subprocess.run([str(cli),'plugin','list','--json'],cwd=prefix/'home',env=isolated_environment(prefix),
                          stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    if result.returncode or len(result.stdout)>2_000_000:raise ValueError('native removal status unavailable')
    doc=json.loads(result.stdout)
    if product=='codex':
        if not isinstance(doc,dict) or not isinstance(doc.get('installed'),list):raise ValueError('invalid native installed list')
        entries=doc['installed'];key='pluginId'
    elif product=='claude':
        if not isinstance(doc,list):raise ValueError('invalid native installed list')
        entries=doc;key='id'
    else:raise ValueError('unsupported native product')
    if len(entries)>1024 or any(not isinstance(row,dict) or not isinstance(row.get(key),str) or '@' not in row[key] for row in entries):
        raise ValueError('invalid native installed identity')
    ids=sorted(row[key] for row in entries)
    if name+'@'+name in ids:raise ValueError('native plugin remains registered')
    cache=prefix/('codex' if product=='codex' else 'claude')/'plugins/cache'/name
    retained=cache.is_symlink() or (cache.is_dir() and any(p.is_symlink() or not p.is_dir() for p in cache.rglob('*')))
    return {'native_uninstalled':True,'installed_plugin_ids':ids,'cache_retained':retained,
            'limits':'Registration absence verified; retained cache/data and existing session contexts are not erased.'}


def apply(value,expect_plan):
    fresh=plan(value['action'],value['package'],value['product'],value['prefix'],value['cli'],expected_name=value['name'])
    if fresh!=value or expect_plan!=fresh['plan_id']:raise ValueError('reviewed plan changed')
    checked=verify(Path(value['package']),value['product'],expected_name=value['name'])
    if checked['package_sha256']!=value['package_sha256']:raise ValueError('release changed before apply')
    prefix=Path(value['prefix']);previous=read_state(prefix)
    if not previous:
        prefix.mkdir(mode=0o700)
        for name in ('home','codex','claude','config','cache'):(prefix/name).mkdir(mode=0o700)
    lock=prefix/'.operation.lock'
    with lock.open('x'):pass
    try:
        if digest(encoded(read_state(prefix)))!=value['state_sha256']:raise ValueError('concurrent receipt change')
        state={'schema_version':1,'product':value['product'],'phase':'partial','action':value['action'],
               'completed_steps':0,'current':None,'previous':previous.get('current') if previous else None}
        write_state(prefix,state)
        for i,command in enumerate(value['commands']):
            if digest(Path(value['cli']).read_bytes())!=value['cli_sha256']:raise ValueError('native CLI changed during operation')
            if verify(Path(value['package']),value['product'],scan=False,expected_name=value['name'])['package_sha256']!=value['package_sha256']:
                raise ValueError('release changed during native operation')
            r=subprocess.run(command,cwd=prefix/'home',env=isolated_environment(prefix),stdin=subprocess.DEVNULL,
                             capture_output=True,timeout=60)
            log=prefix/f'native-{value["action"]}-{value["plan_id"][:16]}-{i}.log'
            with log.open('xb') as stream:stream.write(r.stdout+r.stderr)
            if r.returncode:raise ValueError('native operation failed; partial receipt/log retained')
            state['completed_steps']=i+1;write_state(prefix,state)
        if value['action']=='remove':
            state['uninstall_verification']=uninstall_status(prefix,value['product'],value['cli'],value['name'],value['cli_sha256'])
            state['phase']='removed'
        else:
            release=verify(Path(value['package']),value['product'],scan=False,expected_name=value['name'])
            state['cache']=cached_payload(prefix,value['product'],release)
            state['current']={'package':value['package'],'sha256':value['package_sha256'],'version':value['version']}
            state['phase']='installed'
        write_state(prefix,state);return state
    finally:lock.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['install','update','remove','rollback'])
    for name in ('package','prefix','cli'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--product',choices=['codex','claude'],required=True);p.add_argument('--apply',action='store_true');p.add_argument('--expect-plan')
    a=p.parse_args()
    try:
        value=plan(a.action,a.package,a.product,a.prefix,a.cli)
        print(json.dumps(apply(value,a.expect_plan) if a.apply else value,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print('{"status":"unavailable","message":"lifecycle incomplete; inspect retained isolated state, no automatic retry"}');return 2


if __name__=='__main__':raise SystemExit(main())
