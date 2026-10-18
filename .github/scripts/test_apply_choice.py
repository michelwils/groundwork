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
from test_filtered_trees import LICENSE, README, is_source  # noqa: E402
from test_update_groundwork import ADDRESS, adr, git, init, read, rewritten_env, trimmed, world  # noqa: E402

SCRIPT = os.path.join(HERE, "apply_choice.py")


def put(root, files):
    for name, content in files.items():
        path = os.path.join(root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(content)


def commit(repo, message="chore: adjust"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


class Fixture(unittest.TestCase):
    """A source of groundwork at v0.1.0, and a project in a repository of its own, on a branch."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = os.path.join(self.directory.name, "groundwork")
        self.project = os.path.join(self.directory.name, "project")
        self.outside = os.path.join(self.directory.name, "outside.txt")
        with open(self.outside, "w") as handle:
            handle.write("outside\n")
        init(self.source)
        self.release(world("1"))

    def release(self, files, version="0.1.0"):
        put(self.source, files)
        commit(self.source, f"feat: release {version}")
        git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")

    def adopt(self, files, version=None, choice=None, branch="feat/1-adopt"):
        init(self.project)
        extra = {}
        if version:
            extra[".groundwork-version"] = f"{version}\n"
        if choice is not None:
            extra[".groundwork-adrs"] = choice
        put(self.project, {**files, **extra})
        commit(self.project, "Initial commit")
        if branch:
            git(self.project, "switch", "-q", "-c", branch)

    def run_script(self, *args, source=True, env=None):
        command = [sys.executable, SCRIPT, *args]
        if source and "--source" not in args:
            command += ["--source", self.source]
        return subprocess.run(command, cwd=self.project, capture_output=True, text=True, env=env)

    def run_new(self, *args):
        """Run in a project that has no recorded source: the address of groundwork leads to the source."""
        return self.run_script(*args, source=False, env=rewritten_env(update_groundwork.SOURCE, self.source))

    def has(self, name):
        return os.path.lexists(os.path.join(self.project, name))

    def status(self):
        return git(self.project, "status", "--porcelain").strip()

    def lines(self, result, prefix):
        return [line[len(prefix):] for line in result.stdout.splitlines() if line.startswith(prefix)]


class NewProject(Fixture):
    def template(self, **more):
        """What a repository created from the template holds: all the files, an ADR of groundwork itself and a README."""
        return {**world("1"), "docs/adr/1000-own-of-groundwork.md": "# own\n", "README.md": "# groundwork\n", **more}

    def test_it_keeps_the_adrs_it_is_told_and_the_ones_they_need_and_none_of_the_others(self):
        self.adopt(self.template())
        result = self.run_new("0003")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("two.txt", "three.txt", adr(1), adr(2), adr(3)):
            self.assertTrue(self.has(name), name)
        for name in ("four.txt", adr(4)):
            self.assertFalse(self.has(name), name)
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(world("1")["SHARED.md"], "markdown", {1, 2, 3}))

    def test_it_writes_the_choice_and_the_version_in_their_formats(self):
        self.adopt(self.template())
        self.run_new("0003", "0001-0001")
        self.assertEqual(read(self.project, ".groundwork-adrs"), "0003\n0001-0001\n")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.1.0\n")

    def test_it_deletes_the_adrs_that_no_range_of_the_source_reserves(self):
        self.adopt(self.template())
        self.run_new("0001-0999")
        self.assertFalse(self.has("docs/adr/1000-own-of-groundwork.md"))

    def test_without_a_list_it_writes_no_choice_and_keeps_everything_that_the_source_reserves(self):
        self.adopt(self.template())
        result = self.run_new()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.has(".groundwork-adrs"))
        self.assertEqual(read(self.project, ".groundwork-version"), "0.1.0\n")
        for name in ("two.txt", "three.txt", "four.txt", adr(4)):
            self.assertTrue(self.has(name), name)
        self.assertFalse(self.has("docs/adr/1000-own-of-groundwork.md"))

    def test_it_records_the_version_that_it_is_given(self):
        self.release(world("2"), version="0.2.0")
        self.adopt(self.template())
        self.run_new("--version", "0.1.0")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.1.0\n")

    def test_it_records_the_latest_version_by_default(self):
        self.release(world("2"), version="0.2.0")
        self.adopt(self.template())
        self.run_new()
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_a_version_that_the_source_did_not_publish_is_refused(self):
        self.adopt(self.template())
        result = self.run_new("--version", "9.9.9")
        self.assertEqual(result.returncode, 1)
        self.assertIn("9.9.9", result.stderr)
        self.assertEqual(self.status(), "")

    def test_it_records_the_source_when_it_is_given_an_address(self):
        self.adopt(self.template())
        result = self.run_script("--source", ADDRESS, "0001", source=False, env=rewritten_env(ADDRESS, self.source))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, ".groundwork-source"), ADDRESS + "\n")

    def test_an_address_that_cannot_be_recorded_changes_nothing(self):
        self.adopt(self.template())
        result = self.run_script("--source", "http://example.org/base.git", "0001", source=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-source", result.stderr)
        self.assertEqual(self.status(), "")

    def test_a_number_that_the_source_does_not_reserve_changes_nothing(self):
        self.adopt(self.template())
        result = self.run_new("0003", "1000")
        self.assertEqual(result.returncode, 1)
        self.assertIn("1000", result.stderr)
        self.assertEqual(self.status(), "")
        self.assertTrue(self.has(adr(4)))

    def test_it_says_the_steps_that_stay_by_hand_and_runs_none_of_them(self):
        self.adopt(self.template())
        result = self.run_new("0001")
        for text in ("apply_settings.py", "GROUNDWORK_UPDATE_TOKEN", "README", "license"):
            self.assertIn(text, result.stdout)

    def test_it_lists_what_it_does(self):
        self.adopt(self.template())
        result = self.run_new("0001")
        self.assertIn("write: .groundwork-adrs", result.stdout)
        self.assertIn("write: .groundwork-version 0.1.0", result.stdout)
        self.assertIn("two.txt", self.lines(result, "delete: "))
        self.assertIn("SHARED.md", self.lines(result, "edit: "))

    def test_a_path_of_the_map_that_leaves_the_repository_is_refused_before_anything_changes(self):
        for hostile in ("../outside.txt", self.outside):
            with self.subTest(path=hostile):
                shutil.rmtree(self.project, ignore_errors=True)
                files = self.template()
                files["docs/practices.md"] = files["docs/practices.md"].replace("`four.txt`", f"`{hostile}`")
                self.adopt(files)
                result = self.run_new("0001")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertTrue(os.path.exists(self.outside))
                self.assertEqual(self.status(), "")
                self.assertTrue(self.has("two.txt"))

    def test_a_link_to_a_file_outside_the_repository_is_not_followed(self):
        self.adopt({**self.template(), "four.txt": ""})
        os.remove(os.path.join(self.project, "four.txt"))
        os.symlink(self.outside, os.path.join(self.project, "four.txt"))
        commit(self.project)
        result = self.run_new("0001")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(os.path.exists(self.outside))
        self.assertTrue(self.has("two.txt"))

    def test_it_does_not_delete_a_file_that_git_does_not_track(self):
        self.adopt(self.template())
        put(self.project, {"scratch/two.txt": "mine\n"})
        with open(os.path.join(self.project, ".gitignore"), "w") as handle:
            handle.write("four.txt\n")
        commit(self.project)
        git(self.project, "rm", "-q", "--cached", "four.txt")
        git(self.project, "commit", "-q", "-m", "chore: untrack")
        self.run_new("0001")
        self.assertTrue(self.has("four.txt"))
        self.assertTrue(self.has("scratch/two.txt"))

    def test_it_leaves_the_index_to_the_project(self):
        self.adopt(self.template())
        self.run_new("0001")
        self.assertEqual(git(self.project, "diff", "--cached", "--name-only").strip(), "")


class Narrowed(Fixture):
    """A project with a recorded version, which changed its choice: the command makes the files agree with it."""

    def test_it_deletes_the_files_and_the_blocks_of_the_adrs_that_left_the_choice_and_nothing_else(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("three.txt", "four.txt", adr(3), adr(4)):
            self.assertFalse(self.has(name), name)
        for name in ("two.txt", adr(1), adr(2), "tool.py", "docs/practices.md"):
            self.assertTrue(self.has(name), name)
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(world("1")["SHARED.md"], "markdown", {1, 2}))
        self.assertEqual(read(self.project, ".groundwork-adrs"), "0001\n0002\n")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.1.0\n")

    def test_it_lists_what_it_does(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n0002\n")
        result = self.run_script()
        self.assertEqual(sorted(self.lines(result, "delete: ")), ["docs/adr/0003-third.md", "docs/adr/0004-fourth.md", "four.txt", "three.txt"])
        self.assertEqual(self.lines(result, "edit: "), ["SHARED.md"])

    def test_a_file_that_the_project_changed_is_kept_and_said(self):
        self.adopt({**world("1"), "three.txt": "three 1, mine\n"}, version="0.1.0", choice="0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "three.txt"), "three 1, mine\n")
        self.assertIn("three.txt (changed by the project)", self.lines(result, "keep: "))
        self.assertFalse(self.has(adr(3)))

    def test_a_block_that_the_project_changed_is_kept_and_said(self):
        shared = world("1")["SHARED.md"].replace("middle 3", "middle 3, mine")
        self.adopt({**world("1"), "SHARED.md": shared}, version="0.1.0", choice="0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        text = read(self.project, "SHARED.md")
        self.assertIn("middle 3, mine", text)
        self.assertNotIn("last 4", text)
        self.assertIn("SHARED.md (block 0003 changed by the project)", self.lines(result, "keep: "))

    def test_the_adrs_and_the_blocks_of_the_project_are_not_touched(self):
        shared = world("1")["SHARED.md"] + "\n<!-- groundwork:1001 -->\nmine\n<!-- /groundwork -->\n"
        self.adopt({**world("1"), "SHARED.md": shared, "docs/adr/1001-mine.md": "# mine\n"}, version="0.1.0", choice="0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has("docs/adr/1001-mine.md"))
        self.assertIn("<!-- groundwork:1001 -->", read(self.project, "SHARED.md"))

    def test_without_a_choice_there_is_nothing_to_do_and_it_says_so(self):
        self.adopt(world("1"), version="0.1.0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("nothing", result.stdout.lower())
        self.assertEqual(self.status(), "")

    def test_a_list_of_adrs_is_refused_and_the_file_of_the_choice_is_named(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n")
        result = self.run_script("0003")
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-adrs", result.stderr)

    def test_a_recorded_version_that_the_source_did_not_publish_is_refused(self):
        self.adopt(world("1"), version="0.9.9", choice="0001\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("0.9.9", result.stderr)

    def test_a_refused_choice_changes_nothing(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n1000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-adrs:2", result.stderr)
        self.assertEqual(self.status(), "")

    def test_a_path_of_the_map_of_the_recorded_version_that_leaves_the_repository_is_refused(self):
        files = world("1")
        files["docs/practices.md"] = files["docs/practices.md"].replace("`four.txt`", "`../outside.txt`")
        shutil.rmtree(self.source)
        init(self.source)
        self.release(files)
        self.adopt(world("1"), version="0.1.0", choice="0001\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(os.path.exists(self.outside))
        self.assertEqual(self.status(), "")


class Widened(Fixture):
    def test_it_brings_the_files_and_the_blocks_of_the_adrs_that_entered_the_choice(self):
        self.adopt(trimmed(world("1"), {1, 2}), version="0.1.0", choice="0003\n0004\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("three.txt", "four.txt", adr(3), adr(4)):
            self.assertEqual(read(self.project, name), world("1")[name], name)
        self.assertEqual(read(self.project, "SHARED.md"), world("1")["SHARED.md"])
        self.assertIn("three.txt", self.lines(result, "add: "))
        self.assertIn("SHARED.md", self.lines(result, "merge: "))

    def test_an_adr_that_enters_without_being_listed_is_said(self):
        self.adopt(trimmed(world("1"), {1}), version="0.1.0", choice="0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("added: 0002", result.stdout)
        self.assertTrue(self.has("two.txt"))

    def test_narrowing_and_widening_at_once(self):
        self.adopt(trimmed(world("1"), {1, 2, 3}), version="0.1.0", choice="0001\n0004\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("two.txt", "three.txt", adr(2), adr(3)):
            self.assertFalse(self.has(name), name)
        self.assertEqual(read(self.project, "four.txt"), "four 1\n")
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(world("1")["SHARED.md"], "markdown", {1, 4}))

    def test_what_the_project_changed_in_a_block_that_is_kept_merges(self):
        shared = markers.remove(world("1")["SHARED.md"], "markdown", {1, 2}).replace("first 2", "first 2, mine")
        self.adopt({**trimmed(world("1"), {1, 2}), "SHARED.md": shared}, version="0.1.0", choice="0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = read(self.project, "SHARED.md")
        self.assertIn("first 2, mine", text)
        self.assertIn("last 3 v1", text)


class Safety(Fixture):
    def test_a_working_tree_that_is_not_clean_is_refused(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n")
        put(self.project, {"scratch.txt": "x\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("clean", result.stderr)
        self.assertTrue(self.has("two.txt"))

    def test_the_default_branch_is_refused(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n", branch=None)
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("main", result.stderr)
        self.assertTrue(self.has("two.txt"))

    def test_the_default_branch_that_the_remote_names_is_refused(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n", branch=None)
        git(self.project, "branch", "-m", "trunk")
        git(self.project, "remote", "add", "origin", self.source)
        git(self.project, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        git(self.project, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("trunk", result.stderr)

    def test_a_dry_run_changes_no_file_nor_the_index_nor_the_branches_and_says_what_it_would_do(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n0002\n")
        branches = git(self.project, "branch", "--format=%(refname:short)")
        result = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.status(), "")
        self.assertEqual(git(self.project, "branch", "--format=%(refname:short)"), branches)
        self.assertEqual(git(self.project, "diff", "--cached", "--name-only").strip(), "")
        self.assertIn("three.txt", self.lines(result, "delete: "))
        self.assertIn("dry run", result.stdout)

    def test_a_dry_run_is_allowed_on_the_default_branch_and_with_a_working_tree_that_is_not_clean(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n", branch=None)
        put(self.project, {"scratch.txt": "x\n"})
        result = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("three.txt", self.lines(result, "delete: "))
        self.assertTrue(self.has("three.txt"))

    def test_a_dry_run_says_the_same_as_the_real_run(self):
        self.adopt(trimmed(world("1"), {1, 2, 3}), version="0.1.0", choice="0001\n0004\n")
        dry = self.run_script("--dry-run")
        real = self.run_script()
        keep = lambda result: [line for line in result.stdout.splitlines() if line.split(":")[0] in ("add", "merge", "delete", "edit", "keep")]  # noqa: E731
        self.assertEqual(keep(dry), keep(real))

    def test_a_second_run_changes_nothing(self):
        self.adopt(world("1"), version="0.1.0", choice="0001\n0002\n")
        self.run_script()
        commit(self.project)
        again = self.run_script()
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.status(), "")
        for prefix in ("add: ", "merge: ", "delete: ", "edit: ", "keep: "):
            self.assertEqual(self.lines(again, prefix), [])

    def test_the_second_run_after_widening_changes_nothing(self):
        self.adopt(trimmed(world("1"), {1, 2}), version="0.1.0", choice="0003\n0004\n")
        self.run_script()
        commit(self.project)
        again = self.run_script()
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.status(), "")


def dependents(needs, number):
    found, grew = {number}, True
    while grew:
        grew = False
        for other, wanted in needs.items():
            if other not in found and wanted & found:
                found.add(other)
                grew = True
    return found


@unittest.skipUnless(is_source(ROOT, os.environ), "it describes the files of a source of ADRs, and a project has not all of them: set GROUNDWORK_SOURCE=true to run it in a community base")
class RealFiles(unittest.TestCase):
    """What the command does to the files of groundwork itself."""

    @classmethod
    def setUpClass(cls):
        entries = practices_map.read_map(ROOT)[0]
        cls.needs = practices_map.needs_of(entries)
        cls.numbers = sorted(cls.needs)
        listed = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
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
            return subprocess.run([sys.executable, SCRIPT, "--source", source, *args], cwd=project, capture_output=True, text=True)
        env = rewritten_env(update_groundwork.SOURCE, source)
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=project, capture_output=True, text=True, env=env)

    def kept_without(self, number):
        gone = dependents(self.needs, number)
        return [n for n in self.numbers if n not in gone]

    def test_the_checks_pass_after_the_command_for_each_adr_left_out_and_for_adr_0001_alone(self):
        sets = [("0001", [1])] + [(f"{number:04d}", self.kept_without(number)) for number in self.numbers if number != 1]
        for name, kept in sets:
            with self.subTest(left_out=name):
                source, project = self.world()
                result = self.run_in(project, source, *[f"{n:04d}" for n in kept])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                put(project, {"README.md": README, "LICENSE": LICENSE})
                git(project, "add", "-A")
                problems = check_adrs.check(project) + check_practices.check(project) + check_links.check(project)
                self.assertEqual(problems, [])

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
                for path in self.paths:
                    with open(os.path.join(ROOT, path), encoding="utf-8", errors="surrogateescape") as handle:
                        original = handle.read()
                    self.assertEqual(read(project, path), original, path)


if __name__ == "__main__":
    unittest.main()
