"""The shared source must be complete without personal operations installed."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PublicBoundaryTests(unittest.TestCase):
    def test_no_personal_operational_entrypoints(self):
        skills=ROOT/'common/base/skills'
        self.assertFalse(list(skills.glob('homelab*')))
        self.assertFalse((skills/'artifact-backup').exists())
        self.assertTrue((skills/'document/SKILL.md').is_file())
        self.assertTrue((skills/'project/SKILL.md').is_file())
    def test_record_policy_retains_general_semantics(self):
        text=(ROOT/'common/base/skills/document/references/implementations/local-markdown.md').read_text()
        self.assertIn('BMAD 작업 공간',text)
        self.assertNotIn('### BMAD 산출물 백업',text)
    def test_no_personal_hook_or_backup_runtime_in_shared_payload(self):
        import json
        for product in ('claude', 'codex'):
            hooks = json.loads((ROOT / f'adapters/{product}/hooks/hooks.json').read_text())
            self.assertEqual({'PreToolUse'}, set(hooks['hooks']))
            self.assertIn('commit-guard.py', hooks['hooks']['PreToolUse'][0]['hooks'][0]['command'])
            self.assertNotIn('backup', str(hooks))
        self.assertFalse(list((ROOT/'common/base/scripts').glob('*backup*')))
if __name__=='__main__':unittest.main()
