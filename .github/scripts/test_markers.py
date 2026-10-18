import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import markers  # noqa: E402

MARKDOWN = """# Title

Intro.

<!-- groundwork:0004 -->
## Language

English.
<!-- /groundwork -->

<!-- groundwork:0003 -->
## Workflow

Issues.
<!-- /groundwork -->

## List

- one
<!-- groundwork:0010 -->
- ten
<!-- /groundwork -->
- two
"""

YAML = """repos:
  - repo: local
    hooks:
      # groundwork:0001
      - id: adrs
        name: Check the ADRs
      # /groundwork

      # groundwork:0002
      - id: commit-title
        name: Check the title
      # /groundwork
"""


class Kind(unittest.TestCase):
    def test_markdown_and_yaml_are_told_by_their_extension(self):
        self.assertEqual(markers.kind("a/b/CONTRIBUTING.md"), "markdown")
        self.assertEqual(markers.kind(".pre-commit-config.yaml"), "yaml")
        self.assertEqual(markers.kind("workflow.yml"), "yaml")

    def test_another_file_has_no_markers(self):
        self.assertIsNone(markers.kind("script.py"))


class Parse(unittest.TestCase):
    def blocks(self, text, kind="markdown"):
        found, problems = markers.parse(text.split("\n"), kind)
        self.assertEqual(problems, [])
        return found

    def test_the_blocks_of_a_markdown_file_are_read_with_their_lines(self):
        found = self.blocks(MARKDOWN)
        self.assertEqual([(block["adr"], block["start"], block["end"]) for block in found], [(4, 5, 9), (3, 11, 15), (10, 20, 22)])

    def test_the_blocks_of_a_yaml_file_are_read_with_their_indentation(self):
        found = self.blocks(YAML, "yaml")
        self.assertEqual([(block["adr"], block["start"], block["end"]) for block in found], [(1, 4, 7), (2, 9, 12)])

    def test_a_text_without_markers_has_no_block(self):
        self.assertEqual(self.blocks("# Title\n\nText.\n"), [])

    def test_a_marker_in_a_code_block_is_not_read(self):
        text = "```text\n<!-- groundwork:0004 -->\n```\n"
        self.assertEqual(self.blocks(text), [])

    def test_a_marker_that_is_not_alone_on_its_line_is_not_read(self):
        self.assertEqual(self.blocks("Text <!-- groundwork:0004 --> text\n"), [])

    def test_a_number_that_is_not_of_four_digits_is_not_a_marker(self):
        self.assertEqual(self.blocks("<!-- groundwork:4 -->\n"), [])

    def test_the_markers_of_the_other_syntax_are_not_read(self):
        self.assertEqual(self.blocks("# groundwork:0004\n# /groundwork\n"), [])
        self.assertEqual(self.blocks("<!-- groundwork:0004 -->\n<!-- /groundwork -->\n", "yaml"), [])

    def problems(self, text, kind="markdown"):
        return markers.parse(text.split("\n"), kind)[1]

    def test_a_block_that_is_not_closed_is_reported_at_its_line(self):
        (problem,) = self.problems("Text.\n\n<!-- groundwork:0004 -->\nText.\n")
        self.assertEqual(problem[0], 3)
        self.assertIn("not closed", problem[1])

    def test_a_block_inside_a_block_is_reported_at_its_line(self):
        text = "<!-- groundwork:0004 -->\n<!-- groundwork:0003 -->\nx\n<!-- /groundwork -->\n<!-- /groundwork -->\n"
        problems = self.problems(text)
        self.assertTrue(any(line == 2 and "inside" in message for line, message in problems))

    def test_a_closing_marker_without_a_block_is_reported_at_its_line(self):
        (problem,) = self.problems("Text.\n<!-- /groundwork -->\n")
        self.assertEqual(problem[0], 2)
        self.assertIn("no block", problem[1])


class Remove(unittest.TestCase):
    def test_nothing_is_removed_when_all_the_adrs_are_kept(self):
        self.assertEqual(markers.remove(MARKDOWN, "markdown", {3, 4, 10}), MARKDOWN)

    def test_a_text_without_markers_is_unchanged(self):
        self.assertEqual(markers.remove("# Title\n\n\n\nText.\n", "markdown", set()), "# Title\n\n\n\nText.\n")

    def test_a_block_of_an_adr_that_is_left_out_is_removed_with_its_markers(self):
        result = markers.remove(MARKDOWN, "markdown", {3, 10})
        self.assertNotIn("Language", result)
        self.assertNotIn("0004", result)
        self.assertIn("<!-- groundwork:0003 -->", result)

    def test_the_blank_line_around_a_removed_block_is_not_doubled(self):
        result = markers.remove(MARKDOWN, "markdown", {3, 10})
        self.assertNotIn("\n\n\n", result)
        self.assertIn("Intro.\n\n<!-- groundwork:0003 -->", result)

    def test_a_block_at_the_end_leaves_no_blank_line_at_the_end(self):
        text = "Text.\n\n<!-- groundwork:0004 -->\nMore.\n<!-- /groundwork -->\n"
        self.assertEqual(markers.remove(text, "markdown", set()), "Text.\n")

    def test_a_block_at_the_start_leaves_no_blank_line_at_the_start(self):
        text = "<!-- groundwork:0004 -->\nMore.\n<!-- /groundwork -->\n\nText.\n"
        self.assertEqual(markers.remove(text, "markdown", set()), "Text.\n")

    def test_a_block_between_two_paragraphs_leaves_one_blank_line(self):
        text = "One.\n\n<!-- groundwork:0004 -->\nTwo.\n<!-- /groundwork -->\n\nThree.\n"
        self.assertEqual(markers.remove(text, "markdown", set()), "One.\n\nThree.\n")

    def test_a_block_right_after_a_paragraph_keeps_the_paragraphs_apart(self):
        text = "One.\n<!-- groundwork:0004 -->\nTwo.\n<!-- /groundwork -->\n\nThree.\n"
        self.assertEqual(markers.remove(text, "markdown", set()), "One.\n\nThree.\n")

    def test_a_block_in_a_list_leaves_the_list_in_one_piece(self):
        result = markers.remove(MARKDOWN, "markdown", {3, 4})
        self.assertTrue(result.endswith("- one\n- two\n"))

    def test_two_blocks_in_a_row_leave_one_blank_line(self):
        text = "One.\n\n<!-- groundwork:0004 -->\nA.\n<!-- /groundwork -->\n\n<!-- groundwork:0003 -->\nB.\n<!-- /groundwork -->\n\nThree.\n"
        self.assertEqual(markers.remove(text, "markdown", set()), "One.\n\nThree.\n")

    def test_the_other_blank_lines_of_the_text_are_kept(self):
        text = "One.\n\n\nTwo.\n\n<!-- groundwork:0004 -->\nA.\n<!-- /groundwork -->\n\nThree.\n"
        self.assertEqual(markers.remove(text, "markdown", set()), "One.\n\n\nTwo.\n\nThree.\n")

    def test_a_yaml_block_is_removed_with_its_indentation(self):
        result = markers.remove(YAML, "yaml", {1})
        self.assertIn("      # groundwork:0001", result)
        self.assertNotIn("commit-title", result)
        self.assertTrue(result.endswith("      # /groundwork\n"))

    def test_removing_twice_gives_the_same_text(self):
        once = markers.remove(MARKDOWN, "markdown", {3})
        self.assertEqual(markers.remove(once, "markdown", {3}), once)

    def test_a_text_with_a_malformed_block_is_refused(self):
        with self.assertRaises(ValueError):
            markers.remove("<!-- groundwork:0004 -->\nText.\n", "markdown", set())


if __name__ == "__main__":
    unittest.main()
