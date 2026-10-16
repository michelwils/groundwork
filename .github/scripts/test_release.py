import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import release  # noqa: E402

SCRIPT = os.path.join(HERE, "release.py")


class Repository:
    """A temporary git repository, entered for the duration of a test."""

    def __enter__(self):
        self.previous = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)
        return self

    def __exit__(self, *exc):
        os.chdir(self.previous)
        self.directory.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout

    def commit(self, title, body=""):
        message = title + (f"\n\n{body}" if body else "")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def tag(self, version):
        self.git("tag", "-a", f"v{version}", "-m", f"v{version}")

    def next(self):
        """Return (increment level, next version or None) as the script computes them."""
        previous = release.previous_version()
        commits = release.commits_since(previous)
        release.cancel_reverts(commits)
        major = int((previous or "0.0.0").split(".")[0])
        level = max((release.increment(c, major) for c in commits), key=release.LEVELS.get, default="none")
        return level, None if level == "none" else release.bump(previous, level)

    def run(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


class NextVersion(unittest.TestCase):
    def test_first_release_with_a_feature_is_0_1_0(self):
        with Repository() as repo:
            repo.commit("chore: initialize repository")
            repo.commit("docs: bootstrap the repository (#2)")
            repo.commit("feat: adopt Semantic Versioning (#5)")
            repo.commit("fix: correct a wording (#7)")
            self.assertEqual(repo.next(), ("minor", "0.1.0"))

    def test_no_release_when_nothing_affects_the_version(self):
        with Repository() as repo:
            repo.commit("chore: initialize repository")
            repo.commit("docs: describe the workflow")
            repo.commit("ci: add a workflow")
            self.assertEqual(repo.next(), ("none", None))

    def test_fix_after_a_release_is_a_patch(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("fix: correct a bug")
            repo.commit("docs: describe it")
            self.assertEqual(repo.next(), ("patch", "0.1.1"))

    def test_perf_is_a_patch(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("perf: speed it up")
            self.assertEqual(repo.next(), ("patch", "0.1.1"))

    def test_highest_increment_wins(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            for title in ["feat: add one", "fix: correct one", "feat: add two", "fix: correct two"]:
                repo.commit(title)
            self.assertEqual(repo.next(), ("minor", "0.2.0"))

    def test_breaking_change_in_major_0_is_a_minor(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("fix(api)!: change the format")
            self.assertEqual(repo.next(), ("minor", "0.2.0"))

    def test_breaking_footer_is_recognised(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("1.0.0")
            repo.commit("refactor: rework it", "BREAKING CHANGE: clients must migrate")
            self.assertEqual(repo.next(), ("major", "2.0.0"))

    def test_rules_from_major_1(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("1.2.0")
            repo.commit("fix: correct a bug")
            self.assertEqual(repo.next(), ("patch", "1.2.1"))
            repo.commit("feat: add another")
            self.assertEqual(repo.next(), ("minor", "1.3.0"))
            repo.commit("feat(api)!: remove a field")
            self.assertEqual(repo.next(), ("major", "2.0.0"))

    def test_other_types_do_not_change_the_version(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            for kind in ["docs", "style", "refactor", "test", "build", "ci", "chore", "revert"]:
                repo.commit(f"{kind}: something")
            self.assertEqual(repo.next(), ("none", None))


class Reverts(unittest.TestCase):
    def test_a_reverted_feature_is_ignored_with_its_revert(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add password reset (#10)")
            repo.commit("revert: add password reset (#11)")
            self.assertEqual(repo.next(), ("none", None))

    def test_other_changes_still_count(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add password reset")
            repo.commit("fix: correct a bug")
            repo.commit("revert: add password reset")
            self.assertEqual(repo.next(), ("patch", "0.1.1"))

    def test_a_revert_of_a_released_change_does_not_change_the_version(self):
        with Repository() as repo:
            repo.commit("feat: add password reset")
            repo.tag("0.1.0")
            repo.commit("revert: add password reset")
            self.assertEqual(repo.next(), ("none", None))

    def test_a_breaking_revert_of_a_released_change_is_breaking(self):
        with Repository() as repo:
            repo.commit("feat: add password reset")
            repo.tag("1.0.0")
            repo.commit("revert!: add password reset")
            self.assertEqual(repo.next(), ("major", "2.0.0"))

    def test_each_revert_cancels_one_change(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add x")
            repo.commit("revert: add x")
            repo.commit("feat: add x")
            self.assertEqual(repo.next(), ("minor", "0.2.0"))


class Tags(unittest.TestCase):
    def test_tags_that_are_not_versions_are_ignored(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("fix: correct a bug")
            repo.git("tag", "v0.2.0-rc1")
            repo.git("tag", "release-2")
            self.assertEqual(repo.next(), ("patch", "0.1.1"))

    def test_the_highest_reachable_version_is_the_previous_one(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.9.0")
            repo.commit("feat: add another")
            repo.tag("0.10.0")
            repo.commit("fix: correct a bug")
            self.assertEqual(repo.next(), ("patch", "0.10.1"))


class Branches(unittest.TestCase):
    def test_maintenance_branch_uses_its_own_tags(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("1.0.0")
            repo.git("branch", "maintenance/v1")
            repo.commit("feat!: change the contract")
            repo.tag("2.0.0")
            repo.git("switch", "-q", "maintenance/v1")
            repo.commit("fix: correct a bug")
            self.assertEqual(repo.next(), ("patch", "1.0.1"))


class Notes(unittest.TestCase):
    def test_notes_are_grouped_by_type_without_undone_changes(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            for title in [
                "fix(parser): handle empty input (#4)",
                "feat(api): add a field (#5)",
                "feat: add password reset (#6)",
                "revert: add password reset (#7)",
                "docs: describe it (#8)",
                "feat(api)!: rename a field (#9)",
                "Initial commit",
            ]:
                repo.commit(title)
            commits = release.commits_since("0.1.0")
            release.cancel_reverts(commits)
            self.assertEqual(
                release.notes(commits),
                "## Breaking changes\n\n- **api:** rename a field (#9)\n\n"
                "## feat\n\n- **api:** add a field (#5)\n\n"
                "## fix\n\n- **parser:** handle empty input (#4)\n\n"
                "## docs\n\n- describe it (#8)\n\n"
                "## Other\n\n- Initial commit\n",
            )


class Command(unittest.TestCase):
    def test_version_can_be_given(self):
        with Repository() as repo:
            repo.commit("docs: describe it")
            result = repo.run("--version", "1.0.0")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("version: 1.0.0", result.stdout)

    def test_version_must_be_greater_than_the_previous_one(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("1.2.0")
            repo.commit("fix: correct a bug")
            for bad in ["1.2.0", "1.1.9"]:
                self.assertNotEqual(repo.run("--version", bad).returncode, 0)

    def test_version_must_have_the_form_x_y_z(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            for bad in ["v1.0.0", "1.0", "1.0.0-rc1"]:
                self.assertNotEqual(repo.run("--version", bad).returncode, 0)

    def test_existing_tag_is_refused(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.git("switch", "-q", "-c", "elsewhere")
            repo.commit("chore: somewhere else")
            repo.tag("0.2.0")
            repo.git("switch", "-q", "main")
            repo.commit("feat: add another")
            result = repo.run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)

    def test_no_release_exits_cleanly(self):
        with Repository() as repo:
            repo.commit("docs: describe it")
            result = repo.run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("version: none", result.stdout)

    def test_notes_are_written_to_the_file(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            path = os.path.join(repo.directory.name, "notes.md")
            result = repo.run("--notes", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(path) as handle:
                self.assertIn("- add a feature", handle.read())


if __name__ == "__main__":
    unittest.main()
