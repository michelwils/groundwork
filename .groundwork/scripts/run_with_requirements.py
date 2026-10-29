#!/usr/bin/env python3
"""Run a script of .groundwork/scripts in an environment made from requirements.txt.

The pinned dependencies of the scripts are written once, in requirements.txt, where Dependabot
updates them. This launcher makes an environment named after the hash of that file and of the
version of Python, reuses it as long as neither changes, and runs the script in it with its
arguments, returning its exit status. The environment is built aside and renamed, and marked as
ready once it is complete, so that an interrupted or failed installation is never taken for a
good one. When a new environment is made, the other ones are removed: there is one at a time.

The environments are in the git folder of the repository, `groundwork/`, which is not tracked and
goes with the repository. GROUNDWORK_CACHE names another folder, for a use outside a repository.
The packages are installed with the pip of the Python that runs the launcher, which must be at least
22.3 for `pip --python`, so the environment needs none of its own and is made in a second.
Console scripts of the packages are not usable, since the environment is renamed: run `python`.

Usage: run_with_requirements.py [--requirements FILE] SCRIPT [ARGS…]
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(HERE, "requirements.txt")
STALE_BUILD_SECONDS = 3600


class Failure(Exception):
    pass


def cache_folder():
    given = os.environ.get("GROUNDWORK_CACHE")
    if given:
        return os.path.abspath(given)
    try:
        git = subprocess.run(["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True)
    except FileNotFoundError:
        raise Failure("git is not installed: set GROUNDWORK_CACHE to the folder of the environments")
    if git.returncode != 0:
        raise Failure("this is not a git repository: set GROUNDWORK_CACHE to the folder of the environments")
    return os.path.join(os.path.abspath(git.stdout.strip()), "groundwork")


def python_of(environment):
    return os.path.join(
        environment, "Scripts" if os.name == "nt" else "bin", "python" + (".exe" if os.name == "nt" else "")
    )


def key_of(requirements: str) -> str:
    with open(requirements, "rb") as handle:
        content = handle.read()
    version = f"{sys.version_info.major}.{sys.version_info.minor}".encode()
    return hashlib.sha256(content + b"\0" + version).hexdigest()[:16]


def build(folder, key, requirements):
    """Make the environment of the key in the folder, or fail without leaving anything half made."""
    final = os.path.join(folder, f"venv-{key}")
    temporary = os.path.join(folder, f"building-{key}-{os.getpid()}")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", temporary], check=True, capture_output=True, text=True
        )
        installed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--python",
                python_of(temporary),
                "install",
                "--quiet",
                "--disable-pip-version-check",
                "-r",
                requirements,
            ],
            capture_output=True,
            text=True,
        )
        if installed.returncode != 0:
            raise Failure(f"could not install the requirements of {requirements}: {installed.stderr.strip()}")
        with open(os.path.join(temporary, ".ready"), "w"):
            pass
        if os.path.exists(final) and not os.path.exists(os.path.join(final, ".ready")):
            shutil.rmtree(final, ignore_errors=True)  # not an environment of this launcher, which marks them
        try:
            os.rename(temporary, final)
        except OSError:
            if not os.path.exists(os.path.join(final, ".ready")):  # lost the race to a complete one: use it
                raise
    except subprocess.CalledProcessError as error:
        raise Failure(f"could not make an environment: {error.stderr.strip()}")
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return final


def remove(path):
    if os.path.islink(path):
        os.unlink(path)
    else:
        shutil.rmtree(path, ignore_errors=True)


def age(path):
    """Return the seconds since the path changed, 0 when it is gone: another launch cleans the folder too."""
    try:
        return time.time() - os.lstat(path).st_mtime
    except FileNotFoundError:
        return 0


def prune(folder, keep):
    """Remove the other environments, and the builds that an interrupted run left."""
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        try:
            if name.startswith("venv-") and name != keep:
                remove(path)
            elif name.startswith("building-") and age(path) > STALE_BUILD_SECONDS:
                remove(path)
        except FileNotFoundError:
            pass


def environment_for(requirements):
    folder = cache_folder()
    key = key_of(requirements)
    final = os.path.join(folder, f"venv-{key}")
    if not os.path.exists(os.path.join(final, ".ready")):
        os.makedirs(folder, exist_ok=True)
        build(folder, key, requirements)
        prune(folder, f"venv-{key}")
    return final


def main(arguments):
    requirements = REQUIREMENTS
    if arguments[:1] == ["--requirements"]:
        if len(arguments) < 2:
            raise Failure("--requirements needs the file of requirements")
        requirements, arguments = os.path.abspath(arguments[1]), arguments[2:]
    if not arguments:
        raise Failure(__doc__.strip().splitlines()[-1])
    if not os.path.isfile(arguments[0]):
        raise Failure(f"the script {arguments[0]} does not exist")
    if not os.path.isfile(requirements):
        raise Failure(f"the file of requirements {requirements} does not exist")
    environment = environment_for(requirements)
    return subprocess.run([python_of(environment), *arguments]).returncode


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)
