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

    def test_a_breaking_revert_of_an_unreleased_change_is_ignored_with_it(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add x")
            repo.commit("revert!: add x")
            self.assertEqual(repo.next(), ("none", None))

    def test_a_revert_with_a_breaking_footer_of_an_unreleased_change_is_ignored_with_it(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat(api): add x")
            repo.commit("revert(api): add x", "BREAKING CHANGE: x is gone")
            self.assertEqual(repo.next(), ("none", None))

    def test_each_revert_cancels_one_change(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add x")
            repo.commit("revert: add x")
            repo.commit("feat: add x")
            self.assertEqual(repo.next(), ("minor", "0.2.0"))


class AmbiguousReverts(unittest.TestCase):
    """A revert whose description matches more than one change is not paired: the maintainers give the version."""

    def stops_on(self, repo, revert):
        result = repo.run()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(revert, result.stderr)
        self.assertIn("--version", result.stderr)
        return result

    def test_a_breaking_revert_of_a_released_change_is_not_absorbed_by_the_same_description_in_the_range(self):
        with Repository() as repo:
            repo.commit("feat: add x")
            repo.tag("1.0.0")
            repo.commit("feat: add x")
            repo.commit("revert!: add x")
            result = self.stops_on(repo, "revert!: add x")
            self.assertIn("feat: add x (released by v1.0.0)", result.stderr)

    def test_a_breaking_revert_of_a_released_change_is_not_absorbed_by_a_fix_with_the_same_description(self):
        with Repository() as repo:
            repo.commit("feat: add x")
            repo.tag("1.0.0")
            repo.commit("fix: add x")
            repo.commit("revert!: add x")
            self.stops_on(repo, "revert!: add x")

    def test_a_revert_that_matches_two_changes_of_the_range_stops(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add x")
            repo.commit("fix: add x")
            repo.commit("revert: add x")
            result = self.stops_on(repo, "revert: add x")
            self.assertIn("feat: add x", result.stderr)
            self.assertIn("fix: add x", result.stderr)

    def test_the_version_given_goes_on_and_the_notes_keep_the_revert_and_the_changes(self):
        with Repository() as repo:
            repo.commit("feat: add x")
            repo.tag("1.0.0")
            repo.commit("feat: add x")
            repo.commit("revert!: add x")
            migration = os.path.join(repo.directory.name, "migration.md")
            with open(migration, "w") as handle:
                handle.write("Stop using it.\n")
            result = repo.run("--version", "2.0.0", "--notes-extra", migration)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("version: 2.0.0", result.stdout)
            self.assertEqual(result.stdout.count("- add x"), 2)

    def test_a_revert_that_matches_only_a_released_change_is_neither_paired_nor_ambiguous(self):
        with Repository() as repo:
            repo.commit("feat: add x")
            repo.tag("0.1.0")
            repo.commit("revert: add x")
            commits = release.commits_since("0.1.0")
            self.assertEqual(release.cancel_reverts(commits, release.released_keys("0.1.0")), [])
            self.assertFalse(commits[0]["undone"])

    def test_the_changes_released_are_found_by_their_description_without_the_reverts(self):
        with Repository() as repo:
            repo.commit("feat: add x (#3)")
            repo.commit("revert: add z (#4)")
            repo.commit("Initial commit")
            repo.tag("0.1.0")
            repo.commit("fix: add y")
            self.assertEqual(set(release.released_keys("0.1.0")), {"add x"})
            self.assertEqual(release.released_keys(None), {})

    def test_a_change_that_a_released_revert_undid_is_no_longer_released(self):
        with Repository() as repo:
            repo.commit("feat: add x (#3)")
            repo.commit("feat: add y (#4)")
            repo.commit("revert: add x (#5)")
            repo.tag("0.1.0")
            self.assertEqual(set(release.released_keys("0.1.0")), {"add y"})

    def test_a_change_added_again_after_a_released_revert_is_released(self):
        with Repository() as repo:
            repo.commit("feat: add x")
            repo.commit("revert: add x")
            repo.commit("feat: add x")
            repo.tag("0.1.0")
            self.assertEqual(set(release.released_keys("0.1.0")), {"add x"})

    def test_a_change_that_an_earlier_release_undid_does_not_make_the_next_revert_ambiguous(self):
        with Repository() as repo:
            repo.commit("feat: add x")
            repo.tag("1.0.0")
            repo.commit("revert!: add x")
            repo.tag("2.0.0")
            repo.commit("feat: add x")
            repo.commit("revert: add x")
            self.assertEqual(repo.run().returncode, 0)

    def test_a_change_that_a_revert_undid_is_not_a_second_match_for_the_next_one(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat: add x")
            repo.commit("revert: add x")
            repo.commit("feat: add x")
            repo.commit("revert: add x")
            self.assertEqual(repo.next(), ("none", None))
            self.assertEqual(repo.run().returncode, 0)


class BreakingWithoutText(unittest.TestCase):
    """A breaking change whose commit has no text in its `BREAKING CHANGE:` footer stops the release: the maintainers give the migration."""

    def extra(self, repo, text):
        path = os.path.join(repo.directory.name, "extra.md")
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def sha(self, repo, count=1):
        return repo.git("log", f"-{count}", "--format=%h").split()

    def test_a_change_marked_only_by_the_bang_stops_and_is_named(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it (#9)")
            result = repo.run()
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("the breaking change 'feat!: change it (#9)' (" + self.sha(repo)[0] + ")", result.stderr)
            self.assertIn("--notes-extra", result.stderr)
            self.assertNotIn("version:", result.stdout)

    def test_a_footer_without_text_stops(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("fix: correct it", "BREAKING CHANGE:\nCo-Authored-By: Someone <someone@example.com>")
            result = repo.run()
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("fix: correct it", result.stderr)

    def test_every_change_without_text_is_named(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it")
            repo.commit("fix: correct it", "BREAKING CHANGE: read `account`.")
            repo.commit("refactor!: move it")
            result = repo.run()
            self.assertEqual(result.returncode, 1, result.stdout)
            second, first = self.sha(repo, 3)[0], self.sha(repo, 3)[2]
            self.assertIn(f"'feat!: change it' ({first})", result.stderr)
            self.assertIn(f"'refactor!: move it' ({second})", result.stderr)
            self.assertNotIn("fix: correct it", result.stderr)

    def test_a_change_with_a_footer_is_not_affected(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it", "BREAKING CHANGE: read `account`.")
            result = repo.run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("  read `account`.", result.stdout)

    def test_a_release_without_a_breaking_change_is_not_affected(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            self.assertEqual(repo.run().returncode, 0)

    def test_the_extra_notes_give_the_migration_and_the_release_goes_on(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it")
            result = repo.run("--notes-extra", self.extra(repo, "Read `account` instead of `user`.\n"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Read `account` instead of `user`.", result.stdout)
            self.assertIn("- change it", result.stdout)

    def test_empty_extra_notes_do_not_give_the_migration(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it")
            self.assertEqual(repo.run("--notes-extra", self.extra(repo, " \n")).returncode, 1)

    def test_the_version_given_does_not_give_the_migration(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it")
            result = repo.run("--version", "0.2.0")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("--notes-extra", result.stderr)

    def test_a_change_that_a_revert_undid_is_not_named(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it")
            repo.commit("revert: change it")
            self.assertEqual(repo.run().returncode, 0)


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


class BreakingFooter(unittest.TestCase):
    def breaking_notes(self, title, body=""):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit(title, body)
            commits = release.commits_since("0.1.0")
            release.cancel_reverts(commits)
            return release.notes(commits)

    def test_the_footer_is_given_under_the_change(self):
        text = self.breaking_notes(
            "refactor(layout)!: move the files (#9)",
            "BREAKING CHANGE: the scripts are in `.groundwork/scripts`.\n"
            "Move your copy of them.\n\n"
            "Co-Authored-By: Someone <someone@example.com>",
        )
        self.assertEqual(
            text,
            "## Breaking changes\n\n- **layout:** move the files (#9)\n\n"
            "  the scripts are in `.groundwork/scripts`.\n  Move your copy of them.\n",
        )

    def test_a_footer_followed_by_a_trailer_stops_at_the_trailer(self):
        text = self.breaking_notes(
            "feat!: change it", "BREAKING CHANGE: read `account`.\nCo-Authored-By: Someone <someone@example.com>"
        )
        self.assertEqual(text, "## Breaking changes\n\n- change it\n\n  read `account`.\n")

    def test_a_line_that_looks_like_a_label_is_part_of_the_footer(self):
        text = self.breaking_notes(
            "feat!: change it",
            "BREAKING CHANGE: rename the option.\nBefore: foo\nAfter: bar\n\nStep 1: run it.\n\n"
            "Refs #4\nCo-Authored-By: Someone <someone@example.com>",
        )
        self.assertEqual(
            text,
            "## Breaking changes\n\n- change it\n\n  rename the option.\n  Before: foo\n  After: bar\n\n  Step 1: run it.\n",
        )

    def test_a_hyphenated_label_that_is_not_a_trailer_stays_in_the_footer(self):
        text = self.breaking_notes(
            "feat!: change it",
            "BREAKING CHANGE: read `account`.\nMigration-Guide: https://example.test/guide\n"
            "Co-Authored-By: Someone <someone@example.com>",
        )
        self.assertIn("  Migration-Guide: https://example.test/guide", text)
        self.assertNotIn("Co-Authored-By", text)
        alone = self.breaking_notes("feat!: change it", "BREAKING CHANGE: Migration-Guide: https://example.test/guide")
        self.assertIn("  Migration-Guide: https://example.test/guide", alone)

    def test_the_hyphenated_token_is_recognised(self):
        text = self.breaking_notes("feat!: change it", "BREAKING-CHANGE: read `account`.")
        self.assertIn("  read `account`.", text)

    def test_a_change_marked_only_by_the_bang_has_its_entry_alone(self):
        self.assertEqual(self.breaking_notes("feat!: change it"), "## Breaking changes\n\n- change it\n")

    def test_a_footer_of_a_change_that_was_undone_is_not_given(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            repo.tag("0.1.0")
            repo.commit("feat!: change it", "BREAKING CHANGE: read `account`.")
            repo.commit("revert: change it")
            commits = release.commits_since("0.1.0")
            release.cancel_reverts(commits)
            self.assertEqual(release.notes(commits), "\n")


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

    def test_the_extra_notes_come_first_in_the_output_and_the_file(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            extra = os.path.join(repo.directory.name, "extra.md")
            with open(extra, "w") as handle:
                handle.write("## Migration\n\nMove the scripts.\n")
            path = os.path.join(repo.directory.name, "notes.md")
            result = repo.run("--notes", path, "--notes-extra", extra)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = "## Migration\n\nMove the scripts.\n\n## feat\n\n- add a feature\n"
            self.assertIn(expected, result.stdout)
            with open(path) as handle:
                self.assertEqual(handle.read(), expected)

    def test_extra_notes_alone_have_no_trailing_blank_line(self):
        self.assertEqual(release.notes([], "Move the scripts.\n"), "Move the scripts.\n")

    def test_a_missing_file_of_extra_notes_is_an_error(self):
        with Repository() as repo:
            repo.commit("feat: add a feature")
            result = repo.run("--notes-extra", os.path.join(repo.directory.name, "absent.md"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class Workflow(unittest.TestCase):
    """The workflow that makes the release gives the extra notes to the script without running them."""

    def setUp(self):
        with open(os.path.join(HERE, "..", "..", ".github", "workflows", "release.yml")) as handle:
            self.text = handle.read()

    def test_the_extra_notes_are_an_optional_input(self):
        self.assertRegex(self.text, r"(?s)inputs:.*\n      notes:\n.*?required: false\n        type: string")

    def test_the_extra_notes_reach_the_script_through_a_file_written_from_the_environment(self):
        self.assertIn("NOTES: ${{ inputs.notes }}", self.text)
        self.assertEqual(self.text.count("inputs.notes"), 1)
        self.assertIn('printf \'%s\\n\' "$NOTES" > "$RUNNER_TEMP/extra.md"', self.text)
        self.assertIn('--notes-extra "$RUNNER_TEMP/extra.md"', self.text)

    def test_an_empty_list_of_arguments_is_safe_in_every_version_of_bash(self):
        self.assertIn('${extra[@]+"${extra[@]}"}', self.text)


if __name__ == "__main__":
    unittest.main()
