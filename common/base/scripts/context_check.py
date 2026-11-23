"""Compare declared instruction reads, never tokens or observed model context.

Reuses the old own context_check's full-file/section/discovery comparison.
Adds source-layout support, canonical interval overlap and explicit raw mode.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


class MeasurementError(ValueError):
    pass


class Reader:
    def __init__(self,root):
        self.root=Path(root).resolve(strict=True)
        if not self.root.is_dir():raise MeasurementError('measurement root must be a directory')
        self.cache={}
        self.aliases={}

    def path(self,name):
        if not isinstance(name,str) or not name or Path(name).is_absolute():
            raise MeasurementError('read path must be nonempty and relative to declared root')
        path=(self.root/name).resolve()
        if not path.is_relative_to(self.root):raise MeasurementError('read escapes declared root')
        if name in self.aliases and self.aliases[name]!=path:raise MeasurementError('declared path changed during comparison')
        self.aliases[name]=path
        return path

    def load(self,path):
        if path not in self.cache:
            self.cache[path]=path.read_bytes()
        return self.cache[path].decode('utf-8')

    def unchanged(self):
        for name,path in self.aliases.items():
            if (self.root/name).resolve()!=path:raise MeasurementError('declared path changed during comparison')
        for path,data in self.cache.items():
            if not path.is_file() or path.read_bytes()!=data:
                raise MeasurementError('measured source changed during comparison')


def headings(text):
    """ATX headings outside fenced code, not a complete Markdown renderer."""
    lines=text.splitlines(keepends=True);found=[];fence=None;offset=0
    # Frontmatter is data, not selectable Markdown headings.
    frontmatter=(bool(lines) and lines[0].strip()=='---')
    for index,line in enumerate(lines):
        raw=line.rstrip('\r\n')
        if frontmatter:
            if index and raw=='---':frontmatter=False
            offset+=len(line);continue
        if fence:
            char,count=fence
            if re.fullmatch(r' {0,3}'+re.escape(char)+'{'+str(count)+r',}[ \t]*',raw):fence=None
            offset+=len(line);continue
        marker=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',raw)
        if marker and (marker[1][0]!='`' or '`' not in marker[2]):
            fence=(marker[1][0],len(marker[1]));offset+=len(line);continue
        match=re.fullmatch(r' {0,3}(#{1,6})(?:[ \t]+(.*?)|[ \t]*)',raw)
        if match:
            title=re.sub(r'[ \t]+#+[ \t]*$','',match[2] or '').strip()
            found.append((offset,len(match[1]),title))
        offset+=len(line)
    return found


def selection(reader,item):
    if not isinstance(item,dict) or not set(item).issubset({'path','section'}) or 'path' not in item:
        raise MeasurementError('read requires path and optional section only')
    path=reader.path(item['path']);text=reader.load(path);start,end=0,len(text)
    if 'section' in item:
        section=item['section']
        if not isinstance(section,str) or not section.strip():raise MeasurementError('section must be nonempty')
        if path.name.upper()=='SKILL.MD':raise MeasurementError('SKILL.md must be counted in full')
        entries=headings(text);selected=[h for h in entries if h[2]==section]
        if len(selected)!=1:raise MeasurementError('missing or ambiguous section: '+item['path']+': '+section)
        start,level,_=selected[0]
        end=next((offset for offset,depth,_ in entries if offset>start and depth<=level),len(text))
    return path,text[start:end],start,end


def read_text(root,item):
    return selection(Reader(root),item)[1]


def merged(intervals):
    result=[]
    for start,end in sorted(intervals):
        if result and start<=result[-1][1]:result[-1]=(result[-1][0],max(end,result[-1][1]))
        else:result.append((start,end))
    return result


def measure(root,reads):
    reader=root if isinstance(root,Reader) else Reader(root)
    if not isinstance(reads,list):raise MeasurementError('reads must be a list')
    coverage={};seen=set();steps=[];chars=duplicates=exact=0
    for item in reads:
        path,text,start,end=selection(reader,item)
        old=coverage.get(path,[]);current=merged(old+[(start,end)])
        unique_added=sum(b-a for a,b in current)-sum(b-a for a,b in old)
        repeated=len(text)-unique_added;key=(path,start,end)
        chars+=len(text);duplicates+=repeated
        if key in seen:exact+=len(text)
        seen.add(key);coverage[path]=current
        steps.append({'path':str(path.relative_to(reader.root)),'section':item.get('section'),
                      'chars':len(text),'duplicate_chars':repeated,'start_char':start,'end_char':end,
                      'source_sha256':hashlib.sha256(reader.cache[path]).hexdigest()})
    reader.unchanged()
    return {'chars':chars,'read_steps':len(reads),'duplicate_chars':duplicates,
            'exact_repeat_chars':exact,'unique_chars':chars-duplicates,'reads':steps}


def discovery(root,directory=None):
    reader=root if isinstance(root,Reader) else Reader(root)
    if directory is None:
        options=[p for p in ('common/base/skills','skills') if reader.path(p).is_dir()]
        if len(options)!=1:raise MeasurementError('select one explicit discovery skill directory')
        directory=options[0]
    base=reader.path(directory)
    if not base.is_dir():raise MeasurementError('discovery skill directory is missing')
    paths=sorted(base.glob('*/SKILL.md'))
    if not paths:raise MeasurementError('discovery has no SKILL.md entries; not a zero-cost result')
    try:import yaml
    except ImportError:raise MeasurementError('PyYAML unavailable; metadata measurement not performed') from None
    total=0
    for path in paths:
        path=reader.path(str(path.relative_to(reader.root)))
        content=reader.load(path)
        match=re.match(r'^---\r?\n(.*?)^---[ \t]*(?:\r?\n|$)',content,re.S|re.M)
        if not match:raise MeasurementError('missing discovery frontmatter')
        try:data=yaml.safe_load(match[1])
        except yaml.YAMLError:raise MeasurementError('invalid discovery YAML; source content withheld') from None
        if (not isinstance(data,dict) or any(not isinstance(data.get(k),str) or not data[k].strip()
                                             for k in ('name','description'))):
            raise MeasurementError('discovery name/description must be nonempty strings')
        total+=len(data['name'])+len(data['description'])
    reader.unchanged()
    return {'skills':len(paths),'name_description_chars':total,'directory':directory,
            'scope':'declared directory entries, not native discovery or injected context'}


def text_list(value):
    if not isinstance(value,list) or any(not isinstance(v,str) or not v.strip() for v in value):
        raise MeasurementError('unmeasured entries must be a list of nonempty descriptions')
    return value


def compare(before,after,cases,check_growth=True,before_skills=None,after_skills=None):
    if isinstance(cases,dict):
        if (type(cases.get('schema_version')) is not int or cases.get('schema_version')!=1 or
                not set(cases).issubset({'schema_version','discovery','cases'})):
            raise MeasurementError('unsupported cases schema')
        scope=cases.get('discovery',{})
        if not isinstance(scope,dict) or not set(scope).issubset({'before','after'}):raise MeasurementError('invalid discovery selection')
        if any(not isinstance(v,str) or not v for v in scope.values()):raise MeasurementError('discovery paths must be relative strings')
        # CLI explicit overrides must not silently replace the file's scope.
        if ((before_skills is not None and scope.get('before',before_skills)!=before_skills) or
            (after_skills is not None and scope.get('after',after_skills)!=after_skills)):
            raise MeasurementError('conflicting discovery declarations')
        before_skills=scope.get('before',before_skills);after_skills=scope.get('after',after_skills)
        cases=cases.get('cases')
    if not isinstance(cases,list) or not cases:raise MeasurementError('at least one declared case required')
    old_reader,new_reader=Reader(before),Reader(after);results=[];names=set()
    allowed={'name','before','after','allowed_growth_chars','growth_reason','unmeasured','unmeasured_before','unmeasured_after'}
    for case in cases:
        if not isinstance(case,dict) or not set(case).issubset(allowed):raise MeasurementError('unknown case fields')
        name=case.get('name')
        if not isinstance(name,str) or not name.strip() or name in names:raise MeasurementError('unique nonempty case name required')
        names.add(name)
        old=measure(old_reader,case['before']);new=measure(new_reader,case['after'])
        allowance=case.get('allowed_growth_chars',0);reason=case.get('growth_reason')
        if type(allowance) is not int or allowance<0 or (allowance and (not isinstance(reason,str) or not reason.strip())):
            raise MeasurementError('growth allowance requires a nonnegative integer and reason')
        common=text_list(case.get('unmeasured',[]))
        old_missing=common+text_list(case.get('unmeasured_before',[]))
        new_missing=common+text_list(case.get('unmeasured_after',[]))
        passed=(new['chars']<=old['chars']+allowance and new['duplicate_chars']<=old['duplicate_chars']) if check_growth else None
        results.append({'name':name,'before':old,'after':new,'delta_chars':new['chars']-old['chars'],
            'allowed_growth_chars':allowance,'growth_reason':reason,'unmeasured':common,
            'unmeasured_before':old_missing,'unmeasured_after':new_missing,
            'coverage':'declared reads only; exclusions are not zero measured cost','passed':passed})
    old_meta=discovery(old_reader,before_skills);new_meta=discovery(new_reader,after_skills)
    old_reader.unchanged();new_reader.unchanged()
    passed=(all(c['passed'] for c in results) and new_meta['name_description_chars']<=old_meta['name_description_chars']) if check_growth else None
    return {'schema_version':2,'status':'measured',
            'measurement':'Body: UTF-8 decoded Unicode characters with original line endings. Metadata: YAML-decoded name/description characters. Not tokens or observed runtime reads.',
            'duplicate_definition':'canonical same-file interval rereads, including full/section overlap; not cross-file semantic duplication',
            'before_root':str(old_reader.root),'after_root':str(new_reader.root),
            'before_discovery':old_meta,'after_discovery':new_meta,'cases':results,
            'assessment':'legacy nonincrease comparison' if check_growth else 'not requested (measure only)',
            'passed':passed,'limits':'No required-read completeness, requirement preservation, actual model routing or cost certification.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('before','after','cases'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--before-skills');p.add_argument('--after-skills')
    p.add_argument('--measure-only',action='store_true',help='measure without enforcing legacy nonincrease comparison')
    a=p.parse_args()
    try:
        report=compare(a.before,a.after,json.loads(a.cases.read_text()),not a.measure_only,a.before_skills,a.after_skills)
    except (OSError,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'unavailable','reason':'declared input/section/discovery invalid or unreadable; no successful measurement'}))
        return 2
    print(json.dumps(report,ensure_ascii=False,indent=2));return 1 if report['passed'] is False else 0


if __name__=='__main__':raise SystemExit(main())
