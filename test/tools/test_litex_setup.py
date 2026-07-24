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

    def git_output(self, repo_path, *args):
        return subprocess.check_output(
            ["git"] + list(args),
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()

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

    def create_remote_only_repo(self, commit_count=2):
        remotes_path = os.path.join(self.workspace, "remotes")
        os.makedirs(remotes_path, exist_ok=True)
        remote_path   = os.path.join(remotes_path, "litex.git")
        upstream_path = os.path.join(self.workspace, "upstream")

        self.git(self.workspace, "init", "--bare", remote_path)
        os.makedirs(upstream_path)
        self.git(upstream_path, "init", "-b", "master")
        self.configure_user(upstream_path)
        self.git(upstream_path, "remote", "add", "origin", remote_path)

        commits = []
        for n in range(commit_count):
            self.write_file(os.path.join(upstream_path, "README.md"), "commit-{}\n".format(n))
            self.git(upstream_path, "add", "README.md")
            self.git(upstream_path, "commit", "-m", "Commit {}".format(n))
            commits.append(self.git_output(upstream_path, "rev-parse", "HEAD"))
        self.git(upstream_path, "push", "-u", "origin", "master")

        litex_setup.git_repos = {
            "litex": SimpleNamespace(
                url="file://" + remotes_path + "/",
                branch="master",
                clone="regular",
                tag=None,
                sha1=None,
                develop=True,
                editable=True,
            ),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}
        return upstream_path, remote_path, commits

    def create_recursive_repo(self):
        remotes_path = os.path.join(self.workspace, "remotes")
        os.makedirs(remotes_path, exist_ok=True)

        submodule_remote   = os.path.join(remotes_path, "submodule.git")
        submodule_upstream = os.path.join(self.workspace, "submodule-upstream")
        self.git(self.workspace, "init", "--bare", submodule_remote)
        os.makedirs(submodule_upstream)
        self.git(submodule_upstream, "init", "-b", "master")
        self.configure_user(submodule_upstream)
        self.git(submodule_upstream, "remote", "add", "origin", submodule_remote)
        self.write_file(os.path.join(submodule_upstream, "value.txt"), "submodule-v1\n")
        self.git(submodule_upstream, "add", "value.txt")
        self.git(submodule_upstream, "commit", "-m", "Submodule v1")
        submodule_v1 = self.git_output(submodule_upstream, "rev-parse", "HEAD")
        self.git(submodule_upstream, "push", "-u", "origin", "master")
        self.write_file(os.path.join(submodule_upstream, "value.txt"), "submodule-v2\n")
        self.git(submodule_upstream, "commit", "-am", "Submodule v2")
        submodule_v2 = self.git_output(submodule_upstream, "rev-parse", "HEAD")
        self.git(submodule_upstream, "push")

        main_remote   = os.path.join(remotes_path, "litex.git")
        main_upstream = os.path.join(self.workspace, "main-upstream")
        self.git(self.workspace, "init", "--bare", main_remote)
        os.makedirs(main_upstream)
        self.git(main_upstream, "init", "-b", "master")
        self.configure_user(main_upstream)
        self.git(main_upstream, "remote", "add", "origin", main_remote)
        self.git(
            main_upstream,
            "-c", "protocol.file.allow=always",
            "submodule", "add", submodule_remote, "deps/submodule",
        )
        submodule_path = os.path.join(main_upstream, "deps", "submodule")
        self.git(submodule_path, "checkout", submodule_v1)
        self.git(main_upstream, "add", ".gitmodules", "deps/submodule")
        self.git(main_upstream, "commit", "-m", "Use submodule v1")
        main_v1 = self.git_output(main_upstream, "rev-parse", "HEAD")
        self.git(main_upstream, "push", "-u", "origin", "master")
        self.git(submodule_path, "checkout", submodule_v2)
        self.git(main_upstream, "add", "deps/submodule")
        self.git(main_upstream, "commit", "-m", "Use submodule v2")
        self.git(main_upstream, "push")

        litex_setup.git_repos = {
            "litex": SimpleNamespace(
                url=os.path.join(remotes_path, ""),
                branch="master",
                clone="recursive",
                tag=True,
                sha1=main_v1,
                develop=True,
                editable=True,
            ),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}
        return main_remote, main_v1, submodule_v1

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

    def test_checkout_preserves_leading_zeroes_in_string_sha(self):
        sha1 = "0ddfb44723438d39636cfbf63e9e27609ec9bd43"

        with mock.patch("litex_setup.subprocess_check_output", return_value="") as run:
            litex_setup.git_checkout(sha1=sha1, cwd=self.workspace)

        self.assertEqual(run.call_args[0][0][-1], sha1)

    def test_checkout_keeps_integer_sha_abbreviated(self):
        with mock.patch("litex_setup.subprocess_check_output", return_value="") as run:
            litex_setup.git_checkout(sha1=0xc69953aff92, cwd=self.workspace)

        self.assertEqual(run.call_args[0][0][-1], "c69953aff92")

    def test_format_frozen_repo_keeps_full_sha_as_string(self):
        repo = SimpleNamespace(
            url="https://github.com/enjoy-digital/",
            branch="master",
            clone="regular",
            tag=None,
            develop=True,
            editable=True,
        )
        formatted = litex_setup.litex_setup_format_frozen_repo(
            "litex",
            repo,
            "https://github.com/enjoy-digital/",
            "0ddfb44723438d39636cfbf63e9e27609ec9bd43",
        )

        self.assertIn('sha1="0ddfb44723438d39636cfbf63e9e27609ec9bd43"', formatted)

    def test_update_can_be_cancelled_when_repo_has_local_changes(self):
        _upstream_path, repo_path = self.create_repo()
        self.append_file(os.path.join(repo_path, "README.md"), "local change\n")

        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value="n"):
            output = self.assert_update_error()

        self.assertIn("litex Git repository has local changes.", output)
        self.assertIn("Update cancelled.", output)

    def test_update_assume_yes_preserves_local_changes(self):
        _upstream_path, repo_path = self.create_repo()
        self.append_file(os.path.join(repo_path, "README.md"), "local change\n")

        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input") as input_prompt:
            litex_setup.litex_setup_update_repos(config="minimal", assume_yes=True)

        input_prompt.assert_not_called()
        self.assertIn("README.md", self.git_output(repo_path, "status", "--short"))

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

    def test_init_clone_depth_creates_shallow_clone(self):
        self.create_remote_only_repo()

        litex_setup.litex_setup_init_repos(config="minimal", clone_depth=1)

        repo_path = os.path.join(self.workspace, "litex")
        self.assertEqual(self.git_output(repo_path, "rev-parse", "--is-shallow-repository"), "true")
        self.assertEqual(self.git_output(repo_path, "rev-list", "--count", "HEAD"), "1")

    def test_init_clone_depth_uses_full_clone_for_pinned_sha(self):
        _upstream_path, _remote_path, commits = self.create_remote_only_repo()
        litex_setup.git_repos["litex"].sha1 = commits[0]

        litex_setup.litex_setup_init_repos(config="minimal", clone_depth=1)

        repo_path = os.path.join(self.workspace, "litex")
        self.assertEqual(self.git_output(repo_path, "rev-parse", "HEAD"), commits[0])
        self.assertEqual(self.git_output(repo_path, "rev-parse", "--is-shallow-repository"), "false")

    def test_init_clone_depth_uses_shallow_submodules_for_recursive_repo(self):
        litex_setup.git_repos = {
            "litex": SimpleNamespace(
                url="https://github.com/enjoy-digital/",
                branch="master",
                clone="recursive",
                tag=None,
                sha1=None,
                develop=True,
                editable=True,
            ),
        }
        litex_setup.install_configs = {"minimal": ["litex"]}

        with mock.patch("litex_setup.subprocess_check_output", return_value=b"") as run:
            litex_setup.litex_setup_init_repos(config="minimal", clone_depth=1)

        clone_cmd = run.call_args_list[0][0][0]
        self.assertIn("--recursive", clone_cmd)
        self.assertIn("--shallow-submodules", clone_cmd)

    def test_init_clone_depth_rejects_non_positive_depth(self):
        self.create_remote_only_repo()

        output, stderr = self.assert_setup_error(
            litex_setup.litex_setup_init_repos,
            config      = "minimal",
            clone_depth = 0,
        )

        self.assertIn("--clone-depth must be a positive integer.", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_init_updates_submodules_after_frozen_sha_checkout(self):
        _main_remote, _main_v1, submodule_v1 = self.create_recursive_repo()

        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file"}):
            litex_setup.litex_setup_init_repos(config="minimal")

        submodule_path = os.path.join(self.workspace, "litex", "deps", "submodule")
        self.assertEqual(self.git_output(submodule_path, "rev-parse", "HEAD"), submodule_v1)

    def test_update_updates_submodules_after_frozen_sha_checkout(self):
        main_remote, _main_v1, submodule_v1 = self.create_recursive_repo()
        repo_path = os.path.join(self.workspace, "litex")

        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file"}):
            self.git(
                self.workspace,
                "-c", "protocol.file.allow=always",
                "clone", "--recursive", main_remote, repo_path,
            )
            litex_setup.litex_setup_update_repos(config="minimal")

        submodule_path = os.path.join(repo_path, "deps", "submodule")
        self.assertEqual(self.git_output(submodule_path, "rev-parse", "HEAD"), submodule_v1)

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

    def test_install_reports_all_uninitialized_repositories(self):
        os.makedirs(os.path.join(self.workspace, "migen"))
        litex_setup.git_repos = {
            "migen": SimpleNamespace(develop=True, editable=True),
            "litex": SimpleNamespace(develop=True, editable=True),
            "optional": SimpleNamespace(develop=False, editable=True),
        }
        litex_setup.install_configs = {"standard": ["migen", "litex", "optional"]}

        output, stderr = self.assert_setup_error(litex_setup.litex_setup_install_repos, config="standard")

        self.assertIn("Some Git repositories are not initialized, please run --init first.", output)
        self.assertIn("Missing repositories:", output)
        self.assertIn("litex:", output)
        self.assertIn("Paths that exist but are not Git repositories:", output)
        self.assertIn("migen:", output)
        self.assertIn("Move or remove these paths before running --init.", output)
        self.assertIn("./litex_setup.py --init --config=standard", output)
        self.assertIn("./litex_setup.py --install --config=standard", output)
        self.assertNotIn("optional:", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_install_pip_failure_has_actionable_error(self):
        self.create_repo()

        with mock.patch(
            "litex_setup._pip_install",
            side_effect=subprocess.CalledProcessError(1, [sys.executable, "-m", "pip"]),
        ), mock.patch("litex_setup.pip_install_build_dependencies"), \
           mock.patch("litex_setup.pip_install_in_virtualenv", return_value=False), \
           mock.patch("litex_setup.pip_install_externally_managed", return_value=False):
            output, stderr = self.assert_setup_error(
                litex_setup.litex_setup_install_repos,
                config="minimal",
                user_mode=True,
            )

        self.assertIn("litex Git repository could not be installed.", output)
        self.assertIn("PYTHONPATH=", output)
        self.assertIn("-m pip install --no-build-isolation --editable . --user", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_install_externally_managed_python_has_actionable_error(self):
        self.create_repo()

        with mock.patch("litex_setup.pip_install_in_virtualenv", return_value=False), \
             mock.patch("litex_setup.pip_install_externally_managed", return_value=True):
            output, stderr = self.assert_setup_error(
                litex_setup.litex_setup_install_repos,
                config="minimal",
                user_mode=True,
            )

        self.assertIn("externally managed", output)
        self.assertIn("python3 -m venv ~/litex-venv", output)
        self.assertIn("--break-system-packages", output)
        self.assertIn("--user installs are also blocked", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_install_break_system_packages_passes_pip_override(self):
        self.create_repo()

        with mock.patch("subprocess.check_call") as check_call, \
             mock.patch("litex_setup.pip_install_externally_managed", return_value=True):
            litex_setup.litex_setup_install_repos(
                config="minimal",
                break_system_packages=True,
            )

        cmd, _kwargs = check_call.call_args
        self.assertIn("--break-system-packages", cmd[0])

    def test_install_ignores_user_mode_inside_virtualenv(self):
        self.create_repo()

        output = io.StringIO()
        with contextlib.redirect_stdout(output), \
             mock.patch("subprocess.check_call") as check_call, \
             mock.patch("litex_setup.pip_install_in_virtualenv", return_value=True):
            litex_setup.litex_setup_install_repos(config="minimal", user_mode=True)

        self.assertIn("--user ignored", output.getvalue())
        for call in check_call.call_args_list:
            cmd = call.args[0]
            self.assertNotIn("--user", cmd)

    def test_install_bootstraps_python_build_dependencies(self):
        self.create_repo()

        with mock.patch("subprocess.check_call") as check_call, \
             mock.patch("litex_setup.pip_install_externally_managed", return_value=False):
            litex_setup.litex_setup_install_repos(config="minimal")

        cmd = check_call.call_args_list[0].args[0]
        self.assertIn("setuptools>=65.5", cmd)
        self.assertIn("wheel", cmd)

    def test_build_dependencies_failure_has_actionable_error(self):
        self.create_repo()

        with mock.patch(
            "subprocess.check_call",
            side_effect=subprocess.CalledProcessError(1, [sys.executable, "-m", "pip"]),
        ), mock.patch("litex_setup.pip_install_externally_managed", return_value=False):
            output, stderr = self.assert_setup_error(
                litex_setup.litex_setup_install_repos,
                config="minimal",
            )

        self.assertIn("Python build dependencies could not be installed.", output)
        self.assertIn("setuptools>=65.5", output)
        self.assertIn("wheel", output)
        self.assertNotIn("Traceback", output + stderr)

    def test_local_install_exposes_repo_to_pep517_backend(self):
        self.create_repo()

        with mock.patch("subprocess.check_call") as check_call, \
             mock.patch("litex_setup.pip_install_externally_managed", return_value=False):
            litex_setup.litex_setup_install_repos(config="minimal")

        _cmd, kwargs = check_call.call_args
        env = kwargs["env"]
        pythonpath = env["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(pythonpath[0], os.path.join(self.workspace, "litex"))

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

    def test_riscv_toolchain_uses_homebrew_package_on_macos(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.check_call") as check_call:
            litex_setup.riscv_gcc_install()

        check_call.assert_called_once_with(["brew", "install", "riscv64-elf-gcc"])

    def test_mips_toolchain_uses_ubuntu_mipsel_package(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("litex_setup._read_os_release", return_value="ubuntu"), \
             mock.patch("subprocess.check_call") as check_call:
            litex_setup.mips_gcc_install()

        check_call.assert_called_once_with(["apt", "install", "gcc-mipsel-linux-gnu"])

    def test_mips_toolchain_uses_arch_mipsel_package(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("litex_setup._read_os_release", return_value="arch linux"), \
             mock.patch("subprocess.check_call") as check_call:
            litex_setup.mips_gcc_install()

        check_call.assert_called_once_with(["yay", "-S", "mipsel-linux-gnu-gcc"])

    def test_lm32_toolchain_uses_arch_package(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("litex_setup._read_os_release", return_value="arch linux"), \
             mock.patch("subprocess.check_call") as check_call:
            litex_setup.lm32_gcc_install()

        check_call.assert_called_once_with(["pacman", "-S", "lm32-elf-gcc"])

    def test_lm32_toolchain_uses_conda_fallback(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("litex_setup._read_os_release", return_value="ubuntu"), \
             mock.patch("shutil.which", side_effect=[None, "/opt/conda/bin/conda"]), \
             mock.patch("subprocess.check_call") as check_call:
            litex_setup.lm32_gcc_install()

        check_call.assert_called_once_with([
            "/opt/conda/bin/conda",
            "install",
            "-y",
            "-c",
            "litex-hub",
            "-c",
            "conda-forge",
            "gcc-lm32-elf-newlib",
        ])

    def test_lm32_toolchain_without_package_manager_has_hint(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("litex_setup._read_os_release", return_value="ubuntu"), \
             mock.patch("shutil.which", return_value=None):
            output, stderr = self.assert_setup_error(litex_setup.lm32_gcc_install)

        self.assertIn("LM32 GCC requires manual installation on linux.", output)
        self.assertIn("conda install -c litex-hub -c conda-forge gcc-lm32-elf-newlib", output)
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
