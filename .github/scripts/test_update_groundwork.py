import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import markers  # noqa: E402

SCRIPT = os.path.join(HERE, "update_groundwork.py")

V1 = {
    "README.md": "# groundwork\n",
    "LICENSE": "MIT\n",
    "CONTRIBUTING.md": "one\ntwo\nthree\n",
    "SECURITY.md": "security\n",
    "old.md": "old\n",
    "logo.bin": "a\0b",
}
V2 = {
    **V1,
    "README.md": "# groundwork 0.2\n",
    "LICENSE": "MIT 2026\n",
    "CONTRIBUTING.md": "one\ntwo changed\nthree\n",
    "new.md": "new\n",
    "logo.bin": "a\0c",
}
V3 = {name: content for name, content in V2.items() if name != "old.md"}
V3["SECURITY.md"] = "security 0.3\n"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def init(path):
    os.makedirs(path)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "config", "tag.gpgsign", "false")
    git(path, "config", "core.hooksPath", os.devnull)


def write(path, files):
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as handle:
            handle.write(content)


def read(path, name):
    with open(os.path.join(path, name)) as handle:
        return handle.read()


class Update(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.source = os.path.join(root, "groundwork")
        init(self.source)
        for version, files in (("0.1.0", V1), ("0.2.0", V2), ("0.3.0", V3)):
            for name in os.listdir(self.source):
                if name != ".git":
                    os.remove(os.path.join(self.source, name))
            write(self.source, files)
            git(self.source, "add", "-A")
            git(self.source, "commit", "-q", "-m", f"feat: release {version}")
            git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")
        self.project = os.path.join(root, "project")
        self.adopt("0.1.0", V1)

    def tearDown(self):
        self.directory.cleanup()

    def adopt(self, version, files):
        init(self.project)
        write(self.project, {**files, ".groundwork-version": f"{version}\n" if version else ""})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")

    def commit_project(self, files):
        write(self.project, files)
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "docs: adjust the project")

    def run_script(self, *args, issue="42"):
        return subprocess.run(
            [sys.executable, SCRIPT, *([issue] if issue else []), "--source", self.source, *args],
            cwd=self.project,
            capture_output=True,
            text=True,
        )

    def branches(self):
        return git(self.project, "branch", "--format=%(refname:short)").split()

    def test_updates_to_the_latest_version(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-3-0")
        self.assertEqual(read(self.project, "new.md"), "new\n")
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), V3["CONTRIBUTING.md"])
        self.assertEqual(read(self.project, "SECURITY.md"), V3["SECURITY.md"])
        self.assertEqual(read(self.project, ".groundwork-version"), "0.3.0\n")

    def test_removes_a_file_that_groundwork_removed(self):
        self.run_script()
        self.assertFalse(os.path.exists(os.path.join(self.project, "old.md")))

    def test_keeps_and_reports_a_file_removed_by_groundwork_that_the_project_changed(self):
        self.commit_project({"old.md": "old, adjusted\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("old.md", result.stdout)
        self.assertEqual(read(self.project, "old.md"), "old, adjusted\n")

    def test_keeps_and_reports_a_binary_file_changed_on_both_sides(self):
        self.commit_project({"logo.bin": "a\0d"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("logo.bin", result.stdout)
        self.assertEqual(read(self.project, "logo.bin"), "a\0d")

    def test_updates_to_a_given_version(self):
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, "SECURITY.md"), V1["SECURITY.md"])
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_leaves_out_the_files_of_groundwork_itself(self):
        self.run_script()
        self.assertEqual(read(self.project, "README.md"), V1["README.md"])
        self.assertEqual(read(self.project, "LICENSE"), V1["LICENSE"])

    def test_without_an_issue_the_branch_is_the_one_of_the_update_of_groundwork(self):
        result = self.run_script(issue=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        branch = git(self.project, "branch", "--show-current").strip()
        self.assertEqual(branch, "groundwork/update-to-v0-3-0")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.3.0\n")

    def test_does_not_commit_nor_leave_the_branch_of_the_project(self):
        head = git(self.project, "rev-parse", "main").strip()
        self.run_script()
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        self.assertTrue(git(self.project, "status", "--porcelain").strip())

    def test_the_branch_is_named_after_the_issue_and_the_version(self):
        self.run_script()
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-3-0")

    def test_keeps_the_changes_of_the_project_that_do_not_conflict(self):
        self.commit_project({"CONTRIBUTING.md": "zero\none\ntwo\nthree\n"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), "zero\none\ntwo changed\nthree\n")

    def test_reports_the_files_in_conflict(self):
        self.commit_project({"CONTRIBUTING.md": "one\ntwo mine\nthree\n"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("CONTRIBUTING.md", result.stdout)
        self.assertNotIn("new.md", result.stdout)
        self.assertIn("<<<<<<<", read(self.project, "CONTRIBUTING.md"))
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_accepts_a_project_already_ahead_of_its_recorded_version(self):
        self.commit_project({"new.md": "new\n", "CONTRIBUTING.md": V2["CONTRIBUTING.md"]})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_does_nothing_when_the_project_is_up_to_date(self):
        self.commit_project({".groundwork-version": "0.3.0\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_without_the_version_file(self):
        os.remove(os.path.join(self.project, ".groundwork-version"))
        git(self.project, "commit", "-q", "-am", "chore: remove the version file")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-version", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_with_a_malformed_version_file(self):
        for content in ("v0.1.0\n", "0.1\n", "0.1.0\n0.2.0\n", "\n"):
            with self.subTest(content=content):
                self.commit_project({".groundwork-version": content})
                result = self.run_script()
                self.assertEqual(result.returncode, 1)
                self.assertIn("X.Y.Z", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_fails_with_an_unknown_recorded_version(self):
        self.commit_project({".groundwork-version": "0.9.9\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("0.9.9", result.stderr)

    def test_fails_when_the_target_is_not_a_later_version(self):
        for target in ("0.1.0", "0.0.9"):
            with self.subTest(target=target):
                result = self.run_script("--to", target)
                self.assertEqual(result.returncode, 1)
                self.assertIn("later", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_fails_with_an_unknown_target(self):
        result = self.run_script("--to", "7.0.0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("7.0.0", result.stderr)

    def test_fails_when_the_working_tree_is_not_clean(self):
        write(self.project, {"SECURITY.md": "edited\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("clean", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_when_the_branch_already_exists(self):
        git(self.project, "branch", "chore/42-update-groundwork-to-v0-3-0")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("chore/42-update-groundwork-to-v0-3-0", result.stderr)

    def test_fails_with_an_issue_that_is_not_a_number(self):
        result = self.run_script(issue="abc")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.branches(), ["main"])


NAMES = {1: "first", 2: "second", 3: "third", 4: "fourth"}
NEEDS = {1: [], 2: [], 3: [2], 4: []}
BLOCKED = "<!-- groundwork:{n:04d} -->\nfirst {n}\nmiddle {n}\nlast {n} v{v}\n<!-- /groundwork -->\n"


def adr(number, name=None):
    return f"docs/adr/{number:04d}-{name or NAMES[number]}.md"


def practices(owned, apart):
    lines = ["# Practices", "", "## Practices", ""]
    for number in (2, 3, 4):
        files = "".join(f"  - `{path}`\n" for path in owned.get(number, [])) or "  - none\n"
        needs = ", ".join(f"ADR {need:04d}" for need in NEEDS[number]) or "none"
        lines += [f"### {number:04d}. [{NAMES[number].title()}](adr/{number:04d}-{NAMES[number]}.md)", "", f"- Needs: {needs}", "- Files:", files.rstrip("\n"), "- Shared lines:", "  - `SHARED.md`", ""]
    lines += ["## Shared files", "", "- `SHARED.md`", "", "## Not part of a practice", ""]
    lines += [f"- `{path}`" for path in apart]
    return "\n".join(lines) + "\n"


def world(v, tool=None, adr3="third"):
    """A tree of groundwork whose content carries the token v, with an ADR 0001 to 0004 and their files.

    `tool` is the ADR that owns `tool.py`, or None when it is part of no practice."""
    owned = {2: ["two.txt"], 3: ["three.txt"], 4: ["four.txt"]}
    if tool:
        owned[tool].append("tool.py")
    shared = "# Shared\n\nIntro.\n\n" + "\nBetween.\n\n".join(BLOCKED.format(n=n, v=v) for n in (2, 3, 4)) + "\nEnd.\n"
    files = {
        "two.txt": f"two {v}\n",
        "three.txt": f"three {v}\n",
        "four.txt": f"four {v}\n",
        "tool.py": "tool\n",
        "SHARED.md": shared,
        "docs/practices.md": practices(owned, [] if tool else ["tool.py"]),
    }
    for number in NAMES:
        files[adr(number, adr3 if number == 3 else None)] = f"# ADR {number:04d} v{v}\n"
    return files


def trimmed(files, kept):
    """What a project that keeps only the ADRs in kept holds of a tree: the files of the others are not there."""
    gone = {"two.txt": 2, "three.txt": 3, "four.txt": 4}
    gone.update({adr(number, "third" if number == 3 else None): number for number in NAMES})
    out = {path: text for path, text in files.items() if gone.get(path, 1) in kept}
    out["SHARED.md"] = markers.remove(files["SHARED.md"], "markdown", kept)
    return out


class Choice(unittest.TestCase):
    """The update applies the ADRs that the project chose (ADR 1000)."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.directory.name, "groundwork")
        self.project = os.path.join(self.directory.name, "project")
        init(self.source)

    def tearDown(self):
        self.directory.cleanup()

    def release(self, version, files):
        for name in os.listdir(self.source):
            if name != ".git":
                path = os.path.join(self.source, name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        self.put(self.source, files)
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "--allow-empty", "-m", f"feat: release {version}")
        git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")

    def put(self, root, files):
        for name, content in files.items():
            os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
            with open(os.path.join(root, name), "w") as handle:
                handle.write(content)

    def adopt(self, files, choice=None, version="0.1.0"):
        init(self.project)
        self.put(self.project, {**files, ".groundwork-version": f"{version}\n", **({".groundwork-adrs": choice} if choice is not None else {})})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")

    def run_script(self, *args):
        return subprocess.run([sys.executable, SCRIPT, "42", "--source", self.source, *args], cwd=self.project, capture_output=True, text=True)

    def branches(self):
        return git(self.project, "branch", "--format=%(refname:short)").split()

    def has(self, name):
        return os.path.exists(os.path.join(self.project, name))

    def releases(self, first, second):
        self.release("0.1.0", first)
        self.release("0.2.0", second)

    def test_an_adr_that_is_left_out_is_neither_copied_nor_in_conflict(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1, 2}), "0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "two.txt"), "two 2\n")
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(world("2")["SHARED.md"], "markdown", {1, 2}))
        for name in ("three.txt", "four.txt", adr(3), adr(4)):
            self.assertFalse(self.has(name), name)
        self.assertEqual(read(self.project, adr(2)), "# ADR 0002 v2\n")

    def test_adr_0001_is_never_left_out(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1, 4}), "0004\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, adr(1)), "# ADR 0001 v2\n")
        self.assertEqual(read(self.project, "four.txt"), "four 2\n")

    def test_an_adr_that_a_chosen_adr_needs_is_added_and_said(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("added: 0002\n", result.stdout)
        self.assertEqual(read(self.project, "two.txt"), "two 2\n")
        self.assertEqual(read(self.project, "three.txt"), "three 2\n")
        self.assertFalse(self.has("four.txt"))

    def test_the_lines_of_the_report_cannot_be_taken_for_a_conflict(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0003\n")
        result = self.run_script()
        self.assertNotRegex(result.stdout, r"(?m)^- ")
        self.assertRegex(result.stdout, r"(?m)^branch: chore/42-update-groundwork-to-v0-2-0$")
        self.assertRegex(result.stdout, r"(?m)^from: 0\.1\.0$")
        self.assertRegex(result.stdout, r"(?m)^to: 0\.2\.0$")

    def test_an_adr_that_the_project_lists_is_not_said_to_be_added(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0004\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("added:", result.stdout)

    def test_an_adr_that_enters_the_choice_is_applied_whole_with_its_blocks(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "0002\n0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(world("2")["SHARED.md"], "markdown", {1, 2, 3}))
        for name in ("two.txt", "three.txt", adr(2), adr(3)):
            self.assertTrue(self.has(name), name)

    def test_an_adr_that_enters_is_applied_even_if_its_files_did_not_change(self):
        first = world("1")
        self.releases(first, {**first, "docs/more.md": "more\n"})
        self.adopt(trimmed(first, {1}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "two.txt"), "two 1\n")
        self.assertEqual(read(self.project, adr(2)), "# ADR 0002 v1\n")
        self.assertEqual(read(self.project, "SHARED.md"), markers.remove(first["SHARED.md"], "markdown", {1, 2}))

    def test_an_adr_that_leaves_the_choice_is_no_longer_updated_and_its_files_stay(self):
        self.releases(world("1"), world("2"))
        self.adopt(world("1"), "0001\n0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "two.txt"), "two 2\n")
        self.assertEqual(read(self.project, "three.txt"), "three 1\n")
        self.assertEqual(read(self.project, "four.txt"), "four 1\n")
        self.assertEqual(read(self.project, adr(3)), "# ADR 0003 v1\n")
        shared = read(self.project, "SHARED.md")
        self.assertIn("last 2 v2", shared)
        self.assertIn("last 3 v1", shared)
        self.assertIn("last 4 v1", shared)

    def test_a_change_of_the_project_inside_a_block_that_is_kept_is_merged(self):
        self.releases(world("1"), world("2"))
        mine = world("1")["SHARED.md"].replace("first 2", "first 2, mine")
        self.adopt({**trimmed(world("1"), {1, 2}), "SHARED.md": markers.remove(mine, "markdown", {1, 2})}, "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        shared = read(self.project, "SHARED.md")
        self.assertIn("first 2, mine", shared)
        self.assertIn("last 2 v2", shared)

    def test_a_file_that_leaves_an_adr_for_the_files_of_no_practice_reaches_a_project_that_left_it_out(self):
        self.releases(world("1", tool=3), world("1", tool=None))
        left = {name: text for name, text in trimmed(world("1", tool=3), {1, 2}).items() if name != "tool.py"}
        self.adopt(left, "0002\n")
        self.assertFalse(self.has("tool.py"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "tool.py"), "tool\n")

    def test_an_adr_is_found_by_its_number_and_not_by_the_name_of_its_file(self):
        self.releases(world("1", adr3="before"), world("2", adr3="after"))
        self.adopt(trimmed(world("1", adr3="before"), {1, 2, 3}) | {adr(3, "before"): "# ADR 0003 v1\n"}, "0003\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "three.txt"), "three 2\n")
        self.assertFalse(self.has(adr(3, "before")))
        self.assertTrue(self.has(adr(3, "after")))
        self.assertNotIn("added:", result.stdout)

    def test_a_number_that_the_source_does_not_reserve_is_refused_before_anything_changes(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n1000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-adrs:2", result.stderr)
        self.assertIn("1000", result.stderr)
        self.assertEqual(self.branches(), ["main"])
        self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")

    def test_a_line_that_is_not_a_number_is_refused(self):
        self.releases(world("1"), world("2"))
        self.adopt(trimmed(world("1"), {1}), "second\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-adrs:1", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_the_adrs_that_the_source_does_not_reserve_are_not_copied(self):
        for choice in (None, "0001-0999\n"):
            with self.subTest(choice=choice):
                if os.path.exists(self.project):
                    shutil.rmtree(self.project)
                    shutil.rmtree(self.source)
                    init(self.source)
                self.releases(world("1"), {**world("2"), "docs/adr/1000-own.md": "# own\n"})
                self.adopt(world("1"), choice)
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.has("docs/adr/1000-own.md"))

    def fork(self, ranges="9000-9999\n"):
        second = {**world("2"), "docs/adr/9000-fork.md": "# fork\n"}
        if ranges is not None:
            second[".groundwork-ranges"] = ranges
        self.releases(world("1"), second)

    def test_the_ranges_are_read_in_the_version_the_project_moves_to(self):
        self.fork()
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n9000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, "docs/adr/9000-fork.md"), "# fork\n")
        self.assertEqual(read(self.project, ".groundwork-ranges"), "9000-9999\n")

    def test_a_number_of_a_range_that_the_new_version_does_not_reserve_is_refused(self):
        self.fork(ranges=None)
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n9000\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("9000", result.stderr)

    def test_a_range_of_the_source_is_taken_without_a_choice(self):
        self.fork()
        self.adopt(world("1"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has("docs/adr/9000-fork.md"))

    def test_a_declaration_of_ranges_that_is_refused_stops_the_update(self):
        self.fork(ranges="nine\n")
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-ranges:1", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_the_choice_and_the_version_of_a_source_are_not_copied(self):
        self.releases(world("1"), {**world("2"), ".groundwork-adrs": "0001\n", ".groundwork-version": "9.9.9\n"})
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(read(self.project, ".groundwork-adrs"), "0002\n")
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_a_version_without_a_map_is_refused_when_the_project_has_a_choice(self):
        self.releases(world("1"), {name: text for name, text in world("2").items() if name != "docs/practices.md"})
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/practices.md", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_a_version_without_a_map_is_still_applied_without_a_choice(self):
        self.releases(world("1"), {name: text for name, text in world("2").items() if name != "docs/practices.md"})
        self.adopt(world("1"))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_move_of_owner_is_not_looked_for_when_the_old_version_has_no_map(self):
        self.releases({name: text for name, text in world("1").items() if name != "docs/practices.md"}, world("2"))
        self.adopt(trimmed(world("1"), {1, 2}), "0002\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.has("docs/practices.md"))
        self.assertFalse(self.has("three.txt"))

    def test_without_a_choice_a_file_that_the_project_removed_is_in_conflict_as_before(self):
        self.releases(world("1"), world("2"))
        self.adopt({name: text for name, text in world("1").items() if name != "four.txt"})
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn("- four.txt", result.stdout)
        self.assertNotIn("added:", result.stdout)

    def test_without_a_choice_an_adr_file_that_the_project_removed_does_not_come_back(self):
        first = world("1")
        self.releases(first, {**first, "docs/more.md": "more\n"})
        self.adopt({name: text for name, text in first.items() if name not in ("four.txt", adr(4))})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.has("four.txt"))
        self.assertFalse(self.has(adr(4)))


def ledger(numbers):
    """A map of the practices that holds an entry for each number, in this order."""
    entries = "".join(
        f"### {n:04d}. [Decision {n}](adr/{n:04d}-decision.md)\n\n- Needs: none\n- Files:\n  - none\n- Shared lines:\n  - none\n\n"
        for n in numbers
    )
    footer = "## Shared files\n\n## Not part of a practice\n\n- `.github/scripts/update_groundwork.py`\n- `docs/practices.md`\n"
    return "# Practices of groundwork\n\n## Practices\n\n" + entries + footer


def tree(numbers, script, order=None):
    files = {"docs/practices.md": ledger(order or numbers), ".github/scripts/update_groundwork.py": script}
    files.update({f"docs/adr/{n:04d}-decision.md": f"# {n}\n" for n in numbers})
    return files


class Chain(unittest.TestCase):
    """A change of groundwork reaches a project through a community base, with a pull request on each (the guide of the bases)."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.groundwork, self.base, self.project = (os.path.join(root, name) for name in ("groundwork", "base", "project"))
        with open(SCRIPT) as handle:
            self.script = handle.read()
        self.assertIn('SOURCE = "https://github.com/michelwils/groundwork.git"\n', self.script)
        self.later = self.script.replace('"""Prepare the update', '"""Prepares the update', 1)
        self.assertNotEqual(self.later, self.script)
        init(self.groundwork)
        self.release(self.groundwork, "v0.1.0", tree([1, 13], self.script))
        self.release(self.groundwork, "v0.2.0", tree([1, 13, 14], self.later))

    def tearDown(self):
        self.directory.cleanup()

    def put(self, root, files):
        for name, content in files.items():
            os.makedirs(os.path.dirname(os.path.join(root, name)) or root, exist_ok=True)
            with open(os.path.join(root, name), "w") as handle:
                handle.write(content)

    def release(self, repo, tag, files):
        for name in os.listdir(repo):
            if name != ".git":
                path = os.path.join(repo, name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        self.put(repo, files)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", f"feat: release {tag}")
        git(repo, "tag", "-a", tag, "-m", tag)

    def found_base(self, order):
        """The base: groundwork 0.1.0 with a range of its own, an ADR in it and its entry, released as v0.9.0."""
        init(self.base)
        self.put(self.base, {**tree([1, 13], self.script, order=[n for n in order if n != 9000]), ".groundwork-version": "0.1.0\n"})
        git(self.base, "add", "-A")
        git(self.base, "commit", "-q", "-m", "Initial commit")
        self.put(self.base, {**tree([1, 13, 9000], self.script, order=order), ".groundwork-ranges": "9000-9999\n"})
        git(self.base, "add", "-A")
        git(self.base, "commit", "-q", "-m", "feat: reserve a range")
        git(self.base, "tag", "-a", "v0.9.0", "-m", "v0.9.0")

    def update(self, repo, source):
        return subprocess.run([sys.executable, SCRIPT, "--source", source], cwd=repo, capture_output=True, text=True)

    def test_an_entry_of_the_base_before_those_of_groundwork_does_not_conflict_with_a_new_entry_of_groundwork(self):
        self.found_base([9000, 1, 13])
        result = self.update(self.base, self.groundwork)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("### 0014.", read(self.base, "docs/practices.md"))
        self.assertIn("### 9000.", read(self.base, "docs/practices.md"))

    def test_an_entry_of_the_base_after_those_of_groundwork_conflicts_with_a_new_entry_of_groundwork(self):
        self.found_base([1, 13, 9000])
        result = self.update(self.base, self.groundwork)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("- docs/practices.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
