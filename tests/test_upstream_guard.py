"""Synthetic provenance cases, not native product-hook activation tests."""
import concurrent.futures
import importlib.util
import io
import json
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'common/base/scripts'))
from upstream_guard import (Guard, MAX_BYTES, Result, Unavailable, digest,
                            make_catalog, protocol, read_payload)

ORIGINAL = ('Synthetic official alpha guide. Apply careful ownership and purpose checks.\n'
            'Keep the original workflow intact and connect through its documented entry point.\n'
            'Record verified evidence and remaining uncertainty without claiming runtime success.\n')
OWN = '# Own connector\nUse the separately installed sample tool. Do not include its instructions.\n'


def module(product):
    spec = importlib.util.spec_from_file_location(
        product + '_guard_adapter', ROOT / f'adapters/{product}/scripts/upstream_guard.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / 'kit'; self.project.mkdir()
        self.other = self.base / 'other'; self.other.mkdir()
        self.source = self.base / 'official.txt'; self.source.write_text(ORIGINAL)
        self.catalog = self.base / 'catalog.json'
        self.catalog.write_text(json.dumps(make_catalog([self.source])))
        self.scope = self.base / 'scope.json'
        self.scope.write_text(json.dumps({'version':1,'components':['.'],'artifacts':[]}))
        self.guard = Guard(self.project, self.catalog, self.scope)
        self.original_hash = digest(self.source.read_bytes())

    def tearDown(self):
        self.assertEqual(digest(self.source.read_bytes()), self.original_hash)

    def write(self, text, path='new.md'):
        return self.guard.write(path, text.encode(), self.project)

    def native(self, product, data, tool):
        return module(product).evaluate(self.guard, {
            'hook_event_name': 'PreToolUse', 'cwd': str(self.project),
            'tool_name': tool, 'tool_input': data})

    def call(self, product, payload, catalog=None):
        result = subprocess.run([sys.executable,
            str(ROOT / f'adapters/{product}/scripts/upstream_guard.py'),
            '--root', str(self.project), '--catalog', str(catalog or self.catalog), '--scope',str(self.scope)],
            input=payload, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_own_connector_passes(self):
        self.assertEqual(self.write(OWN).status, 'pass')

    def test_exact_original_blocked(self):
        self.assertEqual(self.write(ORIGINAL).status, 'block')

    def test_renamed_original_blocked(self):
        self.assertEqual(self.write(ORIGINAL, 'own-connector.md').status, 'block')

    def test_embedded_original_blocked(self):
        self.assertEqual(self.write('prefix\n' + ORIGINAL + 'suffix').status, 'block')

    def test_whitespace_similarity_is_not_a_deny(self):
        self.assertEqual(self.write(ORIGINAL.replace(' ', '  ')).status, 'pass')

    def test_word_similarity_is_not_a_deny(self):
        self.assertEqual(self.write(ORIGINAL.replace('alpha', 'beta')).status, 'pass')

    def test_partial_fragment_does_not_prove_copy(self):
        self.assertEqual(self.write(ORIGINAL.splitlines()[1]).status, 'pass')

    def test_fragment_in_own_file_is_not_automatic_deny(self):
        self.assertEqual(self.write(OWN + ORIGINAL.splitlines()[1] + '\nend').status,'pass')

    def test_wrapped_fragment_is_not_automatic_deny(self):
        self.assertEqual(self.write('own prefix '+ORIGINAL.splitlines()[1]+' own suffix').status,'pass')

    def test_other_path_hardlinked_to_kit_is_not_conclusively_outside(self):
        inside=self.project/'local';inside.write_text(OWN)
        alias=self.other/'alias';alias.hardlink_to(inside)
        self.assertTrue(alias.samefile(inside))
        self.assertEqual(self.guard.write(str(alias),ORIGINAL.encode(),self.other).status,'deferred')
        self.assertEqual(self.guard.edit(str(alias),OWN,ORIGINAL,False,self.other).status,'deferred')
        self.assertEqual(self.guard.shell(f'cp {self.source} {alias}',self.other).status,'deferred')

    def test_delete_original_hardlink_alias_does_not_delete_original(self):
        alias=self.other/'alias';alias.hardlink_to(self.source)
        command=f'*** Begin Patch\n*** Delete File: {alias}\n*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'not_applicable')
        alias.unlink()
        self.assertEqual(self.source.read_text(),ORIGINAL)

    def test_delete_official_reference_link_is_not_delete_referent(self):
        alias=self.project/'reference';alias.symlink_to(self.source)
        command='*** Begin Patch\n*** Delete File: reference\n*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'not_applicable')
        alias.unlink();self.assertEqual(self.source.read_text(),ORIGINAL)

    def test_known_noninclusion_delete_does_not_need_catalog(self):
        self.guard=Guard(self.project,self.base/'missing')
        command='*** Begin Patch\n*** Delete File: obsolete-own-file\n*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'not_applicable')

    def test_registered_original_write_blocked(self):
        self.assertEqual(self.write('replacement',str(self.source)).status,'block')

    def test_hardlinked_original_cannot_be_overwritten(self):
        alias=self.project/'alias.md';alias.hardlink_to(self.source)
        self.assertEqual(self.write('replacement',str(alias)).status,'block')

    def test_symlink_out_to_original_cannot_be_overwritten(self):
        alias=self.project/'alias.md';alias.symlink_to(self.source)
        self.assertEqual(self.write('replacement',str(alias)).status,'block')

    def test_registered_original_edit_blocked(self):
        self.assertEqual(self.native('claude',{'file_path':str(self.source),'old_string':'alpha',
                         'new_string':'beta'},'Edit').status,'block')

    def test_registered_original_codex_patch_blocked(self):
        for change in [f'*** Delete File: {self.source}',
                       f'*** Update File: {self.source}\n@@\n-old\n+new']:
            command='*** Begin Patch\n'+change+'\n*** End Patch'
            self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'block')

    def test_copy_over_official_original_blocked(self):
        own=self.other/'own';own.write_text(OWN)
        self.assertEqual(self.guard.shell(f'cp {own} {self.source}',self.project).status,'block')

    def test_copy_to_directory_keeps_operand_basename(self):
        own=self.other/'own';own.write_text(OWN)
        alias=self.other/self.source.name;alias.symlink_to(own)
        self.assertEqual(self.guard.shell(f'cp {alias} {self.base}',self.project).status,'block')

    def test_original_read_stays_available(self):
        self.assertEqual(self.native('claude',{'file_path':str(self.source)},'Read').status,'not_applicable')

    def test_fifo_is_not_opened_blocking(self):
        import os
        fifo=self.base/'pipe';os.mkfifo(fifo)
        with self.assertRaises(Unavailable):make_catalog([fifo])

    def test_unregistered_content_is_not_certified(self):
        result = self.write('Completely different, unregistered external text')
        self.assertEqual(result.status, 'pass')
        self.assertIn('not certified', result.reason)

    def test_other_project_not_affected_by_file_write(self):
        self.assertEqual(self.write(ORIGINAL, str(self.other / 'x.md')).status, 'not_applicable')

    def test_absolute_target_from_other_cwd(self):
        result = self.guard.write(str(self.project / 'x.md'), ORIGINAL.encode(), self.other)
        self.assertEqual(result.status, 'block')

    def test_symlink_into_project_resolved(self):
        (self.other / 'alias').symlink_to(self.project, target_is_directory=True)
        result = self.guard.write(str(self.other / 'alias/x.md'), ORIGINAL.encode(), self.other)
        self.assertEqual(result.status, 'block')

    def test_dotdot_target_resolved(self):
        self.assertEqual(self.write(ORIGINAL, '../kit/x.md').status, 'block')

    def test_missing_catalog_fails(self):
        with self.assertRaises(OSError):
            Guard(self.project, self.base/'missing').write('x.md', OWN.encode(), self.project)

    def test_empty_catalog_fails(self):
        self.catalog.write_text('{"version":2,"sources":[]}')
        with self.assertRaises(Unavailable): self.write(OWN)

    def test_catalog_version_fails(self):
        d=json.loads(self.catalog.read_text());d['version']=999;self.catalog.write_text(json.dumps(d))
        with self.assertRaises(Unavailable): self.write(OWN)

    def test_catalog_boolean_version_is_not_integer(self):
        d=json.loads(self.catalog.read_text());d['version']=True;self.catalog.write_text(json.dumps(d))
        with self.assertRaises(Unavailable):self.write(OWN)

    def test_corrupt_derived_hash_fails(self):
        d=json.loads(self.catalog.read_text());d['sources'][0]['windows']=[]
        self.catalog.write_text(json.dumps(d))
        with self.assertRaises(Unavailable): self.write(OWN)

    def test_source_inside_kit_fails(self):
        inside=self.project/'bad-original';inside.write_text(ORIGINAL)
        self.catalog.write_text(json.dumps(make_catalog([inside])))
        with self.assertRaises(Unavailable): self.write(OWN)

    def test_changed_source_fails(self):
        # Restore the fixture even when an assertion fails.
        try:
            self.source.write_text('new version')
            with self.assertRaises(Unavailable): self.write(OWN)
        finally: self.source.write_text(ORIGINAL)

    def test_oversized_candidate_fails(self):
        with self.assertRaises(Unavailable): self.write('x'*(MAX_BYTES+1))

    def test_catalog_contains_hashes_not_original_text(self):
        self.assertNotIn('Synthetic official', self.catalog.read_text())

    def test_read_tool_does_not_open_missing_catalog(self):
        self.guard=Guard(self.project, self.base/'missing')
        self.assertEqual(self.native('claude', {'file_path':str(self.source)}, 'Read').status,
                         'not_applicable')

    def test_claude_write_contract(self):
        self.assertEqual(self.native('claude', {'file_path':'x.md','content':ORIGINAL},'Write').status,
                         'block')

    def test_claude_edit_checks_full_result(self):
        p=self.project/'x.md';p.write_text('prefix\nplaceholder\nsuffix\n')
        result=self.native('claude', {'file_path':str(p),'old_string':'placeholder',
                                     'new_string':ORIGINAL},'Edit')
        self.assertEqual(result.status,'block')
        self.assertIn('placeholder',p.read_text())

    def test_claude_edit_own_change(self):
        p=self.project/'x.md';p.write_text('old connector')
        self.assertEqual(self.native('claude', {'file_path':str(p),'old_string':'old',
                         'new_string':'new'},'Edit').status,'pass')

    def test_ambiguous_edit_fails(self):
        p=self.project/'x.md';p.write_text('old old')
        with self.assertRaises(Unavailable):
            self.native('claude',{'file_path':str(p),'old_string':'old','new_string':'new'},'Edit')

    def test_codex_add_patch(self):
        command='*** Begin Patch\n*** Add File: x.md\n'+''.join('+'+l+'\n' for l in ORIGINAL.splitlines())+'*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'block')
        self.assertFalse((self.project/'x.md').exists())

    def test_codex_update_patch(self):
        p=self.project/'x.md';p.write_text('placeholder\n')
        command='*** Begin Patch\n*** Update File: x.md\n@@\n-placeholder\n'+''.join('+'+l+'\n' for l in ORIGINAL.splitlines())+'*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'block')
        self.assertEqual(p.read_text(),'placeholder\n')

    def test_codex_labelled_hunk_fails(self):
        p=self.project/'x.md';p.write_text('old\n')
        command='*** Begin Patch\n*** Update File: x.md\n@@ label\n-old\n+new\n*** End Patch'
        with self.assertRaises(Unavailable):self.native('codex',{'command':command},'apply_patch')

    def test_patch_unsupported_line_separators_fail(self):
        for separator in ['\r\n','\u2028','\v']:
            command='*** Begin Patch'+separator+'*** Add File: x'+separator+'+own'+separator+'*** End Patch'
            with self.subTest(separator=repr(separator)),self.assertRaises(Unavailable):
                self.native('codex',{'command':command},'apply_patch')

    def test_update_existing_crlf_or_unterminated_file_fails(self):
        p=self.project/'x'
        command='*** Begin Patch\n*** Update File: x\n@@\n-old\n+new\n*** End Patch'
        for data in [b'old\r\n',b'old']:
            p.write_bytes(data)
            with self.subTest(data=data),self.assertRaises(Unavailable):
                self.native('codex',{'command':command},'apply_patch')

    def test_repeated_patch_path_is_unavailable(self):
        (self.project/'x').write_text('old\n')
        command='*** Begin Patch\n*** Update File: x\n@@\n-old\n+new\n*** Update File: x\n@@\n-old\n+different\n*** End Patch'
        with self.assertRaises(Unavailable):self.native('codex',{'command':command},'apply_patch')

    def test_control_character_shell_effect_is_deferred(self):
        p=self.other/'own';p.write_text(OWN)
        self.assertEqual(self.guard.shell(f'cp {p}\r {self.project}/x',self.other).status,'deferred')

    def test_actual_shell_cr_filename_differs_from_shlex_whitespace(self):
        p=self.other/'own';p.write_text(OWN)
        cr=self.other/'own\r';cr.write_text(ORIGINAL)
        target=self.project/'copy'
        r=subprocess.run(['/bin/sh','-c',f'cp {p}\r {target}'],capture_output=True,timeout=5)
        self.assertEqual(r.returncode,0)
        self.assertEqual(target.read_text(),ORIGINAL)

    def test_codex_other_project_patch(self):
        command=f'*** Begin Patch\n*** Add File: {self.other}/x.md\n+hello\n*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'not_applicable')

    def test_codex_move_from_external_cwd(self):
        outside=self.other/'incoming';outside.write_text(ORIGINAL)
        command=f'*** Begin Patch\n*** Update File: {outside}\n*** Move to: {self.project}/x.md\n*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'block')

    def test_codex_move_to_registered_original_outside_kit(self):
        own=self.other/'own';own.write_text(OWN)
        alias=self.other/'original-alias';alias.hardlink_to(self.source)
        for destination in (self.source,alias):
            command=f'*** Begin Patch\n*** Update File: {own}\n*** Move to: {destination}\n*** End Patch'
            self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'block')

    def test_codex_update_original_hardlink_outside_kit(self):
        alias=self.other/'alias';alias.hardlink_to(self.source)
        command=f'*** Begin Patch\n*** Update File: {alias}\n@@\n-old\n+new\n*** End Patch'
        self.assertEqual(self.native('codex',{'command':command},'apply_patch').status,'block')

    def test_tilde_shell_effect_is_deferred(self):
        for command in [f'cp {self.source} ~/kit/copy',f'cp {self.source} "~/kit/copy"']:
            with self.subTest(command=command):
                self.assertEqual(self.guard.shell(command,self.other).status,'deferred')

    def test_bracket_glob_shell_effect_is_deferred(self):
        command=f'cp {self.source} {self.base}/ki[t]/copy'
        self.assertEqual(self.guard.shell(command,self.other).status,'deferred')

    def test_confirmed_copy_wins_regardless_of_corpus_order(self):
        second=self.other/'source2';second.write_text(ORIGINAL.replace(' ','  '))
        for paths in ([self.source,second],[second,self.source]):
            self.catalog.write_text(json.dumps(make_catalog(paths)))
            guard=Guard(self.project,self.catalog,self.scope)
            self.assertEqual(guard.write('copy',second.read_bytes(),self.project).status,'block')

    def test_shell_registered_copy(self):
        self.assertEqual(self.guard.shell(f'cp {self.source} x.md',self.project).status,'block')

    def test_shell_renamed_copy_detects_content(self):
        alias=self.other/'renamed';alias.write_text(ORIGINAL)
        self.assertEqual(self.guard.shell(f'cp {alias} x.md',self.project).status,'block')

    def test_shell_own_copy(self):
        own=self.other/'own';own.write_text(OWN)
        self.assertEqual(self.guard.shell(f'cp {own} x.md',self.project).status,'pass')

    def test_shell_copy_outside_project(self):
        self.assertEqual(self.guard.shell(f'cp {self.source} {self.other}/x.md',self.project).status,
                         'not_applicable')

    def test_shell_unknown_effects_defer_without_safe_certificate(self):
        for cmd in ['python3 writer.py', 'cp a b; echo done', 'cp "$X" x.md', 'curl https://example.invalid/x']:
            with self.subTest(cmd=cmd):self.assertEqual(self.guard.shell(cmd,self.project).status,'deferred')

    def test_shell_direct_read_pwd(self):
        self.assertEqual(self.guard.shell('pwd',self.project).status,'not_applicable')

    def test_unrecognized_tool_deferred(self):
        for product in ('codex','claude'):
            with self.subTest(product=product):
                self.assertEqual(self.native(product,{},'mcp__unknown__tool').status,'deferred')

    def test_success_never_overrides_other_permission(self):
        self.assertEqual(protocol(Result('pass','ok')), {})
        self.assertEqual(protocol(Result('not_applicable','skip')), {})

    def test_unavailable_is_deny_not_allow(self):
        self.assertEqual(protocol(Result('unavailable','failed'))['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_invalid_result_cannot_be_pass(self):
        self.assertEqual(protocol(Result('bad','oops'))['hookSpecificOutput']['permissionDecision'],'deny')

    def test_malformed_input_blackbox_both_products(self):
        for product in ('codex','claude'):
            with self.subTest(product=product):
                doc=self.call(product,'not json')
                self.assertEqual(doc['hookSpecificOutput']['permissionDecision'],'deny')

    def test_absent_policy_blackbox_both_products(self):
        for product in ('codex','claude'):
            data={'command':'*** Begin Patch\n*** Add File: x\n+own\n*** End Patch'} if product=='codex' else {'file_path':'x','content':OWN}
            p={'hook_event_name':'PreToolUse','cwd':str(self.project),'tool_name':'apply_patch' if product=='codex' else 'Write','tool_input':data}
            doc=self.call(product,json.dumps(p),self.base/'missing')
            self.assertEqual(doc['hookSpecificOutput']['permissionDecision'],'deny')

    def test_wrong_event_fails_blackbox(self):
        doc=self.call('codex',json.dumps({'hook_event_name':'Stop','cwd':str(self.project)}))
        self.assertEqual(doc['hookSpecificOutput']['permissionDecision'],'deny')

    def test_oversized_payload_fails_blackbox(self):
        doc=self.call('claude','x'*(MAX_BYTES+1))
        self.assertEqual(doc['hookSpecificOutput']['permissionDecision'],'deny')

    def test_parallel_and_repeated_requests_no_mutation(self):
        before={str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        def check(n):
            guard=Guard(self.project,self.catalog,self.scope)
            return guard.write(f'{n}.md', (ORIGINAL if n%2 else OWN).encode(), self.project).status
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(check,range(12))), ['pass','block']*6)
        after={str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_catalog_tool_refuses_overwrite(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/upstream-catalog.py'),
            '--source',str(self.source),'--output',str(self.source)],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,2)
        self.assertEqual(self.source.read_text(),ORIGINAL)

    def launcher(self, product, payload, clone=None, env=None, event='PreToolUse'):
        source_root=clone or ROOT
        return subprocess.run(['/bin/sh',str(source_root/'common/base/scripts/run_upstream_guard.sh'),
            product,str(self.project),str(self.catalog),str(self.scope),event],input=payload,text=True,
            capture_output=True,timeout=7,env=env)

    def broken_deployment(self, body):
        clone=self.base/'deployment'
        launcher=clone/'common/base/scripts/run_upstream_guard.sh'
        adapter=clone/'adapters/codex/scripts/upstream_guard.py'
        launcher.parent.mkdir(parents=True);adapter.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/'common/base/scripts/run_upstream_guard.sh',launcher)
        if body is not None:adapter.write_text(body)
        return clone

    def test_launcher_preserves_success_no_allow(self):
        payload=json.dumps({'hook_event_name':'PreToolUse','cwd':str(self.project),
                            'tool_name':'Write','tool_input':{'file_path':'x','content':OWN}})
        p=self.launcher('claude',payload)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout),{})

    def test_launcher_preserves_deny_both_products(self):
        for product in ('codex','claude'):
            p=self.launcher(product,'malformed')
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],'deny')

    def test_launcher_actual_content_both_products(self):
        for product in ('codex','claude'):
            for content,blocked in [(OWN,False),(ORIGINAL,True)]:
                data={'file_path':'x','content':content}
                tool='Write'
                if product=='codex':
                    tool='apply_patch'
                    data={'command':'*** Begin Patch\n*** Add File: x\n'+''.join('+'+l+'\n' for l in content.splitlines())+'*** End Patch'}
                payload=json.dumps({'hook_event_name':'PreToolUse','cwd':str(self.project),
                                    'tool_name':tool,'tool_input':data})
                p=self.launcher(product,payload)
                self.assertEqual(p.returncode,0,p.stderr)
                response=json.loads(p.stdout)
                if blocked:self.assertEqual(response['hookSpecificOutput']['permissionDecision'],'deny')
                else:self.assertEqual(response,{})

    def test_codex_workdir_cannot_hide_destination(self):
        payload={'hook_event_name':'PreToolUse','cwd':str(self.project),
                 'tool_cwd':str(self.other),'tool_name':'Bash',
                 'tool_input':{'command':f'cp {self.source} {self.project}/x'}}
        self.assertEqual(module('codex').evaluate(self.guard,payload).status,'block')

    def test_source_catalog_writer_success_no_copy(self):
        output=self.base/'new-catalog'
        p=subprocess.run([sys.executable,str(ROOT/'scripts/upstream-catalog.py'),
            '--source',str(self.source),'--output',str(output)],text=True,capture_output=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        d=json.loads(output.read_text())
        self.assertEqual(d['sources'][0]['sha256'],digest(self.source.read_bytes()))
        self.assertNotIn('Synthetic official',output.read_text())

    def test_combined_source_size_is_bounded(self):
        a=self.other/'a';b=self.other/'b'
        a.write_bytes(b'a'*(MAX_BYTES//2+1));b.write_bytes(b'b'*(MAX_BYTES//2+1))
        with self.assertRaises(Unavailable):make_catalog([a,b])

    def test_launcher_start_failure_exit_two(self):
        p=self.launcher('codex','{}',self.broken_deployment(None))
        self.assertEqual(p.returncode,2)
        self.assertIn('unavailable',p.stderr)

    def test_launcher_crash_exit_two_no_raw_error(self):
        p=self.launcher('codex','{}',self.broken_deployment('raise RuntimeError("PRIVATE_SENTINEL")'))
        self.assertEqual(p.returncode,2)
        self.assertNotIn('PRIVATE_SENTINEL',p.stdout+p.stderr)

    def test_launcher_timeout_exit_two(self):
        p=self.launcher('codex','{}',self.broken_deployment('import time\ntime.sleep(20)'))
        self.assertEqual(p.returncode,2)

    def test_post_launcher_start_failure_is_feedback_not_pre_deny(self):
        p=self.launcher('codex','{}',self.broken_deployment(None),event='PostToolUse')
        self.assertEqual(p.returncode,0,p.stderr)
        h=json.loads(p.stdout)['hookSpecificOutput']
        self.assertEqual(h['hookEventName'],'PostToolUse')
        self.assertNotIn('permissionDecision',h);self.assertIn('unavailable',h['additionalContext'])

    def test_post_launcher_timeout_is_incomplete_feedback(self):
        p=self.launcher('codex','{}',self.broken_deployment('import time\ntime.sleep(20)'),event='PostToolUse')
        self.assertEqual(p.returncode,0,p.stderr)
        h=json.loads(p.stdout)['hookSpecificOutput']
        self.assertNotIn('permissionDecision',h);self.assertIn('Fresh',h['additionalContext'])

    def test_launcher_malformed_response_exit_two(self):
        p=self.launcher('codex','{}',self.broken_deployment('print("bad-json")'))
        self.assertEqual(p.returncode,2)

    def test_launcher_allow_response_exit_two(self):
        body='import json\nprint(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"override"}}))'
        p=self.launcher('codex','{}',self.broken_deployment(body))
        self.assertEqual(p.returncode,2)

    def test_launcher_optimization_cannot_skip_validation(self):
        p=self.launcher('codex','{}',self.broken_deployment('print("123")'),
                        {'PATH':'/usr/bin:/bin','PYTHONOPTIMIZE':'2'})
        self.assertEqual(p.returncode,2)

    def test_launcher_duplicate_keys_canonicalized(self):
        response='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecision":"deny","permissionDecisionReason":"review"}}'
        p=self.launcher('codex','{}',self.broken_deployment('print('+repr(response)+')'))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertEqual(p.stdout.count('"permissionDecision"'),1)

    def test_registration_templates_not_live(self):
        for product in ('codex','claude'):
            p=ROOT/f'adapters/{product}/hooks/upstream-guard.json.in'
            d=json.loads(p.read_text())
            self.assertEqual('@@PRE_COMMAND@@',d['hooks']['PreToolUse'][0]['hooks'][0]['command'])
            self.assertFalse((ROOT/f'.{product}/hooks.json').exists())
        self.assertFalse((ROOT/'.claude/settings.json').exists())

    def renderer(self):
        spec=importlib.util.spec_from_file_location('renderer',ROOT/'scripts/render-upstream-hook.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        return m

    def test_rendered_template_argv_contract(self):
        for product in ('codex','claude'):
            doc=self.renderer().render(product,ROOT,self.project,self.catalog,self.scope)
            group=doc['hooks']['PreToolUse'][0];handler=group['hooks'][0]
            self.assertNotEqual(group['matcher'],'.*')
            self.assertEqual(handler['timeout'],8)
            self.assertEqual(shlex.split(handler['command']),['/bin/sh',
                str(ROOT/'common/base/scripts/run_upstream_guard.sh'),product,str(self.project),str(self.catalog),str(self.scope),'PreToolUse'])
            if product=='claude':self.assertEqual(handler['onFailure'],'block')

    def test_rendered_shell_paths_are_literal_not_substitutions(self):
        clone=self.base/"source $(touch PWNED) ' `no-such-command`"
        for name in ['common/base/scripts','adapters']:
            shutil.copytree(ROOT/name,clone/name,ignore=shutil.ignore_patterns('__pycache__'))
        protected=self.base/"kit ' $HOME `no-such-command`";protected.mkdir()
        catalog=self.base/"catalog $(touch PWNED) ' `no-such-command`.json"
        shutil.copyfile(self.catalog,catalog)
        for product in ('codex','claude'):
            doc=self.renderer().render(product,clone,protected,catalog,self.scope)
            command=doc['hooks']['PreToolUse'][0]['hooks'][0]['command']
            payload={'hook_event_name':'PreToolUse','cwd':str(protected),'tool_name':'Read',
                     'tool_input':{'file_path':str(self.source)}}
            p=subprocess.run(['/bin/sh','-c',command],cwd=self.base,input=json.dumps(payload),
                             capture_output=True,text=True,timeout=7)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout),{})
            self.assertFalse((self.base/'PWNED').exists())

    def test_renderer_cli_outputs_json_without_activation(self):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/render-upstream-hook.py'),
            '--product','codex','--root',str(self.project),'--catalog',str(self.catalog),'--scope',str(self.scope)],
            capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        d=json.loads(p.stdout)
        self.assertEqual(shlex.split(d['hooks']['PreToolUse'][0]['hooks'][0]['command'])[-3:],
                         [str(self.catalog),str(self.scope),'PreToolUse'])

    def test_renderer_rejects_unreviewed_extra_event(self):
        clone=self.base/'render-source';p=clone/'adapters/codex/hooks/upstream-guard.json.in'
        p.parent.mkdir(parents=True)
        d=json.loads((ROOT/'adapters/codex/hooks/upstream-guard.json.in').read_text())
        d['hooks']['Stop']=[];p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):self.renderer().render('codex',clone,self.project,self.catalog,self.scope)

    def test_renderer_rejects_replaced_command_placeholder(self):
        clone=self.base/'render-source';p=clone/'adapters/codex/hooks/upstream-guard.json.in'
        p.parent.mkdir(parents=True)
        d=json.loads((ROOT/'adapters/codex/hooks/upstream-guard.json.in').read_text())
        d['hooks']['PreToolUse'][0]['hooks'][0]['command']='unexpected handler'
        p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):self.renderer().render('codex',clone,self.project,self.catalog,self.scope)


if __name__ == '__main__':
    unittest.main()
