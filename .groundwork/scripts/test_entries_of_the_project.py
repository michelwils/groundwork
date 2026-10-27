import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import choice  # noqa: E402
import update_groundwork as update  # noqa: E402
from test_filtered_trees import is_source  # noqa: E402

CONFIG = os.path.join(ROOT, ".github", "dependabot.yml")
ANCHOR = "  # The entries of the project go below this line. groundwork adds its own above it.\n"
PROJECT = "\n  - package-ecosystem: cargo\n    directory: /\n    schedule:\n      interval: weekly\n"
GROUNDWORK = "  - package-ecosystem: docker\n    directory: /\n    schedule:\n      interval: weekly\n\n"


def read():
    """Return the entries of groundwork and the comment, whatever a community base writes below it."""
    with open(CONFIG, encoding="utf-8") as handle:
        text = handle.read()
    return text[: text.index(ANCHOR) + len(ANCHOR)] if ANCHOR in text else text


@unittest.skipUnless(is_source(ROOT, os.environ), "it reads the file of groundwork, which a project extends with its own entries")
class EntriesOfTheProject(unittest.TestCase):
    """A project writes its entries below the comment that ends those of groundwork, and the update merges them."""

    def merge(self, project, groundwork):
        base = read().encode()
        content, conflict = update.merge(project.encode(), base, groundwork.encode())
        return content.decode(), conflict

    def test_the_entries_of_groundwork_end_with_the_comment_for_those_of_the_project(self):
        with open(CONFIG, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count(ANCHOR), 1, "the file lacks the comment of the entries of the project, or has it twice")
        self.assertTrue(text.split(ANCHOR)[0].endswith("]\n\n"), "the comment does not follow a blank line after the last entry of groundwork")

    def test_an_entry_of_the_project_and_an_entry_that_groundwork_adds_above_merge_without_conflict(self):
        text = read()
        above = text.replace(ANCHOR, GROUNDWORK + ANCHOR)
        merged, conflict = self.merge(text + PROJECT, above)
        self.assertFalse(conflict, merged)
        self.assertIn("package-ecosystem: docker", merged)
        self.assertIn("package-ecosystem: cargo", merged)
        self.assertLess(merged.index("package-ecosystem: docker"), merged.index(ANCHOR))
        self.assertGreater(merged.index("package-ecosystem: cargo"), merged.index(ANCHOR))

    def test_an_entry_of_the_project_and_a_change_of_the_last_entry_of_groundwork_merge_without_conflict(self):
        text = read()
        last = text.rindex("      prefix: ")
        changed = text[:last] + "      include: scope\n" + text[last:]
        self.assertTrue(last < text.index(ANCHOR) and "include: scope" in changed)
        merged, conflict = self.merge(text + PROJECT, changed)
        self.assertFalse(conflict, merged)
        self.assertIn("include: scope", merged)
        self.assertIn("package-ecosystem: cargo", merged)


HOOKS_PATH = ".pre-commit-config.yaml"
HOOKS = os.path.join(ROOT, HOOKS_PATH)
HOOKS_ANCHOR = "  # The repositories of hooks of the project go below this line. groundwork adds its own above it.\n"
HOOKS_PROJECT = "\n  - repo: https://github.com/example/hooks\n    rev: v1.0.0\n    hooks:\n      - id: example\n"
HOOKS_GROUNDWORK = "  # groundwork:0009\n  - repo: local\n    hooks:\n      - id: added\n        name: Added\n        language: system\n        entry: true\n  # /groundwork\n\n"


def read_hooks():
    """Return the configuration of groundwork up to the comment, whatever a community base writes below it."""
    with open(HOOKS, encoding="utf-8") as handle:
        text = handle.read()
    return text[: text.index(HOOKS_ANCHOR) + len(HOOKS_ANCHOR)] if HOOKS_ANCHOR in text else text


class AllBut:
    """The ADRs of a choice that keeps every ADR except the ones given."""

    def __init__(self, *left_out):
        self.left_out = left_out

    def __contains__(self, number):
        return number not in self.left_out


@unittest.skipUnless(is_source(ROOT, os.environ), "it reads the file of groundwork, which a project extends with its own hooks")
class HooksOfTheProject(unittest.TestCase):
    """A project writes its hooks below the comment that ends the configuration of groundwork, and the update merges them."""

    def merge(self, project, groundwork, kept=None):
        base = read_hooks()
        if kept is not None:
            project, base, groundwork = (choice.content(HOOKS_PATH, text, kept) for text in (project, base, groundwork))
        content, conflict = update.merge(project.encode(), base.encode(), groundwork.encode())
        return content.decode(), conflict

    def test_the_configuration_of_groundwork_ends_with_the_comment_for_the_hooks_of_the_project(self):
        with open(HOOKS, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count(HOOKS_ANCHOR), 1, "the file lacks the comment of the hooks of the project, or has it twice")
        before = text.split(HOOKS_ANCHOR)[0]
        self.assertTrue(before.endswith("# /groundwork\n\n"), "the comment does not follow a blank line after the last block of groundwork")

    def test_a_repository_of_the_project_and_a_block_that_groundwork_adds_above_merge_without_conflict(self):
        text = read_hooks()
        above = text.replace(HOOKS_ANCHOR, HOOKS_GROUNDWORK + HOOKS_ANCHOR)
        merged, conflict = self.merge(text + HOOKS_PROJECT, above)
        self.assertFalse(conflict, merged)
        self.assertLess(merged.index("id: added"), merged.index(HOOKS_ANCHOR))
        self.assertGreater(merged.index("id: example"), merged.index(HOOKS_ANCHOR))

    def test_the_merge_holds_when_the_project_leaves_out_the_adr_of_the_block_before_it(self):
        text = read_hooks()
        above = text.replace(HOOKS_ANCHOR, HOOKS_GROUNDWORK + HOOKS_ANCHOR)
        kept = AllBut(7)
        merged, conflict = self.merge(text + HOOKS_PROJECT, above, kept)
        self.assertFalse(conflict, merged)
        self.assertNotIn("groundwork:0007", merged)
        self.assertGreater(merged.index("id: example"), merged.index(HOOKS_ANCHOR))


if __name__ == "__main__":
    unittest.main()
