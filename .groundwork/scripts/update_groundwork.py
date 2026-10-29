#!/usr/bin/env python3
"""Prepare the update of a project to a later version of groundwork.

The version of groundwork the project is based on is in `.groundwork-version`, at the root of
the project: one line `X.Y.Z`, or `X.Y.Z+<commit>` for a project that was moved to a commit that no
release has yet (`--to head`, below). The source of the updates is `--source`, or else the address in
`.groundwork-source` (one line `https://…`), or else groundwork. The script fetches the tags of the
source under `groundwork/`, after it has deleted the ones an earlier source left there,
creates the branch `chore/<issue>-update-groundwork-to-v<X-Y-Z>`, or
`groundwork/update-to-v<X-Y-Z>` when no issue is given, and applies on it what changed
between the two versions, file by file, keeping the changes of the project. It leaves the result
in the working tree: it does not commit, push or open a pull request.

Files that concern groundwork itself, or that belong to the project, are left out, see EXCLUDED.
A version whose files include a path that a file system can put in a directory .git, such as a hook,
or a path that holds a control character or a line break, which would add a line to the text it prints,
or a bidirectional control, such as U+202E, which changes how the name is shown,
stops the update before anything changes (paths_of).

The project may list the ADRs it keeps in `.groundwork-adrs` (choice.py). The script then reads,
in the version it moves to, the ranges of ADR numbers that the source reserves and the map of the
practices (practices_map.py), and applies only what the choice keeps: the files of the other ADRs
are neither copied nor deleted, and the blocks of their lines are taken out of both versions of the
files that several ADRs share (markers.py) before the merge. What enters the choice starts from
nothing, so that its files are not taken for deletions: an ADR kept whose file the project lacks, a
file that no ADR left out owns any more, an ADR of a range that the source reserves from now on.
Everything is read before the branch is created, so a choice that is refused changes nothing.

Exit status: 0 when the project is updated or up to date, 1 on an error, 2 when the arguments are wrong, 3 when some files are
in conflict. A conflict leaves markers in the file, and the script names the files. After the
lines `branch:`, `from:` and `to:`, the line `source:` names the source that was used, the line `added: 0002, 0003` names the ADRs that enter the
choice and that the project does not list, and the lines `- path` name the files in conflict. This text is for a person.

With `--result PATH`, the script also writes its result to PATH as one JSON object, once the branch is prepared,
for open_update_pull_request.py to read (ADR 1003): `branch`, `from`, `to` and `source` as strings, `added` as a list
of ADR numbers and `conflicts` as a list of paths. It writes none when the project is up to date. It checks that it can write
the file before it creates the branch, and stops there, with no branch, when it cannot.

With `--to head`, the script moves the project to the head of the source, that is its default branch, to try a change
before its release. It is never the default, and open_update_pull_request.py never uses it (ADR 1004). The script
records `X.Y.Z+<commit>`, where X.Y.Z is the latest release in the history of the commit, or `X.Y.Z` alone when the
head is that release. The next update merges from that commit: it goes to a release that has the commit, and says that
the project is up to date while no release has it.

Usage: update_groundwork.py [ISSUE] [--to X.Y.Z|head] [--source URL] [--result PATH]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choice  # noqa: E402
import markers  # noqa: E402
import practices_map  # noqa: E402

SOURCE = "https://github.com/michelwils/groundwork.git"
CONFLICTS = (
    3  # the status of a run that finished and leaves files to resolve; 2 is a wrong use of the script (argparse)
)
VERSION_FILE = ".groundwork-version"
SOURCE_FILE = ".groundwork-source"
EXCLUDED = ("README.md", "LICENSE", VERSION_FILE, choice.CHOICE_FILE, SOURCE_FILE)
ADDRESS = re.compile(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?(?:/[A-Za-z0-9._~%/-]*)?")
ADDRESS_LENGTH = 2048
PREFIX = "groundwork/"
RELEASE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
COMMIT = r"[0-9a-f]{40}|[0-9a-f]{64}"
VERSION = re.compile(rf"^[0-9]+\.[0-9]+\.[0-9]+(?:\+(?:{COMMIT}))?$")
HEAD = "head"
HEAD_REF = f"refs/tags/{PREFIX}{HEAD}"
# The controls of the direction of the text, which change how a name is shown: embeddings, overrides and isolates.
BIDIRECTIONAL_CONTROLS = frozenset(chr(code) for code in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
# The characters that HFS+ ignores in a name, as git does for .git (core.protectHFS).
HFS_IGNORED = dict.fromkeys([0x200C, 0x200D, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x206A, 0x2070), 0xFEFF])


class Failure(Exception):
    pass


def git(*args, check=True, text=True, input=None):
    result = subprocess.run(["git", *args], capture_output=True, text=text, input=input)
    if check and result.returncode != 0:
        message = result.stderr if text else result.stderr.decode(errors="replace")
        raise Failure(f"git {' '.join(args)} failed: {message.strip()}")
    return result


def as_tuple(version):
    return tuple(int(part) for part in version.partition("+")[0].split("."))


def commit_of(version):
    """Return the commit that the version names, or None for a release."""
    return version.partition("+")[2] or None


def revision(version):
    """Return the revision of git that holds the files of the version: the commit it names, else the tag of the release."""
    return commit_of(version) or f"refs/tags/{PREFIX}v{version}"


def label(version):
    """Return the text that names the version in a branch."""
    return commit_of(version)[:12] if commit_of(version) else f"v{version.replace('.', '-')}"


def recorded_version():
    try:
        with open(VERSION_FILE) as handle:
            content = handle.read()
    except FileNotFoundError:
        raise Failure(f"{VERSION_FILE} is missing: create it with the version of groundwork the project is based on.")
    version = content.strip()
    if content != version + "\n" or not VERSION.match(version):
        raise Failure(
            f"{VERSION_FILE} must hold one line of the form X.Y.Z, without 'v', or X.Y.Z+ and the 40 or 64 lowercase hexadecimal characters of a commit."
        )
    return version


def recorded_source():
    """Return the address in `.groundwork-source`, or None when the project has no such file."""
    try:
        with open(SOURCE_FILE, "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise Failure(f"{SOURCE_FILE} cannot be read: {error.strerror}.")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Failure(f"{SOURCE_FILE} must be text in UTF-8.")
    address = content[:-1] if content.endswith("\n") else None
    if address is None or not is_address(address):
        raise Failure(
            f"{SOURCE_FILE} must hold one line with the address of the source, of the form https://host/path, "
            "with no user, password, space, query or fragment."
        )
    return address


def is_address(address):
    """Tell whether the text is an address of a source that a project may record."""
    return len(address) <= ADDRESS_LENGTH and ADDRESS.fullmatch(address) is not None


def source_of(explicit):
    """Return the source of the updates: the one given, else the one the project recorded, else groundwork."""
    return explicit or recorded_source() or SOURCE


def forget_tags():
    """Delete the tags of the source that an earlier run copied, so that only the versions of the source in use are known."""
    refs = git("for-each-ref", "--format=%(refname)", f"refs/tags/{PREFIX}").stdout.split()
    if refs:
        git("update-ref", "--stdin", input="".join(f"delete {ref}\n" for ref in refs))


def fetch_releases(source):
    """Copy the tags of the source under `groundwork/` and return its versions, the oldest first."""
    forget_tags()
    git("fetch", "--quiet", "--no-tags", "--", source, f"+refs/tags/v*:refs/tags/{PREFIX}v*")
    return released_versions()


def released_versions(merged=None):
    """Return the releases that the tags hold, the oldest first, or those in the history of the commit `merged`."""
    tags = git("tag", *(["--merged", merged] if merged else []), "--list", f"{PREFIX}v[0-9]*").stdout.split()
    return sorted((tag[len(PREFIX) + 1 :] for tag in tags if RELEASE.match(tag[len(PREFIX) + 1 :])), key=as_tuple)


def fetch_head(source):
    """Copy the head of the source, which is its default branch, under `groundwork/head` and return its commit."""
    git("fetch", "--quiet", "--no-tags", "--", source, f"+HEAD:{HEAD_REF}")
    return git("rev-parse", "--verify", f"{HEAD_REF}^{{commit}}").stdout.strip()


def fetch_base(source, old, head=False):
    """Fetch what the update reads from the source: its tags, and its head when the project is on a commit or asks for
    the head. Return the versions and whether the recorded version is known to the source: a release it published, or
    a commit that it has."""
    versions = fetch_releases(source)
    if head:
        fetch_head(source)
    if not commit_of(old):
        return versions, old in versions
    if not reached(commit_of(old)) and not head:
        fetch_head(source)
    return versions, reached(commit_of(old))


def reached(commit):
    """Tell whether a tag of the source that was just fetched, a release or its head, has the commit in its history. The
    objects of an earlier source stay in the repository, so that having the commit does not say that this source has it."""
    result = git("tag", "--contains", commit, "--list", f"{PREFIX}*", check=False)
    return result.returncode == 0 and bool(result.stdout.split())


def unknown_message(old, source):
    """Return the sentence for a recorded version that the source does not have."""
    if commit_of(old):
        return f"The recorded commit {commit_of(old)} is not in {source}."
    return f"The recorded version {old} is not a release of groundwork at {source}."


def is_ancestor(ancestor, descendant):
    result = git("merge-base", "--is-ancestor", ancestor, descendant, check=False)
    if result.returncode > 1:
        raise Failure(f"git merge-base failed: {result.stderr.strip()}")
    return result.returncode == 0


def version_of_head(commit):
    """Return the version to record for the commit: its latest release, with the commit unless the release is that commit."""
    releases = released_versions(commit)
    if not releases:
        raise Failure("No release of the source is in the history of its head: the head cannot be recorded.")
    release_commit = git("rev-parse", f"refs/tags/{PREFIX}v{releases[-1]}^{{commit}}").stdout.strip()
    return releases[-1] if release_commit == commit else f"{releases[-1]}+{commit}"


def blob(version, path):
    """Return the content of the path in the version, or None when it does not exist there."""
    result = git("cat-file", "blob", f"{revision(version)}:{path}", check=False, text=False)
    return result.stdout if result.returncode == 0 else None


def mode(version, path):
    line = git("ls-tree", revision(version), "--", path).stdout.split()
    return int(line[0], 8) if line else 0o100644


def in_git_directory(path):
    """Tell whether a file system can put the path in a directory .git: a name of the path that is .git in any case,
    on HFS+ once the characters it ignores are taken out, on NTFS with dots or spaces at the end, a stream after a colon,
    the short name git~1, or a backslash for a separator."""
    names = re.split(r"[/\\]", path.translate(HFS_IGNORED))
    return any(name.split(":", 1)[0].rstrip(". ").lower() in (".git", "git~1") for name in names)


def inside(root, path):
    """Tell whether the path stays in the repository once it is resolved, links included, and out of a directory .git."""
    if os.path.isabs(path) or ".." in path.split("/") or not path or in_git_directory(path):
        return False
    real = os.path.realpath(os.path.join(root, path))
    return real == root or (real.startswith(root + os.sep) and not in_git_directory(os.path.relpath(real, root)))


def paths_of(raw):
    """Return the paths of the output of git, without EXCLUDED. Stop at one that holds a control character or a line
    break, which would add a line to the text it prints, at one that holds a
    bidirectional control, which changes how the name is shown, and at one that would land in a directory .git: the
    source would then write the hooks or the configuration of the project. The callers read the output as bytes, so that Python
    translates no line break."""
    paths = [path for path in raw.split("\0") if path]
    for path in paths:
        if any(unicodedata.category(character) in ("Cc", "Zl", "Zp") for character in path):
            raise Failure(
                f"The source holds {path!r}, whose name holds a control character or a line break: nothing is changed."
            )
        if any(character in BIDIRECTIONAL_CONTROLS for character in path):
            raise Failure(
                f"The source holds {path!r}, whose name holds a bidirectional control, which changes how it is shown: nothing is changed."
            )
        if in_git_directory(path):
            raise Failure(f"The source holds {path}, which would land in a directory .git: nothing is changed.")
    return [path for path in paths if path not in EXCLUDED]


def tree_paths(version):
    return paths_of(git("ls-tree", "-r", "--name-only", "-z", revision(version), text=False).stdout.decode())


def changed_paths(old, new):
    raw = git("diff", "--no-renames", "--name-only", "-z", revision(old), revision(new), text=False).stdout
    return paths_of(raw.decode())


def read(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def write(path, content, file_mode):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)
    os.chmod(path, 0o755 if file_mode & 0o111 else 0o644)


def remove(path):
    os.remove(path)
    try:
        os.removedirs(os.path.dirname(path) or ".")
    except OSError:
        pass


def merge(ours, base, theirs):
    """Return (content, conflict) of the three-way merge of three versions of a text file."""
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for name, content in (("ours", ours), ("base", base or b""), ("theirs", theirs)):
            paths.append(os.path.join(directory, name))
            with open(paths[-1], "wb") as handle:
                handle.write(content)
        result = subprocess.run(
            ["git", "merge-file", "-p", "-L", "project", "-L", "previous groundwork", "-L", "new groundwork", *paths],
            capture_output=True,
        )
    if result.returncode < 0 or result.returncode > 127:
        raise Failure("git merge-file failed: " + result.stderr.decode(errors="replace").strip())
    return result.stdout, result.returncode > 0


def check_result_path(path):
    """Stop, before any branch, when the result cannot be written. It creates and truncates nothing, so a run that fails
    later leaves no file behind, as ADR 1003 says."""
    if os.path.isdir(path):
        raise Failure(f"{path} is a folder, not a file for the result. No branch is created.")
    try:
        tempfile.TemporaryFile(dir=os.path.dirname(path) or ".").close()
    except OSError as error:
        raise Failure(f"{path} cannot be written ({error.strerror}). No branch is created.")


def decide(base, theirs, ours):
    """Tell what applying the change from the base to theirs does to a file that holds ours.

    Return ("none",), ("write", content), ("remove",), ("conflict",) when nothing can be merged, or
    ("merged", content, conflict)."""
    if theirs == ours:
        return ("none",)
    if ours == base:
        return ("remove",) if theirs is None else ("write", theirs)
    if ours is None or theirs is None:
        return ("conflict",)
    if any(b"\0" in content for content in (ours, theirs, base or b"")):
        return ("conflict",)
    merged, conflict = merge(ours, base, theirs)
    return ("merged", merged, conflict)


def apply_path(path, base, theirs, ours, file_mode):
    """Apply what changed in the path from the base to theirs. Return True when it is in conflict."""
    action = decide(base, theirs, ours)
    if action[0] == "remove":
        remove(path)
    elif action[0] in ("write", "merged"):
        write(path, action[1], file_mode)
    return action[0] == "conflict" or (action[0] == "merged" and action[2])


class Without:
    """The ADRs of a choice, except those that enter it."""

    def __init__(self, kept, entering):
        self.kept, self.entering = kept, entering

    def __contains__(self, number):
        return number in self.kept and number not in self.entering


class Side:
    """What a version of groundwork says about the ADRs: the ranges it reserves and the map of the practices."""

    def __init__(self, version=None, root=None):
        """Read a version of groundwork, or the tree at the root."""
        if root is None:
            with tempfile.TemporaryDirectory() as directory:
                for path in (practices_map.MAP, practices_map.RANGES_FILE):
                    content = blob(version, path)
                    if content is not None:
                        write(os.path.join(directory, path), content, 0o644)
                self.read(directory)
        else:
            self.read(root)

    def read(self, root):
        self.has_map = os.path.isfile(os.path.join(root, practices_map.MAP))
        self.reserved, self.problems = practices_map.read_ranges(root)
        entries = practices_map.read_map(root)[0]
        self.needs = practices_map.needs_of(entries)
        self.owners = practices_map.owners(entries)


def adr_number(path):
    directory, _, name = path.rpartition("/")
    match = practices_map.ADR_FILE.match(name) if directory == practices_map.ADR_DIRECTORY else None
    return int(match.group(1)) if match else None


def text_of(path, content, kept):
    """Return the content without the blocks of the ADRs that are not kept, when it is a file with blocks."""
    if content is None or markers.kind(path) is None:
        return content
    try:
        return choice.content(path, content.decode("utf-8"), kept).encode("utf-8")
    except UnicodeDecodeError:
        return content
    except ValueError as error:
        raise Failure(f"{path}: {error}")


class Plan:
    """What the choice of the project asks for at a version: `said` are the ADRs that enter the choice and that the
    project does not list, `steps` are (path, base, theirs) with the contents already filtered and the base None for
    a path that starts from nothing, `side` is what the version says of the ADRs and `kept` the ADRs the project keeps."""

    def __init__(self, said, steps, side, kept):
        self.said, self.steps, self.side, self.kept = said, steps, side, kept


def adrs_entering(new_paths, after, kept_before, kept_after, adopted):
    """Return the ADRs that enter the choice at the version: kept now and not before, or kept by a choice that has no
    file for them, among the ADRs of the ranges that the source reserves."""
    directory = practices_map.ADR_DIRECTORY
    in_project = (
        {adr_number(f"{directory}/{name}") for name in os.listdir(directory)} if os.path.isdir(directory) else set()
    )
    in_tree = {adr_number(path) for path in new_paths} - {None}
    return {
        number
        for number in in_tree
        if practices_map.is_reserved(number, after.reserved)
        and number in kept_after
        and (number not in kept_before or (adopted is not None and number not in in_project))
    }


def paths_with_a_block_of(new, new_paths, entering, candidates):
    """Return the paths of the version, outside the candidates, that have a block of an ADR that enters the choice."""
    found = set()
    for path in new_paths:
        if path not in candidates and markers.kind(path):
            text = blob(new, path)
            try:
                blocks = markers.parse(text.decode("utf-8").split("\n"), markers.kind(path))[0]
            except UnicodeDecodeError:
                continue
            if any(block["adr"] in entering for block in blocks):
                found.add(path)
    return found


def plan(old, new):
    """Return the plan to move the project from the version old to the version new (the same one to apply the
    choice only). It reads the project and the versions and writes nothing."""
    after, before = Side(new), Side(old)
    if after.problems:
        raise Failure(
            "\n".join(f"{practices_map.RANGES_FILE}:{number}: {message}" for number, message in after.problems)
        )
    adopted, problems = choice.read(".", after.reserved)
    if problems:
        raise Failure("\n".join(f"{choice.CHOICE_FILE}:{number}: {message}" for number, message in problems))
    if adopted is not None and not after.has_map:
        raise Failure(
            f"groundwork {new} has no {practices_map.MAP}: it cannot apply the choice of {choice.CHOICE_FILE}."
        )
    kept_after = choice.Kept(adopted, after.needs)
    kept_before = choice.Kept(adopted, before.needs) if before.has_map else kept_after

    new_paths = tree_paths(new)
    new_set = set(new_paths)
    entering = adrs_entering(new_paths, after, kept_before, kept_after, adopted)
    said = [number for number in sorted(entering) if adopted is not None and not kept_after.listed(number)]

    def taken(path):
        """Tell whether the choice takes the path: in the new version if it is there, else in the old one."""
        if path in new_set:
            return choice.included(path, after.owners, kept_after, after.reserved)
        return not before.has_map or choice.included(path, before.owners, kept_before, before.reserved)

    def from_nothing(path):
        """Tell whether the path starts from nothing: its ADR enters the choice, or the choice left it out before."""
        owner = adr_number(path) or after.owners.get(path)
        if owner in entering:
            return True
        return before.has_map and not choice.included(path, before.owners, kept_before, before.reserved)

    candidates = set(changed_paths(old, new)) | {path for path in new_paths if from_nothing(path)}
    if entering:
        candidates |= paths_with_a_block_of(new, new_paths, entering, candidates)
    steps = []
    for path in sorted(candidates):
        if taken(path):
            base = None if path in new_set and from_nothing(path) else blob(old, path)
            steps.append(
                (path, text_of(path, base, Without(kept_after, entering)), text_of(path, blob(new, path), kept_after))
            )
    return Plan(said, steps, after, kept_after)


def check_arguments(args):
    if args.issue is not None and not args.issue.isdigit():
        raise Failure(f"'{args.issue}' is not an issue number.")
    if args.result is not None:
        if not args.result:
            raise Failure("--result needs the path of a file.")
        args.result = os.path.abspath(args.result)  # the script goes to the root of the repository next


def up_to_date(old, more=""):
    print(f"The project is up to date with groundwork {old}." + more)


def target_head(old, source):
    """Return the version of the head of the source, or None when the project is already there."""
    commit = git("rev-parse", "--verify", f"{HEAD_REF}^{{commit}}").stdout.strip()
    if not is_ancestor(revision(old), commit):
        raise Failure(f"The head of {source} does not contain {old}: it was perhaps rewritten.")
    new = version_of_head(commit)
    if commit == (commit_of(old) or git("rev-parse", f"{revision(old)}^{{commit}}").stdout.strip()):
        return None
    return new


def target_release(to, old, versions, source):
    """Return the release that --to names, once it is known to be one that the project can move to."""
    if not RELEASE.match(to):
        raise Failure(f"'{to}' is not a version of the form X.Y.Z, or {HEAD}.")
    if not commit_of(old) and as_tuple(to) <= as_tuple(old):
        raise Failure(f"{to} is not a later version than the recorded {old}.")
    if to not in versions:
        raise Failure(f"{to} is not a release of groundwork at {source}.")
    if commit_of(old) and not is_ancestor(commit_of(old), revision(to)):
        raise Failure(f"{to} does not contain the commit {commit_of(old)} that the project is based on.")
    return to


def target_latest(old, versions):
    """Return the latest release, or None when the project is up to date with it or when it lacks the recorded commit."""
    new = versions[-1]
    if as_tuple(new) <= as_tuple(old) or (commit_of(old) and not is_ancestor(commit_of(old), revision(new))):
        return None
    return new


def target(args, old, versions, source):
    """Return the version to move to, or None when the project is up to date."""
    if args.to == HEAD:
        return target_head(old, source)
    if args.to:
        return target_release(args.to, old, versions, source)
    return target_latest(old, versions)


def branch_name(issue, new):
    return f"chore/{issue}-update-groundwork-to-{label(new)}" if issue else f"groundwork/update-to-{label(new)}"


def refuse_steps_outside(steps):
    root = os.path.realpath(".")
    for path, _, _ in steps:
        if not inside(root, path):
            raise Failure(
                f"{path} leaves the repository or is in a directory .git once the links of the project are followed: nothing is changed."
            )


def report(result):
    for field in ("branch", "from", "to", "source"):
        print(f"{field}: {result[field]}")
    if result["added"]:
        print("added: " + ", ".join(result["added"]))
    if result["conflicts"]:
        print("Resolve the conflicts in these files:")
        for path in result["conflicts"]:
            print(f"- {path}")


def write_result(path, result):
    branch = result["branch"]
    try:
        with open(path, "w") as handle:
            json.dump(result, handle)
    except OSError as error:
        raise Failure(
            f"The branch {branch} is prepared, but the result could not be written to {path} ({error.strerror}). "
            f"To undo the update, run `git reset --hard`, `git clean -fd`, `git switch -` and `git branch -D {branch}`."
        )


def run(args):
    check_arguments(args)
    os.chdir(git("rev-parse", "--show-toplevel").stdout.strip())
    old = recorded_version()
    if git("status", "--porcelain").stdout.strip():
        raise Failure("The working tree is not clean: commit or stash the changes first.")

    source = source_of(args.source)
    versions, known = fetch_base(source, old, args.to == HEAD)
    if not known:
        raise Failure(unknown_message(old, source))
    new = target(args, old, versions, source)
    if new is None:
        up_to_date(old, " No release has its commit yet." if args.to != HEAD and commit_of(old) else "")
        return 0

    branch = branch_name(args.issue, new)
    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0:
        raise Failure(f"The branch {branch} already exists.")
    planned = plan(old, new)
    refuse_steps_outside(planned.steps)
    if args.result:
        check_result_path(args.result)
    git("switch", "--quiet", "-c", branch)

    conflicts = [
        path for path, base, theirs in planned.steps if apply_path(path, base, theirs, read(path), mode(new, path))
    ]
    with open(VERSION_FILE, "w") as handle:
        handle.write(new + "\n")
    result = {
        "branch": branch,
        "from": old,
        "to": new,
        "source": source,
        "added": [f"{number:04d}" for number in planned.said],
        "conflicts": conflicts,
    }
    report(result)
    if args.result:
        write_result(args.result, result)
    return CONFLICTS if conflicts else 0


def main():
    parser = argparse.ArgumentParser(description="Prepare the update of a project to a later version of groundwork.")
    parser.add_argument("issue", nargs="?", help="number of the issue of the update, used in the name of the branch")
    parser.add_argument(
        "--to",
        help=f"version to update to, without the leading v, or {HEAD} for the head of the source (default: the latest release)",
    )
    parser.add_argument(
        "--result", help="file in which to write the result as JSON, for open_update_pull_request.py (ADR 1003)"
    )
    parser.add_argument(
        "--source", help=f"repository of groundwork (default: the address in {SOURCE_FILE}, else {SOURCE})"
    )
    try:
        sys.exit(run(parser.parse_args()))
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
