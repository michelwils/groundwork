#!/usr/bin/env python3
"""Check the relative links and the anchors of the Markdown files (ADR 0008).

Every inline link, image and reference definition that points to a file of the repository must
find that file, and its `#anchor` must be a heading, or an `id` or `name` of an HTML element, of
the target Markdown file. Anchors follow the rules of GitHub: the heading in lowercase, without
punctuation, with hyphens for spaces, and `-1`, `-2` for a heading that repeats. External links
(`http:`, `mailto:`, `//…`) are not checked, nor are links in code, in HTML comments or in the
files of EXCLUDED. The check does not use the network.

In a project that keeps some of the ADRs, a link of the map of the practices, `docs/practices.md`, to a
file that the project left out is not reported, since the map describes groundwork and not the project.
A link to such a file in any other file is.

The files are read with markdown-it-py, a parser of CommonMark, which requirements.txt pins.

Usage: check_links.py [DIR]
"""

import os
import re
import subprocess
import sys
from urllib.parse import unquote

from markdown_it import MarkdownIt

import choice
import practices_map

# Files whose links are placeholders to be filled in.
EXCLUDED = ("docs/adr/template.md",)

# The links and images, as the parser reads them. Without the rule of the reference definitions,
# a link written as [text][label] is not resolved: the definitions are read by a second parser,
# so that a definition is checked once, where it is written.
LINKS = MarkdownIt("commonmark").enable(["table", "strikethrough"]).disable("reference")
DEFINITIONS = MarkdownIt("commonmark").enable(["table", "strikethrough"])

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
EXPLICIT = re.compile(r"<[a-z][a-z0-9]*\s[^>]*?\b(?:name|id)=[\"']([^\"']+)[\"']", re.IGNORECASE)
EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//)")
LINE_ANCHOR = re.compile(r"^L\d+(?:C\d+)?(?:-L\d+(?:C\d+)?)?$")


def slug(heading):
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def ids(html):
    return EXPLICIT.findall(HTML_COMMENT.sub("", html))


def anchors(text):
    """Return the anchors of a Markdown text: its headings, and the ids and names of its HTML."""
    found, counts = set(), {}
    tokens = LINKS.parse(text)
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            children = tokens[index + 1].children or []
            name = slug("".join(c.content for c in children if c.type in ("text", "code_inline", "image")))
            number = counts.get(name, 0)
            counts[name] = number + 1
            found.add(name if number == 0 else f"{name}-{number}")
        elif token.type == "html_block":
            found.update(ids(token.content))
        for child in token.children or []:
            if child.type == "html_inline":
                found.update(ids(child.content))
    return found


def line_of(lines, first, last, target):
    """Return the line, from 1, of a link in the lines [first, last) of its block: the first that has its target."""
    wanted = unquote(target.split("#")[0].split("?")[0]) or unquote(target)
    for number in range(first, last):
        if wanted and wanted in unquote(lines[number]):
            return number + 1
    return first + 1


def links(text):
    """Return the (line, target) of the links, images and reference definitions of a Markdown text."""
    lines, found = text.split("\n"), []
    for token in LINKS.parse(text):
        if token.type != "inline":
            continue
        first, last = token.map
        for child in token.children:
            if child.type in ("link_open", "image"):
                target = child.attrGet("href" if child.type == "link_open" else "src")
                found.append((line_of(lines, first, last, target), target))
    env = {}
    DEFINITIONS.parse(text, env)
    for definition in env.get("references", {}).values():
        found.append((definition["map"][0] + 1, definition["href"]))
    return sorted(found)


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


def left_out(root):
    """Return a function that tells whether a file of groundwork is left out by the choice of the project, or None."""
    reserved = practices_map.read_ranges(root)[0]
    adopted = choice.read(root, reserved)[0]
    path = os.path.join(root, practices_map.MAP)
    if adopted is None or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        entries = practices_map.parse(handle.read().split("\n"))[0]
    kept = choice.Kept(adopted, practices_map.needs_of(entries))
    owners = practices_map.owners(entries)
    return lambda file: not choice.included(file, owners, kept, reserved)


def check(root):
    """Return the broken links of the Markdown files under the root, as 'file:line: message'."""
    root = os.path.abspath(root)
    texts, known = {}, {}

    def text_of(path):
        if path not in texts:
            with open(path, encoding="utf-8-sig", errors="replace") as handle:
                texts[path] = handle.read()
        return texts[path]

    def anchors_of(path):
        if path not in known:
            known[path] = anchors(text_of(path))
        return known[path]

    problems, exempt = [], left_out(root)
    for source in markdown_files(root):
        relative = os.path.relpath(source, root).replace(os.sep, "/")
        if relative in EXCLUDED or not os.path.isfile(source):
            continue
        for line, target in links(text_of(source)):
            problem = broken(root, source, target, anchors_of, exempt if relative == practices_map.MAP else None)
            if problem:
                problems.append(f"{relative}:{line}: {problem}")
    return problems


def broken(root, source, target, anchors_of, exempt=None):
    """Return why the link does not resolve, or None. A link to a file that `exempt` accepts is not broken."""
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
    if exempt and exempt(os.path.relpath(destination, root).replace(os.sep, "/")):
        return None
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
