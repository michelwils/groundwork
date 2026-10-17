import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_practices  # noqa: E402

SCRIPT = os.path.join(HERE, "check_practices.py")

ADR = "# {n}. Decision {n}\n\n**Status:** accepted\n\n## Context\n\nText.\n\n## Decision\n\nText.\n\n## Consequences\n\nText.\n"


def entry(number, needs="none", mentions="none", files=(), shared=()):
    lines = [f"### {number}. Decision {number}", "", f"- Needs: {needs}", f"- Mentions: {mentions}", "- Files:"]
    lines += [f"  - `{path}`" for path in files] or ["  - none"]
    lines += ["- Shared lines:"]
    lines += [f"  - `{path}`, {where}" for path, where in shared] or ["  - none"]
    return "\n".join(lines) + "\n"


def practices(*entries, shared=("CONTRIBUTING.md",), apart=("docs/practices.md",)):
    text = "# Practices of groundwork\n\nIntroduction.\n\n## Practices\n\n" + "\n".join(entries)
    text += "\n## Shared files\n\n" + "".join(f"- `{path}`\n" for path in shared)
    text += "\n## Not part of a practice\n\n" + "".join(f"- `{path}`\n" for path in apart)
    return text


class Practices(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name
        subprocess.run(["git", "init", "--quiet", self.root], check=True)
        self.put("docs/adr/0001-first.md", ADR.format(n="0001"))
        self.put("docs/adr/0002-second.md", ADR.format(n="0002"))
        self.put("docs/adr/template.md", "# NNNN. Title\n")
        self.put("CONTRIBUTING.md", "Rules.\n")
        self.put("tool.py", "")
        self.put("tool_test.py", "")

    def tearDown(self):
        self.directory.cleanup()

    def put(self, name, content):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(content)

    def track(self):
        subprocess.run(["git", "-C", self.root, "add", "--all"], check=True)

    def good_entries(self):
        return (
            entry("0001", files=["docs/adr/template.md", "tool.py", "tool_test.py"], shared=[("CONTRIBUTING.md", "section 'Rules'")]),
            entry("0002", needs="ADR 0001"),
        )

    def good(self):
        return practices(*self.good_entries())

    def problems(self, text=None):
        self.put("docs/practices.md", self.good() if text is None else text)
        self.track()
        return check_practices.check(self.root)

    def only(self, text, map_text=None):
        (problem,) = self.problems(map_text)
        self.assertIn(text, problem)
        return problem


class Valid(Practices):
    def test_a_complete_map_has_no_problem(self):
        self.assertEqual(self.problems(), [])

    def test_the_command_succeeds_on_a_complete_map(self):
        self.problems()
        result = subprocess.run([sys.executable, SCRIPT, self.root], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_the_command_fails_and_names_the_problem_on_an_incomplete_map(self):
        self.problems(practices(entry("0001", files=["docs/adr/template.md", "tool.py", "tool_test.py"])))
        result = subprocess.run([sys.executable, SCRIPT, self.root], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error: docs/practices.md", result.stderr)
        self.assertIn("0002", result.stderr)


class Entries(Practices):
    def test_an_adr_without_an_entry_is_reported(self):
        self.only("0002", practices(entry("0001", files=["docs/adr/template.md", "tool.py", "tool_test.py"])))

    def test_an_entry_for_an_adr_that_does_not_exist_is_reported(self):
        self.only("0003", practices(*self.good_entries(), entry("0003")))

    def test_an_entry_given_twice_is_reported(self):
        text = practices(self.good_entries()[0], self.good_entries()[0], self.good_entries()[1])
        self.assertTrue(any("0001" in problem and "more than once" in problem for problem in self.problems(text)))

    def test_the_problem_gives_the_line_of_the_map(self):
        problem = self.only("0003", practices(*self.good_entries(), entry("0003")))
        self.assertRegex(problem, r"^docs/practices\.md:\d+: ")

    def test_an_entry_without_the_line_needs_is_reported(self):
        text = self.good().replace("- Needs: ADR 0001\n", "")
        self.only("Needs", text)

    def test_an_entry_without_the_line_mentions_is_reported(self):
        text = self.good().replace("- Mentions: none\n", "", 1)
        self.only("Mentions", text)


class Dependencies(Practices):
    def test_a_needed_adr_that_does_not_exist_is_reported(self):
        self.only("0009", self.good().replace("Needs: ADR 0001", "Needs: ADR 0009"))

    def test_an_adr_that_needs_itself_is_reported(self):
        self.only("itself", self.good().replace("Needs: ADR 0001", "Needs: ADR 0002"))

    def test_an_adr_both_needed_and_mentioned_is_reported(self):
        self.only("both", self.good().replace("Needs: ADR 0001", "Needs: ADR 0001").replace("### 0002. Decision 0002\n\n- Needs: ADR 0001\n- Mentions: none", "### 0002. Decision 0002\n\n- Needs: ADR 0001\n- Mentions: ADR 0001"))

    def test_several_adrs_are_separated_by_commas(self):
        self.put("docs/adr/0003-third.md", ADR.format(n="0003"))
        text = practices(
            entry("0001", files=["docs/adr/template.md", "tool.py", "tool_test.py"], shared=[("CONTRIBUTING.md", "x")]),
            entry("0002"),
            entry("0003", needs="ADR 0001, ADR 0002"),
        )
        self.assertEqual(self.problems(text), [])

    def test_a_cycle_of_needs_is_reported(self):
        text = self.good().replace("### 0001. Decision 0001\n\n- Needs: none", "### 0001. Decision 0001\n\n- Needs: ADR 0002")
        self.assertTrue(any("cycle" in problem for problem in self.problems(text)))


class Files(Practices):
    def test_a_file_that_does_not_exist_is_reported(self):
        self.only("missing.py", self.good().replace("  - `tool.py`\n", "  - `tool.py`\n  - `missing.py`\n", 1))

    def test_a_tracked_file_that_the_map_does_not_name_is_reported(self):
        self.put("new.py", "")
        self.only("new.py")

    def test_a_file_untracked_by_git_is_not_required(self):
        self.problems()
        self.put("ignored.py", "")
        self.assertEqual(check_practices.check(self.root), [])

    def test_the_file_of_an_adr_is_covered_by_its_entry(self):
        self.assertEqual(self.problems(), [])

    def test_a_file_named_in_two_practices_is_reported(self):
        text = self.good().replace("### 0002. Decision 0002\n\n- Needs: ADR 0001\n- Mentions: none\n- Files:\n  - none", "### 0002. Decision 0002\n\n- Needs: ADR 0001\n- Mentions: none\n- Files:\n  - `tool.py`")
        self.only("tool.py", text)

    def test_a_file_class_as_not_part_of_a_practice_is_covered(self):
        self.put("LICENSE", "text\n")
        text = practices(*self.good_entries(), apart=("docs/practices.md", "LICENSE"))
        self.assertEqual(self.problems(text), [])

    def test_a_file_listed_in_the_section_not_part_of_a_practice_that_does_not_exist_is_reported(self):
        text = practices(*self.good_entries(), apart=("docs/practices.md", "gone.md"))
        self.only("gone.md", text)

    def test_the_map_must_be_in_a_git_repository(self):
        with tempfile.TemporaryDirectory() as plain:
            problems = check_practices.check(plain)
        self.assertTrue(problems)

    def test_the_map_must_exist(self):
        self.track()
        problems = check_practices.check(self.root)
        self.assertTrue(any("docs/practices.md" in problem and "does not exist" in problem for problem in problems))


class SharedLines(Practices):
    def test_a_shared_line_in_a_file_that_is_not_a_shared_file_is_reported(self):
        text = practices(
            entry("0001", files=["docs/adr/template.md", "tool.py", "tool_test.py"], shared=[("CONTRIBUTING.md", "x"), ("tool_test.py", "y")]),
            entry("0002", needs="ADR 0001"),
        )
        self.only("tool_test.py", text)

    def test_a_shared_file_that_does_not_exist_is_reported(self):
        text = practices(*self.good_entries(), shared=("CONTRIBUTING.md", "AGENTS.md"))
        self.only("AGENTS.md", text)


if __name__ == "__main__":
    unittest.main()
