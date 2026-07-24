#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2018-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import time
import shlex
import shutil
import argparse
import importlib
import subprocess
import sysconfig
import urllib.request

start_time   = time.time()
current_path = os.path.abspath(os.curdir)
python3      = sys.executable
git_repos    = None
install_configs = None
litex_setup_url = "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py"
litex_repos_url = "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_repos.py"

# Helpers ------------------------------------------------------------------------------------------

def colorer(s, color="bright"):
    header  = {
        "bright"    : "\x1b[1m",
        "green"     : "\x1b[1m\x1b[32m",
        "cyan"      : "\x1b[1m\x1b[36m",
        "red"       : "\x1b[1m\x1b[31m",
        "yellow"    : "\x1b[1m\x1b[33m",
        "underline" : "\x1b[1m\x1b[4m",
    }[color]
    trailer = "\x1b[0m"
    return header + str(s) + trailer

def print_banner():
    b  = []
    b.append("          __   _ __      _  __         ")
    b.append("         / /  (_) /____ | |/_/         ")
    b.append("        / /__/ / __/ -_)>  <           ")
    b.append("       /____/_/\\__/\\__/_/|_|         ")
    b.append("     Build your hardware, easily!      ")
    b.append("          LiteX Setup utility.         ")
    b.append(" Copyright 2012-2026 / Enjoy-Digital & LiteX developers")
    b.append("")
    print("\n".join(b))

def print_status(status, underline=False):
    exec_time = (time.time() - start_time)
    print(colorer(f"[{exec_time:8.3f}]", color="green") + " " + colorer(status))
    if underline:
        print(colorer(f"[{exec_time:8.3f}]", color="green") + " " + colorer("-" * len(status)))

def print_error(status):
    exec_time = (time.time() - start_time)
    print(colorer(f"[{exec_time:8.3f}]", color="red") + " " + colorer(status))

def print_warning(status):
    exec_time = (time.time() - start_time)
    print(colorer(f"[{exec_time:8.3f}]", color="yellow") + " " + colorer(status))

class SetupError(Exception):
    pass

# Script location / auto-update --------------------------------------------------------------------

def litex_setup_location_check():
    # Check if script is executed inside a cloned LiteX repository or alongside?
    if os.path.exists(".gitignore"):
        global current_path
        current_path = os.path.join(current_path, "../")

def litex_setup_repos_path():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "litex_repos.py")

def litex_setup_download(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read()

def litex_setup_update_file(url, path, name, restart=False):
    content = litex_setup_download(url)
    if os.path.exists(path):
        with open(path, "rb") as f:
            current = f.read()
    else:
        current = None
    if current == content:
        print_status(f"{name} is up to date.")
        return False
    print_status(f"{name} is obsolete or missing, updating.")
    with open(path, "wb") as f:
        f.write(content)
    if restart:
        os.execl(python3, python3, *sys.argv)
    return True

def litex_setup_update_repos_file():
    try:
        litex_setup_update_file(
            url  = litex_repos_url,
            path = litex_setup_repos_path(),
            name = "LiteX repository definitions",
        )
    except Exception as e:
        print_error(f"Could not download litex_repos.py: {e}")
        raise SetupError

def litex_setup_download_repos():
    print_status("LiteX repository definitions are missing, downloading.")
    litex_setup_update_repos_file()

def litex_setup_import_repos(download=False):
    global git_repos
    global install_configs
    try:
        repos = importlib.import_module("litex_repos")
    except ModuleNotFoundError as e:
        if e.name != "litex_repos":
            raise
        if not download:
            print_error("litex_repos.py is missing.")
            print_status("Run without --dev to download it automatically, or download it next to litex_setup.py.")
            raise SetupError
        litex_setup_download_repos()
        importlib.invalidate_caches()
        repos = importlib.import_module("litex_repos")
    git_repos       = repos.git_repos
    install_configs = repos.install_configs

def litex_setup_validate_config(config):
    if config in install_configs:
        return
    print_error(f"{config} is not a valid install config.")
    print_status(f"Available configs: {', '.join(install_configs)}")
    raise SetupError

def litex_setup_uninitialized_repos(config="standard", develop_only=False):
    missing = []
    invalid = []
    for name in install_configs[config]:
        repo = git_repos[name]
        if develop_only and not repo.develop:
            continue
        repo_path = os.path.join(current_path, name)
        if not os.path.exists(repo_path):
            missing.append((name, repo_path))
        elif not git_is_repository(repo_path):
            invalid.append((name, repo_path))
    return missing, invalid

def litex_setup_check_initialized_repos(config="standard", develop_only=False, retry="install"):
    missing, invalid = litex_setup_uninitialized_repos(
        config       = config,
        develop_only = develop_only,
    )
    if not missing and not invalid:
        return

    if len(missing) + len(invalid) == 1:
        name = (missing or invalid)[0][0]
        print_error(f"{name} Git repository is not initialized, please run --init first.")
    else:
        print_error("Some Git repositories are not initialized, please run --init first.")

    if missing:
        print_status("Missing repositories:")
        for name, repo_path in missing:
            print_status(f"  {name}: {repo_path}")

    if invalid:
        print_status("Paths that exist but are not Git repositories:")
        for name, repo_path in invalid:
            print_status(f"  {name}: {repo_path}")
        print_status("Move or remove these paths before running --init.")

    print_status("Initialize repositories first, then retry:")
    print_status(f"  ./litex_setup.py --init --config={config}")
    print_status(f"  ./litex_setup.py --{retry} --config={config}")
    raise SetupError

def litex_setup_auto_update():
    print_status("LiteX Setup auto-update...")
    try:
        litex_setup_update_file(
            url     = litex_setup_url,
            path    = os.path.realpath(__file__),
            name    = "LiteX Setup",
            restart = True,
        )
    except Exception:
        pass

# Git helpers --------------------------------------------------------------------------------------

def subprocess_check_output(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        output = r.stdout.decode("UTF-8", errors="ignore")
        error  = r.stderr.decode("UTF-8", errors="ignore")
        if output:
            print(output, end="")
        if error:
            print(error, end="")
        raise subprocess.CalledProcessError(r.returncode, cmd, output=r.stdout, stderr=r.stderr)
    return r.stdout.decode("UTF-8")

def print_indented(output, indent="    ", max_lines=None):
    lines = output.splitlines()
    if max_lines is not None and len(lines) > max_lines:
        remaining = len(lines) - max_lines
        lines = lines[:max_lines] + [f"... ({remaining} more line(s))"]
    print("\n".join(indent + line for line in lines))

def git_format_sha1(sha1):
    if isinstance(sha1, int):
        return f"{sha1:07x}"
    return str(sha1)

def git_checkout(sha1=None, tag=None, quiet=False, cwd=None):
    assert not ((sha1 is None) and (tag is None))
    checkout_cmd = ["git", "-c", "advice.detachedHead=false", "checkout"]
    if quiet:
        checkout_cmd.append("--quiet")
    if sha1 is not None:
        subprocess_check_output(checkout_cmd + [git_format_sha1(sha1)], cwd=cwd)
    if tag is not None:
        sha1_tag_cmd = ["git", "rev-list", "-n 1", tag]
        sha1_tag     = subprocess_check_output(sha1_tag_cmd, cwd=cwd).strip()
        subprocess_check_output(checkout_cmd + [sha1_tag], cwd=cwd)

def git_update_submodules(name, repo_path, error):
    submodule_cmds = [
        (["git", "submodule", "sync", "--recursive"], "sync submodules in"),
        (["git", "submodule", "update", "--init", "--recursive"], "update submodules in"),
    ]
    for cmd, action in submodule_cmds:
        try:
            output = subprocess_check_output(cmd, cwd=repo_path).strip()
        except subprocess.CalledProcessError:
            error(name, repo_path, action)
            raise SetupError
        if output:
            print(output)

def git_pull(repo_path):
    color  = "always" if sys.stdout.isatty() else "never"
    pull_cmd = ["git", "-c", f"color.ui={color}", "pull", "--ff-only", "--stat"]
    output   = subprocess_check_output(pull_cmd, cwd=repo_path).strip()
    if output in ["Already up to date.", "Already up-to-date."]:
        return
    if output:
        print_indented(output)

def git_is_repository(repo_path):
    if not os.path.isdir(repo_path):
        return False
    repo_cmd = ["git", "rev-parse", "--is-inside-work-tree"]
    r = subprocess.run(repo_cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return False
    return r.stdout.decode("UTF-8", errors="ignore").strip() == "true"

def git_status(repo_path, short=False):
    status_cmd = ["git", "-c", "color.ui=never", "status"]
    if short:
        status_cmd.append("--short")
    else:
        status_cmd += ["--short", "--branch"]
    r = subprocess.run(status_cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None
    return r.stdout.decode("UTF-8", errors="ignore").strip()

def git_status_has_tracked_changes(status):
    if not status:
        return False
    for line in status.splitlines():
        if len(line) < 2:
            continue
        if line[:2] != "??":
            return True
    return False

def git_confirm_update_with_local_changes(name, repo_path, assume_yes=False):
    status = git_status(repo_path, short=True)
    if not git_status_has_tracked_changes(status) or not sys.stdin.isatty():
        return
    print_warning(f"{name} Git repository has local changes.")
    print_status("Updating can fail if these changes overlap with upstream changes.")
    print_status("Local changes:")
    print_indented(status, max_lines=12)
    if not assume_yes:
        confirm = input("Continue updating this repository? [y/N]: ")
        if confirm.strip().lower() not in ["y", "yes"]:
            print_status("Update cancelled.")
            raise SetupError

def git_update_error(name, repo_path, action):
    print_error(f"Could not {action} {name} Git repository.")
    status = git_status(repo_path)
    if status:
        print_status("Repository status:")
        print_indented(status, max_lines=12)
    print_status("LiteX only performs fast-forward updates and will not merge, rebase or discard local work.")
    print_status("Inspect and resolve the repository manually, then retry:")
    print_status(f"  cd {repo_path}")
    print_status("  git status")
    print_status("  git stash push -u      # save uncommitted changes")
    print_status("  git pull --ff-only     # retry once the branch can fast-forward")
    print_status("If you have local commits, rebase/merge them or move them to another branch first.")

def git_init_error(name, repo_path, action):
    print_error(f"Could not {action} {name} Git repository.")
    if os.path.exists(repo_path):
        if git_is_repository(repo_path):
            status = git_status(repo_path)
            if status:
                print_status("Repository status:")
                print_indented(status, max_lines=12)
        else:
            print_status(f"{repo_path} exists but is not a valid Git repository.")
    print_status("Check the remote URL, network/SSH access and local path, then retry --init.")
    print_status("If a partial clone was left behind, move or remove that directory before retrying.")

def git_repo_uses_pinned_checkout(repo, tag=None):
    if repo.tag is not None and (tag is not None or isinstance(repo.tag, str)):
        return True
    return repo.sha1 is not None

def git_clone_depth_for_repo(name, repo, tag=None, clone_depth=None):
    if clone_depth is None:
        return None
    if clone_depth <= 0:
        print_error("--clone-depth must be a positive integer.")
        raise SetupError
    if git_repo_uses_pinned_checkout(repo, tag=tag):
        print_status(f"{name}: using full clone since repository uses a pinned tag/SHA1 checkout.")
        return None
    return clone_depth

# Git repositories initialization ------------------------------------------------------------------

def litex_setup_init_repos(config="standard", tag=None, dev_mode=False, clone_depth=None):
    print_status("Initializing Git repositories...", underline=True)
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        repo_path = os.path.join(current_path, name)
        if not os.path.exists(repo_path):
            # Clone Repo.
            print_status(f"Cloning {name} Git repository...")
            repo_url = repo.url
            if dev_mode:
                repo_url = repo_url.replace("https://github.com/", "git@github.com:")
            clone_cmd = ["git", "clone"]
            repo_clone_depth = git_clone_depth_for_repo(name, repo, tag=tag, clone_depth=clone_depth)
            if repo_clone_depth is not None:
                clone_cmd += ["--depth", str(repo_clone_depth)]
            if repo.branch is not None:
                clone_cmd += ["--branch", repo.branch]
            if repo.clone == "recursive":
                clone_cmd.append("--recursive")
                if repo_clone_depth is not None:
                    clone_cmd.append("--shallow-submodules")
            clone_cmd.append(repo_url + name + ".git")
            try:
                subprocess_check_output(clone_cmd, cwd=current_path)
            except subprocess.CalledProcessError:
                git_init_error(name, repo_path, "clone")
                raise SetupError
            # Use specific Branch.
            try:
                subprocess_check_output(["git", "checkout", "--quiet", repo.branch], cwd=repo_path)
            except subprocess.CalledProcessError:
                git_init_error(name, repo_path, f"checkout branch {repo.branch} in")
                raise SetupError
            # Use specific Tag (Optional).
            checked_out = False
            if repo.tag is not None:
                # Priority to passed tag (if specified).
                if tag is not None:
                    try:
                        git_checkout(tag=tag, cwd=repo_path)
                    except subprocess.CalledProcessError:
                        git_init_error(name, repo_path, f"checkout tag {tag} in")
                        raise SetupError
                    checked_out = True
                # Else fallback to repo tag (if specified).
                elif isinstance(repo.tag, str):
                    try:
                        git_checkout(tag=repo.tag, cwd=repo_path)
                    except subprocess.CalledProcessError:
                        git_init_error(name, repo_path, f"checkout tag {repo.tag} in")
                        raise SetupError
                    checked_out = True
            # Use specific SHA1 (Optional).
            if not checked_out and repo.sha1 is not None:
                try:
                    git_checkout(sha1=repo.sha1, cwd=repo_path)
                except subprocess.CalledProcessError:
                    git_init_error(name, repo_path, f"checkout SHA1 {git_format_sha1(repo.sha1)} in")
                    raise SetupError
            # Recursive Update (Optional).
            if repo.clone == "recursive":
                git_update_submodules(name, repo_path, git_init_error)
        else:
            if not git_is_repository(repo_path):
                print_error(f"{name} directory already exists but is not a Git repository.")
                print_status(f"Path: {repo_path}")
                print_status("Move or remove it, then retry --init.")
                raise SetupError
            print_status(f"{name} Git Repo already present.")

# Git repositories update --------------------------------------------------------------------------

def litex_setup_update_repos(config="standard", tag=None, assume_yes=False):
    print_status("Updating Git repositories...", underline=True)
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        # Check if Repo is present.
        if not os.path.exists(name):
            print_error(f"{name} Git repository is not initialized, please run --init first.")
            raise SetupError
        # Update Repo.
        print_status(f"Updating {name} Git repository...")
        os.chdir(os.path.join(current_path, name))
        repo_path = os.path.join(current_path, name)
        git_confirm_update_with_local_changes(name, repo_path, assume_yes=assume_yes)
        try:
            subprocess_check_output(["git", "checkout", "--quiet", repo.branch], cwd=repo_path)
        except subprocess.CalledProcessError:
            git_update_error(name, repo_path, f"checkout {repo.branch} in")
            raise SetupError
        try:
            git_pull(repo_path)
        except subprocess.CalledProcessError:
            git_update_error(name, repo_path, "fast-forward")
            raise SetupError
        # Use specific Tag (Optional).
        checked_out = False
        if repo.tag is not None:
            # Priority to passed tag (if specified).
            if tag is not None:
                try:
                    git_checkout(tag=tag, quiet=True, cwd=repo_path)
                except subprocess.CalledProcessError:
                    git_update_error(name, repo_path, f"checkout tag {tag} in")
                    raise SetupError
                checked_out = True
            # Else fallback to repo tag (if specified).
            elif isinstance(repo.tag, str):
                try:
                    git_checkout(tag=repo.tag, quiet=True, cwd=repo_path)
                except subprocess.CalledProcessError:
                    git_update_error(name, repo_path, f"checkout tag {repo.tag} in")
                    raise SetupError
                checked_out = True
        # Use specific SHA1 (Optional).
        if not checked_out and repo.sha1 is not None:
            try:
                git_checkout(sha1=repo.sha1, quiet=True, cwd=repo_path)
            except subprocess.CalledProcessError:
                git_update_error(name, repo_path, f"checkout SHA1 {git_format_sha1(repo.sha1)} in")
                raise SetupError
        # Recursive Update (Optional).
        if repo.clone == "recursive":
            git_update_submodules(name, repo_path, git_update_error)

# Git repositories install -------------------------------------------------------------------------

def pip_install_cmd(packages, user_mode=False, editable=False, no_build_isolation=False):
    pip_cmd = [sys.executable, "-m", "pip", "install"]
    if no_build_isolation:
        pip_cmd.append("--no-build-isolation")
    if editable:
        pip_cmd.append("--editable")
    pip_cmd += packages
    if user_mode:
        pip_cmd.append("--user")
    return pip_cmd

def pip_install_in_virtualenv():
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)

def pip_install_externally_managed():
    if pip_install_in_virtualenv():
        return False
    marker = os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")
    return os.path.exists(marker)

def pip_install_externally_managed_error(user_mode=False):
    print_error("This Python environment is externally managed (PEP 668).")
    print_status("LiteX Setup will not override the system package manager by default.")
    print_status("Recommended options:")
    print_status("  python3 -m venv ~/litex-venv")
    print_status("  source ~/litex-venv/bin/activate")
    print_status("  ./litex_setup.py --init --install")
    if user_mode:
        print_status("On recent Debian/Ubuntu releases, --user installs are also blocked outside a venv.")
    print_status("If you knowingly want pip's override, rerun with --break-system-packages.")

def pip_install_externally_managed_check(user_mode=False, break_system_packages=False):
    if pip_install_externally_managed() and not break_system_packages:
        pip_install_externally_managed_error(user_mode=user_mode)
        raise SetupError

def pip_install_user_mode_check(user_mode=False):
    if user_mode and pip_install_in_virtualenv():
        print_warning("--user ignored since LiteX Setup is running inside a virtual environment.")
        return False
    return user_mode

def pip_install_pythonpath(source_path=None):
    if source_path is None:
        return None
    pythonpath = os.environ.get("PYTHONPATH")
    if pythonpath:
        return os.pathsep.join([source_path, pythonpath])
    return source_path

def pip_install_env(source_path=None):
    pythonpath = pip_install_pythonpath(source_path)
    if pythonpath is None:
        return None
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath
    return env

def pip_install_cmd_str(
    packages,
    user_mode=False,
    editable=False,
    no_build_isolation=False,
    source_path=None,
    break_system_packages=False,
):
    pip_cmd = pip_install_cmd(
        packages,
        user_mode          = user_mode,
        editable           = editable,
        no_build_isolation = no_build_isolation,
    )
    if break_system_packages:
        pip_cmd.append("--break-system-packages")
    cmd = " ".join(shlex.quote(str(arg)) for arg in pip_cmd)
    pythonpath = pip_install_pythonpath(source_path)
    if pythonpath is not None:
        cmd = f"PYTHONPATH={shlex.quote(pythonpath)} {cmd}"
    return cmd

def _pip_install(
    packages,
    user_mode=False,
    editable=False,
    no_build_isolation=False,
    source_path=None,
    break_system_packages=False,
):
    pip_cmd = pip_install_cmd(
        packages,
        user_mode          = user_mode,
        editable           = editable,
        no_build_isolation = no_build_isolation,
    )
    if break_system_packages:
        pip_cmd.append("--break-system-packages")
    subprocess.check_call(pip_cmd, env=pip_install_env(source_path))

def pip_install_error(
    description,
    packages,
    user_mode=False,
    editable=False,
    no_build_isolation=False,
    source_path=None,
    break_system_packages=False,
):
    print_error(f"{description} could not be installed.")
    print_status("Try:")
    pip_cmd = pip_install_cmd_str(
        packages,
        user_mode          = user_mode,
        editable           = editable,
        no_build_isolation = no_build_isolation,
        source_path        = source_path,
        break_system_packages = break_system_packages,
    )
    print_status(f"  {pip_cmd}")

def pip_install_build_dependencies(user_mode=False, break_system_packages=False):
    build_packages = [
        "setuptools>=65.5",
        "wheel",
    ]
    print_status("Installing Python build dependencies...")
    try:
        _pip_install(
            build_packages,
            user_mode             = user_mode,
            break_system_packages = break_system_packages,
        )
    except subprocess.CalledProcessError:
        pip_install_error(
            "Python build dependencies",
            build_packages,
            user_mode             = user_mode,
            break_system_packages = break_system_packages,
        )
        raise SetupError

def litex_setup_install_repos(config="standard", user_mode=False, break_system_packages=False):
    print_status("Installing Git repositories...", underline=True)
    user_mode = pip_install_user_mode_check(user_mode)
    litex_setup_check_initialized_repos(config=config, develop_only=True, retry="install")
    pip_install_externally_managed_check(
        user_mode             = user_mode,
        break_system_packages = break_system_packages,
    )
    pip_install_build_dependencies(
        user_mode             = user_mode,
        break_system_packages = break_system_packages,
    )
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        # Install Repo.
        if repo.develop:
            print_status(f"Installing {name} Git repository...")
            repo_path = os.path.join(current_path, name)
            if not git_is_repository(repo_path):
                print_error(f"{name} Git repository is not initialized, please run --init first.")
                raise SetupError
            os.chdir(repo_path)
            pip_install_externally_managed_check(
                user_mode             = user_mode,
                break_system_packages = break_system_packages,
            )
            try:
                _pip_install(
                    ["."],
                    user_mode          = user_mode,
                    editable           = repo.editable,
                    no_build_isolation = True,
                    source_path        = repo_path,
                    break_system_packages = break_system_packages,
                )
            except subprocess.CalledProcessError:
                pip_install_error(
                    f"{name} Git repository",
                    ["."],
                    user_mode          = user_mode,
                    editable           = repo.editable,
                    no_build_isolation = True,
                    source_path        = repo_path,
                    break_system_packages = break_system_packages,
                )
                raise SetupError

    # Install optional Python dependencies.
    if config in ["standard", "full"]:
        luna_packages = [
            "luna-usb==0.2.3",
            "amaranth==0.5.8",
        ]
        amaranth_packages = [
            "git+https://github.com/amaranth-lang/amaranth-soc.git",
            "m5pre",
            "m5meta",
            "dataclasses-json==0.6.3",
        ]

        print_status("Installing optional LUNA ACM Python dependencies...")
        pip_install_externally_managed_check(
            user_mode             = user_mode,
            break_system_packages = break_system_packages,
        )
        try:
            _pip_install(luna_packages, user_mode=user_mode, break_system_packages=break_system_packages)
        except subprocess.CalledProcessError:
            pip_install_error(
                "Optional LUNA ACM dependencies",
                luna_packages,
                user_mode=user_mode,
                break_system_packages=break_system_packages,
            )
            print_status("USB ACM via LUNA may not be usable until dependencies are installed manually.")

        print_status("Installing optional Amaranth CPU Python dependencies...")
        try:
            _pip_install(amaranth_packages, user_mode=user_mode, break_system_packages=break_system_packages)
        except subprocess.CalledProcessError:
            pip_install_error(
                "Optional Amaranth CPU dependencies",
                amaranth_packages,
                user_mode=user_mode,
                break_system_packages=break_system_packages,
            )
            print_status(
                "Amaranth-based CPUs (ex: Minerva/Sentinel) may not be usable "
                "until dependencies are installed manually."
            )
    if user_mode:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print_status("Make sure that ~/.local/bin is in your PATH.")
            print_status("export PATH=$PATH:~/.local/bin # temporary (limited to the current terminal)")
            print_status("or add the previous line into your ~/.bashrc to permanently update PATH")

# Git repositories freeze --------------------------------------------------------------------------

def litex_setup_freeze_repo(name):
    repo      = git_repos[name]
    repo_path = os.path.join(current_path, name)
    if not os.path.exists(repo_path):
        print_error(f"{name} Git repository is not initialized.")
        raise SetupError
    git_sha1_cmd = ["git", "rev-parse", "HEAD"]
    git_sha1     = subprocess.check_output(git_sha1_cmd, cwd=repo_path).decode("UTF-8")[:-1]
    git_url_cmd  = ["git", "remote", "get-url", "origin"]
    git_url      = subprocess.check_output(git_url_cmd, cwd=repo_path).decode("UTF-8")[:-1]
    git_url      = git_url.replace(f"{name}.git", "")
    return repo, git_url, git_sha1

def litex_setup_format_frozen_repo(name, repo, git_url, git_sha1):
    args = [f'url="{git_url}"']
    if repo.clone != "regular":
        args.append(f'clone="{repo.clone}"')
    if repo.develop is not True:
        args.append(f"develop={repo.develop}")
    if repo.editable is not True:
        args.append(f"editable={repo.editable}")
    args.append(f'sha1="{git_sha1}"')
    if repo.branch != "master":
        args.append(f'branch="{repo.branch}"')
    if repo.tag is not None:
        args.append(f"tag={repr(repo.tag)}")
    return f'    "{name}": GitRepo({", ".join(args)}),'

def litex_setup_format_frozen_repos(config="standard"):
    names = install_configs[config]
    r = [
        "#!/usr/bin/env python3",
        "",
        "# Git repositories ---------------------------------------------------------------------------------",
        "",
        "# Get SHA1: git rev-parse HEAD",
        "",
        "class GitRepo:",
        '    def __init__(self, url, clone="regular", develop=True, editable=True, sha1=None, branch="master",',
        '        tag=None):',
        '        assert clone in ["regular", "recursive"]',
        "        self.url      = url",
        "        self.clone    = clone",
        "        self.develop  = develop",
        "        self.editable = editable",
        "        self.sha1     = sha1",
        "        self.branch   = branch",
        "        self.tag      = tag",
        "",
        "",
        "git_repos = {",
    ]
    for name in names:
        repo, git_url, git_sha1 = litex_setup_freeze_repo(name)
        r.append(litex_setup_format_frozen_repo(name, repo, git_url, git_sha1))
    r += [
        "}",
        "",
        "# Installs -----------------------------------------------------------------------------------------",
        "",
        f"frozen_repos = {names!r}",
        "",
        "# Reuse the frozen set for every install config.",
        "minimal_repos  = frozen_repos",
        "standard_repos = frozen_repos",
        "full_repos     = frozen_repos",
        "",
        "install_configs = {",
        '    "minimal"  : minimal_repos,',
        '    "standard" : standard_repos,',
        '    "full"     : full_repos,',
        "}",
        "",
    ]
    return "\n".join(r)

def litex_setup_freeze_repos(config="standard", output=None):
    print_status("Freezing config of Git repositories...", underline=True)
    r = litex_setup_format_frozen_repos(config=config)
    if output is None:
        print(r)
    else:
        with open(output, "w", encoding="utf-8") as f:
            f.write(r)
        print_status(f"Frozen repository definitions written to {output}.")

# GCC toolchains install ---------------------------------------------------------------------------

def _read_os_release():
    with open("/etc/os-release", "r", encoding="utf-8") as f:
        return f.read().lower()

def toolchain_install_cmd(toolchain, cmd):
    try:
        subprocess.check_call(cmd)
    except FileNotFoundError:
        print_error(f"{cmd[0]} was not found while installing the {toolchain} GCC toolchain.")
        print_status("Install the toolchain manually or use a supported package manager.")
        raise SetupError
    except subprocess.CalledProcessError:
        print_error(f"{toolchain} GCC toolchain could not be installed.")
        print_status("Failed command:")
        print_status(f"  {' '.join(cmd)}")
        if sys.platform.startswith("linux"):
            print_status("You may need to run this command with sudo/root privileges.")
        print_status("Install the toolchain manually or rerun after fixing package-manager access.")
        raise SetupError

def toolchain_conda_install(toolchain, package):
    conda = shutil.which("mamba") or shutil.which("conda")
    if conda is None:
        return False
    toolchain_install_cmd(toolchain, [
        conda,
        "install",
        "-y",
        "-c", "litex-hub",
        "-c", "conda-forge",
        package,
    ])
    return True

def toolchain_manual_install(toolchain, hint=None):
    print_error(f"{toolchain} GCC requires manual installation on {sys.platform}.")
    if hint is not None:
        print_status(hint)
    raise SetupError

# RISC-V toolchain.
# -----------------

def riscv_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = _read_os_release()
        # Fedora.
        if "fedora" in os_release:
            toolchain_install_cmd("RISC-V", ["dnf", "install", "gcc-riscv64-linux-gnu"])
        # Arch.
        elif "arch" in os_release:
            toolchain_install_cmd("RISC-V", ["pacman", "-S", "riscv64-linux-gnu-gcc"])
        # Alpine.
        elif "alpine" in os_release:
            toolchain_install_cmd("RISC-V", ["apk", "add", "gcc-cross-embedded"])
        # Ubuntu.
        else:
            toolchain_install_cmd("RISC-V", ["apt", "install", "gcc-riscv64-unknown-elf"])

    # Mac OS.
    # -------
    elif sys.platform.startswith("darwin"):
        toolchain_install_cmd("RISC-V", ["brew", "install", "riscv64-elf-gcc"])

    # Manual installation.
    # --------------------
    else:
        toolchain_manual_install("RISC-V")

# MIPS toolchain.
# -----------------

def mips_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = _read_os_release()
        # Fedora.
        if "fedora" in os_release:
            toolchain_install_cmd("MIPS", ["dnf", "install", "gcc-mips64-linux-gnu"])
        # Arch (AUR repository).
        elif "arch" in os_release:
            toolchain_install_cmd("MIPS", ["yay", "-S", "mipsel-linux-gnu-gcc"])
        # Ubuntu.
        else:
            toolchain_install_cmd("MIPS", ["apt", "install", "gcc-mipsel-linux-gnu"])

    # Manual installation.
    # --------------------
    else:
        toolchain_manual_install("MIPS")

# PowerPC toolchain.
# -----------------

def powerpc_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = _read_os_release()
        # Fedora.
        if "fedora" in os_release:
            toolchain_install_cmd("PowerPC", ["dnf", "install", "gcc-powerpc64le-linux-gnu"]) # FIXME: binutils-multiarch?
        # Arch (AUR repository).
        elif "arch" in os_release:
            toolchain_install_cmd("PowerPC", ["yay", "-S", "powerpc64le-linux-gnu-gcc"])
        # Alpine.
        elif "alpine" in os_release:
            toolchain_install_cmd("PowerPC", ["apk", "add", "gcc", "binutils-ppc64le"])
        # Ubuntu.
        else:
            toolchain_install_cmd("PowerPC", ["apt", "install", "gcc-powerpc64le-linux-gnu", "binutils-multiarch"])

    # Manual installation.
    # --------------------
    else:
        toolchain_manual_install("PowerPC")

# OpenRISC toolchain.
# -------------------

def openrisc_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = _read_os_release()
        # Fedora.
        if "fedora" in os_release:
            toolchain_install_cmd("OpenRISC", ["dnf", "install", "gcc-or1k-elf"])
        # Arch.
        elif "arch" in os_release:
            toolchain_install_cmd("OpenRISC", ["pacman", "-S", "or1k-elf-gcc"])
        # Alpine.
        elif "alpine" in os_release:
            toolchain_install_cmd("OpenRISC", ["apk", "add", "gcc-cross-embedded"])
        # Ubuntu.
        else:
            toolchain_install_cmd("OpenRISC", ["apt", "install", "gcc-or1k-elf"])

    # Manual installation.
    # --------------------
    else:
        toolchain_manual_install("OpenRISC")

# LM32 toolchain.
# ---------------

def lm32_gcc_install():
    conda_hint = (
        "Try with Conda/Mamba: "
        "conda install -c litex-hub -c conda-forge gcc-lm32-elf-newlib"
    )

    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = _read_os_release()
        # Arch.
        if "arch" in os_release:
            toolchain_install_cmd("LM32", ["pacman", "-S", "lm32-elf-gcc"])
        # Conda/Mamba fallback.
        elif not toolchain_conda_install("LM32", "gcc-lm32-elf-newlib"):
            toolchain_manual_install("LM32", hint=conda_hint)

    # Mac OS.
    # -------
    elif sys.platform.startswith("darwin"):
        if not toolchain_conda_install("LM32", "gcc-lm32-elf-newlib"):
            toolchain_manual_install("LM32", hint=conda_hint)

    # Manual installation.
    # --------------------
    else:
        toolchain_manual_install("LM32", hint=conda_hint)

# Run ----------------------------------------------------------------------------------------------

def main():
    print_banner()
    parser = argparse.ArgumentParser()

    # Git Repositories.
    parser.add_argument("--init",      action="store_true", help="Initialize Git repositories.")
    parser.add_argument("--update",    action="store_true", help="Update Git repositories.")
    parser.add_argument("--install",   action="store_true", help="Install Git repositories.")
    parser.add_argument("--user",      action="store_true", help="Install in User-Mode.")
    parser.add_argument("--break-system-packages", action="store_true",
        help="Pass pip's --break-system-packages option when installing outside a virtual environment.")
    parser.add_argument("--config",    default="standard",  help="Install config (minimal, standard, full).")
    parser.add_argument("--tag",       default=None,        help="Use version from release tag.")
    parser.add_argument("-y", "--yes", action="store_true",
        help="Automatically confirm updates for repositories with local changes.")
    parser.add_argument("--clone-depth", type=int, default=None,
        help="Use shallow Git clones with this depth during --init when compatible.")

    # GCC toolchains.
    parser.add_argument("--gcc", default=None, choices=["riscv", "mips", "powerpc", "openrisc", "lm32"],
        help="Install GCC Toolchain (riscv, mips, powerpc, openrisc or lm32).")

    # Development mode.
    parser.add_argument("--dev",            action="store_true",
        help="Development-Mode (no Auto-Update of litex_setup.py / Switch to git@github.com URLs).")
    parser.add_argument("--freeze",         action="store_true", help="Freeze and display current config.")
    parser.add_argument("--freeze-output",  default=None,        help="Write frozen repository definitions to file.")

    # Retro-compatibility.
    parser.add_argument("compat_args", nargs="*", help="Retro-Compatibility arguments (init, update, install or gcc).")
    args = parser.parse_args()

    # Handle compat_args.
    if args.compat_args is not None:
        for arg in args.compat_args:
            if arg in ["init", "update", "install"]:
                setattr(args, arg, True)
            if arg in ["gcc"]:
                args.gcc = "riscv"

    # Location/Auto-Update.
    litex_setup_location_check()
    if not args.dev:
        litex_setup_auto_update()
    if args.init or args.update or args.install or args.freeze:
        if not args.dev:
            litex_setup_update_repos_file()
        litex_setup_import_repos(download=not args.dev)
        litex_setup_validate_config(args.config)

    # Init.
    if args.init:
        ci_run   = (os.environ.get("GITHUB_ACTIONS") == "true")
        dev_mode = args.dev and (not ci_run)
        litex_setup_init_repos(
            config      = args.config,
            tag         = args.tag,
            dev_mode    = dev_mode,
            clone_depth = args.clone_depth,
        )

    # Update.
    if args.update:
        litex_setup_update_repos(config=args.config, tag=args.tag, assume_yes=args.yes)

    # Install.
    if args.install:
        litex_setup_install_repos(
            config                = args.config,
            user_mode             = args.user,
            break_system_packages = args.break_system_packages,
        )

    # Freeze.
    if args.freeze:
        litex_setup_freeze_repos(config=args.config, output=args.freeze_output)

    # GCC.
    os.chdir(os.path.join(current_path))
    if args.gcc == "riscv":
        riscv_gcc_install()
    if args.gcc == "mips":
        mips_gcc_install()
    if args.gcc == "powerpc":
        powerpc_gcc_install()
    if args.gcc == "openrisc":
        openrisc_gcc_install()
    if args.gcc == "lm32":
        lm32_gcc_install()

def run():
    try:
        main()
    except SetupError:
        sys.exit(1)
    except KeyboardInterrupt:
        print_status("Cancelled.")
        sys.exit(130)

if __name__ == "__main__":
    run()
