import ast
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "README.md")
CODE = re.compile(r"`([^`]+)`")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SCRIPT = re.compile(r"^[a-z_]+\.py$")
TABLES_OF_THE_CODE = ("How an update runs", "How a choice is applied", "The data")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def scripts():
    """Return the scripts of the folder that have a test module next to them, which those of groundwork all have. A
    project that left a practice out has fewer of them, and one that adds a helper script of its own, without a test
    module of that name, does not make the page false."""
    return sorted(
        name
        for name in os.listdir(HERE)
        if name.endswith(".py") and not name.startswith("test_") and os.path.isfile(os.path.join(HERE, f"test_{name}"))
    )


def section(heading):
    """Return the text of a section of the page, from its heading to the next heading of the same level."""
    found = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", read(PAGE), flags=re.MULTILINE | re.DOTALL)
    assert found, f"the page has no section '{heading}'"
    return found.group(1)


def rows(text):
    """Return the cells of each row of the tables of a text, without the header and its separator."""
    cells = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.startswith("|")
    ]
    return [row for row in cells[2:] if row] if len(cells) > 2 else []


def names_defined(script):
    """Return the names of the functions and classes of a script, at any depth."""
    tree = ast.parse(read(os.path.join(HERE, script)))
    return {
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def names_of_the_code():
    """Return the names that the scripts define or use: functions, classes, parameters, variables and attributes."""
    found = set()
    for script in scripts():
        for node in ast.walk(ast.parse(read(os.path.join(HERE, script)))):
            if isinstance(node, ast.Name):
                found.add(node.id)
            elif isinstance(node, ast.arg):
                found.add(node.arg)
            elif isinstance(node, ast.Attribute):
                found.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                found.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found.add(node.name)
    return found


def modules_imported(script):
    """Return the scripts of the folder that a script imports."""
    found = set()
    for node in ast.walk(ast.parse(read(os.path.join(HERE, script)))):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found & {name[:-3] for name in scripts()}


class ReadmeOfTheScripts(unittest.TestCase):
    """The page that says how the scripts work stays true to the code, and stays usable in a project."""

    def test_every_script_is_named_in_the_table_of_who_runs_what(self):
        named = {code for row in rows(section("Who runs what")) for code in CODE.findall(row[0])}
        for script in scripts():
            with self.subTest(script=script):
                self.assertIn(script, named)

    def test_the_tables_of_the_code_name_only_functions_and_classes_that_exist(self):
        """The last cell of a row is the script, and the code in the other cells is a name that the script defines.
        A script that a project left out is not read."""
        for heading in TABLES_OF_THE_CODE:
            checked = 0
            for row in rows(section(heading)):
                script = CODE.findall(row[-1])
                self.assertTrue(
                    script and SCRIPT.match(script[0]), f"{heading}: the last cell of {row} is not a script"
                )
                if script[0] not in scripts():
                    continue
                defined = names_defined(script[0])
                for cell in row[:-1]:
                    for name in (code for code in CODE.findall(cell) if IDENTIFIER.match(code)):
                        with self.subTest(section=heading, script=script[0], name=name):
                            self.assertIn(name, defined)
                        checked += 1
            self.assertGreater(checked, 0, f"{heading}: no name was checked")

    def test_the_imports_of_the_table_are_the_imports_of_the_scripts(self):
        """The second cell of a row names the scripts that the script of the first cell imports. A script that a
        project left out is not named by what the project has."""
        checked = 0
        for row in rows(section("How the modules fit together")):
            script = CODE.findall(row[0])[0]
            if script not in scripts():
                continue
            named = {name for name in CODE.findall(row[1]) if f"{name}.py" in scripts()}
            with self.subTest(script=script):
                self.assertEqual(named, modules_imported(script))
            checked += 1
        self.assertGreater(checked, 0)

    def test_every_script_has_a_row_in_the_table_of_the_imports(self):
        named = {code for row in rows(section("How the modules fit together")) for code in CODE.findall(row[0])}
        for script in scripts():
            with self.subTest(script=script):
                self.assertIn(script, named)

    def test_every_word_of_the_glossary_is_a_name_of_the_code(self):
        """A word that appears only in a comment or a docstring is not a name that the code uses."""
        names = names_of_the_code()
        words = [word for row in rows(section("Glossary")) for word in CODE.findall(row[0])]
        self.assertGreater(len(words), 0)
        for word in words:
            with self.subTest(word=word):
                self.assertIn(word, names)

    def test_the_page_has_no_link(self):
        """It is copied into every project, whose files and ADRs are not those of groundwork, and the check of the
        links reports a link to a file that is absent."""
        link = r"\]\(|\]\[|^\[[^\]]+\]:|<a[\s>]|href=|<[^<>\s]*\.md[^<>\s]*>|<https?:"
        self.assertNotRegex(read(PAGE), re.compile(link, flags=re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
