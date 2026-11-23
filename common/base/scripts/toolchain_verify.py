"""Explicit version/local/network probes; evidence is not host activation."""
import argparse
import http.server
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

import toolchain as tools


def verify(prefix,evidence,root=None,local=False,network_context7=False,network_trivy=False):
    prefix=Path(prefix);root=Path(root or tools.source_root()).resolve(strict=True)
    state=tools.status(prefix,root)
    if state['status']!='ready':raise tools.ToolError('toolchain receipt not ready; no probe performed')
    receipt=json.loads((prefix/'provisioned.json').read_text());kind=receipt['plan']['kind']
    evidence=Path(evidence)
    if (not evidence.is_absolute() or evidence.resolve()!=evidence or not evidence.parent.is_dir() or
            evidence.exists() or evidence.is_symlink() or evidence.is_relative_to(prefix)):
        raise tools.ToolError('new canonical evidence directory outside toolchain required')
    if kind=='gitleaks' and (network_context7 or network_trivy):
        raise tools.ToolError('network development probes do not apply to Gitleaks-only prefix')
    evidence.mkdir(mode=0o700)
    env=tools.environment(evidence,receipt['plan']['prerequisites'])
    env['PATH']=str(prefix/'bin')+os.pathsep+env['PATH']
    env['PLAYWRIGHT_BROWSERS_PATH']=str(prefix/'browsers')
    for name in ('tmp','cache','state','state/config'):(evidence/name).mkdir(mode=0o700,parents=True,exist_ok=True)
    (evidence/'empty.netrc').write_text('')
    checks=[];commands=[];opened=[];server=None;server_thread=None

    def run(args,expected=(0,),timeout=90):
        number=len(commands);command=[str(a) for a in args]
        entry={'args':command,'status':'started'};commands.append(entry)
        try:
            result=subprocess.run(command,cwd=evidence,env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            entry['status']='timeout';raise tools.ToolError('probe timeout; scoped cleanup attempted') from None
        entry.update(status='completed',exit_code=result.returncode)
        for suffix,data in [('stdout',result.stdout),('stderr',result.stderr)]:
            p=evidence/f'{number:02d}.{suffix}';p.write_bytes(data);p.chmod(0o600)
        if result.returncode not in expected:raise tools.ToolError('probe command failed; local evidence retained')
        return result.stdout.decode()

    def pinned(name,version,flag='--version'):
        observed=run([prefix/'bin'/name,flag]).strip()
        if not re.search(r'(?<![A-Za-z0-9_.-])v?'+re.escape(version)+r'(?![A-Za-z0-9_.-])',observed):
            raise tools.ToolError('executable version differs from pin')

    config=receipt['plan']['pins'];dev=config.get('development',{});security=config.get('security',{})
    report={'status':'unavailable','kind':kind,'checks':checks,'commands':commands,
            'evidence':str(evidence),'activation':'none','cleanup_errors':[],
            'unexecuted':[]}
    try:
        versions=({'gitleaks':config['secret']['gitleaks']['version']} if kind=='gitleaks' else
                  {'ctx7':dev['context7']['version'],'playwright-cli':dev['playwright']['cli'],
                   'semgrep':security['semgrep']['version'],'trivy':security['trivy']['version']})
        for name,version in versions.items():pinned(name,version,'version' if name=='gitleaks' else '--version')
        checks.append('pinned executable versions')
        if local and kind=='gitleaks':
            code='''import sys,hashlib
sys.path.insert(0,sys.argv[1])
import secret_guard as g
g.scan([b"safe fixture"],sys.argv[2])
key=b"ghp_"+hashlib.sha256(b"G2 synthetic no real account").hexdigest()[:36].encode()
try:g.scan([key],sys.argv[2])
except g.GuardError as e:
    if not str(e).startswith("secret detected"):raise
else:raise RuntimeError("synthetic secret not detected")
print("clean and redacted synthetic finding verified")
'''
            run([receipt['plan']['prerequisites']['python']['path'],'-B','-c',code,
                 root/'common/base/scripts',prefix/'bin/gitleaks'])
            checks.append('Gitleaks clean and synthetic finding through shared scanner')
        if local and kind=='development':
            source=evidence/'src';source.mkdir()
            unsafe=source/'fixture.py';unsafe.write_text('def parse(value):\n    return eval(value)\n')
            rule=evidence/'rule.yaml';rule.write_text('rules:\n- id: fixture-eval\n  languages: [python]\n'
                '  message: Fixture evaluation\n  severity: ERROR\n  pattern: eval(...)\n')
            for label,value,expected,count in [('finding','eval(value)',(1,),1),('clean','str(value)',(0,),0)]:
                unsafe.write_text(f'def parse(value):\n    return {value}\n')
                result=evidence/f'semgrep-{label}.json'
                run([prefix/'bin/semgrep','scan','--config',rule,'--metrics','off','--error',
                     '--json','--output',result,source],expected=expected)
                parsed=json.loads(result.read_text())
                if parsed.get('errors') or len(parsed['results'])!=count:
                    raise tools.ToolError('Semgrep probe result mismatch')
            checks.append('Semgrep finding and clean fixture, local rule, metrics off')
            python=prefix/'python/bin/python'
            browser_code=r'''from playwright.sync_api import sync_playwright
import sys,json
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=sys.argv[1],headless=True)
    try:
        a=browser.new_context(); b=browser.new_context()
        page=a.new_page(); other=b.new_page()
        html="<button onclick=\"document.querySelector('output').textContent='saved'\">Save</button><output>pending</output>"
        page.set_content(html);other.set_content(html)
        page.get_by_role("button",name="Save").click()
        assert page.locator("output").inner_text()=="saved"
        assert other.locator("output").inner_text()=="pending"
        print(json.dumps({"browser_version":browser.version,"isolated":True}))
    finally:browser.close()
'''
            run([python,'-B','-c',browser_code,receipt['observed']['browser']])
            checks.append('Python Playwright real Chromium click and context isolation')
            page=evidence/'index.html';page.write_text('<!doctype html><title>G2 local probe</title>'
                '<button onclick="document.querySelector(\'output\').textContent=\'saved\'">Save</button><output>pending</output>')
            document=page.read_bytes()
            class FixtureHandler(http.server.BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    if self.path!='/':self.send_error(404);return
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Content-Length',str(len(document)));self.end_headers();self.wfile.write(document)
            # Respect the official CLI's file: restriction. Serve only this
            # synthetic document, not a filesystem directory or user material.
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler)
            server.daemon_threads=True
            server_thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True)
            server_thread.start()
            fixture_url=f'http://127.0.0.1:{server.server_port}/'
            def browser(session,*args):return run([prefix/'bin/playwright-cli','-s='+session,*args])
            sessions=['g2-'+uuid.uuid4().hex[:16] for _ in range(2)]
            for session in sessions:
                opened.append(session)
                browser(session,'open',fixture_url,'--config='+str(prefix/'playwright.json'))
            browser(sessions[0],'click','button')
            for session,word in zip(sessions,['saved','pending']):
                if word not in browser(session,'eval',"document.querySelector('output').textContent"):
                    raise tools.ToolError('Playwright CLI state/isolation probe mismatch')
            screenshot=evidence/'ui.png';browser(sessions[0],'screenshot','--filename='+str(screenshot))
            if not screenshot.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):raise tools.ToolError('invalid screenshot output')
            browser(sessions[0],'close');opened.remove(sessions[0])
            if 'G2 local probe' not in browser(sessions[1],'eval','document.title'):
                raise tools.ToolError('closing one probe affected the other')
            checks.append('Playwright CLI click, screenshot, scoped close and session isolation')
        if network_trivy:
            infra=evidence/'infra';infra.mkdir();(infra/'Dockerfile').write_text('FROM ubuntu:22.04\nUSER root\nRUN echo fixture\n')
            packages=evidence/'packages';packages.mkdir()
            (packages/'package-lock.json').write_text(json.dumps({'name':'fixture','version':'1.0.0','lockfileVersion':2,
                'packages':{'':{'name':'fixture','version':'1.0.0','dependencies':{'lodash':'4.17.15'}},
                            'node_modules/lodash':{'version':'4.17.15'}},'dependencies':{'lodash':{'version':'4.17.15'}}}))
            for mode,target,args,field in [('config',infra,[],'Misconfigurations'),('fs',packages,['--scanners','vuln'],'Vulnerabilities')]:
                output=evidence/f'trivy-{mode}.json'
                run([prefix/'bin/trivy',mode,*args,'--format','json','--output',output,target],timeout=300)
                findings=[f for result in json.loads(output.read_text()).get('Results',[]) for f in result.get(field,[])]
                if mode=='fs':findings=[f for f in findings if f.get('PkgName')=='lodash']
                if not findings:raise tools.ToolError('Trivy probe returned no expected fixture findings')
            checks.append('Trivy IaC checks and live vulnerability DB fixtures')
        elif kind=='development':report['unexecuted'].append('Trivy checks/DB network probe not requested')
        if network_context7:
            library=json.loads(run([prefix/'bin/ctx7','library','react','useEffect cleanup','--json']))
            if not isinstance(library,list) or not any(item.get('id')=='/react/react' and 'v18.2.0' in item.get('versions',[]) for item in library):
                raise tools.ToolError('public Context7 exact fixture version not available')
            parsed=json.loads(run([prefix/'bin/ctx7','docs','/react/react/v18.2.0','use-subscription useSubscription memoize subscribe','--json']))
            if not parsed.get('codeSnippets') or not any('/blob/v18.2.0/' in s.get('codeId','') for s in parsed['codeSnippets']):
                raise tools.ToolError('Context7 exact-version probe mismatch')
            checks.append('Context7 public library and exact-version docs query')
        elif kind=='development':report['unexecuted'].append('Context7 public network query not requested')
        if not local:report['unexecuted'].append('local semantic probes not requested')
        report['status']='pass'
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        report['reason']=str(error) if isinstance(error,tools.ToolError) else 'probe failed; inspect local evidence'
    finally:
        for session in opened:
            try:run([prefix/'bin/playwright-cli','-s='+session,'close'],timeout=30)
            except (OSError,ValueError,subprocess.SubprocessError):report['cleanup_errors'].append(session)
        if server is not None:
            server.shutdown();server.server_close()
            server_thread.join(timeout=5)
            if server_thread.is_alive():report['cleanup_errors'].append('fixture HTTP server')
        if report['cleanup_errors']:report['status']='unavailable'
        p=evidence/'report.json';p.write_text(json.dumps(report,indent=2)+'\n');p.chmod(0o600)
    return {k:v for k,v in report.items() if k!='commands'}


def main():
    p=argparse.ArgumentParser(description='Explicit versions and optional local/network probes')
    p.add_argument('--prefix',required=True,type=Path);p.add_argument('--evidence',required=True,type=Path)
    p.add_argument('--source-root',type=Path,default=tools.source_root())
    p.add_argument('--local',action='store_true');p.add_argument('--network-context7',action='store_true');p.add_argument('--network-trivy',action='store_true')
    a=p.parse_args()
    try:
        report=verify(a.prefix,a.evidence,a.source_root,a.local,a.network_context7,a.network_trivy)
        print(json.dumps(report,indent=2));return 0 if report['status']=='pass' else 2
    except (OSError,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'unavailable','reason':'prefix/evidence prerequisites not satisfied'}));return 2


if __name__=='__main__':raise SystemExit(main())
