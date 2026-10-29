import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choice  # noqa: E402

BASE = [(1, 999)]
FORK = [(1, 999), (9000, 9999)]
NEEDS = {1: set(), 2: set(), 3: {2}, 4: set(), 5: {2}, 6: {3, 5}, 9000: {3}}

BLOCKS = "Intro.\n\n<!-- groundwork:0004 -->\nFour.\n<!-- /groundwork -->\n\n<!-- groundwork:0003 -->\nThree.\n<!-- /groundwork -->\n"


class Read(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def write(self, text, mode="w"):
        with open(
            os.path.join(self.root, ".groundwork-adrs"), mode, **({"encoding": "utf-8"} if mode == "w" else {})
        ) as handle:
            handle.write(text)

    def test_without_the_file_everything_is_synchronised(self):
        self.assertEqual(choice.read(self.root, BASE), (None, []))

    def test_numbers_and_ranges_are_read_with_their_comments_and_blank_lines(self):
        self.write("# What we keep\n0003\n\n0005-0006  \n  # more\n")
        self.assertEqual(choice.read(self.root, BASE), ([(3, 3), (5, 6)], []))

    def test_a_file_with_only_comments_lists_nothing(self):
        self.write("# nothing yet\n")
        self.assertEqual(choice.read(self.root, BASE), ([], []))

    def test_windows_line_ends_and_a_bom_are_read(self):
        self.write(b"\xef\xbb\xbf0003\r\n0005\r\n", "wb")
        self.assertEqual(choice.read(self.root, BASE), ([(3, 3), (5, 5)], []))

    def refused(self, text, reserved=BASE, line=2):
        self.write("0002\n" + text)
        adopted, problems = choice.read(self.root, reserved)
        self.assertEqual([found for found, _ in problems], [line], problems)
        self.assertEqual(adopted, [(2, 2)])

    def test_a_line_that_is_not_a_number_a_range_a_comment_or_blank_is_refused_with_its_line_number(self):
        for text in ("abc\n", "3\n", "00033\n", "0003-\n", "0003,0005\n", "ADR 0003\n", "0003 # note\n", "0003–0005\n"):
            with self.subTest(text=text):
                self.refused(text)

    def test_a_range_whose_first_bound_is_above_the_second_is_refused(self):
        self.refused("0600-0500\n")

    def test_a_number_that_no_range_reserves_is_refused(self):
        for text in ("0000\n", "1000\n", "9000\n"):
            with self.subTest(text=text):
                self.refused(text)

    def test_a_number_of_a_range_that_the_source_reserves_is_accepted(self):
        self.write("9500\n9000-9999\n")
        self.assertEqual(choice.read(self.root, FORK), ([(9500, 9500), (9000, 9999)], []))

    def test_a_range_that_does_not_lie_wholly_within_a_reserved_range_is_refused(self):
        for text in ("0500-1500\n", "0001-1000\n", "0500-9500\n", "8999-9000\n"):
            with self.subTest(text=text):
                self.refused(text, FORK)

    def test_every_problem_of_the_file_is_reported(self):
        self.write("abc\n0003\n1000\n")
        adopted, problems = choice.read(self.root, BASE)
        self.assertEqual(adopted, [(3, 3)])
        self.assertEqual([line for line, _ in problems], [1, 3])


class Kept(unittest.TestCase):
    def test_without_a_choice_every_adr_is_kept(self):
        kept = choice.Kept(None, NEEDS)
        self.assertTrue(all(number in kept for number in (1, 2, 6, 9000, 4000)))

    def test_a_listed_adr_is_kept_with_the_adrs_it_needs_in_turn(self):
        kept = choice.Kept([(6, 6)], NEEDS)
        self.assertEqual({number for number in range(1, 10) if number in kept}, {1, 2, 3, 5, 6})

    def test_an_adr_that_is_not_listed_nor_needed_is_left_out(self):
        kept = choice.Kept([(3, 3)], NEEDS)
        for number in (4, 5, 6, 9000):
            self.assertNotIn(number, kept)

    def test_adr_0001_is_kept_even_if_nothing_is_listed(self):
        self.assertIn(1, choice.Kept([], NEEDS))
        self.assertNotIn(2, choice.Kept([], NEEDS))

    def test_a_range_holds_the_adrs_that_the_source_adds_to_it_later(self):
        kept = choice.Kept([(9000, 9999)], NEEDS)
        self.assertIn(9001, kept)
        self.assertIn(9999, kept)
        self.assertNotIn(10000, kept)

    def test_an_adr_of_a_range_brings_the_adrs_of_groundwork_that_it_needs(self):
        kept = choice.Kept([(9000, 9999)], NEEDS)
        self.assertEqual({number for number in (1, 2, 3, 4, 5, 6) if number in kept}, {1, 2, 3})

    def test_a_range_of_groundwork_holds_its_adrs_whole(self):
        kept = choice.Kept([(1, 999)], NEEDS)
        self.assertTrue(all(number in kept for number in (1, 2, 3, 4, 5, 6, 500)))
        self.assertNotIn(9000, kept)

    def test_the_adrs_added_are_the_ones_needed_and_not_listed(self):
        self.assertEqual(choice.Kept([(6, 6)], NEEDS).added(), [2, 3, 5])
        self.assertEqual(choice.Kept([(5, 6), (3, 3)], NEEDS).added(), [2])

    def test_adr_0001_and_the_adrs_of_a_range_are_not_added(self):
        self.assertEqual(choice.Kept([], NEEDS).added(), [])
        self.assertEqual(choice.Kept([(1, 999)], NEEDS).added(), [])

    def test_without_a_choice_nothing_is_added(self):
        self.assertEqual(choice.Kept(None, NEEDS).added(), [])

    def test_the_needs_are_not_changed(self):
        needs = {3: {2}, 2: set()}
        choice.Kept([(3, 3)], needs).added()
        self.assertEqual(needs, {3: {2}, 2: set()})


class Included(unittest.TestCase):
    OWNERS = {"a.txt": 1, "b.txt": 3, "c.txt": 4, "AGENTS.md": 6}

    def included(self, path, kept, reserved=BASE):
        return choice.included(path, self.OWNERS, kept, reserved)

    def test_the_file_of_an_adr_that_is_kept_is_taken_and_the_file_of_one_that_is_left_out_is_not(self):
        kept = choice.Kept([(3, 3)], NEEDS)
        self.assertTrue(self.included("docs/adr/0003-third.md", kept))
        self.assertTrue(self.included("docs/adr/0002-second.md", kept))
        self.assertFalse(self.included("docs/adr/0004-fourth.md", kept))

    def test_the_files_of_the_map_follow_their_adr(self):
        kept = choice.Kept([(3, 3)], NEEDS)
        self.assertTrue(self.included("a.txt", kept))
        self.assertTrue(self.included("b.txt", kept))
        self.assertFalse(self.included("c.txt", kept))
        self.assertFalse(self.included("AGENTS.md", kept))

    def test_a_file_that_the_map_does_not_give_to_an_adr_is_taken(self):
        kept = choice.Kept([], NEEDS)
        for path in (
            ".groundwork/practices.md",
            "README.md",
            "docs/adr/template.md",
            "docs/adr/notes.md",
            "CONTRIBUTING.md",
        ):
            with self.subTest(path=path):
                self.assertTrue(self.included(path, kept))

    def test_an_adr_outside_the_reserved_ranges_is_never_taken(self):
        for kept in (choice.Kept(None, NEEDS), choice.Kept([(1, 999)], NEEDS)):
            self.assertFalse(self.included("docs/adr/1000-own-decision.md", kept))

    def test_an_adr_of_a_range_that_the_source_reserves_follows_the_choice(self):
        path = "docs/adr/9001-fork.md"
        self.assertFalse(self.included(path, choice.Kept([(3, 3)], NEEDS), FORK))
        self.assertTrue(self.included(path, choice.Kept([(9000, 9999)], NEEDS), FORK))
        self.assertTrue(self.included(path, choice.Kept(None, NEEDS), FORK))
        self.assertFalse(self.included(path, choice.Kept(None, NEEDS), BASE))

    def test_every_file_is_taken_without_a_choice(self):
        kept = choice.Kept(None, NEEDS)
        for path in ("a.txt", "c.txt", "AGENTS.md", "docs/adr/0004-fourth.md", ".groundwork/practices.md"):
            with self.subTest(path=path):
                self.assertTrue(self.included(path, kept))

    def test_a_directory_of_another_name_is_not_taken_for_the_adrs(self):
        kept = choice.Kept([], NEEDS)
        self.assertTrue(self.included("other/docs/adr/0004-fourth.md", kept))


class Content(unittest.TestCase):
    def test_the_blocks_of_the_adrs_left_out_are_removed(self):
        kept = choice.Kept([(3, 3)], NEEDS)
        result = choice.content("CONTRIBUTING.md", BLOCKS, kept)
        self.assertNotIn("Four", result)
        self.assertIn("Three", result)

    def test_nothing_is_removed_when_every_adr_is_kept(self):
        self.assertEqual(choice.content("CONTRIBUTING.md", BLOCKS, choice.Kept(None, NEEDS)), BLOCKS)

    def test_the_blocks_of_a_yaml_file_are_removed(self):
        text = "hooks:\n  # groundwork:0004\n  - id: four\n  # /groundwork\n  - id: other\n"
        self.assertEqual(
            choice.content(".pre-commit-config.yaml", text, choice.Kept([], NEEDS)), "hooks:\n  - id: other\n"
        )

    def test_a_file_that_has_no_markers_syntax_is_unchanged(self):
        text = "# groundwork:0004\nprint(1)\n# /groundwork\n"
        self.assertEqual(choice.content("script.py", text, choice.Kept([], NEEDS)), text)

    def test_a_file_with_a_malformed_block_is_refused(self):
        with self.assertRaises(ValueError):
            choice.content("CONTRIBUTING.md", "<!-- groundwork:0004 -->\nText.\n", choice.Kept([], NEEDS))


if __name__ == "__main__":
    unittest.main()
