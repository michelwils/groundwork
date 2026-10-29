import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import practices_map  # noqa: E402

MAP = """# Practices

## Practices

### 0001. [First](adr/0001-first.md)

- Needs: none
- Files:
  - `a.txt`
- Shared lines:
  - none

### 0003. [Third](adr/0003-third.md)

- Needs: ADR 0002
- Files:
  - `b.txt`
  - `c.txt`
- Shared lines:
  - none

## Shared files

- `CONTRIBUTING.md`

## Not part of a practice

- `README.md`
"""


class Ranges(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def declare(self, text):
        with open(os.path.join(self.root, ".groundwork-ranges"), "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_a_source_without_the_file_reserves_the_base_only(self):
        self.assertEqual(practices_map.read_ranges(self.root), ([(1, 999)], []))

    def test_the_base_is_written_once(self):
        self.assertEqual(practices_map.BASE, (1, 999))

    def test_the_ranges_of_the_file_come_after_the_base(self):
        self.declare("9000-9999\n")
        self.assertEqual(practices_map.read_ranges(self.root), ([(1, 999), (9000, 9999)], []))

    def test_comments_and_blank_lines_are_ignored(self):
        self.declare("# The ranges of the base\n\n  # indented\n5000-5999\n\n")
        self.assertEqual(practices_map.read_ranges(self.root), ([(1, 999), (5000, 5999)], []))

    def test_the_ranges_are_sorted_and_may_be_of_one_number(self):
        self.declare("9000-9999\n2000-2000\n")
        self.assertEqual(practices_map.read_ranges(self.root)[0], [(1, 999), (2000, 2000), (9000, 9999)])

    def test_a_file_with_windows_line_ends_and_a_bom_is_read(self):
        with open(os.path.join(self.root, ".groundwork-ranges"), "wb") as handle:
            handle.write(b"\xef\xbb\xbf9000-9999\r\n")
        self.assertEqual(practices_map.read_ranges(self.root), ([(1, 999), (9000, 9999)], []))

    def refused(self, text, line):
        self.declare(text)
        reserved, problems = practices_map.read_ranges(self.root)
        self.assertEqual([found for found, _ in problems], [line], problems)
        return reserved

    def test_a_line_that_is_not_a_range_is_refused_with_its_line_number(self):
        for text in (
            "9000\n",
            "abc\n",
            "9000-99999\n",
            "900-999\n",
            "9000–9999\n",
            "9000-9999 extra\n",
            "9000 - 9999\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.refused("# comment\n" + text, 2), [(1, 999)])

    def test_the_message_of_a_line_that_is_not_a_range_shows_the_format_without_a_number_of_a_community(self):
        self.declare("abc\n")
        (problem,) = practices_map.read_ranges(self.root)[1]
        self.assertIn("NNNN-NNNN", problem[1])

    def test_a_range_whose_first_bound_is_above_the_second_is_refused(self):
        self.assertEqual(self.refused("9999-9000\n", 1), [(1, 999)])

    def test_a_range_that_overlaps_the_base_is_refused(self):
        for text in ("0500-1500\n", "0900-0999\n", "0000-0100\n", "0000-0000\n", "0001-0001\n"):
            with self.subTest(text=text):
                self.assertEqual(self.refused(text, 1), [(1, 999)])

    def test_a_range_that_overlaps_an_earlier_range_is_refused_at_its_line(self):
        self.assertEqual(self.refused("2000-2999\n\n2500-3500\n", 3), [(1, 999), (2000, 2999)])

    def test_a_valid_range_beside_a_refused_one_is_kept(self):
        self.declare("abc\n9000-9999\n")
        reserved, problems = practices_map.read_ranges(self.root)
        self.assertEqual(reserved, [(1, 999), (9000, 9999)])
        self.assertEqual([line for line, _ in problems], [1])

    def test_a_number_is_reserved_when_a_range_holds_it(self):
        reserved = [(1, 999), (9000, 9999)]
        self.assertTrue(practices_map.is_reserved(1, reserved))
        self.assertTrue(practices_map.is_reserved(999, reserved))
        self.assertTrue(practices_map.is_reserved(9000, reserved))
        self.assertFalse(practices_map.is_reserved(0, reserved))
        self.assertFalse(practices_map.is_reserved(1000, reserved))
        self.assertFalse(practices_map.is_reserved(10000, reserved))


class Entries(unittest.TestCase):
    def entries(self):
        return practices_map.parse(MAP.split("\n"))[0]

    def test_the_map_is_read(self):
        self.assertEqual([entry["number"] for entry in self.entries()], [1, 3])

    def test_the_needs_of_each_adr_are_a_set_of_numbers(self):
        self.assertEqual(practices_map.needs_of(self.entries()), {1: set(), 3: {2}})

    def test_an_entry_without_a_line_needs_is_left_out_of_the_needs(self):
        entries, _, _ = practices_map.parse("## Practices\n\n### 0004. Four\n\n- Files:\n  - none\n".split("\n"))
        self.assertEqual(practices_map.needs_of(entries), {})

    def test_each_file_has_the_number_of_the_adr_that_owns_it(self):
        self.assertEqual(practices_map.owners(self.entries()), {"a.txt": 1, "b.txt": 3, "c.txt": 3})

    def test_the_references_and_the_cycles_are_read(self):
        self.assertEqual(practices_map.references("ADR 0001, ADR 0003"), ([1, 3], []))
        self.assertEqual(practices_map.references("none"), ([], []))
        self.assertEqual(practices_map.cycles({1: [2], 2: [1], 3: [1]}), [1, 2])


class ReadMap(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def write(self, content):
        os.makedirs(os.path.join(self.root, ".groundwork"), exist_ok=True)
        with open(os.path.join(self.root, ".groundwork", "practices.md"), "wb") as handle:
            handle.write(content)

    def test_a_missing_map_has_no_entry_no_shared_file_and_no_other_file(self):
        self.assertEqual(practices_map.read_map(self.root), ([], [], []))

    def test_the_map_of_a_project_is_read_like_the_text_parsed(self):
        self.write(MAP.encode())
        self.assertEqual(practices_map.read_map(self.root), practices_map.parse(MAP.split("\n")))

    def test_a_map_with_a_bom_and_windows_line_ends_is_read(self):
        self.write(b"\xef\xbb\xbf## Shared files\r\n\r\n- `CONTRIBUTING.md`\r\n")
        self.assertEqual(practices_map.read_map(self.root)[1], [("CONTRIBUTING.md", 3)])


class Closure(unittest.TestCase):
    NEEDS = {1: set(), 2: set(), 3: {2}, 6: {3, 5}, 5: {2}, 7: {2, 3}}

    def test_the_adrs_that_are_needed_follow_in_turn(self):
        self.assertEqual(practices_map.closure({6}, self.NEEDS), {6, 3, 5, 2})

    def test_an_adr_with_no_needs_stays_alone(self):
        self.assertEqual(practices_map.closure({1}, self.NEEDS), {1})

    def test_the_closure_of_nothing_is_nothing(self):
        self.assertEqual(practices_map.closure(set(), self.NEEDS), set())

    def test_a_number_that_has_no_entry_stays_in_the_closure(self):
        self.assertEqual(practices_map.closure({4000}, self.NEEDS), {4000})

    def test_a_cycle_does_not_loop(self):
        self.assertEqual(practices_map.closure({1}, {1: {2}, 2: {1}}), {1, 2})

    def test_the_needs_are_not_changed(self):
        needs = {3: {2}, 2: set()}
        practices_map.closure({3}, needs)
        self.assertEqual(needs, {3: {2}, 2: set()})


if __name__ == "__main__":
    unittest.main()
