import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_links  # noqa: E402

SCRIPT = os.path.join(HERE, "check_links.py")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def make(self, files):
        for name, content in files.items():
            path = os.path.join(self.root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as handle:
                handle.write(content)

    def problems(self):
        return check_links.check(self.root)


class Links(Fixture):
    def test_a_link_to_an_existing_file_is_accepted(self):
        self.make({"README.md": "[guide](docs/guide.md) and [config](.editorconfig)\n", "docs/guide.md": "# Guide\n", ".editorconfig": ""})
        self.assertEqual(self.problems(), [])

    def test_a_link_to_a_directory_is_accepted(self):
        self.make({"README.md": "[ADRs](docs/adr/)\n", "docs/adr/a.md": "# A\n"})
        self.assertEqual(self.problems(), [])

    def test_a_link_to_a_missing_file_is_reported_with_its_file_and_line(self):
        self.make({"README.md": "one\n\n[guide](docs/missing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:3", problem)
        self.assertIn("docs/missing.md", problem)

    def test_a_link_is_relative_to_the_file_that_contains_it(self):
        self.make({"docs/a.md": "[b](b.md) [root](../README.md)\n", "docs/b.md": "# B\n", "README.md": "# R\n"})
        self.assertEqual(self.problems(), [])
        self.make({"docs/c.md": "[b](docs/b.md)\n"})
        self.assertEqual(len(self.problems()), 1)

    def test_a_link_starting_with_a_slash_is_relative_to_the_root(self):
        self.make({"docs/a.md": "[readme](/README.md) [bad](/nope.md)\n", "README.md": "# R\n"})
        (problem,) = self.problems()
        self.assertIn("/nope.md", problem)

    def test_a_link_that_leaves_the_repository_is_reported(self):
        self.make({"README.md": "[out](../outside.md)\n"})
        (problem,) = self.problems()
        self.assertIn("outside", problem)

    def test_an_anchor_of_the_same_file_is_checked(self):
        self.make({"README.md": "# Title\n\n## Moving to a later version\n\n[a](#moving-to-a-later-version) [b](#title) [c](#nope)\n"})
        (problem,) = self.problems()
        self.assertIn("#nope", problem)

    def test_an_anchor_of_another_file_is_checked(self):
        self.make({"README.md": "[a](docs/g.md#install) [b](docs/g.md#nope)\n", "docs/g.md": "# Guide\n\n## Install\n"})
        (problem,) = self.problems()
        self.assertIn("docs/g.md#nope", problem)

    def test_anchors_follow_the_rules_of_github(self):
        headings = "## Code `x` and *emphasis*\n## [Link](a.md) text\n## What's new? (v1.0)\n## Under_score and-dash\n## Same\n## Same\n"
        links = "[1](#code-x-and-emphasis) [2](#link-text) [3](#whats-new-v10) [4](#under_score-and-dash) [5](#same) [6](#same-1)\n"
        self.make({"README.md": headings + links, "a.md": "# A\n"})
        self.assertEqual(self.problems(), [])

    def test_a_link_with_parentheses_in_a_heading_is_reduced_to_its_text(self):
        self.make({"README.md": "## See [x](a_(b).md) now\n\n[a](#see-x-now)\n", "a_(b).md": "# A\n"})
        self.assertEqual(self.problems(), [])

    def test_a_closing_sequence_of_hashes_is_not_part_of_the_anchor(self):
        self.make({"README.md": "## Title ##\n\n[a](#title)\n"})
        self.assertEqual(self.problems(), [])

    def test_a_heading_underlined_with_equal_signs_or_hyphens_is_an_anchor(self):
        self.make({"README.md": "Main title\n==========\n\nSub title\n---\n\n[a](#main-title) [b](#sub-title)\n"})
        self.assertEqual(self.problems(), [])

    def test_a_thematic_break_after_a_blank_line_is_not_a_heading(self):
        self.make({"README.md": "Text\n\n---\n\n[a](#text)\n"})
        self.assertEqual(len(self.problems()), 1)

    def test_an_explicit_anchor_is_accepted(self):
        self.make({"README.md": '<a id="top"></a>\n\n[a](#top)\n'})
        self.assertEqual(self.problems(), [])

    def test_an_id_on_any_html_element_is_an_anchor(self):
        self.make({"README.md": '<h2 id="top">Top</h2>\n<div class="x" id="box"></div>\n\n[a](#top) [b](#box) [c](#nope)\n'})
        (problem,) = self.problems()
        self.assertIn("#nope", problem)

    def test_a_reference_definition_is_checked(self):
        self.make({"README.md": "[guide][g]\n\n[g]: docs/missing.md\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:3", problem)

    def test_a_file_that_is_not_valid_utf8_does_not_stop_the_check(self):
        with open(os.path.join(self.root, "README.md"), "wb") as handle:
            handle.write(b"\xff\xfe bad\n\n[a](missing.md)\n")
        (problem,) = self.problems()
        self.assertIn("README.md:3", problem)

    def test_a_byte_order_mark_does_not_hide_the_first_heading(self):
        self.make({"README.md": "\ufeff# Title\n\n[a](#title)\n"})
        self.assertEqual(self.problems(), [])

    def test_a_link_in_an_indented_code_block_is_ignored(self):
        self.make({"README.md": "Text\n\n    [a](missing.md)\n\n[b](missing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:5", problem)

    def test_a_broken_reference_is_reported_once_where_it_is_defined(self):
        self.make({"README.md": "[one][g] and [two][g]\n\n[g]: missing.md\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:3", problem)

    def test_a_reference_that_is_never_used_is_checked_too(self):
        self.make({"README.md": "Text\n\n[unused]: missing.md\n"})
        self.assertEqual(len(self.problems()), 1)

    def test_a_link_on_the_second_line_of_a_paragraph_is_reported_on_that_line(self):
        self.make({"README.md": "A first line,\nthen [a](missing.md) on the second,\nand a third.\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:2", problem)

    def test_a_footnote_is_not_a_reference_definition(self):
        self.make({"README.md": "Text[^1]\n\n[^1]: A note with words.\n"})
        self.assertEqual(self.problems(), [])

    def test_a_target_in_angle_brackets_and_a_title_are_understood(self):
        self.make({"README.md": '[a](<docs/a b.md> "title") [b](docs/b.md \'t\')\n', "docs/a b.md": "# A\n", "docs/b.md": "# B\n"})
        self.assertEqual(self.problems(), [])

    def test_an_image_is_checked_like_a_link(self):
        self.make({"README.md": "![logo](img/logo.png)\n"})
        self.assertEqual(len(self.problems()), 1)

    def test_a_query_and_an_encoded_path_are_understood(self):
        self.make({"README.md": "[a](docs/a%20b.md?plain=1) [b](docs/a%20b.md?plain=1#a)\n", "docs/a b.md": "# A\n"})
        self.assertEqual(self.problems(), [])

    def test_external_links_are_not_checked(self):
        self.make({"README.md": "[a](https://example.com/x) [b](mailto:a@b.c) [c](//example.com) [d](http://x.y#z)\n"})
        self.assertEqual(self.problems(), [])

    def test_a_line_anchor_on_a_file_is_accepted(self):
        self.make({"README.md": "[a](script.py#L10-L20) [b](script.py#L3)\n", "script.py": ""})
        self.assertEqual(self.problems(), [])

    def test_an_anchor_on_a_file_that_is_not_markdown_is_not_checked(self):
        self.make({"README.md": "[a](script.py#anything)\n", "script.py": ""})
        self.assertEqual(self.problems(), [])

    def test_links_in_code_are_ignored(self):
        self.make({"README.md": "```md\n[a](missing.md)\n```\n\n~~~\n[b](missing.md)\n~~~\n\nUse `[c](missing.md)` here.\n"})
        self.assertEqual(self.problems(), [])

    def test_links_in_an_html_comment_are_ignored(self):
        self.make({"README.md": "<!-- [a](missing.md) -->\n\n<!--\n[b](missing.md)\n-->\n[c](missing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:6", problem)

    def test_a_fence_inside_a_nested_list_item_is_a_code_block(self):
        self.make({"README.md": "1. one\n   - two\n\n      ```sh\n      [a](missing.md)\n      ```\n\n[b](missing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:8", problem)

    def test_the_line_of_a_link_is_right_after_a_code_block(self):
        self.make({"README.md": "```\ncode\n```\n[a](missing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("README.md:4", problem)

    def test_a_heading_in_a_code_block_is_not_an_anchor(self):
        self.make({"README.md": "```\n# Hidden\n```\n\n[a](#hidden)\n"})
        self.assertEqual(len(self.problems()), 1)

    def test_the_excluded_files_are_not_checked(self):
        self.make({"docs/adr/template.md": "[NNNN](NNNN-title.md)\n", "README.md": "# R\n"})
        self.assertEqual(self.problems(), [])

    def test_every_markdown_file_is_checked_but_not_the_git_directory(self):
        self.make({"a/b/c.md": "[x](missing.md)\n", ".git/notes.md": "[x](missing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("a/b/c.md", problem)

    def test_a_missing_file_is_reported_once_per_link(self):
        self.make({"README.md": "[a](x.md) [b](x.md)\n"})
        self.assertEqual(len(self.problems()), 2)


MAP = """# Practices

See [the ADR](../docs/adr/0003-third.md), [its anchor](../docs/adr/0003-third.md#decision) and [its script](../three.py).

## Practices

### 0001. [First](../docs/adr/0001-first.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - none

### 0003. [Third](../docs/adr/0003-third.md)

- Needs: none
- Files:
  - `three.py`
- Shared lines:
  - none
"""


class LeftOut(Fixture):
    """A project that keeps some of the ADRs: the map still links what it left out."""

    def project(self, listed="0001\n", files=None):
        self.make({".groundwork/practices.md": MAP, "docs/adr/0001-first.md": "# 0001. First\n", ".groundwork-adrs": listed, **(files or {})})

    def test_a_link_of_the_map_to_the_adr_that_is_left_out_is_not_reported(self):
        self.project()
        self.assertEqual(self.problems(), [])

    def test_a_link_of_the_map_to_the_file_of_an_entry_that_is_left_out_is_not_reported(self):
        self.project()
        self.assertFalse([problem for problem in self.problems() if "three.py" in problem])

    def test_an_anchor_in_the_adr_that_is_left_out_is_not_reported(self):
        self.project()
        self.assertFalse([problem for problem in self.problems() if "decision" in problem])

    def test_a_link_to_what_is_left_out_is_reported_in_any_other_file(self):
        self.project(files={"SECURITY.md": "[third](docs/adr/0003-third.md)\n"})
        (problem,) = self.problems()
        self.assertIn("SECURITY.md:1", problem)

    def test_a_link_of_the_map_to_an_adr_that_is_kept_and_missing_is_reported(self):
        self.project("0001\n0003\n")
        self.assertEqual(len(self.problems()), 4)

    def test_a_range_of_the_choice_keeps_the_adrs_it_holds(self):
        self.project("0001-0999\n")
        self.assertEqual(len(self.problems()), 4)

    def test_a_link_of_the_map_to_a_file_that_does_not_exist_and_is_not_left_out_is_reported(self):
        self.project(files={".groundwork/practices.md": MAP + "\n[nothing](nothing.md)\n"})
        (problem,) = self.problems()
        self.assertIn("nothing.md", problem)

    def test_without_a_choice_every_link_of_the_map_is_checked(self):
        self.project()
        os.remove(os.path.join(self.root, ".groundwork-adrs"))
        self.assertEqual(len(self.problems()), 4)


class CommandLine(unittest.TestCase):
    def run_script(self, files):
        with tempfile.TemporaryDirectory() as root:
            for name, content in files.items():
                with open(os.path.join(root, name), "w") as handle:
                    handle.write(content)
            return subprocess.run([sys.executable, SCRIPT, root], capture_output=True, text=True)

    def test_it_succeeds_when_every_link_resolves(self):
        result = self.run_script({"README.md": "# R\n\n[a](#r)\n"})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_it_fails_and_reports_on_the_error_output_when_a_link_is_broken(self):
        result = self.run_script({"README.md": "[a](missing.md)\n"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.md:1", result.stderr)


if __name__ == "__main__":
    unittest.main()
