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
    for root in manifest.get("roots", []) + manifest.get("input_dirs", []):
        root_path = root["path"]
        root_extract = os.path.join(extract_dir, root["archive_path"])
        if abs_path is not None and _is_subpath(abs_path, root_path):
            rel = os.path.relpath(abs_path, root_path)
            return os.path.join(root_extract, rel)

    for record in manifest.get("files", []):
        if abs_path is not None and abs_path == record["path"]:
            return os.path.join(extract_dir, record["archive_path"])

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


def _mapped_replay_pythonpath(manifest, extract_dir):
    pythonpath = []
    for root in manifest.get("pythonpath", []):
        path = os.path.join(extract_dir, root["archive_path"])
        if os.path.isdir(path) and path not in pythonpath:
            pythonpath.append(path)
    return pythonpath


def _mapped_replay_path_map(manifest, extract_dir):
    path_map = []
    roots = manifest.get("roots", []) + manifest.get("input_dirs", [])
    for root in roots:
        path_map.append({
            "kind"  : "root",
            "path"  : root["path"],
            "mapped": os.path.join(extract_dir, root["archive_path"]),
        })

    for record in manifest.get("files", []):
        if any(_is_subpath(record["path"], root["path"]) for root in roots):
            continue
        path_map.append({
            "kind"  : "file",
            "path"  : record["path"],
            "mapped": os.path.join(extract_dir, record["archive_path"]),
        })

    return path_map


def _mapped_replay_env(manifest, extract_dir):
    env = os.environ.copy()
    env.update(manifest.get("env", {}))

    if "PYTHONPATH" in env:
        paths = env["PYTHONPATH"].split(os.pathsep)
        env["PYTHONPATH"] = os.pathsep.join(
            _map_path_to_extract(path, manifest, extract_dir)
            for path in paths
        )

    pythonpath = _mapped_replay_pythonpath(manifest, extract_dir)
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    path_map = _mapped_replay_path_map(manifest, extract_dir)
    if path_map:
        env["LITEX_BUILD_BUNDLE_PATH_MAP"] = json.dumps(path_map, sort_keys=True)
    env["LITEX_BUILD_BUNDLE_REPLAY"] = "1"
    return env


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
    from litex.build.bundle import BuildBundle, get_pythonpath_roots

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
    for root in getattr(args, "pythonpath_root", []) or []:
        bundle.add_pythonpath(root, role="pythonpath")
    if not getattr(args, "no_auto_pythonpath", False):
        for root in get_pythonpath_roots():
            bundle.add_pythonpath(root, role="pythonpath_auto")

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

        return subprocess.call(
            command,
            cwd = _mapped_replay_cwd(manifest, extract_dir),
            env = _mapped_replay_env(manifest, extract_dir),
        )
    finally:
        if owns_work_dir:
            shutil.rmtree(work_dir)


# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX build input bundle utility.")
    parser.add_argument("--output",             "-o", default=None,              help="Output archive path.")
    parser.add_argument("--output-dir",              default="build",           help="Output directory used when --output is omitted.")
    parser.add_argument("--root",                    action="append", default=[], help="Directory root to archive.")
    parser.add_argument("--include",                 action="append", default=[], help="Extra file/directory to archive.")
    parser.add_argument("--pythonpath-root",         action="append", default=[], help="Python import root to archive/prepend on replay.")
    parser.add_argument("--no-auto-pythonpath",      action="store_true",       help="Do not auto-bundle LiteX Python import roots.")
    parser.add_argument("--env",                     action="append", default=[], help="Environment variable to record/pass (KEY or KEY=VALUE).")
    parser.add_argument("--strict",                  default="warn", choices=["warn", "error"], help="Missing input handling.")
    parser.add_argument("--run-local",               default=None,              help="Replay an existing bundle locally.")
    parser.add_argument("--work-dir",                default=None,              help="Replay work directory.")
    parser.add_argument("command",                   nargs=argparse.REMAINDER,  help="Command to record in the bundle, usually after '--'.")
    args = parser.parse_args()

    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if args.run_local is not None:
        sys.exit(run_local(args.run_local, work_dir=args.work_dir))

    result = create_bundle(args)
    print(result["archive"])


if __name__ == "__main__":
    main()
