#!/usr/bin/env python3
"""Check the relative links and the anchors of the Markdown files (ADR 0008).

Every inline link, image and reference definition that points to a file of the repository must
find that file, and its `#anchor` must be a heading, or an `id` or `name` of an HTML element, of the target
Markdown file, written with `#` or underlined. Anchors follow the rules of GitHub: the heading
in lowercase, without punctuation, with hyphens for spaces, and `-1`, `-2` for a heading that
repeats. External links (`http:`,
`mailto:`, `//…`) are not checked, nor are links in code, in HTML comments or in the files of EXCLUDED.
The check does not use the network.

Usage: check_links.py [DIR]
"""

import os
import re
import subprocess
import sys
from urllib.parse import unquote

# Files whose links are placeholders to be filled in.
EXCLUDED = ("docs/adr/template.md",)

FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
CODE_SPAN = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
INLINE = re.compile(r"\]\(\s*(<[^<>\n]*>|[^()\s]*(?:\([^()\s]*\)[^()\s]*)*)")
REFERENCE = re.compile(r"^ {0,3}\[(?!\^)[^\]\n]+\]:[ \t]*(<[^<>\n]*>|\S+)", re.MULTILINE)
# A heading is written with `#`, or underlined: a line of text, then a line of = or - signs.
HEADING = re.compile(
    r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*$"
    r"|^ {0,3}([^\s#>\-*+=`~|][^\n]*)\n {0,3}(?:=+|-+)[ \t]*$",
    re.MULTILINE,
)
EXPLICIT = re.compile(r"<[a-z][a-z0-9]*\s[^>]*?\b(?:name|id)=[\"']([^\"']+)[\"']", re.IGNORECASE)
EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//)")
LINE_ANCHOR = re.compile(r"^L\d+(?:C\d+)?(?:-L\d+(?:C\d+)?)?$")


def blank(match):
    return re.sub(r"[^\n]", " ", match.group(0))


def without_blocks(text):
    """Return the text with the content of the code blocks emptied and the comments blanked, line for line."""
    lines, fence = [], None
    for line in text.split("\n"):
        opening = FENCE.match(line)
        if fence:
            if line.strip() and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence):
                fence = None
            lines.append("")
        elif opening:
            fence = opening.group(1)
            lines.append("")
        else:
            lines.append(line)
    return COMMENT.sub(blank, "\n".join(lines))


def slug(heading):
    heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    heading = re.sub(r"<[^>]*>", "", heading)
    heading = re.sub(r"[ \t]+#+$", "", heading).lower()
    return re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")


def anchors(text):
    found, counts = set(EXPLICIT.findall(text)), {}
    for match in HEADING.finditer(text):
        name = slug((match.group(1) or match.group(2)).strip())
        number = counts.get(name, 0)
        counts[name] = number + 1
        found.add(name if number == 0 else f"{name}-{number}")
    return found


def markdown_files(root):
    if os.path.isdir(os.path.join(root, ".git")):
        listed = subprocess.run(["git", "-C", root, "ls-files", "-z", "--", "*.md"], capture_output=True, text=True)
        if listed.returncode == 0:
            return sorted(os.path.join(root, name) for name in listed.stdout.split("\0") if name)
    found = []
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name != ".git"]
        found += [os.path.join(directory, name) for name in names if name.endswith(".md")]
    return sorted(found)


def check(root):
    """Return the broken links of the Markdown files under the root, as 'file:line: message'."""
    root = os.path.abspath(root)
    texts, known = {}, {}

    def text_of(path):
        if path not in texts:
            with open(path, encoding="utf-8-sig", errors="replace") as handle:
                texts[path] = without_blocks(handle.read())
        return texts[path]

    def anchors_of(path):
        if path not in known:
            known[path] = anchors(text_of(path))
        return known[path]

    problems = []
    for source in markdown_files(root):
        relative = os.path.relpath(source, root).replace(os.sep, "/")
        if relative in EXCLUDED or not os.path.isfile(source):
            continue
        text = CODE_SPAN.sub(blank, text_of(source))
        targets = [(m.start(1), m.group(1)) for pattern in (INLINE, REFERENCE) for m in pattern.finditer(text)]
        for start, target in sorted(targets):
            line = text.count("\n", 0, start) + 1
            problem = broken(root, source, target.strip("<>"), anchors_of)
            if problem:
                problems.append(f"{relative}:{line}: {problem}")
    return problems


def broken(root, source, target, anchors_of):
    """Return why the link does not resolve, or None."""
    if not target or EXTERNAL.match(target):
        return None
    path, _, fragment = target.partition("#")
    path, fragment = unquote(path.partition("?")[0]), unquote(fragment)
    if not path:
        destination = source
    elif path.startswith("/"):
        destination = os.path.normpath(os.path.join(root, path.lstrip("/")))
    else:
        destination = os.path.normpath(os.path.join(os.path.dirname(source), path))
    if os.path.commonpath([root, destination]) != root:
        return f"'{target}' leaves the repository"
    if not os.path.exists(destination):
        return f"'{target}' points to a file that does not exist"
    if fragment and not LINE_ANCHOR.match(fragment) and os.path.isfile(destination) and destination.endswith(".md"):
        if fragment not in anchors_of(destination):
            return f"'{target}' points to an anchor that does not exist"
    return None


def main():
    problems = check(sys.argv[1] if len(sys.argv) > 1 else ".")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
