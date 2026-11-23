"""Verify explicit external entry points; never install, copy or execute them."""
import hashlib
import json
import re
from pathlib import Path


class LinkError(ValueError):
    pass


def verify(root, declaration, product, *, selected=None):
    root=Path(root).resolve(strict=True)
    declaration=Path(declaration)
    if not declaration.is_file() or declaration.stat().st_size>256_000:raise LinkError('unsupported provider declaration')
    raw=declaration.read_bytes()
    if len(raw)>256_000:raise LinkError('provider declaration too large')
    doc=json.loads(raw)
    if (not isinstance(doc,dict) or sorted(doc)!=['providers','version'] or
            type(doc['version']) is not int or doc['version']!=1 or not isinstance(doc['providers'],list)):
        raise LinkError('invalid provider declaration')
    if product not in ('codex','claude'):raise LinkError('unsupported product')
    if len(doc['providers'])>128:raise LinkError('too many providers')
    results=[];seen=[]
    for entry in doc['providers']:
        keys=['entry','id','kind','products','sha256','source','version']
        if not isinstance(entry,dict) or sorted(entry)!=keys:raise LinkError('invalid provider entry')
        if not isinstance(entry['id'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',entry['id']) or entry['id'] in seen:raise LinkError('duplicate provider id')
        seen.append(entry['id'])
        if entry['kind'] not in ('skill','cli'):raise LinkError('unknown provider interface')
        if (not isinstance(entry['products'],list) or not entry['products'] or
                any(p not in ('codex','claude') for p in entry['products']) or
                len(set(entry['products']))!=len(entry['products'])):raise LinkError('invalid products')
        if any(not isinstance(entry[k],str) or not entry[k] for k in ('entry','sha256','source','version')):
            raise LinkError('missing identity evidence')
        if not re.fullmatch(r'[a-f0-9]{64}',entry['sha256']):raise LinkError('invalid entry pin')
        path=Path(entry['entry'])
        if not path.is_absolute():raise LinkError('absolute external path required')
        # Validate declaration shape/identity for all entries, but inspect bytes
        # only for the requested dependency when resolving one runtime route.
        if selected is not None and entry['id']!=selected:continue
        if product not in entry['products']:
            results.append({**entry,'product_status':'unsupported','limits':'Not selected or inspected for this product.'})
            continue
        path=path.resolve(strict=True)
        if path==root or root in path.parents:raise LinkError('external provider is inside kit')
        if not path.is_file() or path.stat().st_size>64_000_000:raise LinkError('unsupported external entry')
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=entry['sha256']:raise LinkError('provider bytes changed; review before use')
        results.append({'id':entry['id'],'kind':entry['kind'],'entry':str(path),
                        'version':entry['version'],'source':entry['source'],'sha256':actual,
                        'product_status':'entry-pin-verified',
                        'limits':'Pin matches declared entry only; official provenance and runtime use require separate evidence.'})
    return results


def resolve(root, declaration, product, provider_id, kind):
    """Select one explicit provider without executing it or probing other entries."""
    if kind not in ('skill','cli'):raise LinkError('invalid interface request')
    matches=verify(root,declaration,product,selected=provider_id)
    if len(matches)!=1:raise LinkError('selected provider is not uniquely declared')
    entry=matches[0]
    if entry['kind']!=kind:raise LinkError('selected provider interface mismatch')
    if entry['product_status']!='entry-pin-verified':raise LinkError('selected provider unsupported for product')
    if kind=='skill' and Path(entry['entry']).name!='SKILL.md':raise LinkError('skill entry must be SKILL.md')
    return entry


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','declaration'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--product',choices=('codex','claude'),required=True)
    p.add_argument('--id',required=True)
    p.add_argument('--kind',choices=('skill','cli'),required=True)
    a=p.parse_args(argv)
    try:entry=resolve(a.root,a.declaration,a.product,a.id,a.kind)
    except Exception:
        # Do not echo declaration fields, foreign entry content or exceptions.
        print(json.dumps({'status':'unavailable','message':'selected external connection is not verified'}))
        return 2
    print(json.dumps({'status':'entry-pin-verified','id':entry['id'],
                      'kind':entry['kind'],'entry':entry['entry'],'sha256':entry['sha256'],
                      'limits':'Entry pin only. Confirm official installation and runtime support separately.'}))
    return 0


if __name__=='__main__':raise SystemExit(main())
