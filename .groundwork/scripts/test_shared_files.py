import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import check_practices  # noqa: E402
import markers  # noqa: E402
import practices_map  # noqa: E402

LINK = re.compile(r"\]\(([^)\s#]+)")


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


class SharedFiles(unittest.TestCase):
    """What stays of the files that several ADRs share when an ADR is left out (ADR 1000)."""

    @classmethod
    def setUpClass(cls):
        entries, shared, _ = practices_map.parse(read(".groundwork/practices.md").split("\n"))
        cls.numbers = sorted(entry["number"] for entry in entries)
        cls.needs = {entry["number"]: set(check_practices.references(entry["needs"][0])[0]) for entry in entries}
        cls.files = {entry["number"]: [path for path, _ in entry["files"]] for entry in entries}
        cls.candidates = sorted({path for path, _ in shared} | {path for entry in entries for path, _ in entry["shared"]})
        cls.candidates = [path for path in cls.candidates if markers.kind(path) and os.path.isfile(os.path.join(ROOT, path))]

    def dependents(self, number):
        found, grew = {number}, True
        while grew:
            grew = False
            for other, needs in self.needs.items():
                if other not in found and needs & found:
                    found.add(other)
                    grew = True
        return found

    def adr_files(self, numbers):
        return {os.path.relpath(path, ROOT).replace(os.sep, "/") for number in numbers for path in glob.glob(os.path.join(ROOT, "docs", "adr", f"{number:04d}-*.md"))}

    def check_left_out(self, dropped):
        kept = set(self.numbers) - dropped
        gone = {path for number in dropped for path in self.files[number]} | self.adr_files(dropped)
        for path in self.candidates:
            if path in gone:
                continue
            with self.subTest(path=path, left_out=sorted(dropped)):
                syntax = markers.kind(path)
                text = read(path)
                reduced = markers.remove(text, syntax, kept)
                lines = reduced.split("\n")
                numbered = check_practices.outside_code(lines) if syntax == "markdown" else list(enumerate(lines, start=1))
                for number, line in numbered:
                    self.assertEqual(check_practices.named_adrs(line) & dropped, set(), f"line {number}: {line}")
                if syntax == "markdown":
                    for target in LINK.findall(reduced):
                        if "://" in target or target.startswith("mailto:"):
                            continue
                        resolved = os.path.normpath(os.path.join(os.path.dirname(path), target)).replace(os.sep, "/")
                        self.assertNotIn(resolved, gone, f"link to {target}")
                if "\n\n\n" not in text:
                    self.assertNotIn("\n\n\n", reduced)
                self.assertTrue(reduced.endswith("\n") and not reduced.endswith("\n\n"))
                if os.path.basename(path) == ".pre-commit-config.yaml" and shutil.which("pre-commit"):
                    with tempfile.TemporaryDirectory() as directory:
                        target = os.path.join(directory, os.path.basename(path))
                        with open(target, "w", encoding="utf-8") as handle:
                            handle.write(reduced)
                        result = subprocess.run(["pre-commit", "validate-config", target], capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_files_have_markers_to_check(self):
        self.assertTrue(any(markers.parse(read(path).split("\n"), markers.kind(path))[0] for path in self.candidates))

    def test_each_adr_left_out_with_the_adrs_that_need_it_leaves_no_trace_in_the_files_that_remain(self):
        for number in self.numbers:
            if number != 1:
                with self.subTest(left_out=number):
                    self.check_left_out(self.dependents(number))

    def test_only_adr_0001_kept_leaves_no_trace_of_the_others(self):
        self.check_left_out(set(self.numbers) - {1})

    def test_nothing_is_removed_when_every_adr_is_kept(self):
        for path in self.candidates:
            with self.subTest(path=path):
                text = read(path)
                self.assertEqual(markers.remove(text, markers.kind(path), set(self.numbers)), text)


if __name__ == "__main__":
    unittest.main()
