import json
import os
import shutil
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
    if os.environ.get("FAKE_CREATE_FAILS"):
        print("gh: HTTP 403: Resource not accessible", file=sys.stderr)
        sys.exit(1)
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

    def run_script(self, pull_requests="[]", closed="[]", recorded=None, create_fails=False):
        """Run the script; with `recorded`, the project has recorded this address as its source and git reaches it at the source."""
        env = {
            **os.environ,
            "PATH": self.bin + os.pathsep + os.environ["PATH"],
            "FAKE_LOG": self.log,
            "FAKE_PULL_REQUESTS": pull_requests,
            "FAKE_CLOSED_PULL_REQUESTS": closed,
            "FAKE_CREATE_FAILS": "1" if create_fails else "",
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

    def test_shows_the_error_of_the_update_whatever_its_status(self):
        copy = os.path.join(self.directory.name, "copy")
        os.makedirs(copy)
        shutil.copy(SCRIPT, copy)
        with open(os.path.join(copy, "update_groundwork.py"), "w") as handle:
            handle.write("import sys\nprint('error: the update stopped at a step', file=sys.stderr)\nsys.exit(4)\n")
        env = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"], "FAKE_LOG": self.log}
        result = subprocess.run([sys.executable, os.path.join(copy, "open_update_pull_request.py"), "--source", self.source], cwd=self.project, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error: the update stopped at a step", result.stderr)
        self.assertIn("status 4", result.stderr)

    # A stand-in for the update that the test names: it prepares the branch of the update and changes files, then does what
    # the test appends to it. It is copied next to a copy of the opener, which runs it in place of the real one.
    STAND_IN = """import json, subprocess, sys
subprocess.run(["git", "switch", "-q", "-c", "groundwork/update-to-v0-2-0"], check=True)
with open(".groundwork-version", "w") as handle:
    handle.write("0.2.0\\n")
with open("update.md", "w") as handle:
    handle.write("update\\n")
path = sys.argv[sys.argv.index("--result") + 1]
"""

    def run_with_update(self, ending):
        copy = os.path.join(self.directory.name, "copy")
        os.makedirs(copy, exist_ok=True)
        shutil.copy(SCRIPT, copy)
        with open(os.path.join(copy, "update_groundwork.py"), "w") as handle:
            handle.write(self.STAND_IN + ending)
        env = {
            **os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"], "FAKE_LOG": self.log,
            "FAKE_PULL_REQUESTS": "[]", "FAKE_CLOSED_PULL_REQUESTS": "[]",
        }
        return subprocess.run(
            [sys.executable, os.path.join(copy, "open_update_pull_request.py"), "--source", self.source],
            cwd=self.project, capture_output=True, text=True, env=env,
        )

    def assert_put_back(self, result, head, detached=False):
        """The opener failed and left the project as it found it, so that a later run goes through."""
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(git(self.project, "for-each-ref", "--format=%(refname:short)", "refs/heads").split(), ["main"])
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "" if detached else "main")
        self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        self.assertFalse(os.path.exists(os.path.join(self.project, "update.md")))
        self.assertEqual(git(self.project, "show", "HEAD:.groundwork-version"), "0.1.0\n")
        self.assertEqual(self.created(), [])
        later = self.run_script()
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertEqual(len(self.created()), 1)

    def test_puts_the_project_back_when_the_result_is_not_json(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        result = self.run_with_update("open(path, 'w').write('not json')\n")
        self.assertIn("not JSON", result.stderr)
        self.assert_put_back(result, head)

    def test_puts_the_project_back_when_the_update_ends_with_another_status_and_no_result(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        result = self.run_with_update("sys.exit(4)\n")
        self.assertIn("status 4", result.stderr)
        self.assert_put_back(result, head)

    def test_puts_the_project_back_when_the_status_and_the_result_disagree(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        fields = {"branch": "groundwork/update-to-v0-2-0", "from": "0.1.0", "to": "0.2.0", "source": "x", "added": [], "conflicts": []}
        result = self.run_with_update(f"open(path, 'w').write(json.dumps({fields!r}))\nsys.exit(3)\n")
        self.assertIn("status 3", result.stderr)
        self.assert_put_back(result, head)

    def test_puts_the_project_back_when_the_update_fails_after_it_prepared_the_branch(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        self.assert_put_back(self.run_with_update("sys.exit(1)\n"), head)

    def test_puts_a_detached_project_back_on_its_commit(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        git(self.project, "switch", "-q", "--detach")
        self.assert_put_back(self.run_with_update("sys.exit(1)\n"), head, detached=True)

    def test_puts_the_project_back_when_the_push_fails(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        git(self.project, "remote", "set-url", "origin", os.path.join(self.directory.name, "no-such-remote.git"))
        result = self.run_script()
        git(self.project, "remote", "set-url", "origin", self.remote)
        self.assert_put_back(result, head)

    def test_puts_the_project_back_when_the_pull_request_cannot_be_created_and_the_next_run_replaces_the_pushed_branch(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        result = self.run_script(create_fails=True)
        self.assertIn("groundwork/update-to-v0-2-0", self.remote_branches())  # pushed before the pull request failed
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(git(self.project, "for-each-ref", "--format=%(refname:short)", "refs/heads").split(), ["main"])
        self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        later = self.run_script()
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertEqual(len(self.created()), 2)  # the call that failed, and the one that went through

    def test_does_not_delete_a_branch_of_the_update_that_it_did_not_make(self):
        git(self.project, "branch", "groundwork/update-to-v0-2-0")
        copy = os.path.join(self.directory.name, "copy")
        os.makedirs(copy, exist_ok=True)
        shutil.copy(SCRIPT, copy)
        with open(os.path.join(copy, "update_groundwork.py"), "w") as handle:
            handle.write('import subprocess, sys\nsubprocess.run(["git", "switch", "-q", "groundwork/update-to-v0-2-0"], check=True)\nsys.exit(1)\n')
        env = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"], "FAKE_LOG": self.log}
        result = subprocess.run(
            [sys.executable, os.path.join(copy, "open_update_pull_request.py"), "--source", self.source],
            cwd=self.project, capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("groundwork/update-to-v0-2-0", git(self.project, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())

    def test_puts_the_project_back_whatever_the_error_that_stops_it(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        result = self.run_with_update("open(path, 'w').close()\nimport os\nos.chmod(path, 0)\n")
        if os.geteuid() == 0:
            self.skipTest("root reads a file whatever its mode")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_put_back(result, head)

    def test_leaves_the_changes_of_the_person_when_the_update_refuses_a_tree_that_is_not_clean(self):
        write(self.project, {"CONTRIBUTING.md": "mine\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not clean", result.stderr)
        with open(os.path.join(self.project, "CONTRIBUTING.md")) as handle:
            self.assertEqual(handle.read(), "mine\n")
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "main")

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

    def test_a_project_that_is_on_a_commit_is_moved_to_a_release(self):
        fields = {**self.RESULT, "from": "0.1.0+" + "a" * 40}
        self.assertEqual(self.read_result(fields), fields)
        fields = {**self.RESULT, "from": "0.1.0+" + "b" * 64}
        self.assertEqual(self.read_result(fields), fields)

    def test_a_result_that_moves_the_project_to_a_commit_is_refused(self):
        commit = "0.2.0+" + "a" * 40
        for fields in (
            {**self.RESULT, "to": commit},
            {**self.RESULT, "to": commit, "branch": "groundwork/update-to-" + "a" * 12},
            {**self.RESULT, "to": commit, "branch": "groundwork/update-to-v0-2-0"},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(opener.Failure):
                    self.read_result(fields)

    def test_a_commit_that_is_not_lowercase_hexadecimal_is_refused_in_from(self):
        for commit in ("A" * 40, "a" * 39, "a" * 41, "a" * 40 + "\nx", "g" * 40):
            with self.subTest(commit=commit):
                with self.assertRaises(opener.Failure):
                    self.read_result({**self.RESULT, "from": "0.1.0+" + commit})

    def test_the_status_of_the_update_must_agree_with_its_conflicts(self):
        opener.agree(0, {"conflicts": []})
        opener.agree(3, {"conflicts": ["a.md"]})
        for status, conflicts in ((0, ["a.md"]), (3, []), (2, ["a.md"]), (2, []), (-9, [])):
            with self.subTest(status=status, conflicts=conflicts):
                with self.assertRaises(opener.Failure):
                    opener.agree(status, {"conflicts": conflicts})

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
