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
            "litex": SimpleNamespace(branch="master", clone="regular", tag=None, sha1=None),
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


if __name__ == "__main__":
    unittest.main()
