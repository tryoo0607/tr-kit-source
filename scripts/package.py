#!/usr/bin/env python3
"""Own native marketplace packaging; no upstream vendoring or host activation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import assemble


def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def digest(data):return hashlib.sha256(data).hexdigest()


def native_files(root,product,files,options):
    if set(options)!= {'version','profile'}:raise ValueError('explicit version/profile required')
    version,profile=options['version'],options['profile']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?',version):raise ValueError('invalid version')
    if profile not in ('review','guarded'):raise ValueError('unsupported activation profile')
    name=f'tr-{product}';manifest_dir='.codex-plugin' if product=='codex' else '.claude-plugin'
    manifest=json.loads((root/f'adapters/{product}/plugin.json.in').read_text().replace('{{VERSION}}',version))
    if manifest.get('name')!=name or manifest.get('skills')!='./common/base/skills/' or manifest.get('hooks')!='./hooks/hooks.json':
        raise ValueError('unsupported native manifest')
    command='python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/plugin-runtime.py" context --product '+product
    hooks={'SessionStart':[{'hooks':[{'type':'command','command':command,'timeout':5}]}]}
    if profile=='guarded':
        for role in ('secret','upstream'):
            # Reuse each existing renderer's strict template/event validation.
            path=root/f'scripts/render-{role}-hook.py'
            spec=importlib.util.spec_from_file_location('_tr_render_'+role,path)
            renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
            doc=(renderer.render(product,root,Path('/usr/bin/python3')) if role=='secret' else
                 renderer.render(product,root,root,root/'explicit-catalog-required',root/'explicit-scope-required'))
            for event,groups in doc['hooks'].items():
                for group in groups:
                    for handler in group['hooks']:
                        if role=='secret':
                            handler['command']=f'python3 -B "${{CLAUDE_PLUGIN_ROOT}}/adapters/{product}/scripts/secret_guard.py" --event {event}'
                        else:handler['command']=f'python3 -B "${{CLAUDE_PLUGIN_ROOT}}/scripts/plugin-runtime.py" upstream --product {product} --event {event}'
                hooks.setdefault(event,[]).extend(groups)
    for filename in ('LICENSE','NOTICE','SECURITY.md','INSTALL.md'):
        path=root/filename
        if path.is_symlink() or not path.is_file():raise ValueError('own distribution notice missing')
    return wrap_native_files(product,files,manifest,{'hooks':hooks},profile,
        ['native hook trust and new-session verification','official external providers/resources (G7)',
         'upstream binding and pinned Gitleaks for guarded profile'])


def wrap_native_files(product,files,manifest,hooks,profile,requires):
    """Reusable own envelope; callers own identity, hooks and prerequisites."""
    name=manifest.get('name');version=manifest.get('version')
    if product not in ('codex','claude') or not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',name):
        raise ValueError('explicit native identity required')
    if (not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?',version)
            or profile not in ('review','guarded')):raise ValueError('invalid native version/profile')
    if manifest.get('skills')!='./common/base/skills/' or manifest.get('hooks')!='./hooks/hooks.json':
        raise ValueError('unsupported component contract')
    if not isinstance(hooks,dict) or set(hooks)!= {'hooks'} or not isinstance(hooks['hooks'],dict):
        raise ValueError('explicit hook mapping required')
    body=dict(files);body.pop('AGENTS.md' if product=='codex' else 'CLAUDE.md')
    manifest_dir='.codex-plugin' if product=='codex' else '.claude-plugin'
    for reserved in (manifest_dir+'/plugin.json','hooks/hooks.json','installation.json'):
        if reserved in body:raise ValueError('native generated path collision')
    body[manifest_dir+'/plugin.json']=encoded(manifest);body['hooks/hooks.json']=encoded(hooks)
    # Native managers install the payload, without the marketplace assembly.
    body['installation.json']=encoded({'schema_version':1,'product':product,'name':name,'version':version,
        'profile':profile,'files':[{'path':p,'sha256':digest(b)} for p,b in sorted(body.items())]})
    # Preserve paths. Native manifests select the common skill directory directly.
    result={f'plugins/{name}/{path}':data for path,data in body.items()}
    metadata='.agents/plugins' if product=='codex' else '.claude-plugin'
    source={'source':'local','path':f'./plugins/{name}'} if product=='codex' else f'./plugins/{name}'
    market={'name':name,'plugins':[{'name':name,'source':source}]}
    if product=='codex':market['interface']={'displayName':manifest.get('interface',{}).get('displayName',name)}
    else:market['owner']={'name':'tryoo0607'}
    result[metadata+'/marketplace.json']=encoded(market)
    source_hash=digest(encoded({path:digest(data) for path,data in sorted(files.items())}))
    result['release.json']=encoded({'schema_version':1,'product':product,'name':name,'version':version,
        'profile':profile,'source_inventory_sha256':source_hash,'operational_ready':False,
        'requires':requires,
        'mcp_registered':False,'limits':'Own native layout only; no host activation, provenance authentication or official workflow certification.'})
    return result


def verify(path,product,*,scan=True,expected_name=None):
    """Fresh exact inventory; a self-declared hash map is not signature evidence."""
    path=Path(path)
    if expected_name is not None and (not isinstance(expected_name,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',expected_name)):
        raise ValueError('invalid expected native identity')
    if not path.is_absolute() or path.resolve()!=path or path.is_symlink():raise ValueError('canonical release required')
    manifest_path=path/'assembly.json'
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size>2_000_000:
        raise ValueError('regular bounded assembly manifest required')
    record=json.loads(manifest_path.read_bytes())
    if record.get('version')!=1 or record.get('product')!=product or record.get('native_installable') is not True:raise ValueError('not a native package')
    items=record['files'];expected={}
    for item in items:
        rel=item['path'];p=Path(rel)
        if p.is_absolute() or '..' in p.parts or str(p)!=rel or rel in expected or rel=='assembly.json':raise ValueError('invalid release path')
        target=path/p
        if target.is_symlink() or not target.is_file() or target.stat().st_size>2_000_000:raise ValueError('invalid release node')
        data=target.read_bytes()
        if digest(data)!=item['sha256']:raise ValueError('release bytes changed')
        expected[rel]=data
    assembly=(path/'assembly.json').read_bytes();expected['assembly.json']=assembly
    actual=assemble.output_bytes(path,expected)
    release=json.loads(actual['release.json'])
    if release.get('product')!=product or release.get('name')!=(expected_name or f'tr-{product}') or release.get('operational_ready') is not False:
        raise ValueError('release identity/status mismatch')
    if release.get('schema_version')!=1 or release.get('profile') not in ('review','guarded'):raise ValueError('unsupported release contract')
    payload=path/'plugins'/release['name'];manifest_dir='.codex-plugin' if product=='codex' else '.claude-plugin'
    manifest=json.loads((payload/manifest_dir/'plugin.json').read_text())
    if manifest.get('name')!=release['name'] or manifest.get('version')!=release['version']:
        raise ValueError('native identity mismatch')
    for key in ('skills','hooks'):
        relative=manifest[key]
        if not isinstance(relative,str) or not relative.startswith('./') or '..' in Path(relative).parts or not (payload/relative).exists():
            raise ValueError('native component path invalid')
    installed=json.loads((payload/'installation.json').read_bytes())
    if (set(installed)!= {'schema_version','product','name','version','profile','files'} or
        installed['schema_version']!=1 or any(installed[k]!=release[k] for k in ('product','name','version','profile'))):
        raise ValueError('native payload record mismatch')
    payload_files={str(Path(p).relative_to('plugins/'+release['name'])):b for p,b in actual.items()
                   if p.startswith('plugins/'+release['name']+'/')}
    expected_inventory=[{'path':p,'sha256':digest(b)} for p,b in sorted(payload_files.items()) if p!='installation.json']
    if installed['files']!=expected_inventory:raise ValueError('native payload inventory mismatch')
    if scan:assemble.secrets.scan(list(actual.items()),assemble.secrets.trusted_scanner())
    assemble.output_bytes(path,expected)
    return {**release,'package_sha256':digest(encoded({p:digest(b) for p,b in sorted(actual.items())})),
            'files':len(actual),'payload':str(payload),'limits':'Fresh bytes/scan only, not official origin or native readiness.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','verify'])
    p.add_argument('--product',choices=['codex','claude'],required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path);p.add_argument('--version');p.add_argument('--profile',choices=['review','guarded'],default='review')
    for key in ('catalog','scope','providers'):p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    try:
        if a.action=='build':
            if not all((a.root,a.version,a.catalog,a.scope,a.providers)):raise ValueError('explicit build inputs required')
            assemble.build(a.root,a.product,a.output,a.catalog,a.scope,a.providers,native={'version':a.version,'profile':a.profile})
        print(json.dumps(verify(a.output,a.product),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError):
        print('{"status":"unavailable","message":"native package incomplete; preserve partial output for inspection"}');return 2


if __name__=='__main__':raise SystemExit(main())
