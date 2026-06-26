#!/usr/bin/env python3
#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import io
import json
import unittest
import tempfile
import subprocess
import contextlib
from unittest import mock

import litex_release
import litex_setup


class TestLiteXRelease(unittest.TestCase):
    def setUp(self):
        self.tmpdir       = tempfile.TemporaryDirectory()
        self.workspace    = self.tmpdir.name
        self.old_path     = litex_setup.current_path
        self.old_stderr   = sys.stderr
        litex_setup.current_path = self.workspace

    def tearDown(self):
        litex_setup.current_path = self.old_path
        sys.stderr = self.old_stderr
        self.tmpdir.cleanup()

    def git(self, repo_path, *args):
        subprocess.check_call(
            ["git"] + list(args),
            cwd=repo_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def git_output(self, repo_path, *args):
        return subprocess.check_output(
            ["git"] + list(args),
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()

    def assertSetupError(self, callback, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(litex_setup.SetupError):
                callback(*args, **kwargs)
        sys.stderr = self.old_stderr

    def call_quiet(self, callback, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return callback(*args, **kwargs)

    def create_repo(self, name="liteeth", version="2025.12"):
        remotes_path = os.path.join(self.workspace, "remotes")
        os.makedirs(remotes_path, exist_ok=True)
        remote_path = os.path.join(remotes_path, f"{name}.git")
        repo_path   = os.path.join(self.workspace, name)

        self.git(self.workspace, "init", "--bare", remote_path)
        os.makedirs(repo_path)
        self.git(repo_path, "init", "-b", "master")
        self.git(repo_path, "config", "user.email", "release-test@example.com")
        self.git(repo_path, "config", "user.name", "Release Test")
        self.git(repo_path, "remote", "add", "origin", remote_path)

        with open(os.path.join(repo_path, "setup.py"), "w", encoding="utf-8") as f:
            f.write(f'from setuptools import setup\nsetup(name="{name}", version="{version}")\n')
        self.git(repo_path, "add", "setup.py")
        self.git(repo_path, "commit", "-m", "Initial commit")
        self.git(repo_path, "tag", version)
        self.git(repo_path, "push", "-u", "origin", "master")
        self.git(repo_path, "push", "origin", version)
        return repo_path

    def test_default_release_repo_names(self):
        self.assertEqual(litex_release.release_repo_names(repos="litex,liteeth"), ["litex", "liteeth"])
        self.assertSetupError(litex_release.release_repo_names, repos="unknown")
        self.assertSetupError(litex_release.release_repo_names, repos="migen")

    def test_release_tag_validation(self):
        litex_release.check_release_tag("2099.04")
        litex_release.check_release_tag("2099.08")
        litex_release.check_release_tag("2099.12")
        self.assertSetupError(litex_release.check_release_tag, "2099.99")
        litex_release.check_release_tag("2099.99", allow_invalid_tag=True)

    def test_dry_run_no_push_does_not_modify_repo(self):
        repo_path = self.create_repo()
        head      = self.git_output(repo_path, "rev-parse", "HEAD")

        self.call_quiet(
            litex_release.release_repos,
            "2099.04",
            repos="liteeth",
            dry_run=True,
            no_push=True,
        )

        self.assertEqual(self.git_output(repo_path, "rev-parse", "HEAD"), head)
        self.assertEqual(self.git_output(repo_path, "tag", "-l", "2099.04"), "")
        self.assertEqual(litex_release.get_setup_version(os.path.join(repo_path, "setup.py")), "2025.12")

    def test_dirty_tree_is_rejected(self):
        repo_path = self.create_repo()
        with open(os.path.join(repo_path, "setup.py"), "a", encoding="utf-8") as f:
            f.write("# dirty\n")

        self.assertSetupError(
            litex_release.release_repos,
            "2099.04",
            repos="liteeth",
            dry_run=True,
            no_push=True,
        )

    def test_remote_tag_collision_is_rejected(self):
        repo_path = self.create_repo()
        self.git(repo_path, "tag", "2099.04")
        self.git(repo_path, "push", "origin", "2099.04")
        self.git(repo_path, "tag", "-d", "2099.04")

        self.assertSetupError(
            litex_release.release_repos,
            "2099.04",
            repos="liteeth",
            dry_run=True,
            no_push=True,
        )

    def test_push_phase_requires_existing_local_tag(self):
        self.create_repo()

        self.assertSetupError(
            litex_release.release_repos,
            "2099.04",
            repos="liteeth",
            dry_run=True,
            phases=["push"],
        )

    def test_release_writes_state_file(self):
        repo_path  = self.create_repo()
        state_file = os.path.join(self.workspace, "release_state.json")
        cwd        = os.getcwd()

        with mock.patch("builtins.input", return_value="Y"), \
             mock.patch("litex_release.git_call", side_effect=self.git):
            self.call_quiet(
                litex_release.release_repos,
                "2099.04",
                repos="liteeth",
                no_push=True,
                state_file=state_file,
            )

        self.assertEqual(os.getcwd(), cwd)
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.assertEqual(state["tag"], "2099.04")
        self.assertEqual(state["phases"], ["bump", "tag"])
        self.assertEqual(state["completed_phases"], ["bump", "tag"])
        self.assertEqual(state["repositories"][0]["name"], "liteeth")
        self.assertEqual(state["events"][0]["phase"], "bump")
        self.assertEqual(state["events"][0]["repo"], "liteeth")
        self.assertEqual(state["events"][1], {"phase": "tag", "repo": "liteeth", "tag": "2099.04"})
        self.assertEqual(litex_release.get_setup_version(os.path.join(repo_path, "setup.py")), "2099.04")
        self.assertEqual(self.git_output(repo_path, "tag", "-l", "2099.04"), "2099.04")


if __name__ == "__main__":
    unittest.main()
