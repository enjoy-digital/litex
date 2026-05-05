#!/usr/bin/env python3
#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import io
import unittest
import tempfile
import subprocess
import contextlib
from types import SimpleNamespace
from unittest import mock

import litex_setup


class TestLiteXSetup(unittest.TestCase):
    def setUp(self):
        self.tmpdir              = tempfile.TemporaryDirectory()
        self.workspace           = self.tmpdir.name
        self.old_cwd             = os.getcwd()
        self.old_path            = litex_setup.current_path
        self.old_git_repos       = litex_setup.git_repos
        self.old_install_configs = litex_setup.install_configs
        self.old_stderr          = sys.stderr
        litex_setup.current_path = self.workspace

    def tearDown(self):
        os.chdir(self.old_cwd)
        litex_setup.current_path     = self.old_path
        litex_setup.git_repos        = self.old_git_repos
        litex_setup.install_configs  = self.old_install_configs
        sys.stderr                   = self.old_stderr
        self.tmpdir.cleanup()

    def git(self, repo_path, *args):
        subprocess.check_call(
            ["git"] + list(args),
            cwd=repo_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def write_file(self, path, contents):
        with open(path, "w", encoding="utf-8") as f:
            f.write(contents)

    def append_file(self, path, contents):
        with open(path, "a", encoding="utf-8") as f:
            f.write(contents)

    def configure_user(self, repo_path):
        self.git(repo_path, "config", "user.email", "setup-test@example.com")
        self.git(repo_path, "config", "user.name", "Setup Test")

    def create_repo(self):
        remotes_path = os.path.join(self.workspace, "remotes")
        os.makedirs(remotes_path, exist_ok=True)
        remote_path  = os.path.join(remotes_path, "litex.git")
        upstream_path = os.path.join(self.workspace, "upstream")
        repo_path     = os.path.join(self.workspace, "litex")

        self.git(self.workspace, "init", "--bare", remote_path)
        os.makedirs(upstream_path)
        self.git(upstream_path, "init", "-b", "master")
        self.configure_user(upstream_path)
        self.git(upstream_path, "remote", "add", "origin", remote_path)
        self.write_file(os.path.join(upstream_path, "README.md"), "base\n")
        self.git(upstream_path, "add", "README.md")
        self.git(upstream_path, "commit", "-m", "Initial commit")
        self.git(upstream_path, "push", "-u", "origin", "master")

        self.git(self.workspace, "clone", remote_path, repo_path)
        self.configure_user(repo_path)

        litex_setup.git_repos = {
            "litex": SimpleNamespace(
                branch="master",
                clone="regular",
                tag=None,
                sha1=None,
                develop=True,
                editable=True,
            ),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}
        return upstream_path, repo_path

    def assert_update_error(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(litex_setup.SetupError):
                litex_setup.litex_setup_update_repos(config="minimal")
        sys.stderr = self.old_stderr
        return output.getvalue()

    def assert_setup_error(self, callback, *args, **kwargs):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(litex_setup.SetupError):
                callback(*args, **kwargs)
        return stdout.getvalue(), stderr.getvalue()

    def test_update_can_be_cancelled_when_repo_has_local_changes(self):
        _upstream_path, repo_path = self.create_repo()
        self.append_file(os.path.join(repo_path, "README.md"), "local change\n")

        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value="n"):
            output = self.assert_update_error()

        self.assertIn("litex Git repository has local changes.", output)
        self.assertIn("Update cancelled.", output)

    def test_update_fast_forward_failure_has_actionable_error(self):
        upstream_path, repo_path = self.create_repo()

        self.append_file(os.path.join(upstream_path, "README.md"), "remote change\n")
        self.git(upstream_path, "commit", "-am", "Remote change")
        self.git(upstream_path, "push")

        self.append_file(os.path.join(repo_path, "README.md"), "local commit\n")
        self.git(repo_path, "commit", "-am", "Local change")

        with mock.patch("sys.stdin.isatty", return_value=False):
            output = self.assert_update_error()

        self.assertIn("Could not fast-forward litex Git repository.", output)
        self.assertIn("LiteX only performs fast-forward updates", output)
        self.assertIn("git pull --ff-only", output)
        self.assertNotIn("Traceback", output)

    def test_init_rejects_existing_non_git_directory(self):
        os.makedirs(os.path.join(self.workspace, "litex"))
        litex_setup.git_repos = {
            "litex": SimpleNamespace(
                url=self.workspace + "/",
                clone="regular",
                branch="master",
                tag=None,
                sha1=None,
            ),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}

        output, stderr = self.assert_setup_error(litex_setup.litex_setup_init_repos, config="minimal")

        self.assertIn("litex directory already exists but is not a Git repository.", output)
        self.assertIn("Move or remove it, then retry --init.", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_init_clone_failure_has_actionable_error(self):
        litex_setup.git_repos = {
            "litex": SimpleNamespace(
                url=os.path.join(self.workspace, "missing") + "/",
                clone="regular",
                branch="master",
                tag=None,
                sha1=None,
            ),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}

        output, stderr = self.assert_setup_error(litex_setup.litex_setup_init_repos, config="minimal")

        self.assertIn("Could not clone litex Git repository.", output)
        self.assertIn("Check the remote URL, network/SSH access and local path, then retry --init.", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_install_rejects_missing_repository(self):
        litex_setup.git_repos = {
            "litex": SimpleNamespace(develop=True, editable=True),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}

        output, stderr = self.assert_setup_error(litex_setup.litex_setup_install_repos, config="minimal")

        self.assertIn("litex Git repository is not initialized, please run --init first.", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_install_pip_failure_has_actionable_error(self):
        self.create_repo()

        with mock.patch(
            "litex_setup._pip_install",
            side_effect=subprocess.CalledProcessError(1, [sys.executable, "-m", "pip"]),
        ):
            output, stderr = self.assert_setup_error(
                litex_setup.litex_setup_install_repos,
                config="minimal",
                user_mode=True,
            )

        self.assertIn("litex Git repository could not be installed.", output)
        self.assertIn("-m pip install --editable . --user", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_toolchain_command_failure_has_actionable_error(self):
        with mock.patch("subprocess.check_call", side_effect=subprocess.CalledProcessError(1, ["apt"])), \
             mock.patch.object(sys, "platform", "linux"):
            output, stderr = self.assert_setup_error(
                litex_setup.toolchain_install_cmd,
                "RISC-V",
                ["apt", "install", "gcc-riscv64-unknown-elf"],
            )

        self.assertIn("RISC-V GCC toolchain could not be installed.", output)
        self.assertIn("apt install gcc-riscv64-unknown-elf", output)
        self.assertIn("sudo/root privileges", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_toolchain_missing_package_manager_has_actionable_error(self):
        with mock.patch("subprocess.check_call", side_effect=FileNotFoundError):
            output, stderr = self.assert_setup_error(
                litex_setup.toolchain_install_cmd,
                "RISC-V",
                ["missing-package-manager", "install", "gcc"],
            )

        self.assertIn("missing-package-manager was not found", output)
        self.assertIn("supported package manager", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_toolchain_unsupported_platform_is_clean_error(self):
        with mock.patch.object(sys, "platform", "unknown-os"):
            output, stderr = self.assert_setup_error(litex_setup.riscv_gcc_install)

        self.assertIn("RISC-V GCC requires manual installation on unknown-os.", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_invalid_config_is_rejected_cleanly(self):
        litex_setup.install_configs = {"minimal": [], "standard": [], "full": []}

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(litex_setup.SetupError):
                litex_setup.litex_setup_validate_config("unknown")

        self.assertIn("unknown is not a valid install config.", output.getvalue())
        self.assertIn("Available configs: minimal, standard, full", output.getvalue())

    def test_invalid_gcc_choice_is_rejected_by_argparse(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["litex_setup.py", "--gcc", "invalid"]), \
             contextlib.redirect_stdout(stdout), \
             contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                litex_setup.main()

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())

    def test_run_exits_cleanly_on_setup_error(self):
        with mock.patch("litex_setup.main", side_effect=litex_setup.SetupError):
            with self.assertRaises(SystemExit) as cm:
                litex_setup.run()

        self.assertEqual(cm.exception.code, 1)

    def test_run_reports_keyboard_interrupt(self):
        output = io.StringIO()
        with mock.patch("litex_setup.main", side_effect=KeyboardInterrupt), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as cm:
                litex_setup.run()

        self.assertEqual(cm.exception.code, 130)
        self.assertIn("Cancelled.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
