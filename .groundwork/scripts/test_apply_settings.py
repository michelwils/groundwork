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
import apply_settings  # noqa: E402

SCRIPT = os.path.join(HERE, "apply_settings.py")

# A stand-in for the `gh` command: it logs its arguments, and answers like the platform would.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if "--input" in args and args[args.index("--input") + 1] == "-":
    with open(os.environ["FAKE_LOG"] + ".body", "w") as body:
        body.write(sys.stdin.read())
if os.environ.get("FAKE_FAIL") and os.environ["FAKE_FAIL"] in " ".join(args):
    print("gh: HTTP 403: Must have admin rights to Repository.", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["repo", "view"]:
    print("default-owner/default-repo")
elif args[:2] == ["api", "user"]:
    if not os.environ.get("FAKE_USER"):
        print("gh: HTTP 401: Requires authentication", file=sys.stderr)
        sys.exit(1)
    print(os.environ["FAKE_USER"])
elif args[0] == "api" and args[1].endswith("/rulesets") and "-X" not in args:
    print(os.environ.get("FAKE_RULESETS", "[]"))
elif args[0] == "api" and "/rulesets/" in args[1] and "-X" not in args:
    print(os.environ.get("FAKE_RULESET", "{}"))
"""


class ApplySettings(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.directory.name, "log")
        gh = os.path.join(self.directory.name, "gh")
        with open(gh, "w") as handle:
            handle.write(FAKE_GH)
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        self.project = os.path.join(self.directory.name, "project")
        os.makedirs(self.project)

    def tearDown(self):
        self.directory.cleanup()

    def run_script(self, *args, rulesets="[]", fail="", ruleset="{}", user=""):
        """Run the script from the directory of a project, which holds the CODEOWNERS that `self.owners` writes."""
        env = {
            **os.environ,
            "PATH": self.directory.name + os.pathsep + os.environ["PATH"],
            "FAKE_LOG": self.log,
            "FAKE_RULESETS": rulesets,
            "FAKE_RULESET": ruleset,
            "FAKE_FAIL": fail,
            "FAKE_USER": user,
        }
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, cwd=self.project)

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
        self.assertIn("api -X PUT repos/owner/repo/vulnerability-alerts", text)
        self.assertIn("api -X PUT repos/owner/repo/automated-security-fixes", text)
        self.assertTrue(any(call.startswith("api -X POST repos/owner/repo/rulesets") for call in text))

    def test_creates_the_ruleset_from_the_file_of_the_repository(self):
        self.run_script("owner/repo")
        create = next(call for call in self.writes() if "POST" in call)
        path = create[create.index("--input") + 1]
        self.assertTrue(path.endswith(os.path.join(".groundwork", "rulesets", "main.json")))
        self.assertTrue(os.path.exists(path))

    def test_applies_the_ruleset_last(self):
        self.run_script("owner/repo")
        self.assertIn("rulesets", self.writes()[-1][3])
        self.assertEqual(len(self.writes()), 6)

    def test_turns_on_the_alerts_before_the_security_updates_and_both_before_the_ruleset(self):
        self.run_script("owner/repo")
        text = [" ".join(call) for call in self.writes()]
        alerts = text.index("api -X PUT repos/owner/repo/vulnerability-alerts")
        updates = text.index("api -X PUT repos/owner/repo/automated-security-fixes")
        ruleset = next(index for index, call in enumerate(text) if "/rulesets" in call)
        self.assertLess(alerts, updates)
        self.assertLess(updates, ruleset)

    def test_running_it_twice_applies_the_same_settings(self):
        existing = '[{"id": 7, "name": "main"}]'
        self.run_script("owner/repo", rulesets=existing)
        first = self.writes()
        os.remove(self.log)
        self.run_script("owner/repo", rulesets=existing)
        self.assertEqual(self.writes(), first)

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

    def test_stops_when_the_alerts_cannot_be_turned_on_and_does_not_try_the_security_updates(self):
        result = self.run_script("owner/repo", fail="vulnerability-alerts")
        self.assertEqual(result.returncode, 1)
        self.assertIn("owner/repo", result.stderr)
        self.assertIn("vulnerability alerts", result.stderr)
        self.assertIn("admin", result.stderr)
        self.assertFalse(any("automated-security-fixes" in " ".join(call) for call in self.calls()))
        self.assertFalse(any("rulesets" in " ".join(call) and "-X" in call for call in self.calls()))

    def test_says_what_failed_when_the_security_updates_cannot_be_turned_on(self):
        result = self.run_script("owner/repo", fail="automated-security-fixes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("security updates", result.stderr)
        self.assertFalse(any("rulesets" in " ".join(call) and "-X" in call for call in self.calls()))

    def test_says_what_failed_when_the_rulesets_cannot_be_read(self):
        result = self.run_script("owner/repo", fail="owner/repo/rulesets")
        self.assertEqual(result.returncode, 1)
        self.assertIn("owner/repo", result.stderr)
        self.assertIn("rulesets", result.stderr)
        self.assertIn("admin", result.stderr)
        self.assertEqual(self.writes(), [])

    def test_dry_run_changes_nothing_and_shows_what_it_would_do(self):
        result = self.run_script("owner/repo", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.writes(), [])
        for text in (
            "owner/repo",
            "merge",
            "private vulnerability reporting",
            "immutable releases",
            "vulnerability alerts",
            "security updates",
            "ruleset",
        ):
            self.assertIn(text, result.stdout)

    def test_names_the_repository_and_each_setting(self):
        result = self.run_script("owner/repo")
        for text in (
            "owner/repo",
            "merge",
            "private vulnerability reporting",
            "immutable releases",
            "vulnerability alerts",
            "security updates",
            "ruleset",
        ):
            self.assertIn(text, result.stdout)

    def test_acts_on_the_current_repository_by_default(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("default-owner/default-repo", result.stdout)
        self.assertTrue(any("repos/default-owner/default-repo/immutable-releases" in " ".join(c) for c in self.writes()))

    def test_does_not_look_up_the_repository_when_it_is_given(self):
        self.run_script("owner/repo")
        self.assertFalse(any(call[:2] == ["repo", "view"] for call in self.calls()))

    RULESET = os.path.join(HERE, "..", "rulesets", "main.json")

    def owners(self, text="/docs/adr/0*  @reviewers\n", where=os.path.join(".github", "CODEOWNERS")):
        path = os.path.join(self.project, where)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    def sent(self):
        """Return the ruleset that was sent on the standard input of gh, or None when the file of the repository was named."""
        if not os.path.exists(self.log + ".body"):
            return None
        with open(self.log + ".body") as handle:
            return json.load(handle)

    def parameters(self, ruleset):
        return next(rule["parameters"] for rule in ruleset["rules"] if rule["type"] == "pull_request")

    def test_without_an_option_the_ruleset_is_the_file_of_the_repository(self):
        self.run_script("owner/repo", user="maintainer")
        self.assertIsNone(self.sent())
        self.assertFalse(any(call[:2] == ["api", "user"] for call in self.calls()))

    def test_the_code_owner_review_requires_the_review_and_dismisses_the_stale_approvals(self):
        self.owners()
        result = self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        parameters = self.parameters(self.sent())
        self.assertTrue(parameters["require_code_owner_review"])
        self.assertTrue(parameters["dismiss_stale_reviews_on_push"])
        self.assertFalse(parameters["require_last_push_approval"])

    def test_the_code_owner_review_requires_at_least_one_approval(self):
        self.owners()
        self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(self.parameters(self.sent())["required_approving_review_count"], 1)

    def test_the_code_owner_review_keeps_the_approvals_that_the_ruleset_already_requires(self):
        self.owners()
        result = self.run_script(
            "owner/repo", "--code-owner-review", rulesets=self.EXISTING,
            ruleset=self.pull_request(required_approving_review_count=2),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.parameters(self.sent())["required_approving_review_count"], 2)

    def test_the_last_push_approval_is_added_to_the_code_owner_review(self):
        self.owners()
        result = self.run_script("owner/repo", "--code-owner-review", "--last-push-approval")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.parameters(self.sent())["require_last_push_approval"])
        self.owners()
        self.run_script("owner/repo", "--code-owner-review")
        self.assertFalse(self.parameters(self.sent())["require_last_push_approval"])

    def test_the_last_push_approval_alone_is_refused_since_no_approval_is_required_without_the_review(self):
        result = self.run_script("owner/repo", "--last-push-approval")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--code-owner-review", result.stderr)
        self.assertEqual(self.writes(), [])

    def test_the_options_change_nothing_else_of_the_ruleset(self):
        self.owners()
        self.run_script("owner/repo", "--code-owner-review", "--last-push-approval")
        with open(self.RULESET) as handle:
            expected = json.load(handle)
        self.parameters(expected).update(
            required_approving_review_count=1, require_code_owner_review=True,
            dismiss_stale_reviews_on_push=True, require_last_push_approval=True,
        )
        self.assertEqual(self.sent(), expected)

    def test_an_existing_ruleset_is_updated_with_the_options(self):
        self.owners()
        self.run_script("owner/repo", "--code-owner-review", rulesets='[{"id": 7, "name": "main"}]')
        text = [" ".join(call) for call in self.writes()]
        self.assertTrue(any(call.startswith("api -X PUT repos/owner/repo/rulesets/7 --input -") for call in text))
        self.assertTrue(self.parameters(self.sent())["require_code_owner_review"])

    def test_the_code_owner_review_needs_a_file_of_code_owners(self):
        result = self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CODEOWNERS", result.stderr)
        self.assertIn("CODEOWNERS.template", result.stderr)
        self.assertEqual(self.writes(), [])

    def test_the_code_owner_review_refuses_the_owner_of_the_template(self):
        self.owners("/docs/adr/0*  @OWNER\n")
        result = self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(result.returncode, 1)
        self.assertIn("@OWNER", result.stderr)
        self.assertEqual(self.writes(), [])

    def test_the_code_owner_review_is_refused_when_the_only_owner_is_the_person_who_runs_the_script(self):
        for text in ("/docs/adr/0*  @Maintainer\n", "/docs/adr/0*  @maintainer\n/.github/  @maintainer\n"):
            self.owners(text)
            for arguments in ((), ("--dry-run",)):
                with self.subTest(text=text, arguments=arguments):
                    result = self.run_script("owner/repo", "--code-owner-review", *arguments, user="maintainer")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("only code owner", result.stderr)
                    self.assertIn("ADR 0014", result.stderr)
                    self.assertEqual(self.writes(), [])

    def test_the_code_owner_review_is_not_refused_when_someone_else_owns_a_file_too(self):
        for text in (
            "/docs/adr/0*  @maintainer @reviewer\n",
            "/docs/adr/0*  @maintainer\n/.github/  @reviewer\n",
            "/docs/adr/0*  @org/team\n",
            "/docs/adr/0*  reviewer@example.org\n",
        ):
            with self.subTest(text=text):
                self.owners(text)
                result = self.run_script("owner/repo", "--code-owner-review", user="maintainer")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_code_owner_review_is_not_refused_when_the_login_cannot_be_read(self):
        self.owners("/docs/adr/0*  @maintainer\n")
        result = self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped the check that you are not the only code owner", result.stdout)
        self.assertIn("HTTP 401", result.stdout)
        other = self.run_script("owner/repo", "--code-owner-review", user="maintainer")
        self.assertNotIn("skipped the check", other.stdout)

    def test_the_dry_run_refuses_what_the_run_would_refuse(self):
        result = self.run_script("owner/repo", "--dry-run", "--code-owner-review")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CODEOWNERS", result.stderr)

    def test_the_file_of_code_owners_can_be_at_the_root_or_in_docs(self):
        for where in ("CODEOWNERS", os.path.join("docs", "CODEOWNERS")):
            with self.subTest(where=where):
                self.owners(where=where)
                self.assertEqual(self.run_script("owner/repo", "--code-owner-review").returncode, 0)
                shutil.rmtree(self.project)
                os.makedirs(self.project)

    def test_a_file_of_code_owners_without_a_rule_is_refused(self):
        self.owners("# who reviews\n\n")
        result = self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no owner", result.stderr)

    def test_a_byte_that_is_not_text_in_the_file_of_code_owners_does_not_stop_the_script(self):
        path = os.path.join(self.project, ".github", "CODEOWNERS")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as handle:
            handle.write(b"# caf\xff\n/docs/adr/0*  @reviewers\n")
        self.assertEqual(self.run_script("owner/repo", "--code-owner-review").returncode, 0)

    def test_the_message_says_where_the_file_is_looked_for(self):
        self.assertIn("this directory", self.run_script("owner/repo", "--code-owner-review").stderr)

    PROTECTED = '{"rules": [{"type": "pull_request", "parameters": {"require_code_owner_review": true, "require_last_push_approval": false}}]}'

    BOTH = '{"rules": [{"type": "pull_request", "parameters": {"require_code_owner_review": true, "require_last_push_approval": true}}]}'
    EXISTING = '[{"id": 7, "name": "main"}]'

    def test_a_run_that_would_turn_off_a_review_that_the_ruleset_has_is_refused(self):
        for arguments in ((), ("--dry-run",)):
            with self.subTest(arguments=arguments):
                result = self.run_script("owner/repo", *arguments, rulesets=self.EXISTING, ruleset=self.PROTECTED)
                self.assertEqual(result.returncode, 1)
                self.assertIn("code owner review", result.stderr)
                self.assertIn("same options", result.stderr)
                self.assertIn("--turn-off-reviews", result.stderr)
                self.assertEqual(self.writes(), [])

    def test_a_run_that_keeps_only_one_of_two_reviews_is_refused_too(self):
        self.owners()
        result = self.run_script("owner/repo", "--code-owner-review", rulesets=self.EXISTING, ruleset=self.BOTH)
        self.assertEqual(result.returncode, 1)
        self.assertIn("last push approval", result.stderr)
        self.assertNotIn("code owner review required", result.stderr)
        self.assertEqual(self.writes(), [])

    def test_the_option_that_turns_the_reviews_off_lets_the_run_go_on(self):
        result = self.run_script("owner/repo", "--turn-off-reviews", rulesets=self.EXISTING, ruleset=self.BOTH)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.sent())
        self.assertTrue(any("rulesets/7" in " ".join(call) for call in self.writes()))

    def test_nothing_is_refused_when_the_options_keep_the_reviews_or_the_ruleset_has_none(self):
        self.owners()
        kept = self.run_script("owner/repo", "--code-owner-review", "--last-push-approval", rulesets=self.EXISTING, ruleset=self.BOTH)
        self.assertEqual(kept.returncode, 0, kept.stderr)
        plain = self.run_script("owner/repo", rulesets=self.EXISTING, ruleset='{"rules": [{"type": "pull_request", "parameters": {}}]}')
        self.assertEqual(plain.returncode, 0, plain.stderr)
        created = self.run_script("owner/repo")
        self.assertEqual(created.returncode, 0, created.stderr)

    def pull_request(self, **parameters):
        return json.dumps({"rules": [{"type": "pull_request", "parameters": parameters}]})

    def test_every_approval_setting_that_a_run_would_lower_is_guarded(self):
        for parameter, words in (
            ("dismiss_stale_reviews_on_push", "stale approvals"),
            ("required_review_thread_resolution", "thread resolution"),
            ("required_approving_review_count", "required approvals"),
        ):
            with self.subTest(parameter=parameter):
                value = 1 if parameter == "required_approving_review_count" else True
                result = self.run_script("owner/repo", rulesets=self.EXISTING, ruleset=self.pull_request(**{parameter: value}))
                self.assertEqual(result.returncode, 1)
                self.assertIn(words, result.stderr)
                self.assertEqual(self.writes(), [])

    def test_a_setting_that_the_options_set_is_not_lowered(self):
        self.owners()
        result = self.run_script(
            "owner/repo", "--code-owner-review", rulesets=self.EXISTING,
            ruleset=self.pull_request(require_code_owner_review=True, dismiss_stale_reviews_on_push=True),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_setting_that_the_options_do_not_set_is_lowered_even_when_they_are_given(self):
        self.owners()
        result = self.run_script(
            "owner/repo", "--code-owner-review", rulesets=self.EXISTING, ruleset=self.pull_request(required_review_thread_resolution=True)
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("thread resolution", result.stderr)

    def test_a_file_of_code_owners_may_leave_a_path_without_owner(self):
        self.owners("/docs/adr/0001-*\n/docs/adr/0*  @reviewers\n")
        self.assertEqual(self.run_script("owner/repo", "--code-owner-review").returncode, 0)

    def test_without_an_option_a_ruleset_file_needs_no_pull_request_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "main.json")
            with open(path, "w") as handle:
                json.dump({"name": "main", "rules": [{"type": "deletion"}]}, handle)
            previous, apply_settings.RULESET = apply_settings.RULESET, path
            try:
                ruleset, words = apply_settings.protected(False, False)
            finally:
                apply_settings.RULESET = previous
        self.assertEqual((ruleset["name"], words), ("main", []))

    def test_a_ruleset_file_without_a_pull_request_rule_is_not_reported_as_a_read_error(self):
        import argparse

        arguments = argparse.Namespace(
            repository="owner/repo", dry_run=True, code_owner_review=True, last_push_approval=False, turn_off_reviews=False
        )
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "main.json")
            with open(path, "w") as handle:
                json.dump({"name": "main", "rules": [{"type": "deletion"}]}, handle)
            previous, apply_settings.RULESET = apply_settings.RULESET, path
            try:
                with self.assertRaises(apply_settings.Failure) as caught:
                    apply_settings.run(arguments)
            finally:
                apply_settings.RULESET = previous
        self.assertIn("pull_request", str(caught.exception))
        self.assertNotIn("could not read", str(caught.exception))

    def test_a_file_of_code_owners_whose_rules_name_no_owner_is_refused(self):
        self.owners("/docs/adr/0*\n")
        result = self.run_script("owner/repo", "--code-owner-review")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no owner", result.stderr)

    def test_a_ruleset_file_without_a_pull_request_rule_is_an_error_not_a_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "main.json")
            with open(path, "w") as handle:
                json.dump({"name": "main", "rules": [{"type": "deletion"}]}, handle)
            previous, apply_settings.RULESET = apply_settings.RULESET, path
            try:
                with self.assertRaises(apply_settings.Failure):
                    apply_settings.protected(True, False)
            finally:
                apply_settings.RULESET = previous

    def test_the_dry_run_shows_the_protection_that_the_ruleset_would_have(self):
        self.owners()
        plain = self.run_script("owner/repo", "--dry-run")
        self.assertNotIn("code owner review", plain.stdout)
        result = self.run_script("owner/repo", "--dry-run", "--code-owner-review", "--last-push-approval")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.writes(), [])
        self.assertIsNone(self.sent())
        for text in ("1 approval required", "code owner review required", "stale approvals dismissed", "last push approval required"):
            self.assertIn(text, result.stdout)

    def test_refuses_a_repository_that_is_not_owner_slash_name(self):
        result = self.run_script("repo")
        self.assertEqual(result.returncode, 1)
        self.assertIn("OWNER/REPO", result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
