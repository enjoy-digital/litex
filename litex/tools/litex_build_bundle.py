#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import json
import shutil
import tarfile
import argparse
import tempfile
import subprocess

from litex.build.bundle import BuildBundle


# Helpers ------------------------------------------------------------------------------------------

def _parse_env(values):
    env = {}
    for value in values or []:
        if "=" in value:
            key, val = value.split("=", 1)
            env[key] = val
        elif value in os.environ:
            env[value] = os.environ[value]
    return env


def _is_subpath(path, root):
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _map_path_to_extract(path, manifest, extract_dir):
    if not path:
        return path

    abs_path = os.path.abspath(path) if os.path.isabs(path) else None
    for root in manifest.get("roots", []):
        root_path = root["path"]
        root_extract = os.path.join(extract_dir, root["archive_path"])
        if abs_path is not None and _is_subpath(abs_path, root_path):
            rel = os.path.relpath(abs_path, root_path)
            return os.path.join(root_extract, rel)

    return path


def _mapped_replay_cwd(manifest, extract_dir):
    cwd = manifest.get("cwd")
    if cwd:
        mapped = _map_path_to_extract(cwd, manifest, extract_dir)
        if mapped != cwd and os.path.isdir(mapped):
            return mapped

    roots = manifest.get("roots", [])
    if roots:
        root_cwd = os.path.join(extract_dir, roots[0]["archive_path"])
        if os.path.isdir(root_cwd):
            return root_cwd

    return extract_dir


def _mapped_replay_command(manifest, extract_dir):
    command = list(manifest.get("command") or [])
    return [_map_path_to_extract(arg, manifest, extract_dir) for arg in command]


def _safe_extractall(archive, path):
    path = os.path.abspath(path)
    for member in archive.getmembers():
        target = os.path.abspath(os.path.join(path, member.name))
        if not _is_subpath(target, path):
            raise OSError(f"Unsafe path in bundle archive: {member.name}")
        if member.issym() or member.islnk():
            if os.path.isabs(member.linkname):
                raise OSError(f"Unsafe link in bundle archive: {member.name}")
            link_target = os.path.abspath(os.path.join(os.path.dirname(target), member.linkname))
            if not _is_subpath(link_target, path):
                raise OSError(f"Unsafe link in bundle archive: {member.name}")
    archive.extractall(path)


def create_bundle(args):
    env = _parse_env(args.env)
    bundle = BuildBundle(
        output_dir   = args.output_dir,
        archive_path = args.output,
        command      = args.command,
        env          = env,
        strict       = args.strict,
    )

    roots = args.root if args.root else [os.getcwd()]
    for root in roots:
        bundle.add_root(root, role="bundle_root")
    for path in args.include:
        bundle.add_path(path, role="bundle_include")

    return bundle.create()


def run_local(archive_path, work_dir=None):
    archive_path = os.path.abspath(archive_path)
    owns_work_dir = False
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="litex-bundle-")
        owns_work_dir = True
    else:
        work_dir = os.path.abspath(work_dir)
        os.makedirs(work_dir, exist_ok=True)

    try:
        extract_dir = os.path.join(work_dir, "src")
        os.makedirs(extract_dir, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extractall(archive, extract_dir)

        with open(os.path.join(extract_dir, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)

        command = _mapped_replay_command(manifest, extract_dir)
        if not command:
            raise OSError("Bundle does not contain a replay command.")

        env = os.environ.copy()
        env.update(manifest.get("env", {}))
        env["LITEX_BUILD_BUNDLE_REPLAY"] = "1"

        return subprocess.call(command, cwd=_mapped_replay_cwd(manifest, extract_dir), env=env)
    finally:
        if owns_work_dir:
            shutil.rmtree(work_dir)


# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX build input bundle utility.")
    parser.add_argument("--output", "-o", default=None,              help="Output archive path.")
    parser.add_argument("--output-dir",  default="build",           help="Output directory used when --output is omitted.")
    parser.add_argument("--root",        action="append", default=[], help="Directory root to archive.")
    parser.add_argument("--include",     action="append", default=[], help="Extra file/directory to archive.")
    parser.add_argument("--env",         action="append", default=[], help="Environment variable to record/pass (KEY or KEY=VALUE).")
    parser.add_argument("--strict",      default="warn", choices=["warn", "error"], help="Missing input handling.")
    parser.add_argument("--run-local",   default=None,              help="Replay an existing bundle locally.")
    parser.add_argument("--work-dir",    default=None,              help="Replay work directory.")
    parser.add_argument("command",       nargs=argparse.REMAINDER,  help="Command to record in the bundle, usually after '--'.")
    args = parser.parse_args()

    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if args.run_local is not None:
        sys.exit(run_local(args.run_local, work_dir=args.work_dir))

    result = create_bundle(args)
    print(result["archive"])


if __name__ == "__main__":
    main()
