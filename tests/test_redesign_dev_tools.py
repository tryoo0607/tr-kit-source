import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'scripts/setup_dev_tools.py'
spec = importlib.util.spec_from_file_location('setup_dev_tools', SOURCE)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class DevelopmentToolsTests(unittest.TestCase):
    def test_existing_toolchain_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / 'installed'
            prefix.mkdir()
            sentinel = prefix / 'keep'
            sentinel.write_text('original')
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                setup.provision(prefix, SOURCE.parents[1] / 'common/base/scripts/dev-tools.toml', 'uv')
            self.assertEqual([sentinel], list(prefix.iterdir()))
            self.assertEqual('original', sentinel.read_text())

    def test_activation_quotes_paths_and_preserves_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "tools ' $(touch injected)"
            prefix.mkdir()
            setup.write_environment(prefix)
            code = 'source "$1"; printf "%s\\n%s\\n" "$TR_DEVTOOLS_ROOT" "$PATH"'
            result = subprocess.run(['bash', '-c', code, 'probe', str(prefix / 'env.sh')],
                                    cwd=directory, env={'PATH': os.environ['PATH']},
                                    capture_output=True, text=True, check=True)
            lines = result.stdout.splitlines()
            self.assertEqual(str(prefix), lines[0])
            self.assertEqual(str(prefix / 'bin') + ':' + os.environ['PATH'], lines[1])
            self.assertFalse((Path(directory) / 'injected').exists())


if __name__ == '__main__':
    unittest.main()
