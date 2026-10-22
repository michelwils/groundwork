import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import open_update_pull_request as opener  # noqa: E402

SCRIPT = os.path.join(HERE, "open_update_pull_request.py")

V1 = {"README.md": "# groundwork\n", "CONTRIBUTING.md": "one\ntwo\nthree\n"}
V2 = {"README.md": "# groundwork 0.2\n", "CONTRIBUTING.md": "one\ntwo changed\nthree\n", "new.md": "new\n"}

# A stand-in for the `gh` command: it logs its arguments, lists the pull requests of FAKE_PULL_REQUESTS
# and answers the creation of a pull request with a URL.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "list"]:
    state = args[args.index("--state") + 1]
    print(os.environ.get("FAKE_PULL_REQUESTS" if state == "open" else "FAKE_CLOSED_PULL_REQUESTS", "[]"))
elif args[:2] == ["pr", "create"]:
    print("https://github.com/owner/project/pull/1")
"""


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def init(path, bare=False):
    os.makedirs(path)
    git(path, "init", "-q", "-b", "main", *(["--bare"] if bare else []))
    if not bare:
        git(path, "config", "user.email", "test@example.com")
        git(path, "config", "user.name", "Test")
        git(path, "config", "commit.gpgsign", "false")
        git(path, "config", "tag.gpgsign", "false")
        git(path, "config", "core.hooksPath", os.devnull)


def write(path, files):
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as handle:
            handle.write(content)


class OpenUpdatePullRequest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.source = os.path.join(root, "groundwork")
        init(self.source)
        for version, files in (("0.1.0", V1), ("0.2.0", V2)):
            write(self.source, files)
            git(self.source, "add", "-A")
            git(self.source, "commit", "-q", "-m", f"feat: release {version}")
            git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")
        self.remote = os.path.join(root, "remote.git")
        init(self.remote, bare=True)
        self.project = os.path.join(root, "project")
        init(self.project)
        write(self.project, {**V1, ".groundwork-version": "0.1.0\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")
        git(self.project, "remote", "add", "origin", self.remote)
        git(self.project, "push", "-q", "origin", "main")
        self.bin = os.path.join(root, "bin")
        os.makedirs(self.bin)
        gh = os.path.join(self.bin, "gh")
        with open(gh, "w") as handle:
            handle.write(FAKE_GH)
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        self.log = os.path.join(root, "log")

    def tearDown(self):
        self.directory.cleanup()

    def run_script(self, pull_requests="[]", closed="[]", recorded=None):
        """Run the script; with `recorded`, the project has recorded this address as its source and git reaches it at the source."""
        env = {
            **os.environ,
            "PATH": self.bin + os.pathsep + os.environ["PATH"],
            "FAKE_LOG": self.log,
            "FAKE_PULL_REQUESTS": pull_requests,
            "FAKE_CLOSED_PULL_REQUESTS": closed,
        }
        if recorded:
            env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{self.source}.insteadOf", "GIT_CONFIG_VALUE_0": recorded})
        return subprocess.run(
            [sys.executable, SCRIPT, *([] if recorded else ["--source", self.source])], cwd=self.project, capture_output=True, text=True, env=env
        )

    def gh_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return [json.loads(line) for line in handle]

    def created(self):
        return [call for call in self.gh_calls() if call[:2] == ["pr", "create"]]

    def remote_branches(self):
        return git(self.remote, "branch", "--format=%(refname:short)").split()

    def value(self, call, option):
        return call[call.index(option) + 1]

    def test_opens_a_pull_request_with_the_update(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("groundwork/update-to-v0-2-0", self.remote_branches())
        self.assertEqual(
            git(self.remote, "log", "-1", "--format=%s", "groundwork/update-to-v0-2-0").strip(),
            "chore: update groundwork to v0.2.0",
        )
        self.assertEqual(git(self.remote, "show", "groundwork/update-to-v0-2-0:.groundwork-version"), "0.2.0\n")
        self.assertIn("https://github.com/owner/project/pull/1", result.stdout)

    def test_commits_no_file_of_the_result(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        files = git(self.remote, "diff", "--name-only", "main", "groundwork/update-to-v0-2-0").split()
        self.assertNotIn("result.json", [os.path.basename(name) for name in files])
        self.assertEqual(git(self.project, "status", "--porcelain"), "")

    def test_runs_no_hook_of_the_project(self):
        hooks, ran = os.path.join(self.directory.name, "hooks"), os.path.join(self.directory.name, "ran")
        os.makedirs(hooks)
        os.makedirs(ran)
        names = ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "post-checkout", "reference-transaction", "pre-push")
        for name in names:
            path = os.path.join(hooks, name)
            with open(path, "w") as handle:
                handle.write(f"#!/bin/sh\ntouch '{os.path.join(ran, name)}'\n")
            os.chmod(path, 0o755)
        git(self.project, "config", "core.hooksPath", hooks)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.created()), 1)
        self.assertEqual(os.listdir(ran), [])

    def test_runs_no_hook_and_keeps_the_configuration_given_in_the_environment(self):
        environ = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "url.a.insteadOf", "GIT_CONFIG_VALUE_0": "b"}
        self.assertEqual(
            opener.without_hooks(environ),
            {**environ, "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_1": "core.hooksPath", "GIT_CONFIG_VALUE_1": os.devnull},
        )

    def test_the_pull_request_is_ready_and_named_after_the_version(self):
        self.run_script()
        (call,) = self.created()
        self.assertNotIn("--draft", call)
        self.assertEqual(self.value(call, "--title"), "chore: update groundwork to v0.2.0")
        self.assertEqual(self.value(call, "--head"), "groundwork/update-to-v0-2-0")
        self.assertIn("0.1.0", self.value(call, "--body"))
        self.assertIn("0.2.0", self.value(call, "--body"))

    def test_the_release_notes_are_those_of_the_source_that_the_project_recorded(self):
        write(self.project, {".groundwork-source": "https://example.org/team/base.git\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: record the source")
        git(self.project, "push", "-q", "origin", "main")
        result = self.run_script(recorded="https://example.org/team/base.git")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (call,) = self.created()
        self.assertIn("Release notes: https://example.org/team/base/releases/tag/v0.2.0", self.value(call, "--body"))

    def test_a_conflict_opens_a_draft_that_lists_the_files(self):
        write(self.project, {"CONTRIBUTING.md": "one\ntwo mine\nthree\n"})
        git(self.project, "commit", "-q", "-am", "docs: adjust the project")
        git(self.project, "push", "-q", "origin", "main")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        (call,) = self.created()
        self.assertIn("--draft", call)
        self.assertIn("CONTRIBUTING.md", self.value(call, "--body"))
        self.assertNotIn("new.md", self.value(call, "--body"))
        self.assertIn("groundwork/update-to-v0-2-0", self.remote_branches())

    def test_opens_nothing_when_the_project_is_up_to_date(self):
        write(self.project, {".groundwork-version": "0.2.0\n"})
        git(self.project, "commit", "-q", "-am", "chore: record the version")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])

    def test_opens_no_second_pull_request_while_one_is_open(self):
        result = self.run_script('[{"headRefName": "groundwork/update-to-v0-2-0"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already open", result.stdout)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "main")

    def test_another_open_pull_request_does_not_prevent_the_update(self):
        self.run_script('[{"headRefName": "feat/3-add-a-thing"}, {"headRefName": "dependabot/pre_commit/x"}]')
        self.assertEqual(len(self.created()), 1)

    def test_looks_for_an_open_update_among_all_the_open_pull_requests(self):
        self.run_script()
        calls = [call for call in self.gh_calls() if call[:2] == ["pr", "list"]]
        self.assertEqual({self.value(call, "--state") for call in calls}, {"open", "closed"})
        for call in calls:
            self.assertGreaterEqual(int(self.value(call, "--limit")), 1000)

    def test_does_not_propose_again_a_version_whose_pull_request_was_closed_without_a_merge(self):
        result = self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-2-0", "mergedAt": null}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("closed without being merged", result.stdout)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "main")
        self.assertEqual(git(self.project, "branch", "--format=%(refname:short)").split(), ["main"])
        self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")

    def test_goes_back_to_a_detached_commit_when_the_version_was_rejected(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        git(self.project, "switch", "-q", "--detach")
        self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-2-0", "mergedAt": null}]')
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "")

    def test_a_version_rejected_earlier_does_not_prevent_a_later_one(self):
        self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-1-5", "mergedAt": null}]')
        self.assertEqual(len(self.created()), 1)

    def test_a_merged_pull_request_does_not_count_as_rejected(self):
        self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-2-0", "mergedAt": "2026-10-16T00:00:00Z"}]')
        self.assertEqual(len(self.created()), 1)

    def test_does_nothing_in_a_project_without_the_version_file(self):
        os.remove(os.path.join(self.project, ".groundwork-version"))
        git(self.project, "commit", "-q", "-am", "chore: remove the version file")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(".groundwork-version", result.stdout)
        self.assertEqual(self.created(), [])

    def test_fails_when_the_update_fails(self):
        write(self.project, {".groundwork-version": "0.9.9\n"})
        git(self.project, "commit", "-q", "-am", "chore: record a wrong version")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("0.9.9", result.stderr)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])

    def test_replaces_a_branch_left_by_an_earlier_run_that_has_no_pull_request(self):
        git(self.project, "switch", "-q", "-c", "groundwork/update-to-v0-2-0")
        write(self.project, {"stale.md": "stale\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: stale")
        git(self.project, "push", "-q", "origin", "groundwork/update-to-v0-2-0")
        git(self.project, "switch", "-q", "main")
        git(self.project, "branch", "-q", "-D", "groundwork/update-to-v0-2-0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            git(self.remote, "log", "-1", "--format=%s", "groundwork/update-to-v0-2-0").strip(),
            "chore: update groundwork to v0.2.0",
        )
        self.assertEqual(len(self.created()), 1)


class Body(unittest.TestCase):
    def test_it_names_the_adrs_that_the_update_added(self):
        text = opener.body("0.1.0", "0.2.0", [], "https://github.com/o/g.git", ["0002", "0003"])
        self.assertIn("ADR 0002, ADR 0003", text)

    def test_a_path_in_conflict_is_shown_as_text(self):
        paths = ["a`@team`.md", "`x.md", "[x](https://example.org).md", "x.md`", "CONTRIBUTING.md"]
        lines = opener.body("0.1.0", "0.2.0", paths, "https://github.com/o/g.git").splitlines()
        self.assertEqual(
            lines[-5:],
            ["- ``a`@team`.md``", "- `` `x.md ``", "- `[x](https://example.org).md`", "- `` x.md` ``", "- `CONTRIBUTING.md`"],
        )

    def test_it_says_nothing_of_the_adrs_when_none_was_added(self):
        text = opener.body("0.1.0", "0.2.0", [], "https://github.com/o/g.git", [])
        self.assertNotIn("ADR", text)
        self.assertEqual(text, opener.body("0.1.0", "0.2.0", [], "https://github.com/o/g.git"))

    RESULT = {
        "branch": "groundwork/update-to-v0-2-0",
        "from": "0.1.0",
        "to": "0.2.0",
        "source": "https://github.com/o/g.git",
        "added": ["0002", "0003"],
        "conflicts": ["a.md", "b`c.md"],
    }

    def read_result(self, fields):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "result.json")
            with open(path, "w") as handle:
                handle.write(fields if isinstance(fields, str) else json.dumps(fields))
            return opener.result(path)

    def test_the_result_is_read_from_the_file(self):
        self.assertEqual(self.read_result(self.RESULT), self.RESULT)

    def test_an_update_that_wrote_no_result_has_none(self):
        self.assertIsNone(opener.result(os.path.join(tempfile.gettempdir(), "no-such-groundwork-result.json")))

    def test_a_result_that_is_not_the_expected_one_is_refused(self):
        without = lambda name: {key: value for key, value in self.RESULT.items() if key != name}
        for fields in (
            "not json",
            "[]",
            without("branch"),
            without("conflicts"),
            {**self.RESULT, "extra": "x"},
            {**self.RESULT, "branch": "victim"},
            {**self.RESULT, "to": "0.3.0"},
            {**self.RESULT, "to": "0.2.0 [x](https://example.org)"},
            {**self.RESULT, "from": "0.1.0\nx"},
            {**self.RESULT, "source": 3},
            {**self.RESULT, "added": "0002"},
            {**self.RESULT, "added": ["0002", "[x](https://example.org)"]},
            {**self.RESULT, "conflicts": "a.md"},
            {**self.RESULT, "conflicts": ["a.md", 3]},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(opener.Failure):
                    self.read_result(fields)


if __name__ == "__main__":
    unittest.main()
