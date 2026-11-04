import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'common/base/scripts' / file)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
assets = load('assets', 'assets.py')
ignores = load('ignores', 'git-excludes.py')

class AssetsTests(unittest.TestCase):
    def test_plan_and_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = assets.scope_path(tmp, 'project', 'team', 'app')
            assets.prepare(scope)
            self.assertFalse(scope.exists())
            assets.prepare(scope, True)
            self.assertTrue((scope / 'originals').is_dir())
            self.assertTrue((scope / 'extracted').is_dir())
            with self.assertRaises(ValueError): assets.owned(scope, '../escape')
            with self.assertRaises(ValueError): assets.scope_path(tmp, 'project', '../x', 'app')

    def test_atomic_conversion_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = Path(tmp); assets.prepare(scope, True)
            source = scope / 'originals/design.pdf'; source.write_text('first')
            tool = scope / 'fake.py'
            tool.write_text("import sys,pathlib\nif '--version' in sys.argv: print('fixture 1')\nelse: pathlib.Path(sys.argv[-1], 'design.md').write_text('converted')\n")
            command = [sys.executable, str(tool)]
            self.assertEqual(assets.extract(scope, 'design.pdf', command)['status'], 'fresh')
            self.assertEqual(assets.freshness(scope, 'design.pdf'), 'fresh')
            output = scope / 'extracted/design.pdf/content.md'
            source.write_text('second')
            self.assertEqual(assets.freshness(scope, 'design.pdf'), 'stale')
            self.assertEqual(assets.extract(scope, 'design.pdf', ['missing-executable'])['status'], 'stale')
            self.assertEqual(output.read_text(), 'converted')
            self.assertTrue(json.loads((scope / 'extracted/design.pdf/provenance.json').read_text())['stale'])

    def test_search_is_scoped_and_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a', Path(tmp)/'b'
            for scope in [a,b]:
                assets.prepare(scope, True); (scope/'originals/design.pdf').write_text('synthetic')
            report = assets.search([a], 'design')
            self.assertEqual(len(report['results']), 1)
            self.assertEqual(report['results'][0]['freshness'], 'unindexed')
            self.assertEqual(assets.search([Path(tmp)/'missing'], 'x')['scopes'][0]['status'], 'unavailable')

    def test_provenance_publication_failure_restores_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope=Path(tmp); assets.prepare(scope,True)
            (scope/'originals/design.pdf').write_text('fixture')
            output=scope/'extracted/design.pdf/content.md';output.parent.mkdir()
            output.write_text('previous')
            meta=output.with_name('provenance.json');meta.write_text('{"sha256":"previous"}')
            tool=scope/'tool.py';tool.write_text("import pathlib,sys\nif '--version' in sys.argv: print('fixture')\nelse: pathlib.Path(sys.argv[-1], 'design.md').write_text('new')\n")
            replace=assets.os.replace
            def fail_metadata(source,target):
                if Path(source).name=='provenance.json' and Path(target)==meta:
                    raise OSError('fixture publication failure')
                return replace(source,target)
            with patch.object(assets.os,'replace',side_effect=fail_metadata):
                report=assets.extract(scope,'design.pdf',[sys.executable,str(tool)])
            self.assertEqual(report['status'],'stale')
            self.assertEqual(output.read_text(),'previous')
            self.assertEqual(json.loads(meta.read_text())['sha256'],'previous')
            self.assertTrue(json.loads(meta.read_text())['stale'])

    def test_changed_original_during_conversion_preserves_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = Path(tmp); assets.prepare(scope, True)
            source = scope / 'originals/design.pdf'; source.write_text('initial')
            output = scope / 'extracted/design.pdf/content.md'
            output.parent.mkdir(); output.write_text('previous')
            tool = scope / 'race.py'
            tool.write_text("import sys,pathlib\nif '--version' in sys.argv: print('fixture 1')\nelse:\n pathlib.Path(sys.argv[2]).write_text('raced')\n pathlib.Path(sys.argv[-1], 'design.md').write_text('new')\n")
            report = assets.extract(scope, 'design.pdf', [sys.executable,str(tool)])
            self.assertEqual(report['status'],'stale')
            self.assertEqual(output.read_text(),'previous')

    def test_override_and_dedup_and_search_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); scope=root/'scope'; assets.prepare(scope,True)
            (scope/'originals/design.pdf').write_text('fixture')
            cfg=root/'config.toml'; cfg.write_text('schema_version=1\n[roots]\nassets="'+str(root/'assets')+'"\n[projects.app]\nassets="'+str(scope)+'"\n')
            self.assertEqual(assets.configured_scope(cfg,'project','team','app'),scope)
            result=assets.search([scope,scope,root/'other'],'design',limit=1)
            self.assertEqual(len(result['results']),1)
            self.assertEqual(len(result['scopes']),1)
            self.assertEqual(len(result['remaining_scopes']),2)
            self.assertFalse((scope/'.qmd-config').exists())

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); scope=root/'scope'; assets.prepare(scope,True)
            (root/'outside.pdf').write_text('outside')
            (scope/'originals/escape.pdf').symlink_to(root/'outside.pdf')
            with self.assertRaises(ValueError):assets.extract(scope,'escape.pdf',['docling'])

    def test_tool_absence_and_invalid_qmd_json_use_explicit_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); scope=root/'scope'; assets.prepare(scope,True)
            (scope/'originals/design.pdf').write_text('fixture')
            with patch.dict(os.environ,{'TR_ASSETS_STATE_ROOT':str(root/'state')}):
                with patch.object(assets.shutil,'which',return_value=None):
                    self.assertEqual(assets.index(scope)['status'],'not_configured')
                    self.assertEqual(assets.search([scope],'design')['results'][0]['freshness'],'unindexed')
                state=assets.state_path(scope);state.mkdir(parents=True);(state/'indexed.json').write_text('{}')
                response=subprocess.CompletedProcess([],0,stdout='{invalid',stderr='')
                with patch.object(assets.shutil,'which',return_value='/fixture/qmd'),patch.object(assets.subprocess,'run',return_value=response):
                    report=assets.search([scope],'design')
                self.assertEqual(report['scopes'][0]['status'],'unindexed')
                self.assertIn('error',report['scopes'][0])
                self.assertEqual(report['results'][0]['original'],str(scope/'originals/design.pdf'))
                output=scope/'extracted/design.pdf/content.md';output.parent.mkdir();output.write_text('old')
                output.with_name('provenance.json').write_text('{broken')
                self.assertEqual(assets.freshness(scope,'design.pdf'),'stale')

    def prepared_extraction(self, scope, relative):
        source, output, meta=assets.output_paths(scope,relative)
        source.parent.mkdir(parents=True,exist_ok=True);source.write_text('synthetic')
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text('synthetic extracted')
        meta.write_text(json.dumps({'original':str(source.resolve()),'sha256':assets.digest(source),'output_sha256':assets.digest(output),'stale':False}))
        return source,output

    def test_index_preserves_missing_and_unavailable_corpus(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'TR_ASSETS_STATE_ROOT':str(Path(tmp)/'state')}):
            scope=Path(tmp)/'scope';assets.prepare(scope,True)
            source,output=self.prepared_extraction(scope,'old.pdf')
            response=subprocess.CompletedProcess([],0,stdout='',stderr='')
            with patch.object(assets.shutil,'which',return_value='/fixture/qmd'),patch.object(assets.subprocess,'run',return_value=response):
                assets.index(scope)
                corpus=assets.state_path(scope)/'corpus/old.pdf.md';previous=corpus.read_bytes()
                source.unlink()
                assets.index(scope)
                self.assertEqual(corpus.read_bytes(),previous)
                hits=subprocess.CompletedProcess([],0,stdout=json.dumps([{'file':str(corpus)}]),stderr='')
                with patch.object(assets.subprocess,'run',return_value=hits):
                    self.assertEqual(assets.search([scope],'synthetic')['results'],[])
                    source.write_text('changed original')
                    self.assertEqual(assets.search([scope],'synthetic')['results'],[])
                    stale=assets.search([scope],'old')['results']
                    self.assertEqual(stale[0]['freshness'],'stale')
                (scope/'originals').rename(scope/'temporarily-unavailable')
                self.assertEqual(assets.index(scope)['status'],'unavailable')
                self.assertEqual(corpus.read_bytes(),previous)

    def test_search_reports_new_original_in_old_index_as_unindexed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'TR_ASSETS_STATE_ROOT':str(Path(tmp)/'state')}):
            scope=Path(tmp)/'scope';assets.prepare(scope,True)
            self.prepared_extraction(scope,'old.pdf')
            response=subprocess.CompletedProcess([],0,stdout='[]',stderr='')
            with patch.object(assets.shutil,'which',return_value='/fixture/qmd'),patch.object(assets.subprocess,'run',return_value=response):
                assets.index(scope)
                self.assertEqual(assets.search([scope],'old')['scopes'][0]['status'],'searched')
                (scope/'originals/new.pdf').write_text('new original')
                report=assets.search([scope],'new')
                self.assertEqual(report['scopes'][0]['status'],'unindexed')
                self.assertEqual(report['results'][0]['freshness'],'unindexed')
                # A fresh extraction that has not joined the old inventory is also incomplete.
                self.prepared_extraction(scope,'new.pdf')
                self.assertEqual(assets.search([scope],'new')['scopes'][0]['status'],'unindexed')

    def test_preconversion_failures_preserve_output_with_explicit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope=Path(tmp);assets.prepare(scope,True)
            source,output=self.prepared_extraction(scope,'old.pdf')
            previous=output.read_bytes()
            for operation in ['digest','mkdir']:
                with self.subTest(operation=operation):
                    if operation=='digest':
                        failure=patch.object(assets,'digest',side_effect=FileNotFoundError('source raced'))
                    else:
                        failure=patch.object(Path,'mkdir',side_effect=PermissionError('output unavailable'))
                    with failure:
                        report=assets.extract(scope,'old.pdf',['unused'])
                    self.assertEqual(report['status'],'stale')
                    self.assertIn('error',report)
                    self.assertEqual(output.read_bytes(),previous)

    def test_git_global_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); home=root/'home'; home.mkdir()
            with patch.dict(os.environ, {'HOME': str(home), 'GIT_CONFIG_NOSYSTEM':'1', 'GIT_CONFIG_GLOBAL':str(home/'gitconfig')}):
                normal, backup = root/'normal', root/'tr-local-docs'
                for repo in [normal, backup]:
                    subprocess.run(['git','init',str(repo)], check=True, capture_output=True)
                    for directory in ['_bmad','_bmad-output','_tr-assets','_bmad-extra']:
                        (repo/directory).mkdir(); (repo/directory/'x').write_text('fixture')
                excludes=home/'ignore'; excludes.write_text('keep-me\n*.secret\n')
                ignores.setup(excludes,backup,False)
                self.assertEqual(excludes.read_text(),'keep-me\n*.secret\n')
                ignores.setup(excludes,backup,True)
                for name in ['_bmad/x','_bmad-output/x','_tr-assets/x']:
                    self.assertEqual(subprocess.run(['git','-C',str(normal),'check-ignore',name],capture_output=True).returncode,0)
                    self.assertEqual(subprocess.run(['git','-C',str(backup),'check-ignore',name],capture_output=True).returncode,1 if name.startswith('_bmad-output/') else 0)
                self.assertEqual(subprocess.run(['git','-C',str(normal),'check-ignore','_bmad-extra/x'],capture_output=True).returncode,1)
                subprocess.run(['git','-C',str(backup),'add','_bmad-output/x'],check=True)
                nested=backup/'device/team/app/_bmad-output';nested.mkdir(parents=True)
                (nested/'file.md').write_text('fixture');(nested/'private.secret').write_text('fixture')
                self.assertEqual(subprocess.run(['git','-C',str(backup),'check-ignore',str(nested/'file.md')],capture_output=True).returncode,1)
                self.assertEqual(subprocess.run(['git','-C',str(backup),'check-ignore',str(nested/'private.secret')],capture_output=True).returncode,0)
                # A subsequent global policy change remains effective in the backup repo.
                excludes.write_text(excludes.read_text()+'later-rule\n')
                (backup/'later-rule').write_text('fixture')
                self.assertEqual(subprocess.run(['git','-C',str(backup),'check-ignore','later-rule'],capture_output=True).returncode,0)


if __name__ == '__main__': unittest.main()
