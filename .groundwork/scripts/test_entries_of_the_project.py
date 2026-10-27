import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import update_groundwork as update  # noqa: E402
from test_filtered_trees import is_source  # noqa: E402

CONFIG = os.path.join(ROOT, ".github", "dependabot.yml")
ANCHOR = "  # The entries of the project go below this line. groundwork adds its own above it.\n"
PROJECT = "\n  - package-ecosystem: cargo\n    directory: /\n    schedule:\n      interval: weekly\n"
GROUNDWORK = "  - package-ecosystem: docker\n    directory: /\n    schedule:\n      interval: weekly\n\n"


def read():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(is_source(ROOT, os.environ), "it reads the file of groundwork, which a project extends with its own entries")
class EntriesOfTheProject(unittest.TestCase):
    """A project writes its entries below the comment that ends those of groundwork, and the update merges them."""

    def merge(self, project, groundwork):
        base = read().encode()
        content, conflict = update.merge(project.encode(), base, groundwork.encode())
        return content.decode(), conflict

    def test_the_entries_of_groundwork_end_with_the_comment_for_those_of_the_project(self):
        text = read()
        self.assertTrue(text.endswith(ANCHOR), "the file does not end with the comment of the entries of the project")
        self.assertEqual(text.count(ANCHOR), 1)

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
        changed = text.replace("      prefix: ci(deps)\n", "      prefix: ci(deps)\n      include: scope\n")
        self.assertNotEqual(changed, text)
        merged, conflict = self.merge(text + PROJECT, changed)
        self.assertFalse(conflict, merged)
        self.assertIn("include: scope", merged)
        self.assertIn("package-ecosystem: cargo", merged)


if __name__ == "__main__":
    unittest.main()
