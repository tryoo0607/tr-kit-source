import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.build import build_target


ROOT = Path(__file__).resolve().parents[1]


class HookPathResolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_target(ROOT, "codex")
        cls.plugin = ROOT / "out/codex/plugins/tr-codex"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.actual_projects = self.root / "data/projects"
        self.profile = self.root / "profile.d"
        self.home.mkdir()
        self.actual_projects.mkdir(parents=True)
        self.profile.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def resolve(self, function: str, path: Path) -> str:
        environment = {
            **os.environ,
            "HOME": str(self.home),
            "TR_KIT_PROFILE_DIR": str(self.profile),
            "CLAUDE_PLUGIN_ROOT": str(self.plugin),
        }
        result = subprocess.run(
            [
                "bash",
                "-c",
                '. "$1/hooks/lib.sh"; "$2" "$3"',
                "_",
                str(self.plugin),
                function,
                str(path),
            ],
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def configure_projects(self) -> None:
        (self.profile / "90-local.toml").write_text(
            "schema_version = 1\n"
            "[public.paths]\n"
            f'projects = "{self.actual_projects}"\n',
            encoding="utf-8",
        )

    def test_profile_projects_root_resolves_project_and_docs(self):
        self.configure_projects()
        project = self.actual_projects / "demo/src"
        project.mkdir(parents=True)

        self.assertEqual(self.resolve("tr_project", project), "demo")
        self.assertEqual(
            self.resolve("tr_docs", project),
            str(self.actual_projects / "_docs/demo"),
        )

    def test_home_projects_symlink_accepts_canonical_cwd(self):
        (self.home / "projects").symlink_to(self.actual_projects)
        project = self.actual_projects / "demo"
        project.mkdir()

        self.assertEqual(self.resolve("tr_project", project), "demo")
        self.assertEqual(
            self.resolve("tr_docs", project),
            str(self.actual_projects / "_docs/demo"),
        )

    def test_worktree_directory_maps_back_to_repository_name(self):
        self.configure_projects()
        worktree = self.actual_projects / "demo.worktrees/feature-a/src"
        worktree.mkdir(parents=True)

        self.assertEqual(self.resolve("tr_project", worktree), "demo")
        self.assertEqual(
            self.resolve("tr_docs", worktree),
            str(self.actual_projects / "_docs/demo"),
        )

    def test_reserved_collection_root_and_outside_path_have_no_project(self):
        self.configure_projects()
        docs = self.actual_projects / "_docs/demo"
        collection = self.actual_projects / "demo.worktrees"
        outside = self.root / "outside"
        docs.mkdir(parents=True)
        collection.mkdir()
        outside.mkdir()

        for path in (self.actual_projects, docs, collection, outside):
            with self.subTest(path=path):
                self.assertEqual(self.resolve("tr_project", path), "")

    def test_invalid_profile_projects_root_falls_back_to_home(self):
        (self.profile / "90-local.toml").write_text(
            "schema_version = 1\n"
            "[public.paths]\n"
            'projects = "relative/projects"\n',
            encoding="utf-8",
        )
        fallback = self.home / "projects/demo"
        fallback.mkdir(parents=True)

        self.assertEqual(self.resolve("tr_project", fallback), "demo")


if __name__ == "__main__":
    unittest.main()
