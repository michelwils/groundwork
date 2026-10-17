import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(HERE, "run_with_requirements.py")

SCRIPT = """import json, sys
print(json.dumps({"prefix": sys.prefix, "argv": sys.argv[1:]}))
sys.exit(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0)
"""


class Launcher(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name
        self.cache = os.path.join(self.root, "cache")
        self.requirements = os.path.join(self.root, "requirements.txt")
        self.script = os.path.join(self.root, "script.py")
        self.write(self.requirements, "# no package\n")
        self.write(self.script, SCRIPT)

    def tearDown(self):
        self.directory.cleanup()

    def write(self, path, content):
        with open(path, "w") as handle:
            handle.write(content)

    def run_launcher(self, *args, cache=True, cwd=None):
        env = {key: value for key, value in os.environ.items() if key != "GROUNDWORK_CACHE"}
        if cache:
            env["GROUNDWORK_CACHE"] = self.cache
        command = [sys.executable, LAUNCHER, "--requirements", self.requirements, self.script, *args]
        return subprocess.run(command, capture_output=True, text=True, env=env, cwd=cwd)

    def environments(self):
        if not os.path.isdir(self.cache):
            return []
        return sorted(name for name in os.listdir(self.cache) if name.startswith("venv-"))

    def builds(self):
        return [name for name in os.listdir(self.cache) if name.startswith("building-")]

    def test_it_runs_the_script_in_an_environment_of_the_cache_with_its_arguments_and_status(self):
        result = self.run_launcher("3", "--flag")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn('"argv": ["3", "--flag"]', result.stdout)
        (environment,) = self.environments()
        self.assertIn(os.path.join(self.cache, environment), result.stdout)

    def test_the_environment_is_reused_while_the_requirements_do_not_change(self):
        self.run_launcher()
        (environment,) = self.environments()
        marker = os.path.join(self.cache, environment, ".ready")
        before = os.stat(marker).st_mtime_ns
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.environments(), [environment])
        self.assertEqual(os.stat(marker).st_mtime_ns, before)

    def test_a_change_of_the_requirements_makes_a_new_environment_and_removes_the_old_one(self):
        self.run_launcher()
        (old,) = self.environments()
        self.write(self.requirements, "# another comment\n")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        (new,) = self.environments()
        self.assertNotEqual(new, old)

    def test_a_failed_installation_leaves_the_environment_in_use_and_says_what_failed(self):
        self.run_launcher()
        (old,) = self.environments()
        self.write(self.requirements, "-r missing-requirements.txt\n")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertIn("requirements", result.stderr)
        self.assertIn("missing-requirements.txt", result.stderr)
        self.assertEqual(self.environments(), [old])
        self.assertEqual(self.builds(), [])

    def test_a_failed_installation_leaves_no_environment_that_would_be_taken_for_a_good_one(self):
        self.write(self.requirements, "-r missing-requirements.txt\n")
        self.assertEqual(self.run_launcher().returncode, 1)
        self.assertEqual(self.environments(), [])
        self.assertEqual(self.builds(), [])
        self.write(self.requirements, "# fixed\n")
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertEqual(len(self.environments()), 1)

    def test_only_the_environments_and_the_stale_builds_are_removed_from_the_cache(self):
        self.run_launcher()
        stale = os.path.join(self.cache, "building-abc-1")
        fresh = os.path.join(self.cache, "building-abc-2")
        for path in (stale, fresh):
            os.makedirs(path)
        old = time.time() - 2 * 3600
        os.utime(stale, (old, old))
        self.write(os.path.join(self.cache, "notes.txt"), "mine")
        self.write(self.requirements, "# changed\n")
        self.run_launcher()
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(fresh))
        self.assertTrue(os.path.exists(os.path.join(self.cache, "notes.txt")))

    def test_two_launches_at_the_same_time_make_one_environment(self):
        env = {**os.environ, "GROUNDWORK_CACHE": self.cache}
        command = [sys.executable, LAUNCHER, "--requirements", self.requirements, self.script]
        processes = [
            subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)
        ]
        for process in processes:
            _, error = process.communicate()
            self.assertEqual(process.returncode, 0, error)
        self.assertEqual(len(self.environments()), 1)
        self.assertEqual(self.builds(), [])

    def test_without_a_cache_folder_it_uses_the_git_folder_of_the_repository(self):
        repository = os.path.join(self.root, "repository")
        os.makedirs(repository)
        subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
        result = self.run_launcher(cache=False, cwd=repository)
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = os.path.join(repository, ".git", "groundwork")
        self.assertEqual(len([name for name in os.listdir(folder) if name.startswith("venv-")]), 1)

    def test_outside_a_repository_and_without_a_cache_folder_it_says_so(self):
        outside = os.path.join(self.root, "outside")
        os.makedirs(outside)
        result = self.run_launcher(cache=False, cwd=outside)
        self.assertEqual(result.returncode, 1)
        self.assertIn("GROUNDWORK_CACHE", result.stderr)

    def test_a_folder_that_has_the_name_of_the_environment_but_no_marker_is_replaced(self):
        sys.path.insert(0, HERE)
        import run_with_requirements

        half = os.path.join(self.cache, f"venv-{run_with_requirements.key_of(self.requirements)}")
        os.makedirs(half)
        self.write(os.path.join(half, "leftover"), "not an environment")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(os.path.join(half, ".ready")))
        self.assertFalse(os.path.exists(os.path.join(half, "leftover")))

    def test_an_entry_that_vanishes_while_the_cache_is_cleaned_does_not_stop_the_launch(self):
        self.run_launcher()
        os.symlink(os.path.join(self.root, "nowhere"), os.path.join(self.cache, "building-vanished-1"))
        self.write(self.requirements, "# changed\n")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_option_without_its_value_is_reported(self):
        result = subprocess.run([sys.executable, LAUNCHER, "--requirements"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("--requirements", result.stderr)

    def test_a_missing_script_is_reported(self):
        command = [sys.executable, LAUNCHER, "--requirements", self.requirements, os.path.join(self.root, "nope.py")]
        env = {**os.environ, "GROUNDWORK_CACHE": self.cache}
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("nope.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
