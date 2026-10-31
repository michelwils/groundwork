import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import markers  # noqa: E402
import update_groundwork  # noqa: E402
from choice import Kept  # noqa: E402

SCRIPT = os.path.join(HERE, "update_groundwork.py")

V1 = {
    "README.md": "# groundwork\n",
    "LICENSE": "MIT\n",
    "CONTRIBUTING.md": "one\ntwo\nthree\n",
    "SECURITY.md": "security\n",
    "old.md": "old\n",
    "logo.bin": "a\0b",
}
V2 = {
    **V1,
    "README.md": "# groundwork 0.2\n",
    "LICENSE": "MIT 2026\n",
    "CONTRIBUTING.md": "one\ntwo changed\nthree\n",
    "new.md": "new\n",
    "logo.bin": "a\0c",
}
V3 = {name: content for name, content in V2.items() if name != "old.md"}
V3["SECURITY.md"] = "security 0.3\n"


ADDRESS = "https://example.org/base.git"


def rewritten_env(address, path):
    """The environment in which git takes the address for the repository at the path, so that no test needs the network."""
    return {
        **os.environ,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": f"url.{path}.insteadOf",
        "GIT_CONFIG_VALUE_0": address,
    }


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def init(path):
    os.makedirs(path)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "config", "tag.gpgsign", "false")
    git(path, "config", "core.hooksPath", os.devnull)


def write(path, files):
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as handle:
            handle.write(content)


def read(path, name):
    with open(os.path.join(path, name)) as handle:
        return handle.read()


def tag_with_hook(repo, base, version, directory):
    """Tag in repo, on top of the tag base, a version whose tree adds an executable hook under directory
    (a/b for a nested one): git mktree builds such a tree, which no checkout can."""

    def run(*args, input=""):
        return subprocess.run(
            ["git", *args], cwd=repo, input=input, check=True, capture_output=True, text=True
        ).stdout.strip()

    hook = run("hash-object", "-w", "--stdin", input="#!/bin/sh\ntouch ran\n")
    entry = f"100755 blob {hook}\tpre-commit\n"
    for name in reversed(f"{directory}/hooks".split("/")):
        entry = f"040000 tree {run('mktree', input=entry)}\t{name}\n"
    root = run("mktree", input=git(repo, "ls-tree", base) + entry)
    git(
        repo,
        "tag",
        "-a",
        f"v{version}",
        "-m",
        f"v{version}",
        run("commit-tree", root, "-p", f"{base}^{{commit}}", "-m", f"feat: release {version}"),
    )


class CheckOfTheResultPath(unittest.TestCase):
    def test_a_path_that_can_be_written_is_left_as_it_was(self):
        with tempfile.TemporaryDirectory() as directory:
            new, old = os.path.join(directory, "new.json"), os.path.join(directory, "old.json")
            with open(old, "w") as handle:
                handle.write("kept")
            update_groundwork.check_result_path(new)
            update_groundwork.check_result_path(old)
            self.assertFalse(os.path.exists(new))
            with open(old) as handle:
                self.assertEqual(handle.read(), "kept")
            self.assertEqual(sorted(os.listdir(directory)), ["old.json"])

    def test_a_path_that_cannot_be_written_is_refused_with_its_name(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in (os.path.join(directory, "missing", "result.json"), directory):
                with self.subTest(path=path):
                    with self.assertRaises(update_groundwork.Failure) as caught:
                        update_groundwork.check_result_path(path)
                    self.assertIn(path, str(caught.exception))
                    self.assertIn("No branch is created", str(caught.exception))


class Types(unittest.TestCase):
    def test_a_step_names_its_path_and_its_two_contents_and_unpacks_in_three(self):
        step = update_groundwork.Step("a.txt", None, b"new")
        path, base, theirs = step
        self.assertEqual((step.path, step.base, step.theirs), (path, base, theirs))
        self.assertEqual(step, ("a.txt", None, b"new"))

    def test_a_plan_names_what_the_choice_asks_for(self):
        step = update_groundwork.Step("a.txt", b"old", b"new")
        with tempfile.TemporaryDirectory() as root:
            side = update_groundwork.Side(root=root)
        kept = Kept(None, {})
        planned = update_groundwork.Plan(said=[3], steps=[step], side=side, kept=kept)
        self.assertEqual((planned.said, planned.steps), ([3], [step]))
        self.assertIs(planned.side, side)
        self.assertIs(planned.kept, kept)
        self.assertIsInstance(planned.side, update_groundwork.Side)
        self.assertIsInstance(planned.kept, Kept)


class Inside(unittest.TestCase):
    def test_a_path_through_a_link_to_git_is_not_inside(self):
        with tempfile.TemporaryDirectory() as directory:
            root = os.path.realpath(directory)
            os.makedirs(os.path.join(root, ".git"))
            os.symlink(".git", os.path.join(root, "link"))
            self.assertFalse(update_groundwork.inside(root, "link/config"))
            self.assertTrue(update_groundwork.inside(root, "two.txt"))


class Update(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.source = os.path.join(root, "groundwork")
        init(self.source)
        for version, files in (("0.1.0", V1), ("0.2.0", V2), ("0.3.0", V3)):
            for name in os.listdir(self.source):
                if name != ".git":
                    os.remove(os.path.join(self.source, name))
            write(self.source, files)
            git(self.source, "add", "-A")
            git(self.source, "commit", "-q", "-m", f"feat: release {version}")
            git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")
        self.project = os.path.join(root, "project")
        self.adopt("0.1.0", V1)

    def tearDown(self):
        self.directory.cleanup()

    def adopt(self, version, files):
        init(self.project)
        write(self.project, {**files, ".groundwork-version": f"{version}\n" if version else ""})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")

    def commit_project(self, files):
        write(self.project, files)
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "docs: adjust the project")

    def run_script(self, *args, issue="42"):
        return subprocess.run(
            [sys.executable, SCRIPT, *([issue] if issue else []), "--source", self.source, *args],
            cwd=self.project,
            capture_output=True,
            text=True,
        )

    def branches(self):
        return git(self.project, "branch", "--format=%(refname:short)").split()

    def test_updates_to_the_latest_version(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-3-0")
        self.assertEqual(read(self.project, "new.md"), "new\n")
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), V3["CONTRIBUTING.md"])
        self.assertEqual(read(self.project, "SECURITY.md"), V3["SECURITY.md"])
        self.assertEqual(read(self.project, ".groundwork-version"), "0.3.0\n")

    def test_removes_a_file_that_groundwork_removed(self):
        self.run_script()
        self.assertFalse(os.path.exists(os.path.join(self.project, "old.md")))

    def test_keeps_and_reports_a_file_removed_by_groundwork_that_the_project_changed(self):
        self.commit_project({"old.md": "old, adjusted\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("old.md", result.stdout)
        self.assertEqual(read(self.project, "old.md"), "old, adjusted\n")

    def test_keeps_and_reports_a_binary_file_changed_on_both_sides(self):
        self.commit_project({"logo.bin": "a\0d"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("logo.bin", result.stdout)
        self.assertEqual(read(self.project, "logo.bin"), "a\0d")

    def test_updates_to_a_given_version(self):
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, "SECURITY.md"), V1["SECURITY.md"])
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def advance(self, files, tag=None):
        """Commit the files on the main branch of the source, after its last release, and return the commit."""
        for name in os.listdir(self.source):
            if name != ".git":
                os.remove(os.path.join(self.source, name))
        write(self.source, files)
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", "feat: work after the release")
        if tag:
            git(self.source, "tag", "-a", f"v{tag}", "-m", f"v{tag}")
        return git(self.source, "rev-parse", "HEAD").strip()

    def at_the_third_release(self):
        self.commit_project({**V3, ".groundwork-version": "0.3.0\n"})

    def commit_update(self):
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: update groundwork")

    def test_moves_the_project_to_the_head_of_the_source_and_records_the_commit(self):
        self.at_the_third_release()
        head = self.advance({**V3, "SECURITY.md": "security head\n", "extra.md": "extra\n"})
        result = self.run_script("--to", "head")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            git(self.project, "branch", "--show-current").strip(), f"chore/42-update-groundwork-to-{head[:12]}"
        )
        self.assertEqual(read(self.project, "SECURITY.md"), "security head\n")
        self.assertEqual(read(self.project, "extra.md"), "extra\n")
        self.assertEqual(read(self.project, ".groundwork-version"), f"0.3.0+{head}\n")
        self.assertIn(f"to: 0.3.0+{head}", result.stdout)

    def test_the_head_that_is_a_release_is_recorded_as_that_release(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"}, tag="0.4.0")
        result = self.run_script("--to", "head")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-4-0")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.4.0\n")

    def test_an_update_to_the_head_reports_the_files_in_conflict_as_an_update_to_a_release_does(self):
        self.commit_project({**V3, ".groundwork-version": "0.3.0\n", "SECURITY.md": "project security\n"})
        self.advance({**V3, "SECURITY.md": "security head\n"})
        result = self.run_script("--to", "head")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("- SECURITY.md", result.stdout)
        self.assertIn("<<<<<<<", read(self.project, "SECURITY.md"))

    def test_the_project_that_has_the_head_is_up_to_date(self):
        self.advance({**V3, "extra.md": "extra\n"})
        head = git(self.source, "rev-parse", "HEAD").strip()
        self.commit_project({".groundwork-version": f"0.3.0+{head}\n"})
        result = self.run_script("--to", "head")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), ["main"])

    def test_the_head_that_is_the_recorded_release_is_up_to_date(self):
        self.commit_project({".groundwork-version": "0.3.0\n"})
        result = self.run_script("--to", "head")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), ["main"])

    def test_the_next_update_to_a_release_that_has_the_commit_has_no_conflict_on_what_was_applied(self):
        self.at_the_third_release()
        self.advance({**V3, "CONTRIBUTING.md": "one\ntwo head\nthree\n"})
        self.assertEqual(self.run_script("--to", "head").returncode, 0)
        self.commit_update()
        self.advance({**V3, "CONTRIBUTING.md": "one\ntwo release\nthree\n"}, tag="0.4.0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), "one\ntwo release\nthree\n")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.4.0\n")

    def test_a_project_on_a_commit_is_up_to_date_while_no_release_has_the_commit(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"})
        self.assertEqual(self.run_script("--to", "head").returncode, 0)
        self.commit_update()
        branches = self.branches()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), branches)

    def test_a_project_on_a_commit_is_not_moved_to_a_release_that_lacks_it(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"})
        self.assertEqual(self.run_script("--to", "head").returncode, 0)
        self.commit_update()
        result = self.run_script("--to", "0.3.0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("contain", result.stderr)

    def test_a_head_that_does_not_have_the_recorded_commit_is_refused(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"})
        self.assertEqual(self.run_script("--to", "head").returncode, 0)
        self.commit_update()
        git(self.source, "tag", "-a", "v0.4.0", "-m", "v0.4.0")  # a release keeps the commit when the head is rewritten
        git(self.source, "reset", "-q", "--hard", "v0.3.0")
        self.advance({**V3, "other.md": "other\n"})
        branches = self.branches()
        result = self.run_script("--to", "head")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not contain", result.stderr)
        self.assertEqual(self.branches(), branches)

    def test_a_recorded_commit_that_the_source_does_not_have_is_refused(self):
        self.commit_project({".groundwork-version": f"0.3.0+{'a' * 40}\n"})
        for args in ((), ("--to", "head")):
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn("commit", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_a_commit_that_an_earlier_source_left_in_the_repository_is_not_one_of_this_source(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"})
        self.assertEqual(self.run_script("--to", "head").returncode, 0)
        self.commit_update()
        other = os.path.join(self.directory.name, "other")
        git(self.directory.name, "clone", "-q", self.source, other)
        git(other, "reset", "-q", "--hard", "v0.3.0")
        branches = self.branches()
        for args in ((), ("--to", "head")):
            with self.subTest(args=args):
                result = self.run_script(*args, "--source", other)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("is not in", result.stderr)
                self.assertEqual(self.branches(), branches)

    def test_the_message_of_a_project_on_a_commit_says_that_no_release_has_it_yet(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"})
        self.assertEqual(self.run_script("--to", "head").returncode, 0)
        self.commit_update()
        self.assertIn("No release has its commit yet", self.run_script().stdout)

    def test_fails_with_a_malformed_commit_in_the_version_file(self):
        for content in (
            "0.3.0+abc\n",
            f"0.3.0+{'A' * 40}\n",
            f"0.3.0+{'a' * 39}\n",
            f"0.3.0+{'a' * 41}\n",
            f"0.3.0+{'a' * 40}+{'a' * 40}\n",
            f"+{'a' * 40}\n",
        ):
            with self.subTest(content=content):
                self.commit_project({".groundwork-version": content})
                result = self.run_script("--to", "head")
                self.assertEqual(result.returncode, 1)
                self.assertIn("X.Y.Z", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_the_head_is_never_the_default(self):
        self.at_the_third_release()
        self.advance({**V3, "extra.md": "extra\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), ["main"])

    def test_leaves_out_the_files_of_groundwork_itself(self):
        self.run_script()
        self.assertEqual(read(self.project, "README.md"), V1["README.md"])
        self.assertEqual(read(self.project, "LICENSE"), V1["LICENSE"])

    def test_without_an_issue_the_branch_is_the_one_of_the_update_of_groundwork(self):
        result = self.run_script(issue=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        branch = git(self.project, "branch", "--show-current").strip()
        self.assertEqual(branch, "groundwork/update-to-v0-3-0")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.3.0\n")

    def test_does_not_commit_nor_leave_the_branch_of_the_project(self):
        head = git(self.project, "rev-parse", "main").strip()
        self.run_script()
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        self.assertTrue(git(self.project, "status", "--porcelain").strip())

    def test_the_branch_is_named_after_the_issue_and_the_version(self):
        self.run_script()
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-3-0")

    def test_keeps_the_changes_of_the_project_that_do_not_conflict(self):
        self.commit_project({"CONTRIBUTING.md": "zero\none\ntwo\nthree\n"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), "zero\none\ntwo changed\nthree\n")

    def test_reports_the_files_in_conflict(self):
        self.commit_project({"CONTRIBUTING.md": "one\ntwo mine\nthree\n"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CONTRIBUTING.md", result.stdout)
        self.assertNotIn("new.md", result.stdout)
        self.assertIn("<<<<<<<", read(self.project, "CONTRIBUTING.md"))
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def result_file(self):
        return os.path.join(self.directory.name, "result.json")

    def result(self):
        with open(self.result_file()) as handle:
            return json.load(handle)

    def test_gives_the_result_in_the_file_that_the_caller_names(self):
        self.commit_project({"CONTRIBUTING.md": "one\ntwo mine\nthree\n"})
        result = self.run_script("--to", "0.2.0", "--result", self.result_file())
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(
            self.result(),
            {
                "branch": "chore/42-update-groundwork-to-v0-2-0",
                "from": "0.1.0",
                "to": "0.2.0",
                "source": self.source,
                "added": [],
                "conflicts": ["CONTRIBUTING.md"],
            },
        )

    def test_a_relative_path_of_the_result_is_the_one_of_the_directory_of_the_caller(self):
        directory = os.path.join(self.project, "sub")
        os.makedirs(directory)
        result = subprocess.run(
            [sys.executable, SCRIPT, "42", "--source", self.source, "--to", "0.2.0", "--result", "out.json"],
            cwd=directory,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(os.path.join(directory, "out.json")))
        self.assertFalse(os.path.exists(os.path.join(self.project, "out.json")))

    def test_an_empty_path_of_the_result_stops_the_update_before_anything_changes(self):
        result = self.run_script("--to", "0.2.0", "--result", "")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("--result", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_a_result_that_cannot_be_written_stops_the_update_before_the_branch(self):
        missing = os.path.join(self.directory.name, "missing", "result.json")
        for path in (missing, self.directory.name):  # a folder that does not exist, and a folder in place of a file
            with self.subTest(path=path):
                result = self.run_script("--to", "0.2.0", "--result", path)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(path, result.stderr)
                self.assertIn("No branch is created", result.stderr)
                self.assertEqual(self.branches(), ["main"])
                self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")
                self.assertEqual(read(self.project, ".groundwork-version"), "0.1.0\n")

    def test_a_result_that_cannot_be_written_does_not_matter_when_the_project_is_up_to_date(self):
        self.commit_project({".groundwork-version": "0.3.0\n"})
        missing = os.path.join(self.directory.name, "missing", "result.json")
        result = self.run_script("--result", missing)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertFalse(os.path.exists(os.path.dirname(missing)))

    def test_the_result_of_an_update_without_conflict_lists_none(self):
        result = self.run_script("--to", "0.2.0", "--result", self.result_file())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result()["conflicts"], [])

    def test_writes_no_result_when_the_project_is_up_to_date(self):
        self.run_script("--to", "0.3.0")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: update groundwork to v0.3.0")
        result = self.run_script("--result", self.result_file(), issue=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(os.path.exists(self.result_file()))

    def test_a_path_cannot_add_or_replace_a_field_of_the_result(self):
        name = 'x", "branch": "victim.md'
        self.assertEqual(
            json.loads(json.dumps({"conflicts": [name]}))["conflicts"], [name]
        )  # the encoding the script relies on
        self.commit_project({name: "mine\n"})
        git(self.source, "checkout", "-q", "-b", "other", "v0.3.0")
        write(self.source, {name: "theirs\n"})
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", "feat: release 0.4.0")
        git(self.source, "tag", "-a", "v0.4.0", "-m", "v0.4.0")
        result = self.run_script("--to", "0.4.0", "--result", self.result_file())
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        fields = self.result()
        self.assertEqual(fields["conflicts"], [name])
        self.assertEqual(fields["branch"], "chore/42-update-groundwork-to-v0-4-0")
        self.assertEqual(sorted(fields), ["added", "branch", "conflicts", "from", "source", "to"])

    def test_accepts_a_project_already_ahead_of_its_recorded_version(self):
        self.commit_project({"new.md": "new\n", "CONTRIBUTING.md": V2["CONTRIBUTING.md"]})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_does_nothing_when_the_project_is_up_to_date(self):
        self.commit_project({".groundwork-version": "0.3.0\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_without_the_version_file(self):
        os.remove(os.path.join(self.project, ".groundwork-version"))
        git(self.project, "commit", "-q", "-am", "chore: remove the version file")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-version", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_with_a_malformed_version_file(self):
        for content in ("v0.1.0\n", "0.1\n", "0.1.0\n0.2.0\n", "\n"):
            with self.subTest(content=content):
                self.commit_project({".groundwork-version": content})
                result = self.run_script()
                self.assertEqual(result.returncode, 1)
                self.assertIn("X.Y.Z", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_fails_with_an_unknown_recorded_version(self):
        self.commit_project({".groundwork-version": "0.9.9\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("0.9.9", result.stderr)

    def test_fails_when_the_target_is_not_a_later_version(self):
        for target in ("0.1.0", "0.0.9"):
            with self.subTest(target=target):
                result = self.run_script("--to", target)
                self.assertEqual(result.returncode, 1)
                self.assertIn("later", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_fails_with_an_unknown_target(self):
        result = self.run_script("--to", "7.0.0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("7.0.0", result.stderr)

    def test_fails_when_the_working_tree_is_not_clean(self):
        write(self.project, {"SECURITY.md": "edited\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("clean", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_when_the_branch_already_exists(self):
        git(self.project, "branch", "chore/42-update-groundwork-to-v0-3-0")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("chore/42-update-groundwork-to-v0-3-0", result.stderr)

    def test_fails_with_an_issue_that_is_not_a_number(self):
        result = self.run_script(issue="abc")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.branches(), ["main"])

    # Names that a file system can take for .git: in any case, on HFS+ with the characters it ignores, on NTFS with
    # trailing dots and spaces, a stream, its short name or a backslash for a separator.
    GIT_DIRECTORIES = (
        ".git",
        ".GIT",
        "sub/.git",
        ".git.",
        ".git ",
        ".git::$INDEX_ALLOCATION",
        "GIT~1",
        ".g\u200cit",
        ".git\\x",
    )

    def test_a_version_that_holds_a_path_under_git_is_refused_before_anything_changes(self):
        for version, directory in enumerate(self.GIT_DIRECTORIES, start=4):
            with self.subTest(directory=directory):
                shutil.rmtree(self.project)
                self.adopt("0.1.0", V1)
                tag_with_hook(self.source, "v0.3.0", f"0.{version}.0", directory)
                result = self.run_script("--to", f"0.{version}.0")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(f"{directory}/hooks/pre-commit", result.stderr)
                self.assertFalse(os.path.exists(os.path.join(self.project, ".git", "hooks", "pre-commit")))
                self.assertEqual(git(self.project, "status", "--porcelain", "--ignored"), "")
                self.assertEqual(self.branches(), ["main"])

    def test_a_version_that_holds_a_path_with_a_control_character_is_refused_before_anything_changes(self):
        # A line break in a name would add a line to the text that the script prints. A bidirectional
        # control, such as U+202E, changes how the name is shown to the reviewer.
        for version, character in enumerate(
            ("\n", "\r", "\x1b", "\x85", "\u2028", "\u2029", "\u202a", "\u202e", "\u2066", "\u2069"), start=4
        ):
            with self.subTest(character=character):
                shutil.rmtree(self.project)
                self.adopt("0.1.0", V1)
                name = f"notes{character}branch: victim"
                write(self.source, {name: "notes\n"})
                git(self.source, "add", "-A")
                git(self.source, "commit", "-q", "-m", f"feat: release 0.{version}.0")
                git(self.source, "tag", "-a", f"v0.{version}.0", "-m", f"v0.{version}.0")
                os.remove(os.path.join(self.source, name))
                result = self.run_script("--to", f"0.{version}.0")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(repr(name), result.stderr)
                self.assertEqual(git(self.project, "status", "--porcelain", "--ignored"), "")
                self.assertEqual(self.branches(), ["main"])

    def test_a_path_under_git_with_a_bidirectional_control_is_named_without_the_control(self):
        tag_with_hook(self.source, "v0.3.0", "0.4.0", ".git\u202e")
        result = self.run_script("--to", "0.4.0")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(repr(".git\u202e/hooks/pre-commit"), result.stderr)
        self.assertNotIn("\u202e", result.stderr)

    def test_a_name_with_an_invisible_character_that_a_script_needs_is_updated(self):
        # U+200C is required in Persian and Hindi, U+200D in emoji sequences, U+00AD is a soft hyphen.
        for version, character in enumerate(("\u200c", "\u200d", "\u00ad"), start=4):
            with self.subTest(character=character):
                shutil.rmtree(self.project)
                self.adopt("0.1.0", V1)
                name = f"notes{character}.md"
                write(self.source, {name: "notes\n"})
                git(self.source, "add", "-A")
                git(self.source, "commit", "-q", "-m", f"feat: release 0.{version}.0")
                git(self.source, "tag", "-a", f"v0.{version}.0", "-m", f"v0.{version}.0")
                result = self.run_script("--to", f"0.{version}.0")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(os.path.exists(os.path.join(self.project, name)))

    def test_a_name_that_only_starts_like_git_is_updated(self):
        for version, directory in enumerate((".github", ".gitx", "git~2", "x.git"), start=4):
            with self.subTest(directory=directory):
                shutil.rmtree(self.project)
                self.adopt("0.1.0", V1)
                tag_with_hook(self.source, "v0.3.0", f"0.{version}.0", directory)
                result = self.run_script("--to", f"0.{version}.0")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(os.path.exists(os.path.join(self.project, directory, "hooks", "pre-commit")))

    def test_a_path_through_a_link_of_the_project_to_git_or_outside_is_refused_before_anything_changes(self):
        outside = os.path.join(self.directory.name, "outside")
        os.makedirs(os.path.join(outside, "hooks"))
        for version, target in enumerate((".git", outside), start=4):
            with self.subTest(target=target):
                shutil.rmtree(self.project)
                self.adopt("0.1.0", V1)
                os.symlink(target, os.path.join(self.project, "s"))
                self.commit_project({})
                tag_with_hook(self.source, "v0.3.0", f"0.{version}.0", "s")
                result = self.run_script("--to", f"0.{version}.0")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("s/hooks/pre-commit", result.stderr)
                self.assertFalse(os.path.exists(os.path.join(self.project, ".git", "hooks", "pre-commit")))
                self.assertFalse(os.path.exists(os.path.join(outside, "hooks", "pre-commit")))
                self.assertEqual(git(self.project, "status", "--porcelain", "--ignored"), "")
                self.assertEqual(self.branches(), ["main"])

    def tags(self, repo):
        return git(repo, "tag", "--list").split()

    def source_that_ran_the_update(self):
        """A repository that ran the update and published a version: a project that is the source of another."""
        git(self.project, "tag", "-a", "v0.9.0", "-m", "v0.9.0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "fix: update groundwork to v0.3.0")
        git(self.project, "tag", "-a", "v1.0.0", "-m", "v1.0.0")
        second = os.path.join(self.directory.name, "second")
        init(second)
        write(second, {**V1, ".groundwork-version": "0.9.0\n"})
        git(second, "add", "-A")
        git(second, "commit", "-q", "-m", "Initial commit")
        return second

    def update_from(self, repo, source):
        return subprocess.run([sys.executable, SCRIPT, "--source", source], cwd=repo, capture_output=True, text=True)

    def test_leaves_the_tags_of_the_source_under_their_own_prefix_only(self):
        self.run_script()
        self.assertEqual(self.tags(self.project), ["groundwork/v0.1.0", "groundwork/v0.2.0", "groundwork/v0.3.0"])

    def test_keeps_a_tag_of_the_project_named_like_one_of_the_source(self):
        git(self.project, "tag", "-a", "v0.1.0", "-m", "the project's own")
        before = git(self.project, "rev-parse", "v0.1.0").strip()
        self.run_script()
        self.assertEqual(git(self.project, "rev-parse", "v0.1.0").strip(), before)
        self.assertIn("groundwork/v0.1.0", self.tags(self.project))

    def test_a_repository_that_ran_the_update_can_be_the_source_of_another(self):
        second = self.source_that_ran_the_update()
        result = self.update_from(second, self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(second, ".groundwork-version"), "1.0.0\n")
        self.assertEqual(read(second, "new.md"), "new\n")
        self.assertEqual(read(second, "SECURITY.md"), V3["SECURITY.md"])
        self.assertEqual(self.tags(second), ["groundwork/v0.9.0", "groundwork/v1.0.0"])

    def record(self, content):
        """Commit `.groundwork-source` in the project with this content (text or bytes)."""
        path = os.path.join(self.project, ".groundwork-source")
        if os.path.isdir(path):
            shutil.rmtree(path)
        with open(path, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: record the source")

    def run_from_the_file(self, *args, address=ADDRESS):
        return subprocess.run(
            [sys.executable, SCRIPT, "42", *args],
            cwd=self.project,
            capture_output=True,
            text=True,
            env=rewritten_env(address, self.source),
        )

    def test_takes_its_updates_from_the_source_that_the_project_recorded(self):
        self.record(ADDRESS + "\n")
        result = self.run_from_the_file()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, rf"(?m)^source: {ADDRESS}$")
        self.assertEqual(read(self.project, "new.md"), "new\n")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.3.0\n")

    def test_a_source_given_on_the_command_line_wins_over_the_file_even_a_broken_one(self):
        self.record("not an address\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"source: {self.source}\n", result.stdout)

    def test_without_a_file_or_a_source_it_is_the_constant_of_the_script(self):
        result = self.run_from_the_file(address=update_groundwork.SOURCE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, rf"(?m)^source: {update_groundwork.SOURCE}$")

    def test_the_messages_name_the_source_that_was_used(self):
        self.record(ADDRESS + "\n")
        self.commit_project({".groundwork-version": "0.9.9\n"})
        result = self.run_from_the_file()
        self.assertEqual(result.returncode, 1)
        self.assertIn(ADDRESS, result.stderr)

    def test_a_file_that_is_not_one_address_stops_the_update_before_any_fetch(self):
        refused = [
            "",
            "\n",
            ADDRESS,
            ADDRESS + "\n\n",
            ADDRESS + "\r\n",
            "\ufeff" + ADDRESS + "\n",
            b"\xff\n",
            " " + ADDRESS + "\n",
            "http://example.org/base.git\n",
            "ssh://example.org/base.git\n",
            "git://example.org/base.git\n",
            "/tmp/base\n",
            "../base\n",
            "-x\n",
            "--upload-pack=true\n",
            "https://\n",
            "https://user:token@example.org/base.git\n",
            "https://user@example.org/base.git\n",
            "https://example.org/base .git\n",
            "https://example.org/base.git?x=1\n",
            "https://example.org/base.git#x\n",
            "https://example.org/" + "a" * 2100 + "\n",
        ]
        for content in refused:
            with self.subTest(content=content[:60] if isinstance(content, str) else content):
                self.record(content)
                result = self.run_from_the_file()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(".groundwork-source", result.stderr)
                self.assertEqual(self.branches(), ["main"])
                self.assertEqual(git(self.project, "tag", "--list").split(), [])

    def test_a_directory_in_place_of_the_file_stops_the_update(self):
        os.makedirs(os.path.join(self.project, ".groundwork-source"))
        write(self.project, {".groundwork-source/x": "x\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: a directory")
        result = self.run_from_the_file()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-source", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_an_address_with_a_port_and_a_path_is_accepted(self):
        address = "https://git.example.org:8443/team/base.git"
        self.record(address + "\n")
        result = self.run_from_the_file(address=address)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_file_of_a_source_is_not_copied_to_the_project(self):
        write(self.source, {".groundwork-source": "https://evil.example/x.git\n"})
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", "feat: release 0.4.0")
        git(self.source, "tag", "-a", "v0.4.0", "-m", "v0.4.0")
        self.record(ADDRESS + "\n")
        result = self.run_from_the_file()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, ".groundwork-source"), ADDRESS + "\n")

    def test_the_tags_of_an_earlier_source_do_not_stay(self):
        git(self.project, "tag", "groundwork/v9.9.9", "HEAD")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-3-0")
        self.assertNotIn("groundwork/v9.9.9", git(self.project, "tag", "--list").split())

    def test_an_address_is_never_taken_for_an_option_of_git(self):
        marker = os.path.join(self.directory.name, "marker")
        result = subprocess.run(
            [sys.executable, SCRIPT, "42", f"--source=--upload-pack=touch {marker}"],
            cwd=self.project,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(self.branches(), ["main"])


NAMES = {1: "first", 2: "second", 3: "third", 4: "fourth"}
NEEDS = {1: [], 2: [], 3: [2], 4: []}
BLOCKED = "<!-- groundwork:{n:04d} -->\nfirst {n}\nmiddle {n}\nlast {n} v{v}\n<!-- /groundwork -->\n"


def adr(number, name=None):
    return f"docs/adr/{number:04d}-{name or NAMES[number]}.md"


def practices(owned, apart):
    lines = ["# Practices", "", "## Practices", ""]
    for number in (2, 3, 4):
        files = "".join(f"  - `{path}`\n" for path in owned.get(number, [])) or "  - none\n"
        needs = ", ".join(f"ADR {need:04d}" for need in NEEDS[number]) or "none"
        lines += [
            f"### {number:04d}. [{NAMES[number].title()}](adr/{number:04d}-{NAMES[number]}.md)",
            "",
            f"- Needs: {needs}",
            "- Files:",
            files.rstrip("\n"),
            "- Shared lines:",
            "  - `SHARED.md`",
            "",
        ]
    lines += ["## Shared files", "", "- `SHARED.md`", "", "## Not part of a practice", ""]
    lines += [f"- `{path}`" for path in apart]
    return "\n".join(lines) + "\n"


def world(v, tool=None, adr3="third"):
    """A tree of groundwork whose content carries the token v, with an ADR 0001 to 0004 and their files.

    `tool` is the ADR that owns `tool.py`, or None when it is part of no practice."""
    owned = {2: ["two.txt"], 3: ["three.txt"], 4: ["four.txt"]}
    if tool:
        owned[tool].append("tool.py")
    shared = "# Shared\n\nIntro.\n\n" + "\nBetween.\n\n".join(BLOCKED.format(n=n, v=v) for n in (2, 3, 4)) + "\nEnd.\n"
    files = {
        "two.txt": f"two {v}\n",
        "three.txt": f"three {v}\n",
        "four.txt": f"four {v}\n",
        "tool.py": "tool\n",
        "SHARED.md": shared,
        ".groundwork/practices.md": practices(owned, [] if tool else ["tool.py"]),
    }
    for number in NAMES:
        files[adr(number, adr3 if number == 3 else None)] = f"# ADR {number:04d} v{v}\n"
    return files


def trimmed(files, kept):
    """What a project that keeps only the ADRs in kept holds of a tree: the files of the others are not there."""
    gone = {"two.txt": 2, "three.txt": 3, "four.txt": 4}
    gone.update({adr(number, "third" if number == 3 else None): number for number in NAMES})
    out = {path: text for path, text in files.items() if gone.get(path, 1) in kept}
    out["SHARED.md"] = markers.remove(files["SHARED.md"], "markdown", kept)
    return out


class Fixture(unittest.TestCase):
    """A source of groundwork that releases versions, and a project in a repository of its own."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.directory.name, "groundwork")
        self.project = os.path.join(self.directory.name, "project")
        init(self.source)

    def tearDown(self):
        self.directory.cleanup()

    def release(self, version, files):
        for name in os.listdir(self.source):
            if name != ".git":
                path = os.path.join(self.source, name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        self.put(self.source, files)
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "--allow-empty", "-m", f"feat: release {version}")
        git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")

    def put(self, root, files):
        for name, content in files.items():
            os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
            with open(os.path.join(root, name), "w") as handle:
                handle.write(content)

    def adopt(self, files, choice=None, version="0.1.0"):
        init(self.project)
        self.put(
            self.project,
            {
                **files,
                ".groundwork-version": f"{version}\n",
                **({".groundwork-adrs": choice} if choice is not None else {}),
            },
        )
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, "42", "--source", self.source, *args],
            cwd=self.project,
            capture_output=True,
            text=True,
        )

    def branches(self):
        return git(self.project, "branch", "--format=%(refname:short)").split()

    def has(self, name):
        return os.path.exists(os.path.join(self.project, name))


class Choice(Fixture):
    """The update applies the ADRs that the project chose (ADR 1000)."""

    def releases(self, first, second):
        self.release("0.1.0", first)
        self.release("0.2.0", second)

    def test_an_adr_that_is_left_out_is_neither_copied_nor_in_conflict(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1, 2}), "0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "two.txt"), "two 2\n")
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(world("2")["SHARED.md"], "markdown", {1, 2}))
        for name in ("three.txt", "four.txt", adr(3), adr(4)):
            self.assertFalse(self.has(name), name)
        self.assertEqual(read(self.project, adr(2)), "# ADR 0002 v2\n")

    def test_adr_0001_is_never_left_out(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1, 4}), "0004\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, adr(1)), "# ADR 0001 v2\n")
        self.assertEqual(read(self.project, "four.txt"), "four 2\n")

    def test_an_adr_that_a_chosen_adr_needs_is_added_and_said(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("added: 0002\n", result.stdout)
        self.assertEqual(read(self.project, "two.txt"), "two 2\n")
        self.assertEqual(read(self.project, "three.txt"), "three 2\n")
        self.assertFalse(self.has("four.txt"))

    def test_the_lines_of_the_report_cannot_be_taken_for_a_conflict(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0003\n")
        result = self.run_script()
        self.assertNotRegex(result.stdout, r"(?m)^- ")
        self.assertRegex(result.stdout, r"(?m)^branch: chore/42-update-groundwork-to-v0-2-0$")
        self.assertRegex(result.stdout, r"(?m)^from: 0\.1\.0$")
        self.assertRegex(result.stdout, r"(?m)^to: 0\.2\.0$")

    def test_the_result_names_the_adrs_that_enter_the_choice(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0003\n")
        path = os.path.join(self.directory.name, "result.json")
        result = self.run_script("--result", path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with open(path) as handle:
            added = json.load(handle)["added"]
        self.assertTrue(added)
        self.assertEqual(result.stdout.count("added: " + ", ".join(added)), 1)

    def test_an_adr_that_the_project_lists_is_not_said_to_be_added(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0004\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("added:", result.stdout)

    def test_an_adr_that_enters_the_choice_is_applied_whole_with_its_blocks(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0002\n0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            read(self.project, "SHARED.md"), markers.remove(world("2")["SHARED.md"], "markdown", {1, 2, 3})
        )
        for name in ("two.txt", "three.txt", adr(2), adr(3)):
            self.assertTrue(self.has(name), name)

    def test_an_adr_that_enters_is_applied_even_if_its_files_did_not_change(self):
        first = world("1")
        self.releases(first, {**first, "docs/more.md": "more\n"})
        self.adopt(trimmed(first, {1}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "two.txt"), "two 1\n")
        self.assertEqual(read(self.project, adr(2)), "# ADR 0002 v1\n")
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(first["SHARED.md"], "markdown", {1, 2}))

    def test_an_adr_that_leaves_the_choice_is_no_longer_updated_and_its_files_stay(self):
        self.releases(world("1"), world("2"))
        self.adopt(world("1"), "0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "two.txt"), "two 2\n")
        self.assertEqual(read(self.project, "three.txt"), "three 1\n")
        self.assertEqual(read(self.project, "four.txt"), "four 1\n")
        self.assertEqual(read(self.project, adr(3)), "# ADR 0003 v1\n")
        shared = read(self.project, "SHARED.md")
        self.assertIn("last 2 v2", shared)
        self.assertIn("last 3 v1", shared)
        self.assertIn("last 4 v1", shared)

    def test_a_change_of_the_project_inside_a_block_that_is_kept_is_merged(self):
        self.releases(world("1"), world("2"))
        mine = world("1")["SHARED.md"].replace("first 2", "first 2, mine")
        self.adopt({**trimmed(world("1"), {1, 2}), "SHARED.md": markers.remove(mine, "markdown", {1, 2})}, "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        shared = read(self.project, "SHARED.md")
        self.assertIn("first 2, mine", shared)
        self.assertIn("last 2 v2", shared)

    def test_a_file_that_leaves_an_adr_for_the_files_of_no_practice_reaches_a_project_that_left_it_out(self):
        self.releases(world("1", tool=3), world("1", tool=None))
        left = {name: text for name, text in trimmed(world("1", tool=3), {1, 2}).items() if name != "tool.py"}
        self.adopt(left, "0002\n")
        self.assertFalse(self.has("tool.py"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "tool.py"), "tool\n")

    def test_an_adr_is_found_by_its_number_and_not_by_the_name_of_its_file(self):
        self.releases(world("1", adr3="before"), world("2", adr3="after"))
        self.adopt(trimmed(world("1", adr3="before"), {1, 2, 3}) | {adr(3, "before"): "# ADR 0003 v1\n"}, "0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "three.txt"), "three 2\n")
        self.assertFalse(self.has(adr(3, "before")))
        self.assertTrue(self.has(adr(3, "after")))
        self.assertNotIn("added:", result.stdout)

    def test_a_number_that_the_source_does_not_reserve_is_refused_before_anything_changes(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n1000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-adrs:2", result.stderr)
        self.assertIn("1000", result.stderr)
        self.assertEqual(self.branches(), ["main"])
        self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")

    def test_the_adrs_that_the_source_does_not_reserve_are_not_copied(self):
        for choice in (None, "0001-0999\n"):
            with self.subTest(choice=choice):
                if os.path.exists(self.project):
                    shutil.rmtree(self.project)
                    shutil.rmtree(self.source)
                    init(self.source)
                self.releases(world("1"), {**world("2"), "docs/adr/1000-own.md": "# own\n"})
                self.adopt(world("1"), choice)
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.has("docs/adr/1000-own.md"))

    def fork(self, ranges="9000-9999\n"):
        second = {**world("2"), "docs/adr/9000-fork.md": "# fork\n"}
        if ranges is not None:
            second[".groundwork-ranges"] = ranges
        self.releases(world("1"), second)

    def test_the_ranges_are_read_in_the_version_the_project_moves_to(self):
        self.fork()
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n9000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "docs/adr/9000-fork.md"), "# fork\n")
        self.assertEqual(read(self.project, ".groundwork-ranges"), "9000-9999\n")

    def test_a_number_of_a_range_that_the_new_version_does_not_reserve_is_refused(self):
        self.fork(ranges=None)
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n9000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("9000", result.stderr)

    def test_a_range_of_the_source_is_taken_without_a_choice(self):
        self.fork()
        self.adopt(world("1"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has("docs/adr/9000-fork.md"))

    def test_a_declaration_of_ranges_that_is_refused_stops_the_update(self):
        self.fork(ranges="nine\n")
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-ranges:1", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_the_choice_and_the_version_of_a_source_are_not_copied(self):
        self.releases(world("1"), {**world("2"), ".groundwork-adrs": "0001\n", ".groundwork-version": "9.9.9\n"})
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, ".groundwork-adrs"), "0002\n")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_a_version_without_a_map_is_refused_when_the_project_has_a_choice(self):
        self.releases(
            world("1"), {name: text for name, text in world("2").items() if name != ".groundwork/practices.md"}
        )
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork/practices.md", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_a_version_without_a_map_is_still_applied_without_a_choice(self):
        self.releases(
            world("1"), {name: text for name, text in world("2").items() if name != ".groundwork/practices.md"}
        )
        self.adopt(world("1"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_move_of_owner_is_not_looked_for_when_the_old_version_has_no_map(self):
        self.releases(
            {name: text for name, text in world("1").items() if name != ".groundwork/practices.md"}, world("2")
        )
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has(".groundwork/practices.md"))
        self.assertFalse(self.has("three.txt"))

    def test_without_a_choice_a_file_that_the_project_removed_is_in_conflict_as_before(self):
        self.releases(world("1"), world("2"))
        self.adopt({name: text for name, text in world("1").items() if name != "four.txt"})
        result = self.run_script()
        self.assertEqual(result.returncode, 3)
        self.assertIn("- four.txt", result.stdout)
        self.assertNotIn("added:", result.stdout)

    def test_without_a_choice_an_adr_file_that_the_project_removed_does_not_come_back(self):
        first = world("1")
        self.releases(first, {**first, "docs/more.md": "more\n"})
        self.adopt({name: text for name, text in first.items() if name not in ("four.txt", adr(4))})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.has("four.txt"))
        self.assertFalse(self.has(adr(4)))


def ledger(numbers):
    """A map of the practices that holds an entry for each number, in this order."""
    entries = "".join(
        f"### {n:04d}. [Decision {n}](adr/{n:04d}-decision.md)\n\n- Needs: none\n- Files:\n  - none\n- Shared lines:\n  - none\n\n"
        for n in numbers
    )
    footer = "## Shared files\n\n## Not part of a practice\n\n- `.groundwork/scripts/update_groundwork.py`\n- `.groundwork/practices.md`\n"
    return "# Practices of groundwork\n\n## Practices\n\n" + entries + footer


def tree(numbers, script, order=None):
    files = {".groundwork/practices.md": ledger(order or numbers), ".groundwork/scripts/update_groundwork.py": script}
    files.update({f"docs/adr/{n:04d}-decision.md": f"# {n}\n" for n in numbers})
    return files


DEPENDABOT = ".github/dependabot.yml"
NEUTRAL = "  - package-ecosystem: github-actions\n    directory: /.groundwork\n\n"
ENTRIES = "  - package-ecosystem: pip\n    groups: x\n\n"
ANCHOR = "  # The entries of the project go below this line.\n"
CARGO = "\n  - package-ecosystem: cargo\n"


class EntriesOfTheSource(Fixture):
    """The entries of Dependabot for what the source owns are not brought to a project, which would open the same
    pull requests as the source (ADR 0008)."""

    # Before the block existed, the entries had no marker.
    BEFORE = "version: 2\nupdates:\n" + ENTRIES + ANCHOR
    AFTER = (
        "version: 2\nupdates:\n"
        + NEUTRAL
        + "  # groundwork:source\n"
        + ENTRIES.rstrip("\n")
        + "\n  # /groundwork:source\n\n"
        + ANCHOR
    )

    def test_a_project_that_has_the_entries_without_markers_loses_them_and_keeps_its_own(self):
        self.release("0.1.0", {DEPENDABOT: self.BEFORE})
        self.release("0.2.0", {DEPENDABOT: self.AFTER})
        self.adopt({DEPENDABOT: self.BEFORE + CARGO})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, DEPENDABOT), "version: 2\nupdates:\n" + NEUTRAL + ANCHOR + CARGO)

    def test_a_project_created_from_the_template_loses_the_block_at_its_first_update(self):
        self.release("0.2.0", {DEPENDABOT: self.AFTER})
        self.release("0.3.0", {DEPENDABOT: self.AFTER.replace("groups: x", "groups: y")})
        self.adopt({DEPENDABOT: self.AFTER + CARGO}, version="0.2.0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, DEPENDABOT), "version: 2\nupdates:\n" + NEUTRAL + ANCHOR + CARGO)

    def test_a_project_that_changed_an_entry_of_the_source_has_a_conflict(self):
        self.release("0.1.0", {DEPENDABOT: self.BEFORE})
        self.release("0.2.0", {DEPENDABOT: self.AFTER})
        self.adopt({DEPENDABOT: (self.BEFORE + CARGO).replace("groups: x", "groups: mine")})
        result = self.run_script()
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(DEPENDABOT, result.stdout)

    def test_the_block_is_not_brought_back_by_a_later_update(self):
        self.release("0.1.0", {DEPENDABOT: self.BEFORE})
        self.release("0.2.0", {DEPENDABOT: self.AFTER})
        self.adopt({DEPENDABOT: self.BEFORE + CARGO})
        self.assertEqual(self.run_script().returncode, 0)
        branch = git(self.project, "branch", "--show-current").strip()
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: update groundwork")
        git(self.project, "switch", "-q", "main")
        git(self.project, "merge", "-q", "--ff-only", branch)
        self.release("0.3.0", {DEPENDABOT: self.AFTER.replace("groups: x", "groups: y")})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, DEPENDABOT), "version: 2\nupdates:\n" + NEUTRAL + ANCHOR + CARGO)

    def test_a_project_that_holds_the_block_loses_it_when_the_new_version_does_not_change_the_file(self):
        # The update that brought the block ran with scripts that did not take it out.
        self.release("0.2.0", {DEPENDABOT: self.AFTER, "other.txt": "1\n"})
        self.release("0.3.0", {DEPENDABOT: self.AFTER, "other.txt": "2\n"})
        self.adopt({DEPENDABOT: self.AFTER + CARGO, "other.txt": "1\n"}, version="0.2.0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, DEPENDABOT), "version: 2\nupdates:\n" + NEUTRAL + ANCHOR + CARGO)


class Chain(unittest.TestCase):
    """A change of groundwork reaches a project through a community base, with a pull request on each (the guide of the bases)."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.groundwork, self.base, self.project = (
            os.path.join(root, name) for name in ("groundwork", "base", "project")
        )
        with open(SCRIPT) as handle:
            self.script = handle.read()
        self.assertIn('SOURCE = "https://github.com/michelwils/groundwork.git"\n', self.script)
        self.later = self.script.replace('"""Prepare the update', '"""Prepares the update', 1)
        self.assertNotEqual(self.later, self.script)
        init(self.groundwork)
        self.release(self.groundwork, "v0.1.0", tree([1, 13], self.script))
        self.release(self.groundwork, "v0.2.0", tree([1, 13, 14], self.later))

    def tearDown(self):
        self.directory.cleanup()

    def put(self, root, files):
        for name, content in files.items():
            os.makedirs(os.path.dirname(os.path.join(root, name)) or root, exist_ok=True)
            with open(os.path.join(root, name), "w") as handle:
                handle.write(content)

    def release(self, repo, tag, files):
        for name in os.listdir(repo):
            if name != ".git":
                path = os.path.join(repo, name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        self.put(repo, files)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", f"feat: release {tag}")
        git(repo, "tag", "-a", tag, "-m", tag)

    def found_base(self, order):
        """The base: groundwork 0.1.0 with a range of its own, an ADR in it and its entry, released as v0.9.0."""
        init(self.base)
        self.put(
            self.base,
            {**tree([1, 13], self.script, order=[n for n in order if n != 9000]), ".groundwork-version": "0.1.0\n"},
        )
        git(self.base, "add", "-A")
        git(self.base, "commit", "-q", "-m", "Initial commit")
        self.put(self.base, {**tree([1, 13, 9000], self.script, order=order), ".groundwork-ranges": "9000-9999\n"})
        git(self.base, "add", "-A")
        git(self.base, "commit", "-q", "-m", "feat: reserve a range")
        git(self.base, "tag", "-a", "v0.9.0", "-m", "v0.9.0")

    def update(self, repo, source):
        return subprocess.run([sys.executable, SCRIPT, "--source", source], cwd=repo, capture_output=True, text=True)

    def test_an_entry_of_the_base_before_those_of_groundwork_does_not_conflict_with_a_new_entry_of_groundwork(self):
        self.found_base([9000, 1, 13])
        result = self.update(self.base, self.groundwork)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("### 0014.", read(self.base, ".groundwork/practices.md"))
        self.assertIn("### 9000.", read(self.base, ".groundwork/practices.md"))

    def test_an_entry_of_the_base_after_those_of_groundwork_conflicts_with_a_new_entry_of_groundwork(self):
        self.found_base([1, 13, 9000])
        result = self.update(self.base, self.groundwork)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("- .groundwork/practices.md", result.stdout)

    def test_the_project_gets_the_change_of_groundwork_and_the_range_of_the_base_from_the_base(self):
        self.found_base([9000, 1, 13])
        self.assertEqual(self.update(self.base, self.groundwork).returncode, 0)
        git(self.base, "add", "-A")
        git(self.base, "commit", "-q", "-m", "fix: update groundwork to v0.2.0")
        git(self.base, "switch", "-q", "main")
        git(self.base, "merge", "-q", "--ff-only", "groundwork/update-to-v0-2-0")
        git(self.base, "tag", "-a", "v1.0.0", "-m", "v1.0.0")
        self.adopt_from_the_base()
        result = self.update(self.project, self.base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, ".groundwork-version"), "1.0.0\n")
        self.assertEqual(read(self.project, "docs/adr/0014-decision.md"), "# 14\n")
        self.assertEqual(read(self.project, "docs/adr/9000-decision.md"), "# 9000\n")
        self.assertEqual(read(self.project, ".groundwork-ranges"), "9000-9999\n")
        script = read(self.project, ".groundwork/scripts/update_groundwork.py")
        self.assertIn('"""Prepares the update', script)
        self.assertIn('SOURCE = "https://example.org/base.git"\n', script)

    def adopt_from_the_base(self):
        """A project made from the base at v0.9.0, which sets the source of its updates to the base."""
        init(self.project)
        archive = subprocess.run(
            ["git", "archive", "--format=tar", "v0.9.0"], cwd=self.base, capture_output=True, check=True
        ).stdout
        subprocess.run(["tar", "-x", "-C", self.project], input=archive, check=True)
        path = os.path.join(self.project, ".groundwork/scripts/update_groundwork.py")
        with open(path) as handle:
            text = handle.read()
        with open(path, "w") as handle:
            handle.write(
                text.replace(
                    'SOURCE = "https://github.com/michelwils/groundwork.git"', 'SOURCE = "https://example.org/base.git"'
                )
            )
        self.put(self.project, {".groundwork-version": "0.9.0\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")


if __name__ == "__main__":
    unittest.main()
