"""Reform-specific regressions; synthetic inputs, never a native hook claim."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock

from test_secret_legacy import GuardFixture, guard, PRODUCTS, ROOT, REAL_TRUSTED_SCANNER


class Revision(GuardFixture):
    def test_audit_missing_shell_fields_fail_closed(self):
        for payload in ({}, {'tool_name':'Bash'}, {'tool_name':'Bash','tool_input':None},
                        {'tool_name':'Bash','tool_input':{'command':None}},
                        {'tool_name':'Bash','tool_input':{'command':[1]}},
                        {'tool_name':'exec_command','tool_input':{'cmd':['git','\x00']}}):
            for product in PRODUCTS:
                self.assertEqual('deny',PRODUCTS[product].input_response(payload)['hookSpecificOutput']['permissionDecision'])

    def test_audit_quoted_operators_are_argument_values(self):
        for sep in (';', '\n', '&&', '(', ')'):
            import shlex
            for flag in ('-a','--all','--no-verify'):
                self.assertIsNotNone(guard.command_reason('git commit -m '+shlex.quote(sep)+' '+flag))
            self.assertIsNone(guard.command_reason('echo '+shlex.quote(sep)+' git add .'))

    def test_audit_git_option_values_wrappers_and_pathspec(self):
        for command in ('git commit --author "-a" -m fixture','git commit -Sabc -m fixture',
                        'git commit --date "-n" -m fixture','git commit -tannotation -m fixture',
                        'git commit -t annotation -m fixture','git commit --template=annotation -m fixture'):
            self.assertIsNone(guard.command_reason(command))
        for command in ('git commit --message=fixture -an','env -i git commit -am fixture',
                        'git add --pathspec-from-file=-','git commit -S -a -m fixture',
                        'git commit -tannotation -a -m fixture'):
            self.assertIsNotNone(guard.command_reason(command))

    def test_audit_disclosure_continuations(self):
        for command in ('print\\\nenv','echo "$TO\\\nKEN"','printf "%s" "$API_\\\nKEY"'):
            self.assertIsNotNone(guard.disclosure_reason(command))
        self.assertIsNone(guard.disclosure_reason("echo '$TO\\\nKEN'"))

    def test_native_candidates_preserve_nested_raw_strings(self):
        value={'content':[{'text':'line1\nline2\r\n"quote"\\backslash'}]}
        candidates=guard.native_candidates(value)
        self.assertIn(value['content'][0]['text'].encode(),candidates)
        self.assertIn(json.dumps(value,ensure_ascii=False).encode(),candidates)
        self.assertEqual(guard.safe_findings([{'RuleID':'unknown'}])['rules'],['other-rule'])
        with self.assertRaises(guard.GuardError):guard.native_candidates([None]*65536)

    def test_pre_keeps_safe_diagnostic_and_policy_kind_is_distinct(self):
        error=guard.GuardError('secret detected',{'count':1,'rules':['generic-api-key']})
        with mock.patch.object(guard,'scan',side_effect=error):
            for product in PRODUCTS:
                r=PRODUCTS[product].input_response({'tool_name':'Write','tool_input':{'content':'synthetic'}})
                self.assertIn('stage=input',r['hookSpecificOutput']['permissionDecisionReason'])
                self.assertIn('generic-api-key',r['hookSpecificOutput']['permissionDecisionReason'])
        self.stage('evidence/local','safe')
        r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-git-secrets.py'),'index',
            '--repo',str(self.repo),'--policy',str(self.policy)],capture_output=True,text=True)
        self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)['status'],'policy_violation')

    def test_reported_multiline_commit_does_not_consume_next_options(self):
        lines=['git commit -m "feat: add dedicated reader with reading position resume"',
               'git rev-parse HEAD','git status --short','playwright-cli -s=ieo-reader close']
        for separator in ('\n','\r\n','; ',' && '):
            for product in PRODUCTS:
                self.assertEqual({},guard.agent(product,{'tool_name':'Bash','tool_input':{'command':separator.join(lines)}}))

    def test_multiline_still_checks_each_actual_git_command(self):
        for command in ('git commit -m "safe"\ngit add .',
                        'echo safe\ngit commit -am unsafe',
                        'echo safe\ngit push --no-verify',
                        'echo safe\nenv SKIP=gitleaks git commit -m fixture'):
            self.assertIsNotNone(guard.command_reason(command))

    def test_quoted_and_continued_lines_are_data_or_same_command(self):
        self.assertIsNone(guard.command_reason('git commit -m "prose\n-a is text"'))
        self.assertIsNone(guard.command_reason('echo "git add ."'))
        self.assertIsNotNone(guard.command_reason('git commit \\\n -a -m unsafe'))

    def test_source_edit_is_not_shell_execution(self):
        for product in PRODUCTS:
            self.assertEqual({},guard.agent(product,{'tool_name':'Write',
                'tool_input':{'command':'git add .','content':'def example(): return 1'}}))

    def test_quoted_cat_source_body_does_not_become_shell_commands(self):
        command="cat > file.py <<'EOF'\nresult = sorted(set(rules))\ngit add .\nEOF\nprintf safe"
        for product in PRODUCTS:
            self.assertEqual({},guard.agent(product,{'tool_name':'Bash','tool_input':{'command':command}}))
            for tail in ('\nprintenv','\ngit commit -am unsafe'):
                self.assertEqual('deny',guard.agent(product,{'tool_name':'Bash',
                    'tool_input':{'command':command+tail}})['hookSpecificOutput']['permissionDecision'])
            for unsafe in (command.replace('> file.py','.env > file.py'),
                           command.replace('sorted(set(rules))','SYNTHETIC_SECRET'),
                           "cat /dev/null # <<'EOF'\ngit commit -am fixture\nEOF"):
                self.assertEqual('deny',guard.agent(product,{'tool_name':'Bash',
                    'tool_input':{'command':unsafe}})['hookSpecificOutput']['permissionDecision'])
            self.assertEqual({},guard.agent(product,{'tool_name':'Bash',
                'tool_input':{'command':command.replace('file.py','"file#name.py"')}}))
        with self.assertRaises(guard.GuardError):
            guard.scan([b'SYNTHETIC_SECRET'],self.scanner)

    def test_safe_metadata_never_copies_rule_or_path_values(self):
        result=guard.safe_findings([{'File':'SENSITIVE_PATH','RuleID':'SENSITIVE_ID','Secret':'SENSITIVE_VALUE'},
                                    {'File':'x','RuleID':'generic-api-key'}])
        self.assertEqual(result,{'count':2,'rules':['generic-api-key','other-rule']})
        text=guard.notice({'status':'finding','diagnostic':result})
        self.assertNotIn('SENSITIVE',text);self.assertIn('findings=2',text)
        self.assertIn('generic-api-key',text)

    def python_payload(self, body, header="python3 - <<'PY'", tail=''):
        return header + '\n' + body + '\nPY\n' + tail

    def assert_shell_decision(self, command, allowed):
        for product, adapter in PRODUCTS.items():
            for tool, field in (('Bash', 'command'), ('exec_command', 'cmd')):
                with self.subTest(product=product, tool=tool, command=command):
                    result = adapter.input_response({'tool_name': tool, 'tool_input': {field: command}})
                    if allowed:
                        self.assertEqual({}, result)
                    else:
                        self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])

    def test_python_quoted_stdin_set_is_not_shell_environment_dump(self):
        for header in ("python3 - <<'PY'", 'python - <<"PY"',
                       "/usr/bin/python3 -B -u - <<'PY'", "python3 -I -E -s -S - <<'PY'"):
            for body in ("print(sorted(set(['a']) - set(['b'])))",
                         "print('git add .; printenv TOKEN')",
                         "rules = {'x'}\nprint(sorted(set(rules)))"):
                self.assert_shell_decision(self.python_payload(body, header), True)

    def test_python_stdin_actual_disclosures_and_tail_remain_denied(self):
        for body in ('import os\nprint(os.environ)',
                     'import os\nif True:\n    print(os.getenv("TOKEN"))',
                     'print(open(".env").read())'):
            self.assert_shell_decision(self.python_payload(body), False)
        for tail in ('printenv', 'set', 'git add .', 'git commit -am fixture'):
            self.assert_shell_decision(self.python_payload('print(set())', tail=tail), False)
        self.assert_shell_decision(self.python_payload('print(set())', tail='printf safe'), True)

    def test_python_stdin_raw_secret_and_body_bytes_preserved(self):
        command = self.python_payload("print('SYNTHETIC_SECRET')")
        self.assert_shell_decision(command, False)
        body = "print('a\\\\b')\nprint('set(\\\n)')"
        view = guard.literal_command_view(self.python_payload(body))
        self.assertEqual(guard.python_inline_source(guard.literal_tokens(view)[:-1]), body + '\n')
        self.assertIn(command.encode(), guard.native_candidates({'command': command}))

    def test_python_stdin_child_process_literals_are_checked(self):
        for call in ('subprocess.run(["env"])', 'subprocess.check_output(("printenv", "TOKEN"))',
                     'subprocess.Popen(["git", "add", "."])',
                     'subprocess.run("git commit -am fixture", shell=True)',
                     'subprocess.getoutput("printenv")', 'os.system("printenv")',
                     'os.popen("cat .env")'):
            self.assert_shell_decision(self.python_payload('import subprocess, os\n' + call), False)
        for call in ('subprocess.run(["printf", "git add .; printenv"])',
                     'subprocess.run("git add .", shell=False)',
                     'subprocess.run(["printf", "safe"])'):
            self.assert_shell_decision(self.python_payload('import subprocess\n' + call), True)

    def test_python_stdin_multiple_blocks_and_real_shell_positions(self):
        first = self.python_payload('print(set())')
        self.assert_shell_decision(first + self.python_payload('print(set())'), True)
        self.assert_shell_decision(first + self.python_payload('import os\nprint(os.environ)'), False)
        self.assert_shell_decision('printenv\n' + first, False)
        self.assert_shell_decision(self.python_payload('print(set())').replace('\n', '\r\n'), True)
        self.assert_shell_decision(self.python_payload('not valid Python', tail='printenv'), False)

    def test_unknown_python_headers_do_not_hide_shell_commands(self):
        for header in ("python3 - <<PY", "python3 - <<'PY' # comment",
                       "python3 - <<'PY' | printenv", "python3 - <<'PY'; printenv",
                       "python3 - <<'PY' > file"):
            command = self.python_payload('printenv', header)
            self.assertEqual(command, guard.literal_command_view(command))
        self.assert_shell_decision("python3 - <<'PY'\nprintenv\nMISSING\n", False)

    def test_nested_literal_python_calls_and_inspection_limit(self):
        import shlex
        child = 'printenv'
        for _ in range(3):
            child = shlex.join(['python3', '-c', 'import os; os.system(' + repr(child) + ')'])
        self.assert_shell_decision(child, False)
        calls = '\n'.join('os.system("printf safe")' for _ in range(33))
        self.assert_shell_decision(self.python_payload('import os\n' + calls), False)

    def test_result_inspection_error_is_not_finding(self):
        payload={'tool_name':'mcp__fixture__get_site','tool_response':{'title':'synthetic'}}
        with mock.patch.object(guard,'scan',side_effect=guard.GuardError('scanner failed')):
            self.assertEqual(guard.inspect_output(payload)['status'],'error')
            for product in PRODUCTS:
                r=PRODUCTS[product].output_response(payload)
                self.assertFalse(r['continue']);self.assertIn('failed',json.dumps(r))

    def test_metadata_finding_both_product_outputs(self):
        payload={'tool_name':'mcp__fixture__get_site','tool_response':{'content':'SENSITIVE_PAYLOAD'}}
        error=guard.GuardError('secret detected',{'count':1,'rules':['generic-api-key']})
        with mock.patch.object(guard,'scan',side_effect=error):
            for product in PRODUCTS:
                r=PRODUCTS[product].output_response(payload)
                self.assertNotIn('SENSITIVE_PAYLOAD',json.dumps(r));self.assertIn('generic-api-key',json.dumps(r))

    def test_git_cli_uses_explicit_policy_and_nonzero_failure(self):
        self.stage('fixture','SYNTHETIC_SECRET')
        run=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-git-secrets.py'),
            'index','--repo',str(self.repo),'--policy',str(self.policy)],capture_output=True,text=True)
        self.assertEqual(run.returncode,2);self.assertEqual(json.loads(run.stdout)['status'],'finding')
        self.assertNotIn('SYNTHETIC_SECRET',run.stdout+run.stderr)

    def test_renderer_and_real_adapter_subprocess_clean_payload(self):
        spec=importlib.util.spec_from_file_location('render_secret',ROOT/'scripts/render-secret-hook.py')
        render=importlib.util.module_from_spec(spec);spec.loader.exec_module(render)
        for product in PRODUCTS:
            doc=render.render(product,ROOT,Path(sys.executable))
            for event,groups in doc['hooks'].items():
                data={'hook_event_name':event,'cwd':str(self.repo),'tool_name':'Bash',
                      'tool_input':{'command':'printf safe'},'tool_response':{'stdout':'safe'},'error':'ordinary failure'}
                run=subprocess.run(['/bin/sh','-c',groups[0]['hooks'][0]['command']],input=json.dumps(data),
                    capture_output=True,text=True,timeout=45)
                self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout),{})


class RealChecksums(GuardFixture):
    def setUp(self):
        super().setUp()
        self.scanner=REAL_TRUSTED_SCANNER()

    def lines(self,n=4):
        return ''.join('cloud.google.com/go/auth v1.2.3 h1:'+
            base64.b64encode(hashlib.sha256(('synthetic '+str(i)).encode()).digest()).decode()+'\n' for i in range(n))

    def test_lf_crlf_first_later_blank_final_lines(self):
        for newline in ('\n','\r\n'):
            for count in (1,2,12):
                text=self.lines(count).replace('\n',newline)
                for content in (text,text.rstrip('\r\n'),newline+text,text+newline):
                    guard.scan([('nested/go.sum',content.encode())],self.scanner)

    def test_multiline_contamination_and_other_files_remain_detected(self):
        fake='ghp_'+hashlib.sha256(b'synthetic never real account').hexdigest()[:36]
        for label,data in [('other.txt',self.lines()),('go.sum',self.lines().replace('h1:','h2:')),
                           ('go.sum',self.lines()+fake),('go.sum',self.lines().rstrip()+fake)]:
            with self.assertRaisesRegex(guard.GuardError,'secret detected'):
                guard.scan([(label,data.encode())],self.scanner)

    def test_real_scanner_reports_safe_rule_identifier(self):
        with self.assertRaises(guard.GuardError) as error:
            guard.scan([('go.sum',self.lines().replace('h1:','h2:').encode())],self.scanner)
        self.assertIn('generic-api-key',error.exception.diagnostic['rules'])
        self.assertNotIn('h2:',str(error.exception))

    def test_index_and_outgoing_multiline_checksum(self):
        self.stage('go.sum',self.lines())
        guard.check_index(self.repo,self.policy)
        tip=self.commit()
        guard.check_push(self.repo,self.policy,self.push_data(tip))

    def test_synthetic_multiline_key_shape_nested_mcp(self):
        body=base64.b64encode(b'synthetic invalid key bytes never a real private key'*8).decode()
        key='-----BEGIN PRIVATE KEY-----\n'+body[:64]+'\n'+body[64:]+'\n-----END PRIVATE KEY-----'
        with self.assertRaises(guard.GuardError):guard.scan([key.encode()],self.scanner)
        for product in PRODUCTS:
            payload={'tool_name':'mcp__fixture__document','tool_response':{'content':[{'type':'text','text':key}]}}
            r=PRODUCTS[product].output_response(payload)
            self.assertNotIn('BEGIN PRIVATE',json.dumps(r));self.assertIn('withheld',json.dumps(r))
