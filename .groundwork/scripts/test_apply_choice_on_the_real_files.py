import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import check_adrs  # noqa: E402
import check_links  # noqa: E402
import check_practices  # noqa: E402
import markers  # noqa: E402
import practices_map  # noqa: E402
import update_groundwork  # noqa: E402
from test_apply_choice import SCRIPT, commit, put  # noqa: E402
from test_filtered_trees import LICENSE, README, adoption_order, is_source  # noqa: E402
from test_update_groundwork import git, init, read, rewritten_env  # noqa: E402


def dependents(needs, number):
    found, grew = {number}, True
    while grew:
        grew = False
        for other, wanted in needs.items():
            if other not in found and wanted & found:
                found.add(other)
                grew = True
    return found


@unittest.skipUnless(
    is_source(ROOT, os.environ),
    "it describes the files of a source of ADRs, and a project has not all of them: set GROUNDWORK_SOURCE=true to run it in a community base",
)
class RealTree(unittest.TestCase):
    """The files of groundwork itself, copied into a source and into a project."""

    @classmethod
    def setUpClass(cls):
        entries = practices_map.read_map(ROOT)[0]
        cls.needs = practices_map.needs_of(entries)
        cls.numbers = sorted(cls.needs)
        listed = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, text=True, check=True
        ).stdout
        cls.paths = [path for path in listed.split("\0") if path and os.path.isfile(os.path.join(ROOT, path))]

    def copy(self, destination, version=None, choice=None):
        for path in self.paths:
            target = os.path.join(destination, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(os.path.join(ROOT, path), target)
        if version:
            put(destination, {".groundwork-version": f"{version}\n"})
        if choice is not None:
            put(destination, {".groundwork-adrs": choice})

    def world(self, version=None, choice=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source = os.path.join(directory.name, "source")
        project = os.path.join(directory.name, "project")
        init(source)
        self.copy(source)
        commit(source, "feat: release")
        git(source, "tag", "-a", "v0.1.0", "-m", "v0.1.0")
        init(project)
        self.copy(project, version, choice)
        commit(project, "Initial commit")
        git(project, "switch", "-q", "-c", "feat/1-adopt")
        return source, project

    def run_in(self, project, source, *args):
        if os.path.exists(os.path.join(project, ".groundwork-version")):
            return subprocess.run(
                [sys.executable, SCRIPT, "--source", source, *args], cwd=project, capture_output=True, text=True
            )
        env = rewritten_env(update_groundwork.SOURCE, source)
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=project, capture_output=True, text=True, env=env)

    def kept_without(self, number):
        gone = dependents(self.needs, number)
        return [n for n in self.numbers if n not in gone]

    def existing_project(self, directory, kept):
        """A project that exists: files of its own, a recorded version and the choice."""
        project = os.path.join(directory, "existing")
        init(project)
        put(
            project,
            {
                "README.md": README,
                "LICENSE": LICENSE,
                ".gitignore": "build/\n",
                "src/app.py": "print(1)\n",
                ".groundwork-version": "0.1.0\n",
                ".groundwork-adrs": "".join(f"{number:04d}\n" for number in kept),
            },
        )
        commit(project, "Initial commit")
        git(project, "switch", "-q", "-c", "feat/1-adopt")
        return project

    def files_of(self, project):
        found = {}
        for directory, names, files in os.walk(project):
            names[:] = [name for name in names if name != ".git"]
            for name in files:
                path = os.path.join(directory, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, project)] = handle.read()
        return found


@unittest.skipUnless(
    is_source(ROOT, os.environ),
    "it describes the files of a source of ADRs, and a project has not all of them: set GROUNDWORK_SOURCE=true to run it in a community base",
)
class RealFiles(RealTree):
    """What the command does to the files of groundwork itself."""

    def test_a_project_that_exists_gets_the_files_of_the_template_and_its_own_checks_run(self):
        own = {"README.md", "LICENSE", ".gitignore", "src/app.py", ".groundwork-version", ".groundwork-adrs"}
        sets = [("0001", [1])] + [
            (f"{number:04d}", self.kept_without(number)) for number in self.numbers if number != 1
        ]
        for name, kept in sets:
            with self.subTest(left_out=name):
                source, template = self.world()
                self.assertEqual(self.run_in(template, source, *[f"{n:04d}" for n in kept]).returncode, 0)
                project = self.existing_project(os.path.dirname(source), kept)
                result = self.run_in(project, source)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                wanted = {path: text for path, text in self.files_of(template).items() if path not in own}
                got = {path: text for path, text in self.files_of(project).items() if path not in own}
                self.assertEqual(sorted(got), sorted(wanted))
                self.assertEqual([path for path in wanted if got[path] != wanted[path]], [])
                git(project, "add", "-A")
                for script in ("check_adrs.py", "check_practices.py"):
                    if not os.path.exists(os.path.join(project, ".groundwork", "scripts", script)):
                        continue  # the script belongs to an ADR that the project left out
                    run = subprocess.run(
                        [sys.executable, f".groundwork/scripts/{script}"], cwd=project, capture_output=True, text=True
                    )
                    self.assertEqual(run.returncode, 0, f"{script}: {run.stdout}{run.stderr}")
                imports = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        ".groundwork/scripts",
                        "-p",
                        "test_*.py",
                        "-k",
                        "no_test_has_this_name",
                    ],
                    cwd=project,
                    capture_output=True,
                    text=True,
                )
                self.assertNotIn("_FailedTest", imports.stdout + imports.stderr, imports.stderr[-600:])

    def test_the_checks_pass_after_the_command_for_each_adr_left_out_and_for_adr_0001_alone(self):
        sets = [("0001", [1])] + [
            (f"{number:04d}", self.kept_without(number)) for number in self.numbers if number != 1
        ]
        for name, kept in sets:
            with self.subTest(left_out=name):
                source, project = self.world()
                result = self.run_in(project, source, *[f"{n:04d}" for n in kept])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                put(project, {"README.md": README, "LICENSE": LICENSE})
                git(project, "add", "-A")
                problems = check_adrs.check(project) + check_practices.check(project) + check_links.check(project)
                self.assertEqual(problems, [])

    def test_the_map_passes_after_the_command_before_the_deletions_are_staged(self):
        sets = [("0001", [1])] + [
            (f"{number:04d}", self.kept_without(number)) for number in self.numbers if number != 1
        ]
        for name, kept in sets:
            with self.subTest(left_out=name):
                source, project = self.world()
                result = self.run_in(project, source, *[f"{n:04d}" for n in kept])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                put(project, {"README.md": README, "LICENSE": LICENSE})
                self.assertEqual(check_practices.check(project), [])

    def test_narrowing_then_widening_gives_back_the_original_files(self):
        for number in self.numbers:
            if number == 1:
                continue
            with self.subTest(left_out=f"{number:04d}"):
                kept = self.kept_without(number)
                source, project = self.world(version="0.1.0", choice="".join(f"{n:04d}\n" for n in kept))
                self.assertEqual(self.run_in(project, source).returncode, 0)
                commit(project)
                put(project, {".groundwork-adrs": "0001-0999\n"})
                commit(project)
                result = self.run_in(project, source)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                owners = practices_map.owners(practices_map.read_map(ROOT)[0])
                for path in self.paths:
                    with open(os.path.join(ROOT, path), encoding="utf-8", errors="surrogateescape") as handle:
                        original = handle.read()
                    # A file that left with its ADR comes back without the blocks that only a source needs.
                    if markers.kind(path) and owners.get(path) not in (None, *kept):
                        original = markers.remove_source(original, markers.kind(path))
                    self.assertEqual(read(project, path), original, path)


@unittest.skipUnless(
    is_source(ROOT, os.environ),
    "it describes the files of a source of ADRs, and a project has not all of them: set GROUNDWORK_SOURCE=true to run it in a community base",
)
class ExistingProject(RealTree):
    """A project that exists, with files of its own, follows the path of the README phase by phase."""

    OWN = {
        "README.md": "# My app\n\nBuilds things.\n",
        "CONTRIBUTING.md": "# Contributing\n\nOpen a pull request.\n\n## Style\n\nUse tabs.\n",
        ".pre-commit-config.yaml": "repos:\n  - repo: local\n    hooks:\n      - id: lint\n        name: lint\n        entry: make lint\n        language: system\n",
        "src/app.py": "print(1)\n",
    }

    def test_each_phase_of_the_path_arrives_without_an_error_and_conflicts_stay_in_the_files_of_the_project(self):
        order = adoption_order()
        self.assertTrue(order)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source, project = (os.path.join(directory.name, name) for name in ("source", "project"))
        init(source)
        self.copy(source)
        commit(source, "feat: release")
        git(source, "tag", "-a", "v0.1.0", "-m", "v0.1.0")
        init(project)
        put(project, {**self.OWN, ".groundwork-version": "0.1.0\n"})
        commit(project, "Initial commit")
        git(project, "switch", "-q", "-c", "feat/1-adopt")
        for count in range(1, len(order) + 1):
            kept = order[:count]
            with self.subTest(adopted=f"{kept[-1]:04d}"):
                put(project, {".groundwork-adrs": "".join(f"{number:04d}\n" for number in kept)})
                commit(project, "chore: list the ADRs of the step")
                result = self.run_in(project, source)
                self.assertIn(result.returncode, (0, 3), result.stdout + result.stderr)
                for path in [
                    line[len("conflict: ") :] for line in result.stdout.splitlines() if line.startswith("conflict: ")
                ]:
                    self.assertIn(path, self.OWN, f"{path} is in conflict and the project did not have it")
                    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
                        put(project, {path: handle.read()})
                for path in [
                    line[len("keep: ") :].split(" (")[0]
                    for line in result.stdout.splitlines()
                    if line.startswith("keep: ")
                ]:
                    self.assertIn(path, self.OWN, f"{path} is kept and the project did not have it")
                commit(project)
        for number in order:
            with self.subTest(arrived=f"{number:04d}"):
                self.assertTrue(glob.glob(os.path.join(project, "docs", "adr", f"{number:04d}-*.md")))
        self.assertEqual(check_links.check(project), [])


if __name__ == "__main__":
    unittest.main()
