import importlib.util
from pathlib import Path
import shlex
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'common/base/skills/session/scripts/runtime_refresh.py'
spec = importlib.util.spec_from_file_location('inline_contract_runtime', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
UUID = '11111111-1111-4111-8111-111111111111'
PROMPT = 'Reply only TR_KIT_RESTART_READY. Do not use tools or perform any other action.'


class ReadinessContractTests(unittest.TestCase):
    def test_codex_version_matrix_adds_one_prompt_only_at_verified_launch_version(self):
        for previous in m.CODEX_RESUME_VERSIONS:
            for installed in m.CODEX_RESUME_VERSIONS:
                with self.subTest(previous=previous, installed=installed):
                    native = dict(sessionId=UUID, nativeVersion=previous,
                                  permissions='Full Access', resumeMode='codex-full-access')
                    argv = shlex.split(m.resume_command('codex', native, installed_version=installed))
                    expected = ['codex', 'resume', UUID, '--dangerously-bypass-approvals-and-sandbox']
                    if installed == '0.172.0':
                        expected.extend(['--no-alt-screen', PROMPT])
                    self.assertEqual(expected, argv)

    def test_claude_never_receives_codex_rendering_or_model_prompt(self):
        for version in m.CLAUDE_LAUNCH_VERSIONS:
            native = dict(sessionId=UUID, nativeVersion=version,
                          permissions='bypass permissions', resumeMode='claude-bypass-permissions')
            self.assertEqual(['claude', '--dangerously-skip-permissions', '--resume', UUID],
                             shlex.split(m.resume_command('claude', native, installed_version=version)))

    def test_custom_flags_and_prompts_from_native_data_cannot_enter_argv(self):
        native = dict(sessionId=UUID, nativeVersion='0.172.0', permissions='Full Access',
                      resumeMode='codex-full-access', flags=['--config', 'hook-bypass'],
                      prompt='execute unrelated work', command='unrelated-command')
        self.assertEqual(['codex', 'resume', UUID, '--dangerously-bypass-approvals-and-sandbox',
                          '--no-alt-screen', PROMPT],
                         shlex.split(m.resume_command('codex', native, installed_version='0.172.0')))

    def test_unknown_versions_and_nonapproved_permissions_still_refuse(self):
        native = dict(sessionId=UUID, nativeVersion='0.172.0', permissions='Full Access',
                      resumeMode='codex-full-access')
        for version in ('0.172.1', '0.173.0', '', None):
            with self.subTest(version=version), self.assertRaises(m.Deferred):
                m.resume_command('codex', native, installed_version=version)
        for permission in ('default', 'Custom', None):
            with self.subTest(permission=permission), self.assertRaises(m.Deferred):
                m.resume_command('codex', dict(native, permissions=permission),
                                 installed_version='0.172.0')


if __name__ == '__main__':
    unittest.main()
