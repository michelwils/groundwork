import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "apply_settings.py")

# A stand-in for the `gh` command: it logs its arguments, and answers like the platform would.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if os.environ.get("FAKE_FAIL") and os.environ["FAKE_FAIL"] in " ".join(args):
    print("gh: HTTP 403: Must have admin rights to Repository.", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["repo", "view"]:
    print("default-owner/default-repo")
elif args[0] == "api" and args[1].endswith("/rulesets") and "-X" not in args:
    print(os.environ.get("FAKE_RULESETS", "[]"))
"""


class ApplySettings(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.directory.name, "log")
        gh = os.path.join(self.directory.name, "gh")
        with open(gh, "w") as handle:
            handle.write(FAKE_GH)
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.directory.cleanup()

    def run_script(self, *args, rulesets="[]", fail=""):
        env = {
            **os.environ,
            "PATH": self.directory.name + os.pathsep + os.environ["PATH"],
            "FAKE_LOG": self.log,
            "FAKE_RULESETS": rulesets,
            "FAKE_FAIL": fail,
        }
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return [json.loads(line) for line in handle]

    def writes(self):
        return [call for call in self.calls() if "-X" in call]

    def test_applies_every_setting(self):
        result = self.run_script("owner/repo")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = [" ".join(call) for call in self.writes()]
        merge = next(call for call in text if "-X PATCH repos/owner/repo " in call + " ")
        for field in (
            "allow_squash_merge=true",
            "allow_merge_commit=false",
            "allow_rebase_merge=false",
            "delete_branch_on_merge=true",
            "squash_merge_commit_title=PR_TITLE",
            "squash_merge_commit_message=BLANK",
        ):
            self.assertIn(field, merge)
        self.assertIn("api -X PUT repos/owner/repo/private-vulnerability-reporting", text)
        self.assertIn("api -X PUT repos/owner/repo/immutable-releases", text)
        self.assertTrue(any(call.startswith("api -X POST repos/owner/repo/rulesets") for call in text))

    def test_creates_the_ruleset_from_the_file_of_the_repository(self):
        self.run_script("owner/repo")
        create = next(call for call in self.writes() if "POST" in call)
        path = create[create.index("--input") + 1]
        self.assertTrue(path.endswith(os.path.join(".github", "rulesets", "main.json")))
        self.assertTrue(os.path.exists(path))

    def test_applies_the_ruleset_last(self):
        self.run_script("owner/repo")
        self.assertIn("rulesets", self.writes()[-1][3])
        self.assertEqual(len(self.writes()), 4)

    def test_updates_the_ruleset_that_already_exists_instead_of_creating_a_second(self):
        result = self.run_script("owner/repo", rulesets='[{"id": 7, "name": "main"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = [" ".join(call) for call in self.writes()]
        self.assertTrue(any(call.startswith("api -X PUT repos/owner/repo/rulesets/7 ") for call in text))
        self.assertFalse(any("POST" in call for call in text))

    def test_ignores_a_ruleset_with_another_name(self):
        self.run_script("owner/repo", rulesets='[{"id": 3, "name": "other"}]')
        self.assertTrue(any("POST" in call for call in self.writes()))
        self.assertFalse(any("rulesets/3" in " ".join(call) for call in self.writes()))

    def test_stops_at_the_first_error_and_says_what_failed(self):
        result = self.run_script("owner/repo", fail="private-vulnerability-reporting")
        self.assertEqual(result.returncode, 1)
        self.assertIn("owner/repo", result.stderr)
        self.assertIn("private vulnerability reporting", result.stderr)
        self.assertIn("admin", result.stderr)
        self.assertFalse(any("immutable-releases" in " ".join(call) for call in self.calls()))
        self.assertFalse(any("rulesets" in " ".join(call) and "-X" in call for call in self.calls()))

    def test_dry_run_changes_nothing_and_shows_what_it_would_do(self):
        result = self.run_script("owner/repo", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.writes(), [])
        for text in ("owner/repo", "merge", "private vulnerability reporting", "immutable releases", "ruleset"):
            self.assertIn(text, result.stdout)

    def test_names_the_repository_and_each_setting(self):
        result = self.run_script("owner/repo")
        for text in ("owner/repo", "merge", "private vulnerability reporting", "immutable releases", "ruleset"):
            self.assertIn(text, result.stdout)

    def test_acts_on_the_current_repository_by_default(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("default-owner/default-repo", result.stdout)
        self.assertTrue(any("repos/default-owner/default-repo/immutable-releases" in " ".join(c) for c in self.writes()))

    def test_does_not_look_up_the_repository_when_it_is_given(self):
        self.run_script("owner/repo")
        self.assertFalse(any(call[:2] == ["repo", "view"] for call in self.calls()))

    def test_refuses_a_repository_that_is_not_owner_slash_name(self):
        result = self.run_script("repo")
        self.assertEqual(result.returncode, 1)
        self.assertIn("OWNER/REPO", result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
