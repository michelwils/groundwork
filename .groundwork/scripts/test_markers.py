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
        self.assertEqual(
            [(block.adr, block.start, block.end) for block in found], [(4, 5, 9), (3, 11, 15), (10, 20, 22)]
        )

    def test_the_blocks_of_a_yaml_file_are_read_with_their_indentation(self):
        found = self.blocks(YAML, "yaml")
        self.assertEqual([(block.adr, block.start, block.end) for block in found], [(1, 4, 7), (2, 9, 12)])

    def test_a_block_is_named_and_does_not_change(self):
        block = self.blocks(MARKDOWN)[0]
        self.assertEqual(block, markers.Block(adr=4, start=5, end=9))
        self.assertEqual(tuple(block), (4, 5, 9))
        with self.assertRaises(AttributeError):
            block.end = 10

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


SOURCE = """updates:
  - own: neutral

  # groundwork:source
  - for: the source
  # /groundwork:source

  # groundwork:0002
  - for: an adr
  # /groundwork

  # The entries of the project go below this line.
"""


class SourceBlocks(unittest.TestCase):
    """A block of the source holds the lines that only the source needs, and that the update does not bring."""

    def test_a_block_of_the_source_is_not_a_block_of_an_adr(self):
        blocks, problems = markers.parse(SOURCE.split("\n"), "yaml")
        self.assertEqual(problems, [])
        self.assertEqual([block.adr for block in blocks], [2])

    def test_a_block_of_an_adr_inside_a_block_of_the_source_is_reported(self):
        text = "# groundwork:source\n# groundwork:0002\nx\n# /groundwork\n# /groundwork:source\n"
        self.assertTrue(any("inside" in message for _, message in markers.parse(text.split("\n"), "yaml")[1]))

    def test_a_block_of_the_source_that_is_not_closed_is_reported_at_its_line(self):
        (problem,) = markers.parse("x\n# groundwork:source\ny\n".split("\n"), "yaml")[1]
        self.assertEqual(problem[0], 2)
        self.assertIn("not closed", problem[1])

    def test_a_block_of_the_source_is_closed_by_its_own_marker(self):
        self.assertEqual(
            markers.parse("<!-- groundwork:source -->\nx\n<!-- /groundwork:source -->\n".split("\n"), "markdown")[1], []
        )

    def test_a_block_of_the_source_closed_by_the_marker_of_an_adr_is_reported(self):
        text = "x\n# groundwork:source\ny\n# /groundwork\n"
        problems = markers.parse(text.split("\n"), "yaml")[1]
        self.assertTrue(any(line == 4 and "source" in message for line, message in problems), problems)

    def test_a_block_of_an_adr_closed_by_the_marker_of_the_source_is_reported(self):
        text = "x\n# groundwork:0002\ny\n# /groundwork:source\n"
        problems = markers.parse(text.split("\n"), "yaml")[1]
        self.assertTrue(any(line == 4 and "0002" in message for line, message in problems), problems)

    def test_a_block_closed_by_the_wrong_marker_gives_one_problem(self):
        text = "# groundwork:0002\n# /groundwork:source\n# groundwork:0003\nx\n# /groundwork\n"
        self.assertEqual(len(markers.parse(text.split("\n"), "yaml")[1]), 1)

    def test_a_closing_marker_of_the_source_without_a_block_is_reported(self):
        (problem,) = markers.parse("x\n# /groundwork:source\n".split("\n"), "yaml")[1]
        self.assertEqual(problem[0], 2)
        self.assertIn("no block", problem[1])

    def test_the_choice_of_the_adrs_keeps_a_block_of_the_source(self):
        self.assertEqual(markers.remove(SOURCE, "yaml", set()).count("# groundwork:source\n"), 1)
        self.assertNotIn("an adr", markers.remove(SOURCE, "yaml", set()))

    def test_remove_source_takes_out_the_block_with_its_markers_and_its_blank_line(self):
        self.assertEqual(
            markers.remove_source(SOURCE, "yaml"),
            "updates:\n  - own: neutral\n\n  # groundwork:0002\n  - for: an adr\n  # /groundwork\n\n"
            "  # The entries of the project go below this line.\n",
        )

    def test_remove_source_leaves_the_blocks_of_the_adrs(self):
        self.assertEqual(markers.remove_source(YAML, "yaml"), YAML)
        self.assertEqual(markers.remove_source(MARKDOWN, "markdown"), MARKDOWN)

    def test_removing_the_source_twice_gives_the_same_text(self):
        once = markers.remove_source(SOURCE, "yaml")
        self.assertEqual(markers.remove_source(once, "yaml"), once)

    def test_a_text_with_a_malformed_block_is_refused_by_remove_source(self):
        with self.assertRaises(ValueError):
            markers.remove_source("# groundwork:source\nText.\n", "yaml")


if __name__ == "__main__":
    unittest.main()
