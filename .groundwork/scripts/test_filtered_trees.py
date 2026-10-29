import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import check_adrs  # noqa: E402
import check_links  # noqa: E402
import check_practices  # noqa: E402
import choice  # noqa: E402
import practices_map  # noqa: E402

# The files that a project has of its own: the update synchronises neither of them.
README = "# Project\n\nText.\n"
LICENSE = "License.\n"

ADR = "# {n}. Decision {n}\n\n**Status:** accepted\n\n## Context\n\nText.\n\n## Decision\n\nText.\n\n## Consequences\n\nText.\n"
MAP = """# Practices

## Practices

### 0001. First

- Needs: none
- Files:
  - none
- Shared lines:
  - none

### 9000. Of the community

- Needs: ADR 0001
- Files:
  - none
- Shared lines:
  - none

## Shared files

- `CONTRIBUTING.md`

## Not part of a practice

- `.groundwork/practices.md`
"""


PATH_HEADING = "### Adopting in an existing project"
GAPS_HEADING = "### Recording the gaps"


def readme_section(heading):
    """Return the lines of a section of the README of groundwork, from its heading to the next heading of the same level or above."""
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    level = len(heading.split(" ")[0])
    start = lines.index(heading) + 1 if heading in lines else len(lines)
    found = []
    for line in lines[start:]:
        marks = re.match(r"^(#+) ", line)
        if marks and len(marks.group(1)) <= level:
            break
        found.append(line)
    return found


def adoption_order():
    """Return the numbers of the ADRs in the order of the path to adopt groundwork in an existing project."""
    return [
        int(number)
        for line in readme_section(PATH_HEADING)
        for number in re.findall(r"^- \*\*ADR ([0-9]{4})\*\*", line)
    ]


def is_source(root, environ):
    """Tell whether the repository is a source of ADRs: groundwork, which has no `.groundwork-version`, or a
    community base, which sets the variable GROUNDWORK_SOURCE to `true`. A project follows a source and is not one."""
    return environ.get("GROUNDWORK_SOURCE") == "true" or not os.path.exists(os.path.join(root, ".groundwork-version"))


def put(root, path, content):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


def track(root):
    subprocess.run(["git", "init", "--quiet", root], check=True)
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)


def check_all(root):
    return check_adrs.check(root) + check_practices.check(root) + check_links.check(root)


class Source(unittest.TestCase):
    def test_a_repository_without_a_version_is_a_source(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(is_source(root, {}))

    def test_a_repository_with_a_version_is_a_project_unless_the_variable_says_it_is_a_source(self):
        with tempfile.TemporaryDirectory() as root:
            put(root, ".groundwork-version", "0.6.0\n")
            self.assertFalse(is_source(root, {}))
            self.assertTrue(is_source(root, {"GROUNDWORK_SOURCE": "true"}))

    def test_the_variable_must_be_true(self):
        with tempfile.TemporaryDirectory() as root:
            put(root, ".groundwork-version", "0.6.0\n")
            for value in ("", "false", "1", "True", "yes"):
                with self.subTest(value=value):
                    self.assertFalse(is_source(root, {"GROUNDWORK_SOURCE": value}))


@unittest.skipUnless(
    is_source(ROOT, os.environ),
    "it reads the files of a source of ADRs, which a project may extend with scripts of its own",
)
class NoSuggestedRange(unittest.TestCase):
    """The range 9000-9999 is a suggestion of the guide of the community bases, which is the only file that gives it, and no script or workflow assumes it."""

    def test_no_file_of_the_automation_that_is_not_a_test_writes_it(self):
        listed = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "-z", ".github", ".groundwork"], capture_output=True, text=True, check=True
        ).stdout
        files = [
            path
            for path in listed.split("\0")
            if path and not os.path.basename(path).startswith("test_") and path != ".groundwork/community-base.md"
        ]
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path), open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as handle:
                self.assertNotRegex(handle.read(), r"9000|9999")


CONVENTIONAL = {
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "README.md",
    "LICENSE",
    ".editorconfig",
    ".gitignore",
    ".gitattributes",
    ".github/dependabot.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/change.md",
    ".github/zizmor.yml",
    ".github/workflows/checks.yml",
    ".github/workflows/project-checks.yml",
    ".github/workflows/release.yml",
    ".github/workflows/update-groundwork.yml",
    ".markdownlint.yaml",
    ".markdownlintignore",
    ".pre-commit-config.yaml",
    "docs/adr/template.md",
}
FORMER_PATHS = (
    ".github/scripts",
    ".github/rulesets",
    "docs/practices.md",
    "docs/groundwork-community-base.md",
    '".github", "scripts"',
    '".github", "rulesets"',
    '"docs", "practices.md"',
)
DESCRIBES_THE_FORMER_STATE = (
    "docs/adr/1001-naming-the-files-of-groundwork.md",
    ".github/scripts/test_filtered_trees.py",
    ".groundwork/scripts/test_filtered_trees.py",
)


@unittest.skipUnless(
    is_source(ROOT, os.environ), "it reads the files of groundwork, which a project extends with files of its own"
)
class PlacesOfTheFiles(unittest.TestCase):
    """The files of groundwork that have no conventional name are in `.groundwork/` (ADR 1001)."""

    def named(self):
        entries, shared, apart = practices_map.read_map(ROOT)
        return {path for entry in entries for path, _ in entry.files} | {path for path, _ in shared + apart}

    def test_every_file_of_the_map_is_in_the_directory_unless_its_name_and_place_are_fixed(self):
        for path in sorted(self.named() - CONVENTIONAL):
            with self.subTest(path=path):
                self.assertTrue(
                    path.startswith(".groundwork/"), f"{path} has no conventional name and is not in .groundwork/"
                )

    def test_the_list_of_the_conventional_names_names_only_files_of_the_map(self):
        self.assertEqual(sorted(CONVENTIONAL - self.named()), [])

    def test_no_file_names_a_former_path(self):
        listed = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, text=True, check=True
        ).stdout
        for path in sorted(path for path in listed.split("\0") if path and path not in DESCRIBES_THE_FORMER_STATE):
            full = os.path.join(ROOT, path)
            if not os.path.isfile(full):
                continue
            with open(full, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for former in FORMER_PATHS:
                with self.subTest(path=path, former=former):
                    self.assertNotIn(former, text)

    def test_no_hook_and_no_ignore_file_leaves_the_directory_out(self):
        samples = [
            ".groundwork/practices.md",
            ".groundwork/community-base.md",
            ".groundwork/scripts/check_adrs.py",
            ".groundwork/rulesets/main.json",
        ]
        with open(os.path.join(ROOT, ".pre-commit-config.yaml"), encoding="utf-8") as handle:
            config = re.sub(r"^\s*#.*\n", "", handle.read(), flags=re.MULTILINE)
        for pattern in re.findall(r"^\s*exclude: ['\"]?(.+?)['\"]?\s*$", config, flags=re.MULTILINE):
            for sample in samples:
                with self.subTest(exclude=pattern, path=sample):
                    self.assertIsNone(re.search(pattern, sample))
        with open(os.path.join(ROOT, ".markdownlintignore"), encoding="utf-8") as handle:
            ignored = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        for line in ignored:
            with self.subTest(ignored=line):
                self.assertFalse(line.lstrip("/").startswith(".groundwork") or line.startswith("*"))


@unittest.skipUnless(
    is_source(ROOT, os.environ), "it reads the files of groundwork, which a project extends with files of its own"
)
class ImportsOfTheFiles(unittest.TestCase):
    """A script of groundwork imports only files that are kept whenever it is kept."""

    def test_a_script_imports_only_its_own_adr_the_adrs_it_needs_adr_0001_and_the_files_of_no_adr(self):
        entries = practices_map.read_map(ROOT)[0]
        owners, needs = practices_map.owners(entries), practices_map.needs_of(entries)
        listed = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "-z", ".groundwork/scripts"], capture_output=True, text=True, check=True
        ).stdout
        scripts = {path: os.path.basename(path)[:-3] for path in listed.split("\0") if path.endswith(".py")}
        modules = {name: path for path, name in scripts.items()}
        for path in sorted(scripts):
            with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            imported = {
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imported |= {
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
            }
            mine = owners.get(path)
            allowed = {1} | ({mine} | practices_map.closure([mine], needs) if mine else set())
            for name in sorted(imported & set(modules) - {scripts[path]}):
                owner = owners.get(modules[name])
                with self.subTest(script=path, imports=name):
                    if owner is not None and owner not in allowed:
                        self.fail(f"{path} imports {modules[name]}, which ADR {owner:04d} owns")


@unittest.skipUnless(is_source(ROOT, os.environ), "it reads the README of groundwork, which a project replaces")
class ReadmeOfGroundwork(unittest.TestCase):
    """The README never tells a project to delete or remove a file that the map names: the check of the map reports it as missing."""

    def test_no_sentence_tells_to_delete_a_file_of_the_map(self):
        entries, shared, apart = practices_map.read_map(ROOT)
        named = {path for entry in entries for path, _ in entry.files + entry.shared} | {
            path for path, _ in shared + apart
        }
        self.assertTrue(named)
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        for path in sorted(named):
            pattern = re.compile(r"\b(?:delete|remove)\b(?:(?!\. )[^\n])*?" + re.escape(path), re.IGNORECASE)
            for number, line in enumerate(lines, start=1):
                with self.subTest(path=path, line=number):
                    self.assertIsNone(
                        pattern.search(line), f"README.md:{number} tells to delete {path}, which the map names"
                    )


@unittest.skipUnless(is_source(ROOT, os.environ), "it reads the README of groundwork, which a project replaces")
class AdoptionPath(unittest.TestCase):
    """The path to adopt groundwork in an existing project, and the rule of the gaps, in the README of groundwork."""

    def test_the_path_lists_each_adr_of_the_map_once_after_the_adrs_it_needs(self):
        needs = practices_map.needs_of(practices_map.read_map(ROOT)[0])
        order = adoption_order()
        self.assertEqual(sorted(order), sorted(needs), "each ADR of the map appears once in the path")
        for position, number in enumerate(order):
            with self.subTest(adr=number):
                self.assertLessEqual(
                    needs[number], set(order[:position]), f"ADR {number:04d} comes before an ADR it needs"
                )

    def example(self):
        text = "\n".join(readme_section(GAPS_HEADING))
        found = re.search(r"```yaml\n(.+?)\n[ ]*```", text, flags=re.DOTALL)
        self.assertIsNotNone(found, "the rule of the gaps gives an example of configuration")
        return textwrap.dedent(found.group(1)) + "\n"

    def test_the_example_of_the_gaps_is_a_valid_configuration_of_the_checks(self):
        if not shutil.which("pre-commit"):
            self.skipTest("pre-commit is not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, ".pre-commit-config.yaml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.example())
            result = subprocess.run(["pre-commit", "validate-config", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_exclusion_of_the_example_names_one_file_and_not_the_same_name_elsewhere(self):
        patterns = re.findall(r"^\s+exclude: '(.+)'$", self.example(), flags=re.MULTILINE)
        self.assertTrue(patterns, "the example excludes a file")
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertRegex(pattern, r"^\^(?:[A-Za-z0-9_/-]|\\\.)+\$$", "anchored at both ends, the dots escaped")
                name = pattern[1:-1].replace("\\.", ".")
                self.assertIsNotNone(re.search(pattern, name))
                self.assertIsNone(re.search(pattern, "other/" + name))
                self.assertIsNone(re.search(pattern, name + "x"))


@unittest.skipUnless(
    is_source(ROOT, os.environ),
    "it describes the files of a source of ADRs, and a project has not all of them: set GROUNDWORK_SOURCE=true to run it in a community base",
)
class FilteredTrees(unittest.TestCase):
    """What groundwork gives to a project that keeps some of its ADRs, checked on the real files."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, practices_map.MAP), encoding="utf-8") as handle:
            entries, _, _ = practices_map.parse(handle.read().split("\n"))
        cls.needs = practices_map.needs_of(entries)
        cls.owners = practices_map.owners(entries)
        cls.numbers = sorted(entry.number for entry in entries)
        listing = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, check=True)
        cls.files = [
            path for path in listing.stdout.decode().split("\0") if path and os.path.isfile(os.path.join(ROOT, path))
        ]

    def dependents(self, number):
        found, grew = {number}, True
        while grew:
            grew = False
            for other, needs in self.needs.items():
                if other not in found and needs & found:
                    found.add(other)
                    grew = True
        return found

    def tree(self, left_out):
        """Return a project that keeps the ADRs but the ones left out: the files of groundwork that it takes."""
        listed = [number for number in self.numbers if number not in left_out]
        kept = choice.Kept([(number, number) for number in listed], self.needs)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = directory.name
        for path in self.files:
            if path in ("README.md", "LICENSE") or not choice.included(path, self.owners, kept, [practices_map.BASE]):
                continue
            with open(os.path.join(ROOT, path), "rb") as handle:
                data = handle.read()
            try:
                data = choice.content(path, data.decode("utf-8"), kept).encode("utf-8")
            except UnicodeDecodeError:
                pass
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as handle:
                handle.write(data)
        put(root, "README.md", README)
        put(root, "LICENSE", LICENSE)
        put(root, ".groundwork-version", "0.6.0\n")
        put(root, ".groundwork-adrs", "# The ADRs kept\n" + "".join(f"{number:04d}\n" for number in listed))
        track(root)
        return root

    def test_a_project_that_keeps_every_adr_passes_the_checks(self):
        self.assertEqual(check_all(self.tree(set())), [])

    def test_a_project_that_leaves_out_an_adr_with_the_adrs_that_need_it_passes_the_checks(self):
        for number in self.numbers:
            if number != 1:
                with self.subTest(left_out=sorted(self.dependents(number))):
                    self.assertEqual(check_all(self.tree(self.dependents(number))), [])

    def test_a_project_that_keeps_only_adr_0001_passes_the_checks(self):
        self.assertEqual(check_all(self.tree(set(self.numbers) - {1})), [])


class Community(unittest.TestCase):
    """A community base that reserves a range of its own, and the project that follows it."""

    def base(self, version=False, ranges="9000-9999\n"):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = directory.name
        put(root, "docs/adr/0001-first.md", ADR.format(n="0001"))
        put(root, "docs/adr/9000-of-the-community.md", ADR.format(n="9000"))
        put(root, ".groundwork/practices.md", MAP)
        put(root, "CONTRIBUTING.md", "Rules.\n")
        put(root, ".groundwork-ranges", "# The range of the community\n" + ranges)
        if version:
            put(root, ".groundwork-version", "0.6.0\n")
        track(root)
        return root

    def test_a_base_that_reserves_a_range_passes_the_checks(self):
        self.assertEqual(check_all(self.base()), [])

    def test_a_project_of_the_base_passes_the_checks(self):
        self.assertEqual(check_all(self.base(version=True)), [])

    def test_a_project_that_keeps_only_adr_0001_passes_the_checks_without_the_adrs_of_the_community(self):
        root = self.base(version=True)
        os.remove(os.path.join(root, "docs/adr/9000-of-the-community.md"))
        put(root, ".groundwork-adrs", "0001\n")
        track(root)
        self.assertEqual(check_all(root), [])

    def test_a_project_that_takes_the_range_of_the_community_whole_passes_the_checks(self):
        root = self.base(version=True)
        put(root, ".groundwork-adrs", "0001-0999\n9000-9999\n")
        self.assertEqual(check_all(root), [])

    def test_an_adr_of_the_project_in_the_range_of_the_community_has_no_entry_in_the_map(self):
        root = self.base(version=True)
        put(root, "docs/adr/9001-of-the-project.md", ADR.format(n="9001"))
        track(root)
        problems = check_all(root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("9001", problems[0])
        self.assertIn("no entry", problems[0])


if __name__ == "__main__":
    unittest.main()
