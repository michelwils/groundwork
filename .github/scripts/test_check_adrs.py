import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_adrs  # noqa: E402

SCRIPT = os.path.join(HERE, "check_adrs.py")

TEMPLATE = """# NNNN. Title of the decision

**Status:** proposed | accepted | rejected | superseded by [NNNN](NNNN-title.md)

## Context

The situation.

## Decision

We will do it.

## Consequences

What changes.
"""


def adr(number, title="A decision", status="accepted", sections=("Context", "Decision", "Consequences")):
    body = "".join(f"## {name}\n\nText of {name}.\n\n" for name in sections)
    return f"# {number}. {title}\n\n**Status:** {status}\n\n{body}".rstrip("\n") + "\n"


class Adrs(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name
        os.makedirs(os.path.join(self.root, "docs", "adr"))
        self.put("template.md", TEMPLATE)

    def tearDown(self):
        self.directory.cleanup()

    def put(self, name, content):
        with open(os.path.join(self.root, "docs", "adr", name), "w") as handle:
            handle.write(content)

    def adrs(self, *numbers):
        for number in numbers:
            self.put(f"{number:04d}-decision-{number}.md", adr(f"{number:04d}"))

    def problems(self):
        return check_adrs.check(self.root)

    def only(self, text):
        (problem,) = self.problems()
        self.assertIn(text, problem)
        return problem

    def test_a_valid_set_and_the_template_pass(self):
        self.adrs(1, 2, 3)
        self.assertEqual(self.problems(), [])

    def test_a_directory_without_adrs_passes(self):
        self.assertEqual(self.problems(), [])

    def test_a_missing_directory_is_reported(self):
        os.remove(os.path.join(self.root, "docs", "adr", "template.md"))
        os.rmdir(os.path.join(self.root, "docs", "adr"))
        self.only("docs/adr")

    def test_the_four_statuses_are_accepted(self):
        self.put("0001-a.md", adr("0001", status="proposed"))
        self.put("0002-b.md", adr("0002", status="rejected"))
        self.put("0003-c.md", adr("0003", status="superseded by [0004](0004-d.md)"))
        self.put("0004-d.md", adr("0004"))
        self.put("0005-e.md", adr("0005", status="superseded by 0006"))
        self.put("0006-f.md", adr("0006"))
        self.assertEqual(self.problems(), [])

    def test_an_unknown_status_is_reported(self):
        self.put("0001-a.md", adr("0001", status="maybe"))
        self.only("0001-a.md:3")

    def test_a_missing_status_is_reported(self):
        self.put("0001-a.md", adr("0001").replace("**Status:** accepted\n", ""))
        self.only("**Status:**")

    def test_the_status_must_be_given_once(self):
        self.put("0001-a.md", adr("0001").replace("## Context", "**Status:** accepted\n\n## Context"))
        self.only("more than once")

    def test_a_status_in_a_code_block_is_not_the_status(self):
        content = adr("0001") + "\n```\n**Status:** maybe\n```\n"
        self.put("0001-a.md", content)
        self.assertEqual(self.problems(), [])
        self.put("0001-a.md", adr("0001").replace("**Status:** accepted\n", "```\n**Status:** accepted\n```\n"))
        self.only("**Status:**")

    def test_files_with_windows_line_endings_are_understood(self):
        with open(os.path.join(self.root, "docs", "adr", "0001-a.md"), "w", newline="") as handle:
            handle.write(adr("0001").replace("\n", "\r\n"))
        self.assertEqual(self.problems(), [])

    def test_a_superseding_adr_must_exist_and_be_more_recent(self):
        self.put("0001-a.md", adr("0001", status="superseded by [0009](0009-x.md)"))
        self.only("0009")
        self.put("0001-a.md", adr("0001", status="superseded by 0001"))
        self.only("more recent")

    def test_the_text_and_the_target_of_a_superseded_link_must_agree(self):
        self.put("0001-a.md", adr("0001", status="superseded by [0002](0003-c.md)"))
        self.put("0002-b.md", adr("0002"))
        self.put("0003-c.md", adr("0003"))
        self.only("leads to 0003")

    def test_the_file_name_must_follow_the_convention(self):
        self.put("README.md", "# Index\n")
        self.only("README.md")
        os.remove(os.path.join(self.root, "docs", "adr", "README.md"))
        self.put("0001_Bad Name.md", adr("0001"))
        self.only("0001_Bad Name.md")

    def test_files_that_are_not_markdown_are_ignored(self):
        for name in (".DS_Store", "0001-diagram.png", "0001-a.md~", ".0001-a.md.swp"):
            self.put(name, "binary")
        os.makedirs(os.path.join(self.root, "docs", "adr", "images"))
        self.assertEqual(self.problems(), [])

    def test_the_title_must_carry_the_number_of_the_file(self):
        self.put("0001-a.md", adr("0002"))
        self.only("0001-a.md:1")

    def test_a_title_without_a_number_is_reported(self):
        self.put("0001-a.md", adr("0001").replace("# 0001. A decision", "# A decision"))
        self.only("0001-a.md:1")

    def test_every_section_is_required(self):
        for missing in ("Context", "Decision", "Consequences"):
            with self.subTest(missing=missing):
                sections = tuple(name for name in ("Context", "Decision", "Consequences") if name != missing)
                self.put("0001-a.md", adr("0001", sections=sections))
                self.only(missing)

    def test_the_sections_must_come_in_the_order_of_the_template(self):
        self.put("0001-a.md", adr("0001", sections=("Decision", "Context", "Consequences")))
        self.only("order")

    def test_a_section_title_may_have_a_closing_sequence_of_hashes(self):
        self.put("0001-a.md", adr("0001").replace("## Context", "## Context ##"))
        self.assertEqual(self.problems(), [])

    def test_a_section_that_holds_only_a_code_block_is_not_empty(self):
        self.put("0001-a.md", adr("0001").replace("Text of Decision.\n", "```sh\nmake it\n```\n"))
        self.assertEqual(self.problems(), [])

    def test_a_section_must_not_be_repeated(self):
        self.put("0001-a.md", adr("0001", sections=("Context", "Decision", "Decision", "Consequences")))
        self.only("Decision")

    def test_a_section_must_not_be_empty(self):
        self.put("0001-a.md", adr("0001").replace("Text of Decision.\n", ""))
        self.only("empty")

    def test_more_sections_are_allowed(self):
        self.put("0001-a.md", adr("0001", sections=("Context", "Decision", "Alternatives", "Consequences")))
        self.assertEqual(self.problems(), [])

    def test_a_heading_in_a_code_block_is_not_a_section(self):
        content = adr("0001", sections=("Context", "Consequences")) + "\n```\n## Decision\n```\n"
        self.put("0001-a.md", content)
        self.only("Decision")

    def test_a_duplicate_number_is_reported(self):
        self.adrs(1, 2)
        self.put("0002-other.md", adr("0002"))
        self.only("0002")

    def test_a_skipped_number_of_groundwork_is_reported(self):
        self.adrs(1, 2, 4)
        self.only("0003")

    def test_the_numbers_of_groundwork_start_at_0001(self):
        self.adrs(2, 3)
        self.only("0001")

    def test_the_numbers_of_a_project_start_at_1000_and_follow_each_other(self):
        self.adrs(1, 2, 1000, 1001, 1002)
        self.assertEqual(self.problems(), [])

    def test_a_project_that_starts_after_1000_is_reported(self):
        self.adrs(1, 1001)
        self.only("1000")

    def test_a_skipped_number_of_a_project_is_reported(self):
        self.adrs(1, 1000, 1002)
        self.only("1001")

    def test_the_two_ranges_are_independent(self):
        self.adrs(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1000)
        self.assertEqual(self.problems(), [])

    def test_the_number_0000_is_reported(self):
        self.put("0000-a.md", adr("0000"))
        self.assertTrue(any("0000" in problem for problem in self.problems()))

    def test_the_template_needs_its_title_and_its_sections(self):
        self.put("template.md", TEMPLATE.replace("## Decision\n\nWe will do it.\n\n", ""))
        self.only("template.md")
        self.put("template.md", TEMPLATE.replace("# NNNN. Title of the decision", "# Title"))
        self.only("template.md:1")

    def test_problems_are_reported_in_a_stable_order(self):
        self.put("0001-a.md", adr("0001", status="maybe"))
        self.put("0002-b.md", adr("0002", status="maybe"))
        problems = self.problems()
        self.assertEqual(problems, sorted(problems))


class CommandLine(unittest.TestCase):
    def run_script(self, files):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "docs", "adr"))
            for name, content in files.items():
                with open(os.path.join(root, "docs", "adr", name), "w") as handle:
                    handle.write(content)
            return subprocess.run([sys.executable, SCRIPT, root], capture_output=True, text=True)

    def test_it_succeeds_when_the_adrs_follow_the_rules(self):
        result = self.run_script({"template.md": TEMPLATE, "0001-a.md": adr("0001")})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_it_fails_and_reports_on_the_error_output(self):
        result = self.run_script({"template.md": TEMPLATE, "0001-a.md": adr("0001", status="maybe")})
        self.assertEqual(result.returncode, 1)
        self.assertIn("0001-a.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
