#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import json
import subprocess
import argparse

import litex_repos
import litex_setup as setup

# Helpers ------------------------------------------------------------------------------------------

def print_banner():
    b  = []
    b.append("          __   _ __      _  __         ")
    b.append("         / /  (_) /____ | |/_/         ")
    b.append("        / /__/ / __/ -_)>  <           ")
    b.append("       /____/_/\\__/\\__/_/|_|         ")
    b.append("     Build your hardware, easily!      ")
    b.append("          LiteX Release utility.       ")
    b.append("")
    print("\n".join(b))

def get_current_tag(repo_path):
    try:
        cmd    = ["git", "describe", "--tags", "--abbrev=0"]
        result = subprocess.check_output(cmd, cwd=repo_path).decode("UTF-8").strip()
        return result
    except subprocess.CalledProcessError:
        return "No tags"

def get_setup_version(setup_path):
    try:
        with open(setup_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        return "No version found"
    except FileNotFoundError:
        return "No setup.py"

def check_release_tag(tag, allow_invalid_tag=False):
    if re.match(r"^\d{4}\.(04|08|12)$", tag):
        return
    if allow_invalid_tag:
        return
    setup.print_error(f"{tag} is not a valid LiteX release tag.")
    print("Expected YYYY.04, YYYY.08 or YYYY.12.")
    raise setup.SetupError

def release_repo_names(repos=None, with_pythondata=False):
    if repos:
        names = [name.strip() for name in repos.split(",") if name.strip()]
    else:
        names = [
            name for name in litex_repos.install_configs["full"]
            if (name != "migen") and (litex_repos.git_repos[name].tag is not None)
        ]
        if with_pythondata:
            for name in litex_repos.install_configs["full"]:
                if (name != "migen") and name.startswith("pythondata-") and name not in names:
                    names.append(name)
    for name in names:
        if name not in litex_repos.git_repos:
            setup.print_error(f"{name} is not a known repository.")
            raise setup.SetupError
        if name == "migen":
            setup.print_error("migen is not released by litex_release.py.")
            raise setup.SetupError
    return names

def git_output(repo_path, *args, check=True):
    cmd = ["git"] + list(args)
    try:
        return subprocess.check_output(cmd, cwd=repo_path, stderr=subprocess.STDOUT).decode("UTF-8").strip()
    except subprocess.CalledProcessError as e:
        if check:
            output = e.output.decode("UTF-8", errors="ignore").strip()
            setup.print_error(f"{repo_path}: {' '.join(cmd)} failed.")
            if output:
                print(output)
            raise setup.SetupError
        return None

def git_call(repo_path, *args):
    cmd = ["git"] + list(args)
    subprocess.check_call(cmd, cwd=repo_path)

# Release State ------------------------------------------------------------------------------------

def release_state_filename(tag):
    safe_tag = tag.replace("/", "_").replace("\\", "_")
    return f".litex_release_{safe_tag}.json"

def init_release_state(tag, phases, states):
    repos = []
    for state in states:
        repo = {
            "name"          : state["name"],
            "path"          : state["repo_path"],
            "branch"        : state["branch"],
            "upstream"      : state["upstream"],
            "last_tag"      : state["last_tag"],
            "setup_version" : state["setup_version"],
            "head_before"   : None,
        }
        if state["exists"]:
            repo["head_before"] = git_output(state["repo_path"], "rev-parse", "HEAD", check=False)
        repos.append(repo)
    return {
        "tag"              : tag,
        "phases"           : phases,
        "completed_phases" : [],
        "repositories"     : repos,
        "events"           : [],
    }

def save_release_state(state_file, release_state):
    if state_file is None:
        return
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(release_state, f, indent=2, sort_keys=True)
        f.write("\n")

def add_release_event(release_state, state_file, phase, repo, commit=None, tag=None):
    if release_state is None:
        return
    event = {
        "phase" : phase,
        "repo"  : repo,
    }
    if commit is not None:
        event["commit"] = commit
    if tag is not None:
        event["tag"] = tag
    release_state["events"].append(event)
    save_release_state(state_file, release_state)

def complete_release_phase(release_state, state_file, phase):
    if release_state is None:
        return
    if phase not in release_state["completed_phases"]:
        release_state["completed_phases"].append(phase)
    save_release_state(state_file, release_state)


# Release Checks -----------------------------------------------------------------------------------

def release_repo_state(name, tag):
    repo_path = os.path.join(setup.current_path, name)
    state = {
        "name"                    : name,
        "repo_path"               : repo_path,
        "exists"                  : os.path.exists(repo_path),
        "last_tag"                : "Not initialized",
        "setup_version"           : "Not initialized",
        "branch"                  : "Not initialized",
        "expected"                : litex_repos.git_repos[name].branch,
        "upstream"                : None,
        "ahead"                   : None,
        "behind"                  : None,
        "dirty"                   : False,
        "push_url"                : None,
        "local_tag"               : False,
        "remote_tag"              : False,
        "remote_tag_check_failed" : False,
    }
    if not state["exists"]:
        return state

    state["last_tag"]      = get_current_tag(repo_path)
    state["setup_version"] = get_setup_version(os.path.join(repo_path, "setup.py"))
    state["branch"]        = git_output(repo_path, "rev-parse", "--abbrev-ref", "HEAD", check=False) or "unknown"
    state["upstream"]      = git_output(repo_path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    state["dirty"]         = bool(git_output(repo_path, "status", "--porcelain", check=False))
    state["push_url"]      = git_output(repo_path, "remote", "get-url", "--push", "origin", check=False)
    state["local_tag"]     = git_output(repo_path, "rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False) is not None
    remote_tag             = git_output(repo_path, "ls-remote", "--tags", "origin", f"refs/tags/{tag}", check=False)
    state["remote_tag"]    = bool(remote_tag)
    state["remote_tag_check_failed"] = (remote_tag is None)
    if state["upstream"] is not None:
        counts = git_output(repo_path, "rev-list", "--left-right", "--count", "HEAD...@{u}", check=False)
        if counts is not None:
            ahead, behind = counts.split()
            state["ahead"]  = int(ahead)
            state["behind"] = int(behind)
    return state

def release_actions(state, tag, phases):
    actions = []
    if "bump" in phases:
        if state["setup_version"] in ["No setup.py", "No version found", "Not initialized"]:
            actions.append("no-bump")
        elif state["setup_version"] == tag:
            actions.append("bump-skip")
        else:
            actions.append("bump")
    if "tag" in phases:
        actions.append("tag")
    if "push" in phases:
        actions.append("push")
    return ",".join(actions) if actions else "check"

def print_release_summary(states, tag, phases):
    setup.print_status(f"Release {tag} plan...", underline=True)
    print(setup.colorer(
        "Repo".ljust(35) +
        "Branch".ljust(15) +
        "Upstream".ljust(25) +
        "Last Tag".ljust(15) +
        "Version".ljust(15) +
        "Actions"
    ))
    print("-" * 120)
    for state in states:
        upstream = state["upstream"] or "-"
        print(
            f"{state['name']:<35} "
            f"{state['branch']:<15} "
            f"{upstream:<25} "
            f"{state['last_tag']:<15} "
            f"{state['setup_version']:<15} "
            f"{release_actions(state, tag, phases)}"
        )

def check_release_state(states, tag, phases, allow_dirty=False, allow_branch_mismatch=False, allow_unpushed=False):
    errors = []
    for state in states:
        name = state["name"]
        if not state["exists"]:
            errors.append(f"{name}: repository is not initialized.")
            continue
        if state["dirty"] and not allow_dirty:
            errors.append(f"{name}: working tree is not clean.")
        if state["branch"] != state["expected"] and not allow_branch_mismatch:
            errors.append(f"{name}: on branch {state['branch']}, expected {state['expected']}.")
        if state["local_tag"] and "tag" in phases:
            errors.append(f"{name}: local tag {tag} already exists.")
        if state["remote_tag"] and ("tag" in phases or "push" in phases):
            errors.append(f"{name}: remote tag {tag} already exists.")
        if "push" in phases:
            if state["remote_tag_check_failed"]:
                errors.append(f"{name}: could not check remote tag {tag} on origin.")
            if state["push_url"] is None:
                errors.append(f"{name}: no push URL configured for origin.")
            if state["upstream"] is None and not allow_unpushed:
                errors.append(f"{name}: no upstream branch configured.")
            if state["behind"] not in [None, 0] and not allow_unpushed:
                errors.append(f"{name}: branch is behind upstream by {state['behind']} commit(s).")
            if state["ahead"] not in [None, 0] and "bump" in phases and not allow_unpushed:
                errors.append(f"{name}: branch is ahead of upstream by {state['ahead']} commit(s).")
            if "tag" not in phases and not state["local_tag"]:
                errors.append(f"{name}: local tag {tag} is missing.")
        if "bump" in phases:
            setup_path = os.path.join(state["repo_path"], "setup.py")
            if os.path.exists(setup_path) and state["setup_version"] == "No version found" and litex_repos.git_repos[name].tag is not None:
                errors.append(f"{name}: setup.py has no parseable version.")

    if errors:
        setup.print_error("Release checks failed:")
        for error in errors:
            print(f"  - {error}")
        raise setup.SetupError

def release_check_repos(repos=None, with_pythondata=False):
    names = release_repo_names(repos=repos, with_pythondata=with_pythondata)
    setup.print_status("Checking repositories for release...", underline=True)
    print(setup.colorer("Repo".ljust(35) + "Last Tag".ljust(17) + "Setup Version"))
    print("-" * 80)
    for name in names:
        repo_path = os.path.join(setup.current_path, name)
        if not os.path.exists(repo_path):
            last_tag      = "Not initialized"
            setup_version = "Not initialized"
        else:
            last_tag      = get_current_tag(repo_path)
            setup_version = get_setup_version(os.path.join(repo_path, "setup.py"))
        print(f"{name:<35} {last_tag:<15} {setup_version}")

def release_list_repos(repos=None, with_pythondata=False):
    names = release_repo_names(repos=repos, with_pythondata=with_pythondata)
    setup.print_status("Release repositories...", underline=True)
    for name in names:
        print(name)

# Release ------------------------------------------------------------------------------------------

def release_repos(tag, repos=None, with_pythondata=False, dry_run=False, phases=None,
    no_push=False, allow_dirty=False, allow_branch_mismatch=False, allow_unpushed=False,
    allow_invalid_tag=False, state_file=None):

    check_release_tag(tag, allow_invalid_tag=allow_invalid_tag)
    phases = phases or ["bump", "tag", "push"]
    if no_push and "push" in phases:
        phases.remove("push")
    names = release_repo_names(repos=repos, with_pythondata=with_pythondata)
    states = [release_repo_state(name, tag) for name in names]

    print_release_summary(states, tag, phases)
    check_release_state(
        states,
        tag,
        phases,
        allow_dirty            = allow_dirty,
        allow_branch_mismatch = allow_branch_mismatch,
        allow_unpushed         = allow_unpushed,
    )

    if dry_run:
        setup.print_status("Dry-run complete, no repository was modified.")
        return

    setup.print_status(f"Making release {tag}...", underline=True)
    confirm = input("Please confirm by pressing Y:")
    if confirm.upper() != "Y":
        setup.print_status("Not confirmed, exiting.")
        return

    release_state = None
    if state_file is not None:
        release_state = init_release_state(tag, phases, states)
        save_release_state(state_file, release_state)
        setup.print_status(f"Release state file: {state_file}")

    if "bump" in phases:
        for state in states:
            name      = state["name"]
            repo_path = state["repo_path"]
            os.chdir(repo_path)
            setup_path = os.path.join(repo_path, "setup.py")
            if not os.path.exists(setup_path):
                setup.print_status(f"No setup.py in {name}, skipping bump.")
                continue
            current_version = get_setup_version(setup_path)
            if current_version == "No version found":
                setup.print_status(f"No version in {name} setup.py, skipping bump.")
                continue
            if current_version == tag:
                setup.print_status(f"Version in {name} already at {tag}, skipping bump.")
                continue

            setup.print_status(f"Bumping version in {name} setup.py from {current_version} to {tag}...")
            with open(setup_path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = re.sub(r'version\s*=\s*["\'][^"\']+["\']', f'version = "{tag}"', content)
            with open(setup_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            git_call(repo_path, "add", "setup.py")
            git_call(repo_path, "commit", "-m", f"Bump to version {tag}")
            add_release_event(
                release_state,
                state_file,
                "bump",
                name,
                commit = git_output(repo_path, "rev-parse", "HEAD"),
            )
        complete_release_phase(release_state, state_file, "bump")

    if "tag" in phases:
        for state in states:
            name      = state["name"]
            repo_path = state["repo_path"]
            setup.print_status(f"Tagging {name} Git repository as {tag}...")
            git_call(repo_path, "tag", tag)
            add_release_event(release_state, state_file, "tag", name, tag=tag)
        complete_release_phase(release_state, state_file, "tag")

    if "push" in phases:
        for state in states:
            name      = state["name"]
            repo_path = state["repo_path"]
            setup.print_status(f"Pushing {name} Git repository...")
            git_call(repo_path, "push")
            git_call(repo_path, "push", "origin", tag)
            add_release_event(
                release_state,
                state_file,
                "push",
                name,
                commit = git_output(repo_path, "rev-parse", "HEAD"),
                tag    = tag,
            )
        complete_release_phase(release_state, state_file, "push")

def release_phases(args):
    phases = []
    if args.bump:
        phases.append("bump")
    if args.tag:
        phases.append("tag")
    if args.push:
        phases.append("push")
    if not phases:
        phases = ["bump", "tag", "push"]
    if args.no_push and "push" in phases:
        phases.remove("push")
    if args.no_push and args.push:
        setup.print_error("--no-push and --push cannot be used together.")
        raise setup.SetupError
    return phases


# Run ----------------------------------------------------------------------------------------------

def main():
    print_banner()
    parser = argparse.ArgumentParser()

    # Release repositories.
    parser.add_argument("--list-repos",      action="store_true", help="List repositories selected for release.")
    parser.add_argument("--check",           action="store_true", help="Check repositories before release.")
    parser.add_argument("--repos",           default=None,        help="Comma-separated release repository allow-list.")
    parser.add_argument("--with-pythondata", action="store_true", help="Also include pythondata repositories in the release set.")

    # Release flow.
    parser.add_argument("--release",       default=None,        help="Make release.")
    parser.add_argument("--dry-run",       action="store_true", help="Print release plan and checks without modifying repositories.")
    parser.add_argument("--no-push",       action="store_true", help="Create local release commits/tags without pushing.")
    parser.add_argument("--bump",          action="store_true", help="Run release version-bump phase.")
    parser.add_argument("--tag",           action="store_true", help="Run release tag phase.")
    parser.add_argument("--push",          action="store_true", help="Run release push phase.")

    # Release checks.
    parser.add_argument("--allow-invalid-tag",     action="store_true", help="Allow release tags outside YYYY.04/YYYY.08/YYYY.12.")
    parser.add_argument("--allow-dirty",           action="store_true", help="Allow dirty working trees during release.")
    parser.add_argument("--allow-branch-mismatch", action="store_true", help="Allow repositories to be on branches different from litex_setup.py defaults.")
    parser.add_argument("--allow-unpushed",        action="store_true", help="Allow repositories without clean upstream synchronization.")
    parser.add_argument("--state-file",            default=None,        help="Release state file path.")

    # Development mode.
    parser.add_argument("--dev", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Location.
    setup.litex_setup_location_check()

    # List.
    if args.list_repos:
        release_list_repos(
            repos=args.repos,
            with_pythondata=args.with_pythondata,
        )

    # Check.
    if args.check:
        release_check_repos(
            repos=args.repos,
            with_pythondata=args.with_pythondata,
        )

    # Release.
    if args.release:
        state_file = args.state_file
        if (state_file is None) and (not args.dry_run):
            state_file = os.path.abspath(release_state_filename(args.release))
        release_repos(
            tag                   = args.release,
            repos                 = args.repos,
            with_pythondata       = args.with_pythondata,
            dry_run               = args.dry_run,
            phases                = release_phases(args),
            no_push               = args.no_push,
            allow_dirty            = args.allow_dirty,
            allow_branch_mismatch = args.allow_branch_mismatch,
            allow_unpushed         = args.allow_unpushed,
            allow_invalid_tag      = args.allow_invalid_tag,
            state_file             = state_file,
        )
    elif args.dry_run or args.bump or args.tag or args.push or args.no_push:
        setup.print_error("--release is required with release action options.")
        raise setup.SetupError

if __name__ == "__main__":
    main()
