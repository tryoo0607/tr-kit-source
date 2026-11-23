"""Own glue against synthetic process/stdio fixtures, NOT official runtime proof."""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from unittest import mock

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'common/base/scripts'))
import claude_mem as cm
import provider_review


# Entirely own test doubles. No upstream implementation/resource is embedded.
WORKER=r'''
import http.server,json,os,sys,threading,urllib.request
from pathlib import Path
port=int(os.environ['CLAUDE_MEM_WORKER_PORT'])
mode=Path(__file__).with_name('mode').read_text()
if sys.argv[1]=='stop':
    if mode!='ignore-stop':
        urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%s/api/admin/shutdown'%port,data=b''),timeout=2).close()
    sys.exit(0)
if sys.argv[1]!='--daemon':sys.exit(3)
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path=='/api/health':
            body={'status':'ok','version':'15.2.1','workerPath':str(Path(__file__).resolve()),'pid':os.getpid(),
                  'initialized':True,'mcpReady':mode!='warming','dependencies':{'degraded':mode=='degraded'}}
            code=503 if mode=='degraded' else 200
        else:body={'status':'ready' if mode!='warming' else 'initializing','mcpReady':mode!='warming'};code=200 if mode!='warming' else 503
        raw=json.dumps(body).encode();self.send_response(code);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        self.send_response(200);self.end_headers();threading.Thread(target=self.server.shutdown,daemon=True).start()
server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
server.serve_forever();server.server_close()
'''
MCP=r'''
import json,os,sys
from pathlib import Path
assert os.environ['CLAUDE_MEM_WORKER_AUTOSTART']=='false'
assert os.environ['CLAUDE_MEM_TRANSCRIPTS_ENABLED']=='false'
assert 'G4_TEST_PARENT_SECRET' not in os.environ
Path(os.environ['CLAUDE_MEM_DATA_DIR'],'fixture-start.json').write_text(json.dumps({'cwd':os.getcwd(),'autostart':os.environ['CLAUDE_MEM_WORKER_AUTOSTART']}))
for line in sys.stdin:
    req=json.loads(line)
    if 'id' not in req:continue
    method=req['method']
    if method=='initialize':result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'synthetic-memory-fixture','version':'0'}}
    elif method=='tools/list':result={'tools':[{'name':n,'description':'synthetic','inputSchema':{'type':'object'}} for n in ('search','timeline','get_observations')]}
    else:
        project=req['params']['arguments']['project']
        result={'content':[{'type':'text','text':json.dumps([{'id':'synthetic-A','project':'A'}] if project=='A' else [])}]}
    print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result}),flush=True)
'''


class Connection(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.kit=ROOT
        self.install=self.base/'official-shaped-fixture';scripts=self.install/'scripts';scripts.mkdir(parents=True)
        meta=self.install/'.claude-plugin/plugin.json';meta.parent.mkdir();meta.write_text(json.dumps({'name':'claude-mem','version':'15.2.1'}))
        self.worker=scripts/'worker-service.cjs';self.worker.write_text(WORKER)
        self.mcp=scripts/'mcp-server.cjs';self.mcp.write_text(MCP)
        self.mode=scripts/'mode';self.mode.write_text('ready')
        self.node=self.runtime('node','v22.12.0');self.bun=self.runtime('bun','1.3.0')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        self.providers=self.base/'providers.json';self.save_providers()
        self.binding=self.base/'binding.json'
        self.cfg={'schema_version':2,'providers':str(self.providers),'node':str(self.node),'bun':str(self.bun),
                  'data_dir':str(self.base/'memory'),'state_dir':str(self.base/'controller'),'port':port,'profile':'manual-local-worker'}
        self.review_fixture()
        self.save_binding();self.p=self.plan()
        self.addCleanup(self.cleanup_worker)

    def runtime(self,name,version):
        path=self.base/name
        path.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo '+version+'; exit 0; fi\nexec /usr/bin/python3 "$@"\n')
        path.chmod(0o700);return path

    def save_providers(self,products=None):
        self.providers.write_text(json.dumps({'version':1,'providers':[
            {'id':name,'kind':'cli','entry':str(path),'products':products or ['codex','claude'],
             'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source':'synthetic fixture, NOT official provenance','version':'15.2.1'}
            for name,path in [('claude-mem-mcp',self.mcp),('claude-mem-worker',self.worker)]]}))

    def save_binding(self):self.binding.write_text(json.dumps(self.cfg))
    def plan(self,product='codex'):return cm.plan(self.kit,self.binding,product)

    def review_fixture(self):
        # Explicit synthetic review; these bytes never represent official provenance.
        self.cfg['reviews']={}
        for name in ('claude-mem-mcp','claude-mem-worker'):
            doc=provider_review.snapshot(self.kit,self.providers,'codex',name,'cli',self.install,
                'native-plugin','https://example.invalid/synthetic-memory',[self.install/'.claude-plugin/plugin.json'])
            doc.update(review_status='reviewed',unresolved=[],products={p:{'status':'supported',
                'basis':'Own synthetic process fixture, not official runtime proof.'} for p in ('codex','claude')})
            path=self.base/(name+'-review.json');path.write_text(json.dumps(doc));self.cfg['reviews'][name]=str(path)

    def set_mode(self,value):
        self.mode.write_text(value);self.review_fixture();self.save_binding();self.p=self.plan()

    def cleanup_worker(self):
        # Only the PID recorded by this isolated fixture, never a host process.
        file=self.base/'controller/worker.json'
        if file.exists():
            rec=json.loads(file.read_text());pid=rec.get('identity',{}).get('pid') or rec.get('launched_pid')
            if pid:
                try:os.kill(pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:os.waitpid(pid,0)
                except ChildProcessError:pass

    def cli(self,action,extra=()):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/claude-mem.py'),action,
            '--root',str(ROOT),'--binding',str(self.binding),'--product','codex',*extra],capture_output=True,text=True,timeout=10)

    def test_plan_and_doctor_are_static_without_directories(self):
        for action in ('plan','doctor'):
            r=self.cli(action);self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse((self.base/'memory').exists());self.assertFalse((self.base/'controller').exists())
        self.assertEqual(self.plan()['plan_id'],self.p['plan_id'])
        self.assertIn('provenance',self.p['limits'])

    def test_codex_and_claude_render_formats_no_native_write(self):
        for product in ('codex','claude'):
            p=self.plan(product);raw=cm.render(p)
            if product=='codex':entry=tomllib.loads(raw)['mcp_servers']['claude-mem'];self.assertIs(entry['enabled'],False)
            else:entry=json.loads(raw)['mcpServers']['claude-mem'];self.assertNotIn('enabled',entry)
            self.assertEqual(entry['args'][-1],product);self.assertEqual(entry['env']['CLAUDE_MEM_WORKER_AUTOSTART'],'false')
        self.assertFalse((self.base/'controller').exists())

    def test_products_share_connection_not_lifecycle_plan(self):
        other=self.plan('claude');self.assertEqual(other['connection_id'],self.p['connection_id'])
        self.assertNotEqual(other['plan_id'],self.p['plan_id'])

    def test_changed_entry_pin_refused(self):
        self.worker.write_text(WORKER+'\n# drift\n')
        with self.assertRaises(ValueError):self.plan()

    def test_changed_upstream_version_refused(self):
        (self.install/'.claude-plugin/plugin.json').write_text('{"name":"claude-mem","version":"16.0.0"}')
        with self.assertRaises(ValueError):self.plan()

    def test_unsupported_product_refused(self):
        self.save_providers(['claude'])
        with self.assertRaises(ValueError):self.plan()

    def test_invalid_binding_fields_paths_and_ports(self):
        for key,value in [('profile','default'),('extra',True),('data_dir',str(ROOT/'memory')),
                          ('data_dir',str(self.base/'controller')),('port',True),('port',80),('node','relative')]:
            with self.subTest(key=key,value=value):
                changed=dict(self.cfg);changed[key]=value;self.binding.write_text(json.dumps(changed))
                with self.assertRaises((ValueError,OSError)):self.plan()
        self.save_binding()

    def test_symlink_data_path_refused(self):
        real=self.base/'actual';real.mkdir();link=self.base/'linked';link.symlink_to(real)
        self.cfg['data_dir']=str(link);self.save_binding()
        with self.assertRaises(ValueError):self.plan()

    def test_unmanaged_existing_data_not_adopted(self):
        (self.base/'memory').mkdir()
        with self.assertRaisesRegex(ValueError,'unmanaged'):cm.start(self.p,1)
        self.assertFalse(cm.port_open(self.p))

    def test_lifecycle_requires_reviewed_plan(self):
        r=self.cli('start',['--expect-plan','not-reviewed']);self.assertEqual(r.returncode,2)
        self.assertFalse((self.base/'memory').exists())

    def test_absent_health_is_not_success(self):
        r=self.cli('health');self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)['status'],'absent')

    def test_start_health_idempotency_stop_verified(self):
        report=cm.start(self.p,4);self.assertEqual(report['status'],'ready');self.assertTrue(report['owned'])
        again=cm.start(self.p,2);self.assertEqual(again['action'],'already-running');self.assertEqual(again['pid'],report['pid'])
        stopped=cm.stop(self.p,3);self.assertEqual(stopped['status'],'stopped');self.assertFalse(cm.port_open(self.p))

    def test_degraded_is_reported_without_claiming_fully_ready(self):
        self.set_mode('degraded');self.assertEqual(cm.start(self.p,4)['status'],'degraded')
        self.assertEqual(self.cli('health').returncode,2)
        self.assertEqual(cm.stop(self.p,3)['status'],'stopped')

    def test_exit_zero_stop_without_actual_stop_is_failure(self):
        self.set_mode('ignore-stop');cm.start(self.p,4)
        with self.assertRaisesRegex(ValueError,'stop did not verify'):cm.stop(self.p,.4)
        self.assertTrue(cm.owned(self.p));self.assertTrue(cm.port_open(self.p))

    def test_readiness_timeout_retains_owned_failure_receipt(self):
        self.set_mode('warming')
        with self.assertRaisesRegex(ValueError,'readiness failed'):cm.start(self.p,.7)
        self.assertEqual(cm.receipt(self.p)['phase'],'failed-running');self.assertTrue(cm.owned(self.p))
        self.assertEqual(cm.stop(self.p,3)['status'],'stopped')

    def test_pid_birth_mismatch_never_stops_process(self):
        cm.start(self.p,4);r=cm.receipt(self.p);r['identity']['started_ticks']='not-that-process';cm.write_receipt(self.p,r)
        with self.assertRaisesRegex(ValueError,'no live owned'):cm.stop(self.p,1)
        self.assertTrue(cm.port_open(self.p));self.assertFalse(cm.health(self.p)['owned'])

    def test_command_drift_never_stops_process(self):
        cm.start(self.p,4);r=cm.receipt(self.p);r['identity']['command_sha256']='0'*64;cm.write_receipt(self.p,r)
        with self.assertRaises(ValueError):cm.stop(self.p,1)
        self.assertTrue(cm.port_open(self.p))

    def test_foreign_listener_not_adopted_or_stopped(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',self.p['port']));sock.listen()
            # No HTTP request is needed to establish non-adoption.
            with mock.patch.object(cm,'health',return_value={'status':'unverified','owned':False}):
                with self.assertRaisesRegex(ValueError,'not adopted'):cm.start(self.p,1)
            with self.assertRaises(ValueError):cm.stop(self.p,1)
            self.assertFalse((self.base/'controller/worker.json').exists())

    def test_bad_runtime_version_refuses_execution(self):
        self.runtime('bun','1.0.0');self.p=self.plan()
        with self.assertRaisesRegex(ValueError,'Bun version'):cm.start(self.p,1)
        self.assertFalse(cm.port_open(self.p))

    def test_lock_contention_does_not_replace_worker(self):
        cm.prepare_dirs(self.p);lock=cm.acquire(self.p)
        try:
            with self.assertRaisesRegex(ValueError,'lock'):cm.start(self.p,1)
        finally:lock.unlink()

    def test_controller_symlink_cannot_redirect_logs_or_subdirectories(self):
        cm.prepare_dirs(self.p);outside=self.base/'unrelated';outside.write_text('keep')
        log=self.base/'controller/worker.log';log.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'log must be regular'):cm.start(self.p,1)
        self.assertEqual(outside.read_text(),'keep');log.unlink()
        sub=self.base/'controller/tmp';sub.rmdir();sub.symlink_to(self.base,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'subdirectory'):cm.prepare_dirs(self.p)

    def test_inconsistent_health_or_pid_not_certified(self):
        cm.start(self.p,4)
        good={'status':'ok','version':'15.2.1','workerPath':self.p['worker'],
              'pid':cm.receipt(self.p)['identity']['pid'],'initialized':True,'mcpReady':True}
        def answer(endpoint):
            return (200,good) if endpoint=='/api/health' else (200,{'status':'ready','mcpReady':False})
        with mock.patch.object(cm,'http',side_effect=lambda p,e:answer(e)):
            self.assertEqual(cm.health(self.p)['status'],'warming')
            good['status']='unexpected';self.assertEqual(cm.health(self.p)['status'],'unverified')
            good['status']='ok';good['pid']+=1;self.assertFalse(cm.health(self.p)['owned'])

    def test_failed_child_exit_retains_failure_not_running_claim(self):
        self.worker.write_text('raise SystemExit(6)\n');self.save_providers();self.review_fixture();self.save_binding();self.p=self.plan()
        with self.assertRaises(ValueError):cm.start(self.p,1)
        self.assertEqual(cm.receipt(self.p)['phase'],'failed-exited');self.assertFalse(cm.owned(self.p))
        self.assertFalse(cm.port_open(self.p))

    def test_mcp_failure_uses_stderr_not_protocol_stdout(self):
        self.mcp.write_text(MCP+'\n# drift\n')
        r=self.cli('mcp');self.assertEqual(r.returncode,2);self.assertEqual(r.stdout,'')
        self.assertEqual(json.loads(r.stderr)['status'],'unavailable')

    def test_legacy_binding_inspectable_but_no_start_or_mcp(self):
        self.cfg['schema_version']=1;del self.cfg['reviews'];self.save_binding();p=self.plan()
        for call in (cm.start,cm.mcp):
            with self.assertRaisesRegex(ValueError,'installation review'):call(p)
        self.assertFalse((self.base/'memory').exists());self.assertFalse((self.base/'controller').exists())

    def test_resource_drift_blocks_start_before_any_state_creation(self):
        self.mode.write_text('not-reviewed')
        with self.assertRaises(ValueError):cm.start(self.p,1)
        self.assertFalse((self.base/'memory').exists());self.assertFalse((self.base/'controller').exists())

    def test_review_changed_after_plan_is_not_adopted(self):
        path=Path(self.cfg['reviews']['claude-mem-worker']);path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'changed after'):cm.start(self.p,1)
        self.assertFalse((self.base/'memory').exists())

    def test_review_drift_does_not_strand_owned_worker(self):
        cm.start(self.p,4)
        Path(self.cfg['reviews']['claude-mem-worker']).write_text('unavailable')
        self.assertEqual(cm.stop(self.p,3)['status'],'stopped')

    def test_missing_review_does_not_block_new_stop_plan(self):
        cm.start(self.p,4)
        Path(self.cfg['reviews']['claude-mem-worker']).unlink()
        current=self.plan()
        self.assertIsNone(current['reviews']['claude-mem-worker']['sha256'])
        self.assertEqual(cm.stop(current,3)['status'],'stopped')

    def test_explicit_claude_directory_is_static_and_used_only_when_selected(self):
        directory=self.base/'claude-bin';directory.mkdir()
        cli=directory/'claude';cli.write_text('#!/bin/sh\necho "2.1.329 (Claude Code)"\n');cli.chmod(0o700)
        self.assertNotIn(str(directory),cm.env_for(self.p)['PATH'])
        self.cfg['claude_bin']=str(directory);self.save_binding();p=self.plan()
        self.assertNotEqual(self.p['connection_id'],p['connection_id'])
        self.assertEqual(cm.env_for(p)['PATH'].split(os.pathsep)[0],str(directory))
        self.assertEqual(cm.check_runtimes(p)['claude'],'2.1.329 (Claude Code)')
        self.assertFalse((self.base/'memory').exists())

    def test_official_style_claude_alias_is_bound_to_resolved_bytes(self):
        directory=self.base/'claude-bin';directory.mkdir()
        target=self.base/'native-cli';target.write_text('#!/bin/sh\necho "2.1.329 (Claude Code)"\n');target.chmod(0o700)
        (directory/'claude').symlink_to(target)
        self.cfg['claude_bin']=str(directory);self.save_binding();p=self.plan()
        self.assertEqual(p['runtimes']['claude']['path'],str(target))
        cm.check_runtimes(p)
        target.write_text('#!/bin/sh\necho "changed"\n')
        with self.assertRaisesRegex(ValueError,'changed after plan'):cm.check_runtimes(p)

    def test_other_cli_cannot_satisfy_claude_dependency(self):
        directory=self.base/'claude-bin';directory.mkdir()
        cli=directory/'claude';cli.write_text('#!/bin/sh\necho "codex-cli 0.167.2"\n');cli.chmod(0o700)
        self.cfg['claude_bin']=str(directory);self.save_binding()
        with self.assertRaisesRegex(ValueError,'Claude CLI identity'):cm.check_runtimes(self.plan())

    def test_stdio_handshake_tools_project_filter_no_worker_autostart(self):
        caller=self.base/'project-A';caller.mkdir();env=dict(os.environ);env['G4_TEST_PARENT_SECRET']='synthetic-not-a-credential'
        proc=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/claude-mem.py'),'mcp','--root',str(ROOT),
            '--binding',str(self.binding),'--product','codex'],cwd=caller,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            def request(i,method,params):
                proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':i,'method':method,'params':params})+'\n');proc.stdin.flush()
                self.assertTrue(select.select([proc.stdout],[],[],4)[0],'fixture MCP timeout')
                return json.loads(proc.stdout.readline())['result']
            self.assertEqual(request(1,'initialize',{})['serverInfo']['name'],'synthetic-memory-fixture')
            proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n');proc.stdin.flush()
            self.assertEqual([t['name'] for t in request(2,'tools/list',{})['tools']],['search','timeline','get_observations'])
            a=request(3,'tools/call',{'name':'search','arguments':{'project':'A'}})
            b=request(4,'tools/call',{'name':'search','arguments':{'project':'B'}})
            self.assertIn('synthetic-A',a['content'][0]['text']);self.assertEqual(json.loads(b['content'][0]['text']),[])
            self.assertEqual(json.loads((self.base/'memory/fixture-start.json').read_text())['cwd'],str(caller))
            self.assertFalse((self.base/'controller/worker.json').exists());self.assertFalse(cm.port_open(self.p))
            proc.stdin.close();self.assertEqual(proc.wait(timeout=4),0,proc.stderr.read())
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=3)
            for stream in (proc.stdin,proc.stdout,proc.stderr):
                if not stream.closed:stream.close()


if __name__=='__main__':unittest.main()
