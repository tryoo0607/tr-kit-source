"""Offline installer/probe protocol fixtures, not real package acquisition."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'common/base/scripts'))
import toolchain as tools
import toolchain_verify as probes
import secret_guard


def archive(name,version,link=False):
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w:gz') as tar:
        body=f'#!/bin/sh\necho {version}\n'.encode()
        info=tarfile.TarInfo(name);info.size=len(body)
        if link:info.type=tarfile.SYMTYPE;info.linkname='/outside'
        tar.addfile(info,None if link else io.BytesIO(body))
    return raw.getvalue()


class ToolFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'source';p=self.root/'common/base/scripts';p.mkdir(parents=True)
        self.payloads={'gitleaks':archive('gitleaks','8.30.1'),'trivy':archive('trivy','Version: 0.76.1')}
        for name in tools.PIN_FILES:
            data=(ROOT/'common/base/scripts'/name).read_text()
            if name=='secret-tools.toml':data=data.replace('551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb',tools.digest(self.payloads['gitleaks']))
            if name=='security-tools.toml':data=data.replace('c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0',tools.digest(self.payloads['trivy']))
            (p/name).write_text(data)
        self.prefix=self.base/'new tool prefix';self.evidence=self.base/'evidence'
        self.prerequisites={}
        for name in ('node','npm','uv'):
            path=self.base/name;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755);self.prerequisites[name]=path
        self.commands=[];self.engine_drift=False;self.release_version_drift=False

    def plan(self,kind='development',**kw):
        return tools.plan(kind,self.prefix,self.root,**(self.prerequisites if kind=='development' else {}),**kw)

    def fake_run(self,args,prefix,env,expected=(0,),timeout=180):
        args=[str(a) for a in args];self.commands.append(args)
        self.assertNotIn('SEMGREP_APP_TOKEN',env);self.assertNotIn('NODE_AUTH_TOKEN',env)
        self.assertNotIn('npm_config_registry',env);self.assertNotIn('HOME',env)
        name=Path(args[0]).name
        if args[1:] == ['--version']:
            if name=='node':return b'v26.2.0\n'
            if name=='npm':return b'11.0.0\n'
            if name=='uv':return b'uv 0.9.0\n'
            if name=='trivy':return b'Version: 0.76.10\n' if self.release_version_drift else b'Version: 0.76.1\n'
        if args[1:]==['version']:return b'8.30.1-unknown\n' if self.release_version_drift else b'8.30.1\n'
        if name=='npm' and 'install' in args:
            node=prefix/'node';(node/'node_modules/.bin').mkdir(parents=True)
            for package,version,cli in [('ctx7','0.8.2','ctx7'),('@playwright/cli','0.1.22','playwright-cli'),
                                         ('playwright','0.0.0' if self.engine_drift else '1.64.0-alpha-1790635538000',None)]:
                d=node/'node_modules'/package;d.mkdir(parents=True,exist_ok=True)
                (d/'package.json').write_text(json.dumps({'version':version}))
                if cli:
                    entry=d/'cli.js';entry.write_text('fixture');entry.chmod(0o755)
                    (node/'node_modules/.bin'/cli).symlink_to(entry)
            (node/'package-lock.json').write_text('{"lockfileVersion":3}')
        elif name=='uv' and 'venv' in args:
            b=prefix/'python/bin';b.mkdir(parents=True);(b/'python').symlink_to(Path(sys.executable).resolve())
        elif name=='uv' and 'install' in args:
            s=prefix/'python/bin/semgrep';s.write_text('#!/bin/sh\nexit 0\n');s.chmod(0o755)
        elif name=='uv' and 'freeze' in args:return b'semgrep==1.182.1\nplaywright==1.64.1\n'
        elif '-m' in args and 'playwright' in args:
            b=prefix/'browsers/chromium/chrome';b.parent.mkdir(parents=True);b.write_text('fixture Chromium');b.chmod(0o755)
        elif '-c' in args:
            code=args[args.index('-c')+1]
            if 'platform.python_version' in code:return b'3.11.8\n'
            if 'importlib.metadata' in code:return b'{"semgrep":"1.182.1","playwright":"1.64.1"}'
            if 'executable_path' in code:return (str(prefix/'browsers/chromium/chrome')+'\n').encode()
        return b''

    def prepare(self,kind='development'):
        report=self.plan(kind)
        def transport(url):return self.payloads['gitleaks' if 'gitleaks' in url else 'trivy']
        with mock.patch.object(tools,'download',side_effect=transport),mock.patch.object(tools,'run',side_effect=self.fake_run):
            result=tools.apply(report,tools.plan_id(report))
        self.assertEqual('ready',result['status']);return report


class Preparation(ToolFixture):
    def test_readonly_plan_pins_and_no_command_execution(self):
        with mock.patch.object(tools,'download') as download,mock.patch.object(tools,'run') as run:
            report=self.plan();download.assert_not_called();run.assert_not_called()
        self.assertFalse(self.prefix.exists());self.assertEqual('0.8.2',report['pins']['development']['context7']['version'])
        self.assertEqual(64,len(tools.public(report)['plan_id']))

    def test_existing_or_source_prefix_not_overwritten(self):
        self.prefix.mkdir();sentinel=self.prefix/'keep';sentinel.write_text('user data')
        with self.assertRaisesRegex(tools.ToolError,'never overwritten'):self.plan()
        self.assertEqual('user data',sentinel.read_text())
        with self.assertRaisesRegex(tools.ToolError,'outside kit'):
            tools.plan('gitleaks',self.root/'runtime',self.root)

    def test_manifest_prerequisite_and_plan_drift_prevent_creation(self):
        report=self.plan()
        with self.assertRaisesRegex(tools.ToolError,'reviewed'):tools.apply(report,'0'*64)
        self.assertFalse(self.prefix.exists())
        self.prerequisites['uv'].write_text('changed')
        with self.assertRaisesRegex(tools.ToolError,'inputs changed'):tools.apply(report,tools.plan_id(report))
        self.assertFalse(self.prefix.exists())

    def test_prefix_created_after_plan_is_never_adopted(self):
        report=self.plan();self.prefix.mkdir();(self.prefix/'keep').write_text('new user data')
        with self.assertRaisesRegex(tools.ToolError,'never overwritten'):tools.apply(report,tools.plan_id(report))
        self.assertEqual('new user data',(self.prefix/'keep').read_text())

    def test_official_commands_isolated_caches_and_no_host_activation(self):
        with mock.patch.dict(os.environ,{'SEMGREP_APP_TOKEN':'fixture','NODE_AUTH_TOKEN':'fixture',
                                        'npm_config_registry':'https://invalid.example'}):self.prepare()
        npm=next(a for a in self.commands if Path(a[0]).name=='npm' and 'install' in a)
        self.assertIn('--ignore-scripts',npm);self.assertIn('--registry=https://registry.npmjs.org',npm)
        pip=next(a for a in self.commands if 'pip' in a and 'install' in a)
        self.assertIn('--no-config',pip);self.assertIn('--no-python-downloads',pip)
        self.assertIn('https://pypi.org/simple',pip);self.assertIn('semgrep==1.182.1',pip)
        self.assertEqual('ready',tools.status(self.prefix,self.root)['status'])
        self.assertEqual(0o700,self.prefix.stat().st_mode & 0o777)
        self.assertEqual(0o600,(self.prefix/'provisioned.json').stat().st_mode & 0o777)
        self.assertFalse(any('sudo' in a or 'install-deps' in a for a in self.commands))

    def test_checksum_failure_retained_but_not_marked_ready_or_overwritten(self):
        report=self.plan('gitleaks')
        with mock.patch.object(tools,'download',return_value=b'not trusted'):
            with self.assertRaisesRegex(tools.ToolError,'checksum'):tools.apply(report,tools.plan_id(report))
        self.assertFalse((self.prefix/'bin/gitleaks').exists())
        self.assertEqual('failed',tools.status(self.prefix,self.root)['status'])
        with self.assertRaisesRegex(tools.ToolError,'never overwritten'):self.plan('gitleaks')
        old=self.prefix;self.prefix=self.base/'explicit recovery prefix';self.prepare('gitleaks')
        self.assertEqual('failed',tools.status(old,self.root)['status'])
        self.assertEqual('ready',tools.status(self.prefix,self.root)['status'])

    def test_archive_symlink_rejected_without_extracting_target(self):
        self.payloads['gitleaks']=archive('gitleaks','8.30.1',link=True)
        p=self.root/'common/base/scripts/secret-tools.toml'
        data=p.read_text();data=data.replace(__import__('tomllib').loads(data)['gitleaks']['linux_x64_sha256'],tools.digest(self.payloads['gitleaks']));p.write_text(data)
        with self.assertRaisesRegex(tools.ToolError,'regular'):self.prepare('gitleaks')
        self.assertFalse((self.prefix/'bin/gitleaks').exists())

    def test_engine_and_release_version_drift_fail_closed(self):
        self.engine_drift=True
        with self.assertRaisesRegex(tools.ToolError,'engine pin drift'):self.prepare()
        self.assertEqual('failed',tools.status(self.prefix,self.root)['status'])
        self.prefix=self.base/'next prefix';self.engine_drift=False;self.release_version_drift=True
        with self.assertRaisesRegex(tools.ToolError,'version mismatch'):self.prepare('gitleaks')

    def test_manager_failure_retains_partial_receipt_without_recovery_guess(self):
        report=self.plan()
        with mock.patch.object(tools,'run',side_effect=subprocess.TimeoutExpired('fixture',1)):
            with self.assertRaises(subprocess.TimeoutExpired):tools.apply(report,tools.plan_id(report))
        self.assertEqual('failed',tools.status(self.prefix,self.root)['status'])
        self.assertFalse((self.prefix/'bin/trivy').exists())

    def test_empty_release_version_is_an_unavailable_failed_prefix(self):
        report=self.plan('gitleaks')
        with mock.patch.object(tools,'download',return_value=self.payloads['gitleaks']),mock.patch.object(tools,'run',return_value=b''):
            with self.assertRaisesRegex(tools.ToolError,'version mismatch'):tools.apply(report,tools.plan_id(report))
        self.assertEqual('failed',tools.status(self.prefix,self.root)['status'])

    def test_status_detects_artifact_and_pin_drift(self):
        self.prepare('gitleaks');(self.prefix/'bin/gitleaks').write_text('changed')
        self.assertEqual('conflict',tools.status(self.prefix,self.root)['status'])
        p=self.root/'common/base/scripts/secret-tools.toml';p.write_text(p.read_text()+'\n# changed pin source\n')
        self.assertEqual('pin-drift',tools.status(self.prefix,self.root)['status'])

    def test_symlink_escape_in_artifact_receipt_rejected(self):
        self.prepare('gitleaks');target=self.prefix/'bin/gitleaks';target.unlink();target.symlink_to(self.prerequisites['node'])
        with self.assertRaisesRegex(tools.ToolError,'outside prefix'):tools.status(self.prefix,self.root)

    def test_incomplete_receipt_is_not_a_ready_toolchain(self):
        self.prepare();p=self.prefix/'provisioned.json';receipt=json.loads(p.read_text())
        receipt['artifacts'].pop();p.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(tools.ToolError,'inventory incomplete'):tools.status(self.prefix,self.root)

    def test_stored_pin_values_cannot_drift_behind_unchanged_hash_fields(self):
        self.prepare('gitleaks');p=self.prefix/'provisioned.json';receipt=json.loads(p.read_text())
        receipt['plan']['pins']['secret']['gitleaks']['version']='9.0.0';p.write_text(json.dumps(receipt))
        self.assertEqual('pin-drift',tools.status(self.prefix,self.root)['status'])

    def test_gitleaks_receipt_compatible_with_shared_guard(self):
        self.prepare('gitleaks')
        with mock.patch.object(secret_guard,'__file__',str(self.root/'common/base/scripts/secret_guard.py')):
            self.assertEqual(self.prefix/'bin/gitleaks',secret_guard.verify_scanner(self.prefix/'bin/gitleaks'))

    def test_gitleaks_group_has_no_development_pin_dependency(self):
        for name in ('dev-tools.toml','security-tools.toml'):(self.root/'common/base/scripts'/name).unlink()
        self.prepare('gitleaks');self.assertEqual('ready',tools.status(self.prefix,self.root)['status'])

    def test_environment_file_shell_quotes_path_and_preserves_parent_path(self):
        self.prefix=self.base/"tools ' $(touch injected)";self.prepare()
        result=subprocess.run(['bash','-c','source "$1"; printf "%s\\n%s\\n" "$TR_DEVTOOLS_ROOT" "$PATH"',
            'fixture',str(self.prefix/'env.sh')],env={'PATH':'/usr/bin:/bin'},cwd=self.base,capture_output=True,check=True,text=True)
        self.assertEqual([str(self.prefix),str(self.prefix/'bin')+':/usr/bin:/bin'],result.stdout.splitlines())
        self.assertFalse((self.base/'injected').exists())

    def test_unsupported_platform_and_relative_prefix_require_no_download(self):
        with mock.patch.object(tools.platform,'system',return_value='Windows'),mock.patch.object(tools,'download') as fetch:
            with self.assertRaisesRegex(tools.ToolError,'Linux'):self.plan()
            fetch.assert_not_called()
        with self.assertRaisesRegex(tools.ToolError,'canonical'):tools.plan('gitleaks',Path('relative'),self.root)

    def test_cli_plan_never_applies_or_downloads(self):
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/setup_git_guard.py'),'plan',
            '--prefix',str(self.prefix),'--source-root',str(self.root)],capture_output=True,check=True)
        self.assertIn('plan_id',json.loads(result.stdout));self.assertFalse(self.prefix.exists())
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/setup_git_guard.py'),'apply',
            '--prefix',str(self.prefix),'--source-root',str(self.root)],capture_output=True)
        self.assertNotEqual(0,result.returncode);self.assertFalse(self.prefix.exists())


class Verification(ToolFixture):
    def setUp(self):
        super().setUp();self.prepare();self.probe_commands=[];self.session_state={};self.bad_semgrep=False;self.fail_browser=False

    def fake_probe(self,args,cwd,env,capture_output,timeout,stdin):
        args=[str(a) for a in args];self.probe_commands.append(args);name=Path(args[0]).name
        if '-c' in args:
            # The harness still compiles the exact generated Python: mock success
            # must not conceal a program which the real interpreter rejects.
            compile(args[args.index('-c')+1],'<toolchain probe>','exec')
        self.assertEqual(subprocess.DEVNULL,stdin)
        self.assertNotIn('SEMGREP_APP_TOKEN',env);self.assertEqual(str(self.evidence/'tmp'),env['TMPDIR'])
        if args[1:]==['--version']:
            values={'ctx7':'0.8.2','playwright-cli':'0.1.22','semgrep':'1.182.1','trivy':'Version: 0.76.1'}
            return SimpleNamespace(stdout=values[name].encode(),stderr=b'',returncode=0)
        if name=='semgrep':
            output=Path(args[args.index('--output')+1]);bad='finding' in output.name
            output.write_text(json.dumps({'results':[{}] if bad else [],'errors':['fixture parse failure'] if self.bad_semgrep else []}))
            return SimpleNamespace(stdout=b'',stderr=b'',returncode=1 if bad else 0)
        if name=='playwright-cli':
            session=args[1][3:];action=args[2]
            if self.fail_browser:
                if action=='open':raise subprocess.TimeoutExpired(args,timeout)
                return SimpleNamespace(stdout=b'',stderr=b'',returncode=2)
            if action=='open':self.session_state[session]='pending'
            if action=='click':self.session_state[session]='saved'
            if action=='close':self.session_state.pop(session,None)
            if action=='screenshot':Path(args[3].split('=',1)[1]).write_bytes(b'\x89PNG\r\n\x1a\nfixture')
            output=('G2 local probe' if action=='eval' and 'document.title' in args else self.session_state.get(session,''))
            return SimpleNamespace(stdout=output.encode(),stderr=b'',returncode=0)
        if name=='ctx7':
            output=([{'id':'/react/react','versions':['v18.2.0']}] if args[1]=='library' else
                    {'codeSnippets':[{'codeId':'https://github.com/react/react/blob/v18.2.0/fixture.js'}]})
            return SimpleNamespace(stdout=json.dumps(output).encode(),stderr=b'',returncode=0)
        if name=='trivy':
            output=Path(args[args.index('--output')+1]);field='Misconfigurations' if args[1]=='config' else 'Vulnerabilities'
            output.write_text(json.dumps({'Results':[{field:[{'fixture':True,'PkgName':'lodash'}]}]}))
        return SimpleNamespace(stdout=b'{"isolated":true}',stderr=b'',returncode=0)

    def verify(self,**kwargs):
        with mock.patch.object(probes.subprocess,'run',side_effect=self.fake_probe):
            return probes.verify(self.prefix,self.evidence,self.root,**kwargs)

    def test_default_checks_versions_without_network_browser_or_scan(self):
        result=self.verify();self.assertEqual('pass',result['status'])
        self.assertEqual(4,len(self.probe_commands));self.assertTrue(all(args[1:]==['--version'] for args in self.probe_commands))
        self.assertEqual(3,len(result['unexecuted']))

    def test_local_protocol_assertions_and_scoped_session_cleanup(self):
        result=self.verify(local=True);self.assertEqual('pass',result['status'])
        self.assertFalse(self.session_state);self.assertEqual([],result['cleanup_errors'])
        self.assertFalse(any('close-all' in a or 'kill-all' in a for a in self.probe_commands))
        self.assertFalse(any(Path(a[0]).name=='trivy' and a[1:]!=['--version'] for a in self.probe_commands))

    def test_parse_errors_are_not_successful_findings(self):
        self.bad_semgrep=True;result=self.verify(local=True)
        self.assertEqual('unavailable',result['status']);self.assertIn('mismatch',result['reason'])

    def test_browser_timeout_and_failed_scoped_close_reported(self):
        self.fail_browser=True;result=self.verify(local=True)
        self.assertEqual('unavailable',result['status']);self.assertEqual(1,len(result['cleanup_errors']))
        self.assertTrue(any(a[2:] == ['close'] for a in self.probe_commands if Path(a[0]).name=='playwright-cli'))

    def test_network_probes_only_when_selected(self):
        result=self.verify(network_context7=True,network_trivy=True)
        self.assertEqual('pass',result['status'])
        self.assertTrue(any('library' in a for a in self.probe_commands))
        self.assertTrue(any('fs' in a and 'vuln' in a for a in self.probe_commands))
        self.assertEqual(['local semantic probes not requested'],result['unexecuted'])

    def test_existing_evidence_and_failed_prefix_refused_without_execution(self):
        self.evidence.mkdir()
        with mock.patch.object(probes.subprocess,'run') as run:
            with self.assertRaisesRegex(tools.ToolError,'evidence'):probes.verify(self.prefix,self.evidence,self.root)
            run.assert_not_called()

    def test_probe_version_prefix_match_does_not_accept_different_patch(self):
        def wrong(args,**kwargs):return SimpleNamespace(stdout=b'0.8.20',stderr=b'',returncode=0)
        with mock.patch.object(probes.subprocess,'run',side_effect=wrong):
            result=probes.verify(self.prefix,self.evidence,self.root)
        self.assertEqual('unavailable',result['status']);self.assertIn('version',result['reason'])
