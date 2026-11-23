"""Declared scope, current-byte post inspection and downstream gate contracts."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'common/base/scripts'))
import upstream_artifacts
from upstream_guard import make_catalog

ORIGINAL = 'Synthetic external guide: preserve a separately installed original.\nNever embed its functional instructions in this kit.\n'
OWN = '# Own connector\nCalls the separately installed function.\n'


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.project=self.base/'kit';self.project.mkdir()
        self.src=self.project/'src';self.src.mkdir()
        self.out=self.base/'out';self.out.mkdir()
        self.original=self.base/'original';self.original.write_text(ORIGINAL)
        self.catalog=self.base/'catalog.json'
        self.catalog.write_text(json.dumps(make_catalog([self.original])))
        self.scope=self.base/'scope.json'
        self.scope.write_text(json.dumps({'version':1,'components':['src'],'artifacts':[str(self.out)]}))
        (self.src/'connector.md').write_text(OWN)

    def scan(self,phase='post'):
        return upstream_artifacts.inspect(self.project,self.catalog,self.scope,phase)

    def gate(self,phase='transfer'):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-upstream-artifacts.py'),
            '--root',str(self.project),'--catalog',str(self.catalog),'--scope',str(self.scope),
            '--phase',phase],capture_output=True,text=True,timeout=10)

    def hook(self,product,event,tool,data=None):
        payload={'hook_event_name':event,'cwd':str(self.project),'tool_name':tool,'tool_input':data or {}}
        p=subprocess.run(['/bin/sh',str(ROOT/'common/base/scripts/run_upstream_guard.sh'),product,
            str(self.project),str(self.catalog),str(self.scope),event],input=json.dumps(payload),
            capture_output=True,text=True,timeout=8)
        self.assertEqual(p.returncode,0,p.stderr)
        return json.loads(p.stdout)

    def test_clean_components_pass(self):
        r=self.scan('assembly');self.assertEqual(r['status'],'pass');self.assertTrue(r['complete'])

    def test_file_count_is_distinct_from_directory_nodes(self):
        r=self.scan('post');self.assertEqual(r['files'],1);self.assertEqual(r['nodes'],3)

    def test_report_binds_declared_scope_and_actual_file_hashes(self):
        r=self.scan('assembly')
        record=r['inventory'][str(self.src/'connector.md')]
        self.assertEqual(record['sha256'],hashlib.sha256(OWN.encode()).hexdigest())
        self.assertEqual(r['scope_fingerprint'],hashlib.sha256(self.scope.read_bytes()).hexdigest())
        self.assertNotIn(OWN,json.dumps(r))

    def test_direct_mutation_api_requires_declared_scope(self):
        from upstream_guard import Guard, Unavailable
        with self.assertRaises(Unavailable):
            Guard(self.project,self.catalog).write(str(self.src/'new'),OWN.encode(),self.project)

    def test_post_finds_actual_created_copy(self):
        (self.src/'renamed').write_text(ORIGINAL)
        r=self.scan();self.assertEqual(r['status'],'block')
        self.assertTrue((self.src/'renamed').exists(),'post check must not delete or roll back')

    def test_similarity_is_not_a_gate_failure(self):
        (self.src/'own-method').write_text(ORIGINAL.replace('preserve','keep'))
        self.assertEqual(self.scan()['status'],'pass')

    def test_partial_text_similarity_remains_noncertified(self):
        (self.src/'own-method').write_text('preface '+ORIGINAL.splitlines()[0]+' explanation')
        r=self.scan();self.assertEqual(r['status'],'pass');self.assertIn('authorship',r['limits'])

    def test_unregistered_source_not_certified(self):
        (self.src/'unregistered').write_text('unknown third-party material')
        r=self.scan();self.assertEqual(r['status'],'pass')
        self.assertIn('unregistered-source',r['limits'])

    def test_hidden_and_ignored_files_are_inspected(self):
        (self.src/'.gitignore').write_text('*.ignored\n')
        (self.src/'.hidden.ignored').write_text(ORIGINAL)
        self.assertEqual(self.scan()['status'],'block')

    def test_untracked_files_do_not_require_git(self):
        self.assertFalse((self.project/'.git').exists())
        (self.src/'untracked').write_text(ORIGINAL)
        self.assertEqual(self.scan()['status'],'block')

    def test_declared_scope_not_all_project_folders(self):
        (self.project/'not-a-component').write_text(ORIGINAL)
        self.assertEqual(self.scan()['status'],'pass')

    def test_scope_has_no_filename_based_exemption(self):
        d=self.src/'_bmad-output';d.mkdir();(d/'copied.txt').write_text(ORIGINAL)
        self.assertEqual(self.scan()['status'],'block')

    def test_transfer_scans_all_expanded_artifact_files(self):
        (self.out/'surprise').write_text(ORIGINAL)
        self.assertEqual(self.scan('assembly')['status'],'pass')
        self.assertEqual(self.scan('transfer')['status'],'block')

    def test_opaque_container_is_not_certified_by_raw_byte_no_match(self):
        import zipfile
        with zipfile.ZipFile(self.out/'not-obvious-name',mode='w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('inside',ORIGINAL)
        self.assertEqual(self.scan('transfer')['status'],'unavailable')
        self.assertEqual(self.gate().returncode,2)

    def test_transfer_requires_artifact_declaration(self):
        self.scope.write_text(json.dumps({'version':1,'components':['src'],'artifacts':[]}))
        self.assertEqual(self.scan('transfer')['status'],'unavailable')

    def test_absent_output_not_misreported_as_transfer_success(self):
        self.out.rmdir()
        self.assertEqual(self.scan('post')['status'],'pass')
        self.assertEqual(self.scan('transfer')['status'],'unavailable')

    def test_missing_component_is_incomplete(self):
        self.scope.write_text(json.dumps({'version':1,'components':['missing'],'artifacts':[]}))
        r=self.scan();self.assertEqual(r['status'],'unavailable');self.assertFalse(r['complete'])

    def test_missing_policy_is_not_pass(self):
        self.catalog.unlink();self.assertEqual(self.scan()['status'],'unavailable')

    def test_changed_original_is_not_automatically_repinned(self):
        self.original.write_text('changed')
        r=self.scan();self.assertEqual(r['status'],'unavailable')
        self.assertNotEqual(json.loads(self.catalog.read_text())['sources'][0]['sha256'],
                            hashlib.sha256(self.original.read_bytes()).hexdigest())

    def test_official_file_reference_is_not_bundled_content(self):
        (self.src/'official-link').symlink_to(self.original)
        self.assertEqual(self.scan()['status'],'pass')

    def test_component_may_be_an_explicit_official_file_reference(self):
        link=self.project/'official-ref';link.symlink_to(self.original)
        self.scope.write_text(json.dumps({'version':1,'components':['official-ref'],'artifacts':[]}))
        r=self.scan('assembly');self.assertEqual(r['status'],'pass');self.assertEqual(r['references'],1)

    def test_declared_internal_reference_cannot_hide_copy(self):
        p=self.src/'copy';p.write_text(ORIGINAL);(self.src/'alias').symlink_to(p)
        self.assertEqual(self.scan()['status'],'block')

    def test_unknown_outside_reference_is_incomplete(self):
        p=self.base/'outside';p.write_text(OWN);(self.src/'link').symlink_to(p)
        self.assertEqual(self.scan()['status'],'unavailable')

    def test_symlink_loop_reports_unavailable_not_crash(self):
        (self.src/'loop').symlink_to('loop')
        self.assertEqual(self.scan()['status'],'unavailable')

    def test_directory_link_does_not_claim_complete_inventory(self):
        (self.src/'dir-link').symlink_to(self.out,target_is_directory=True)
        self.assertEqual(self.scan()['status'],'unavailable')

    def test_artifact_root_directory_link_is_not_resolved_away(self):
        link=self.base/'output-link';link.symlink_to(self.out,target_is_directory=True)
        self.scope.write_text(json.dumps({'version':1,'components':['src'],'artifacts':[str(link)]}))
        self.assertEqual(self.scan('transfer')['status'],'unavailable')

    def test_broken_artifact_root_link_is_incomplete(self):
        link=self.base/'missing-output';link.symlink_to(self.base/'missing',target_is_directory=True)
        self.scope.write_text(json.dumps({'version':1,'components':['src'],'artifacts':[str(link)]}))
        self.assertEqual(self.scan('transfer')['status'],'unavailable')
        self.assertEqual(self.scan('post')['status'],'unavailable')
        for product in ('codex','claude'):
            h=self.hook(product,'PostToolUse','Bash',{'command':'task'})['hookSpecificOutput']
            self.assertIn('unavailable',h['additionalContext'])

    def test_catalog_swap_after_load_cannot_mislabel_inspected_corpus(self):
        from upstream_guard import Guard
        alternate=self.base/'other-original';alternate.write_text('a different synthetic original')
        swapped=json.dumps(make_catalog([alternate]));load=Guard.load;changed=[]
        (self.src/'copy').write_text(ORIGINAL)
        def changing(guard):
            result=load(guard)
            if not changed:self.catalog.write_text(swapped);changed.append(True)
            return result
        with mock.patch.object(Guard,'load',new=changing):
            self.assertEqual(self.scan()['status'],'unavailable')

    def test_outside_patch_hardlink_is_deferred_then_actual_copy_is_found(self):
        local=self.src/'local';local.write_text(OWN)
        alias=self.base/'alias';alias.hardlink_to(local)
        patch='*** Begin Patch\n*** Update File: '+str(alias)+'\n@@\n-'+OWN.splitlines()[0]+'\n+changed\n*** End Patch'
        h=self.hook('codex','PreToolUse','apply_patch',{'command':patch})['hookSpecificOutput']
        self.assertNotIn('permissionDecision',h);self.assertIn('not pre-inspected',h['additionalContext'])
        external=self.base/'plain';external.write_text(OWN)
        moving=('*** Begin Patch\n*** Update File: '+str(external)+'\n*** Move to: '+str(alias)+
                '\n@@\n-'+OWN.splitlines()[0]+'\n+changed\n*** End Patch')
        h=self.hook('codex','PreToolUse','apply_patch',{'command':moving})['hookSpecificOutput']
        self.assertIn('not pre-inspected',h['additionalContext'])
        # A synthetic in-place writer, not a claim about a native patcher's inode handling.
        alias.write_text(ORIGINAL)
        self.assertEqual(self.scan()['status'],'block');self.assertEqual(self.gate('assembly').returncode,2)

    def test_component_file_reference_uses_same_pre_target_identity(self):
        outside=self.base/'referent';outside.write_text(OWN)
        link=self.project/'component-ref';link.symlink_to(outside)
        self.scope.write_text(json.dumps({'version':1,'components':['component-ref'],'artifacts':[]}))
        for path in (link,outside):
            h=self.hook('claude','PreToolUse','Write',{'file_path':str(path),'content':ORIGINAL})['hookSpecificOutput']
            self.assertEqual(h.get('permissionDecision'),'deny')
        self.assertEqual(self.scan('assembly')['status'],'unavailable')

    def test_registered_mutation_tools_cannot_skip_original_target_check(self):
        for product in ('codex','claude'):
            for tool in ('Write','Edit','MultiEdit','NotebookEdit'):
                data={'file_path':str(self.original),'notebook_path':str(self.original),
                      'content':OWN,'old_string':ORIGINAL,'new_string':OWN}
                h=self.hook(product,'PreToolUse',tool,data)['hookSpecificOutput']
                self.assertEqual(h.get('permissionDecision'),'deny',(product,tool,h))

    def test_unreconstructed_structured_changes_hold_only_applicable_targets(self):
        for product in ('codex','claude'):
            for tool in ('MultiEdit','NotebookEdit'):
                for path,expected in ((self.src/'target',True),(self.base/'outside',False)):
                    data={'file_path':str(path),'notebook_path':str(path)}
                    doc=self.hook(product,'PreToolUse',tool,data)
                    if expected:self.assertEqual(doc['hookSpecificOutput'].get('permissionDecision'),'deny')
                    else:self.assertEqual(doc,{})

    def test_codex_write_edit_use_full_candidate_checks(self):
        self.assertEqual(self.hook('codex','PreToolUse','Write',
            {'file_path':str(self.src/'new'),'content':ORIGINAL})['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertEqual(self.hook('codex','PreToolUse','Write',
            {'file_path':str(self.src/'new'),'content':OWN}),{})
        self.assertEqual(self.hook('codex','PreToolUse','Edit',
            {'file_path':str(self.src/'connector.md'),'old_string':OWN,'new_string':ORIGINAL})
            ['hookSpecificOutput']['permissionDecision'],'deny')

    def test_structured_mutation_missing_target_is_not_opaque_execution(self):
        for product in ('codex','claude'):
            for tool in ('Write','Edit','MultiEdit','NotebookEdit'):
                for data in ({},'invalid'):
                    h=self.hook(product,'PreToolUse',tool,data)['hookSpecificOutput']
                    self.assertEqual(h.get('permissionDecision'),'deny',(product,tool))

    def test_transfer_caller_does_not_proceed_after_gate_failure(self):
        marker=self.base/'sent'
        caller=self.base/'sender.py'
        caller.write_text('import subprocess,sys\nfrom pathlib import Path\nr=subprocess.run(sys.argv[2:])\n'
                          'if r.returncode:raise SystemExit(r.returncode)\nPath(sys.argv[1]).write_text("sent")\n')
        command=[sys.executable,str(caller),str(marker),sys.executable,'-B',
                 str(ROOT/'scripts/check-upstream-artifacts.py'),'--root',str(self.project),
                 '--catalog',str(self.catalog),'--scope',str(self.scope),'--phase','transfer']
        (self.out/'copy').write_text(ORIGINAL)
        for mode in ('copy','missing-output','bad-policy'):
            if mode=='missing-output':(self.out/'copy').unlink();self.out.rmdir()
            if mode=='bad-policy':self.out.mkdir();self.catalog.write_text('bad')
            bad=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(bad.returncode,2,mode);self.assertFalse(marker.exists(),mode)
        self.catalog.write_text(json.dumps(make_catalog([self.original])))
        good=subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual(good.returncode,0,good.stderr);self.assertTrue(marker.exists())

    def test_policy_change_during_inspection_is_incomplete(self):
        read=upstream_artifacts.bounded_read
        for policy in (self.scope,self.catalog):
            original=policy.read_bytes(); changed=[]
            def mutating(path):
                data=read(path)
                if Path(path)==self.src/'connector.md' and not changed:
                    policy.write_bytes(original+b' ');changed.append(True)
                return data
            with mock.patch.object(upstream_artifacts,'bounded_read',side_effect=mutating):
                self.assertEqual(self.scan()['status'],'unavailable')
            policy.write_bytes(original)

    def test_observed_node_change_during_read_is_incomplete(self):
        read=upstream_artifacts.bounded_read;changed=[]
        def mutating(path):
            data=read(path)
            if Path(path)==self.src/'connector.md' and not changed:
                Path(path).write_text(OWN+'extra');changed.append(True)
            return data
        with mock.patch.object(upstream_artifacts,'bounded_read',side_effect=mutating):
            self.assertEqual(self.scan()['status'],'unavailable')

    def test_inventory_limits_hold_on_boundary_and_reject_excess(self):
        with mock.patch.object(upstream_artifacts,'MAX_NODES',3):
            self.assertEqual(self.scan()['status'],'pass')
            (self.src/'extra').write_text('own')
            self.assertEqual(self.scan()['status'],'unavailable')
        (self.src/'extra').unlink()
        with mock.patch.object(upstream_artifacts,'MAX_TOTAL_BYTES',len(OWN.encode())):
            self.assertEqual(self.scan()['status'],'pass')
            (self.src/'extra').write_text('own')
            self.assertEqual(self.scan()['status'],'unavailable')

    def test_scope_cannot_escape_source_project(self):
        self.scope.write_text(json.dumps({'version':1,'components':['../'],'artifacts':[]}))
        self.assertEqual(self.scan()['status'],'unavailable')

    def test_observed_concurrent_change_invalidates_snapshot(self):
        original=upstream_artifacts._snapshot
        calls=[]
        def changing(*args):
            result=original(*args);calls.append(1)
            if len(calls)==1:(self.src/'connector.md').write_text(ORIGINAL)
            return result
        with mock.patch.object(upstream_artifacts,'_snapshot',side_effect=changing):r=self.scan()
        self.assertEqual(r['status'],'unavailable')

    def test_previous_pass_is_not_reused(self):
        first=self.scan();(self.src/'copy').write_text(ORIGINAL)
        second=self.scan()
        self.assertEqual(first['status'],'pass');self.assertEqual(second['status'],'block')
        self.assertNotEqual(first['fingerprint'],second['fingerprint'])

    def test_rescan_can_resolve_post_inspection_failure(self):
        saved=self.catalog.read_bytes();self.catalog.write_text('bad')
        self.assertEqual(self.scan()['status'],'unavailable')
        self.catalog.write_bytes(saved)
        self.assertEqual(self.scan()['status'],'pass')

    def test_no_files_mutated_or_logged_by_inspection(self):
        before={str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.scan();self.scan('transfer')
        after={str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_gate_exit_and_current_report(self):
        good=self.gate();self.assertEqual(good.returncode,0,good.stderr)
        (self.out/'copy').write_text(ORIGINAL)
        bad=self.gate();self.assertEqual(bad.returncode,2)
        self.assertEqual(json.loads(bad.stdout)['status'],'block')

    def test_fixture_assembly_caller_consumes_gate_failure(self):
        marker=self.base/'built'
        caller=self.base/'caller.py'
        caller.write_text('import subprocess,sys\nfrom pathlib import Path\nr=subprocess.run(sys.argv[2:])\n'
                          'if r.returncode:raise SystemExit(r.returncode)\nPath(sys.argv[1]).write_text("built")\n')
        command=[sys.executable,str(caller),str(marker),sys.executable,'-B',
                 str(ROOT/'scripts/check-upstream-artifacts.py'),'--root',str(self.project),
                 '--catalog',str(self.catalog),'--scope',str(self.scope),'--phase','assembly']
        (self.src/'copy').write_text(ORIGINAL)
        bad=subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual(bad.returncode,2);self.assertFalse(marker.exists())
        (self.src/'copy').unlink()
        good=subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual(good.returncode,0,good.stderr);self.assertTrue(marker.exists())

    def test_normal_python_precheck_does_not_deny(self):
        for product in ('codex','claude'):
            doc=self.hook(product,'PreToolUse','Bash',{'command':'python3 -m unittest'})
            h=doc['hookSpecificOutput']
            self.assertNotIn('permissionDecision',h)
            self.assertIn('not pre-inspected',h['additionalContext'])

    def test_unknown_command_does_not_load_broken_provenance_policy_as_global_deny(self):
        self.catalog.unlink();self.scope.unlink()
        h=self.hook('codex','PreToolUse','Bash',{'command':'python3 -m unittest'})['hookSpecificOutput']
        self.assertNotIn('permissionDecision',h)
        self.assertIn('not pre-inspected',h['additionalContext'])
        self.assertEqual(self.gate('assembly').returncode,2)

    def test_unknown_mcp_precheck_not_a_safe_certificate(self):
        doc=self.hook('codex','PreToolUse','mcp__unknown__effect')
        self.assertNotIn('permissionDecision',doc['hookSpecificOutput'])
        self.assertIn('not pre-inspected',doc['hookSpecificOutput']['additionalContext'])

    def test_python_created_copy_is_reported_then_gate_blocks(self):
        for product in ('codex','claude'):
            data={'command':'python3 writer.py'}
            pre=self.hook(product,'PreToolUse','Bash',data)
            self.assertNotIn('permissionDecision',pre['hookSpecificOutput'])
            subprocess.run([sys.executable,'-c','from pathlib import Path;import sys;Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes())',
                            str(self.original),str(self.src/'python-result')],check=True,timeout=5)
            post=self.hook(product,'PostToolUse','Bash',data)['hookSpecificOutput']
            self.assertEqual(post['hookEventName'],'PostToolUse')
            self.assertNotIn('permissionDecision',post)
            self.assertIn('block',post['additionalContext']);self.assertIn('not undone',post['additionalContext'])
            self.assertTrue((self.src/'python-result').exists())
            self.assertEqual(self.gate('assembly').returncode,2)
            (self.src/'python-result').unlink()

    def test_normal_own_change_post_is_quiet_and_gate_fresh(self):
        (self.src/'generated').write_text('own result')
        for product in ('codex','claude'):
            self.assertEqual(self.hook(product,'PostToolUse','Bash',{'command':'python3 build.py'}),{})
        self.assertEqual(self.gate('assembly').returncode,0)

    def test_failed_claude_tool_partial_write_is_inspected(self):
        (self.src/'partial').write_text(ORIGINAL)
        h=self.hook('claude','PostToolUseFailure','Bash',{'command':'failed task'})['hookSpecificOutput']
        self.assertEqual(h['hookEventName'],'PostToolUseFailure')
        self.assertIn('block',h['additionalContext']);self.assertNotIn('permissionDecision',h)
        self.assertEqual(self.gate('assembly').returncode,2)

    def test_readonly_post_skips_collection_not_downstream_gate(self):
        self.catalog.write_text('bad policy')
        self.assertEqual(self.hook('codex','PostToolUse','Read',{'file_path':'src/connector.md'}),{})
        self.assertEqual(self.gate('assembly').returncode,2)

    def test_post_error_is_report_not_pre_deny(self):
        self.catalog.unlink()
        h=self.hook('codex','PostToolUse','Bash',{'command':'python3 build.py'})['hookSpecificOutput']
        self.assertIn('unavailable',h['additionalContext']);self.assertNotIn('permissionDecision',h)
        self.assertEqual(self.gate('assembly').returncode,2)

    def test_outside_hardlink_changes_are_seen_in_declared_inventory(self):
        local=self.src/'local';local.write_text(OWN)
        alias=self.base/'alias';alias.hardlink_to(local)
        alias.write_text(ORIGINAL)
        self.assertEqual(self.scan()['status'],'block')

    def test_pre_file_mutation_outside_components_is_not_general_project_ban(self):
        for product in ('codex','claude'):
            path=str(self.project/'not-a-component')
            data={'file_path':path,'content':ORIGINAL};tool='Write'
            if product=='codex':
                data={'command':f'*** Begin Patch\n*** Add File: {path}\n'+''.join('+'+l+'\n' for l in ORIGINAL.splitlines())+'*** End Patch'}
                tool='apply_patch'
            self.assertEqual(self.hook(product,'PreToolUse',tool,data),{})

    def test_actual_artifact_destination_is_prechecked(self):
        doc=self.hook('claude','PreToolUse','Write',{'file_path':str(self.out/'copy'),'content':ORIGINAL})
        self.assertEqual(doc['hookSpecificOutput']['permissionDecision'],'deny')

    def test_catalog_v1_is_not_silently_reinterpreted(self):
        self.catalog.write_text(json.dumps({'version':1,'window':16,'sources':[]}))
        self.assertEqual(self.gate('assembly').returncode,2)

    def test_rendered_events_and_arguments_match_each_phase(self):
        import shlex
        spec=importlib.util.spec_from_file_location('renderer',ROOT/'scripts/render-upstream-hook.py')
        renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        for product in ('codex','claude'):
            doc=renderer.render(product,ROOT,self.project,self.catalog,self.scope)
            expected={'PreToolUse','PostToolUse'}|({'PostToolUseFailure'} if product=='claude' else set())
            self.assertEqual(set(doc['hooks']),expected)
            for event,groups in doc['hooks'].items():
                command=groups[0]['hooks'][0]['command']
                self.assertEqual(shlex.split(command)[-2:],[str(self.scope),event])
                payload={'hook_event_name':event,'cwd':str(self.project),'tool_name':'Bash','tool_input':{'command':'python3 -m unittest'}}
                p=subprocess.run(['/bin/sh','-c',command],input=json.dumps(payload),capture_output=True,text=True,timeout=8)
                self.assertEqual(p.returncode,0,p.stderr)
                result=json.loads(p.stdout)
                if event=='PreToolUse':self.assertIn('not pre-inspected',result['hookSpecificOutput']['additionalContext'])
                else:self.assertEqual(result,{})


if __name__=='__main__':unittest.main()
