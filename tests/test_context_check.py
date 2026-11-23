"""Declared-read invariants and legacy comparison behavior in isolated fixtures."""
import builtins
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('g3_context',ROOT/'common/base/scripts/context_check.py')
context=importlib.util.module_from_spec(spec);spec.loader.exec_module(context)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'skills/demo').mkdir(parents=True)
        self.skill=self.root/'skills/demo/SKILL.md'
        self.skill.write_text('---\nname: demo\ndescription: Demo\n---\nBody\n')
        self.guide=self.root/'guide.md'
        self.guide.write_text('# Guide\n## Pick\nsmall\n```md\n## Not a heading\n```\n## Other\nlarge\n')
        self.read={'path':'guide.md'}

    def case(self,**kw):return {'name':'fixture','before':[self.read],'after':[self.read],**kw}

    def test_section_boundary_ignores_code_examples(self):
        text=context.read_text(self.root,{'path':'guide.md','section':'Pick'})
        self.assertIn('Not a heading',text);self.assertNotIn('large',text)

    def test_full_skill_is_required(self):
        with self.assertRaisesRegex(ValueError,'full'):
            context.read_text(self.root,{'path':'skills/demo/SKILL.md','section':'Body'})

    def test_missing_and_outside_reads_fail_without_contents(self):
        for item in [{'path':'guide.md','section':'Missing'},{'path':'../outside'},{'path':str(self.guide)}]:
            with self.subTest(item=item),self.assertRaises(ValueError):context.read_text(self.root,item)

    def test_added_duplicate_fails_legacy_comparison(self):
        report=context.compare(self.root,self.root,[self.case(after=[self.read,self.read])])
        self.assertFalse(report['passed']);self.assertEqual(len(self.guide.read_text()),report['cases'][0]['after']['duplicate_chars'])

    def test_dynamic_exclusion_reported_not_zero_measured(self):
        report=context.compare(self.root,self.root,[self.case(unmeasured=['CLI guide'])])
        self.assertTrue(report['passed']);case=report['cases'][0]
        self.assertEqual(['CLI guide'],case['unmeasured']);self.assertEqual(['CLI guide'],case['unmeasured_after'])
        self.assertIn('not zero',case['coverage'])

    def test_measure_only_reports_increase_without_gate(self):
        report=context.compare(self.root,self.root,[self.case(after=[self.read,self.read])],check_growth=False)
        self.assertEqual('measured',report['status']);self.assertIsNone(report['passed'])
        self.assertGreater(report['cases'][0]['delta_chars'],0)

    def test_raw_unicode_and_crlf_count_without_normalization(self):
        data='한글🙂\r\nnext\r\n';self.guide.write_bytes(data.encode())
        result=context.measure(self.root,[self.read])
        self.assertEqual(len(data),result['chars']);self.assertNotEqual(len(data.encode()),result['chars'])
        self.assertEqual(0,result['duplicate_chars'])

    def test_full_file_section_overlap_counted_in_either_order(self):
        selected={'path':'guide.md','section':'Pick'};size=len(context.read_text(self.root,selected))
        for reads in [[self.read,selected],[selected,self.read]]:
            result=context.measure(self.root,reads)
            self.assertEqual(size,result['duplicate_chars']);self.assertEqual(0,result['exact_repeat_chars'])
            self.assertEqual(len(self.guide.read_text()),result['unique_chars'])

    def test_three_repeated_sections_have_two_rereads(self):
        selected={'path':'guide.md','section':'Pick'}
        result=context.measure(self.root,[selected,selected,selected]);size=len(context.read_text(self.root,selected))
        self.assertEqual(3*size,result['chars']);self.assertEqual(2*size,result['duplicate_chars'])
        self.assertEqual(2*size,result['exact_repeat_chars']);self.assertEqual(size,result['unique_chars'])

    def test_canonical_aliases_count_as_same_file(self):
        (self.root/'alias.md').symlink_to(self.guide)
        result=context.measure(self.root,[self.read,{'path':'./guide.md'},{'path':'alias.md'}])
        self.assertEqual(2*len(self.guide.read_text()),result['duplicate_chars'])

    def test_cross_file_same_words_not_inferred_as_duplicate(self):
        (self.root/'copy.md').write_bytes(self.guide.read_bytes())
        result=context.measure(self.root,[self.read,{'path':'copy.md'}]);self.assertEqual(0,result['duplicate_chars'])

    def test_symlink_escape_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as outside:
            p=Path(outside)/'not-authorized';p.write_text('do not read')
            (self.root/'escape').symlink_to(p)
            with self.assertRaisesRegex(ValueError,'escapes'):context.read_text(self.root,{'path':'escape'})

    def test_short_or_other_fence_does_not_end_code_example(self):
        self.guide.write_text('## Pick\n````md\n```\n~~~\n## Fake\n````\nbody\n## Stop\nend\n')
        selected=context.read_text(self.root,{'path':'guide.md','section':'Pick'})
        self.assertIn('## Fake',selected);self.assertIn('body',selected);self.assertNotIn('end',selected)

    def test_tilde_fence_and_four_space_code_heading_not_section(self):
        self.guide.write_text('## Pick ###\n~~~\n## Fake\n~~~\n    ## Indented\n## Stop\nend\n')
        selected=context.read_text(self.root,{'path':'guide.md','section':'Pick'})
        self.assertIn('Indented',selected);self.assertNotIn('end',selected)
        with self.assertRaises(ValueError):context.read_text(self.root,{'path':'guide.md','section':'Fake'})

    def test_nested_section_boundary_and_ambiguous_heading(self):
        self.guide.write_text('# Guide\n## Pick\na\n### Nested\nb\n## Other\nc\n')
        selected=context.read_text(self.root,{'path':'guide.md','section':'Pick'})
        self.assertIn('Nested',selected);self.assertNotIn('Other',selected)
        self.guide.write_text('## Pick\na\n## Pick\nb\n')
        with self.assertRaisesRegex(ValueError,'ambiguous'):context.read_text(self.root,{'path':'guide.md','section':'Pick'})

    def test_source_layout_discovery_and_explicit_scope(self):
        target=self.root/'common/base/skills';target.parent.mkdir(parents=True)
        (self.root/'skills').rename(target)
        result=context.discovery(self.root);self.assertEqual(1,result['skills']);self.assertEqual(8,result['name_description_chars'])
        (self.root/'skills').mkdir()
        with self.assertRaisesRegex(ValueError,'explicit'):context.discovery(self.root)
        self.assertEqual(1,context.discovery(self.root,'common/base/skills')['skills'])

    def test_missing_or_empty_discovery_is_not_zero(self):
        self.skill.unlink()
        with self.assertRaisesRegex(ValueError,'zero-cost'):context.discovery(self.root)

    def test_invalid_frontmatter_types_and_yaml_withheld(self):
        for text in ['no frontmatter','---\nname: demo\ndescription: [list]\n---\n',
                     '---\nname: [\ndescription: PRIVATE_SOURCE_MARKER\n---\n']:
            self.skill.write_text(text)
            with self.assertRaises(ValueError) as caught:context.discovery(self.root)
            self.assertNotIn('PRIVATE_SOURCE_MARKER',str(caught.exception))

    def test_metadata_crlf_and_yaml_block_description(self):
        self.skill.write_bytes(b'---\r\nname: demo\r\ndescription: |\r\n  Line one\r\n  Line two\r\n---\r\nBody\r\n')
        result=context.discovery(self.root)
        self.assertEqual(len('demo')+len('Line one\nLine two\n'),result['name_description_chars'])

    def test_pyyaml_missing_fails_without_installer(self):
        original=builtins.__import__
        def imports(name,*args,**kwargs):
            if name=='yaml':raise ImportError('fixture')
            return original(name,*args,**kwargs)
        with mock.patch('builtins.__import__',side_effect=imports):
            with self.assertRaisesRegex(ValueError,'PyYAML unavailable'):context.discovery(self.root)

    def test_growth_allowance_needs_reason_and_integer(self):
        for allowance,reason in [(1,''),(-1,'why'),(True,'why'),('1','why')]:
            with self.subTest(value=allowance),self.assertRaises(ValueError):
                context.compare(self.root,self.root,[self.case(allowed_growth_chars=allowance,growth_reason=reason)])

    def test_metadata_growth_separate_from_body_in_measure_only(self):
        after=self.root/'after';(after/'skills/demo').mkdir(parents=True)
        (after/'skills/demo/SKILL.md').write_text('---\nname: demo\ndescription: Longer description\n---\nBody\n')
        (after/'guide.md').write_bytes(self.guide.read_bytes())
        strict=context.compare(self.root,after,[self.case()]);self.assertFalse(strict['passed'])
        measured=context.compare(self.root,after,[self.case()],check_growth=False)
        self.assertEqual(0,measured['cases'][0]['delta_chars']);self.assertIsNone(measured['passed'])

    def test_side_specific_exclusions_and_empty_declared_path(self):
        case=self.case(before=[],unmeasured_before=['dynamic input'],unmeasured_after=['provider'])
        report=context.compare(self.root,self.root,[case],check_growth=False)['cases'][0]
        self.assertEqual(0,report['before']['chars']);self.assertEqual(['dynamic input'],report['unmeasured_before'])
        self.assertEqual(['provider'],report['unmeasured_after'])

    def test_source_and_alias_changes_are_detected(self):
        reader=context.Reader(self.root);context.measure(reader,[self.read]);self.guide.write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):reader.unchanged()
        (self.root/'other.md').write_text('other');(self.root/'alias.md').symlink_to(self.guide)
        reader=context.Reader(self.root);context.measure(reader,[{'path':'alias.md'}])
        (self.root/'alias.md').unlink();(self.root/'alias.md').symlink_to(self.root/'other.md')
        with self.assertRaisesRegex(ValueError,'changed'):reader.unchanged()

    def test_case_schema_names_and_unknown_fields_fail(self):
        invalid=[[],[self.case(),self.case()],[self.case(unmeasured='not a list')],
                 [self.case(after=[{'path':'guide.md','misspelled_section':'Pick'}])],
                 {'schema_version':True,'cases':[self.case()]}]
        for cases in invalid:
            with self.subTest(cases=cases),self.assertRaises(ValueError):context.compare(self.root,self.root,cases)

    def test_cli_measure_growth_failure_and_input_error_are_distinct(self):
        cases=self.root/'cases.json';cases.write_text(json.dumps([self.case(after=[self.read,self.read])]))
        cmd=[sys.executable,'-B',str(ROOT/'scripts/context_check.py'),'--before',str(self.root),
             '--after',str(self.root),'--cases',str(cases)]
        raw=subprocess.run(cmd+['--measure-only'],capture_output=True)
        self.assertEqual(0,raw.returncode);self.assertEqual('measured',json.loads(raw.stdout)['status'])
        growth=subprocess.run(cmd,capture_output=True);self.assertEqual(1,growth.returncode)
        self.assertFalse(json.loads(growth.stdout)['passed'])
        cases.write_text(json.dumps([self.case(after=[{'path':'missing'}])]))
        invalid=subprocess.run(cmd,capture_output=True);self.assertEqual(2,invalid.returncode)
        self.assertEqual('unavailable',json.loads(invalid.stdout)['status'])
