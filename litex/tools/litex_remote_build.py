#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import sys
import json
import time
import shlex
import argparse
import subprocess
from types import SimpleNamespace

from litex.tools.litex_build_bundle import create_bundle


# Helpers ------------------------------------------------------------------------------------------

def _ssh_command(host, command, pty="auto"):
    ssh = ["ssh"]
    if pty == "yes" or (pty == "auto" and sys.stdin.isatty()):
        ssh.append("-t")
    elif pty == "no":
        ssh.append("-T")
    ssh += [host, command]
    return ssh


def _run_ssh(host, command, pty="auto", check=True):
    rc = subprocess.call(_ssh_command(host, command, pty=pty))
    if check and rc != 0:
        raise OSError(f"SSH command failed with exit code {rc}.")
    return rc


def _upload(host, local_path, remote_path):
    subprocess.check_call(["scp", local_path, f"{host}:{remote_path}"])


def _download(host, remote_path, local_path):
    subprocess.check_call(["scp", "-r", f"{host}:{remote_path}", local_path])


def _load_manifest(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def _default_job_name(archive_path):
    base = os.path.basename(archive_path)
    for suffix in [".tar.gz", ".tgz"]:
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("._") or "bundle"
    return f"{base}-{int(time.time())}"


def _remote_join(first, *parts):
    path = first.rstrip("/")
    for part in parts:
        if part:
            path += "/" + part.strip("/")
    return path


def _first_replay_root(manifest):
    roots = manifest.get("roots", [])
    return roots[0]["archive_path"] if roots else ""


def _create_archive_from_command(args):
    bundle_args = SimpleNamespace(
        output     = None,
        output_dir = args.output_dir,
        root       = args.root,
        include    = args.include,
        env        = args.env,
        strict     = args.strict,
        command    = args.command,
    )
    return create_bundle(bundle_args)


# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run a LiteX build from a build bundle on a remote host.")
    parser.add_argument("--host",        required=True,             help="SSH host, for example user@server.")
    parser.add_argument("--remote-root", default="~/.cache/litex/remote-builds", help="Remote work root.")
    parser.add_argument("--archive",     default=None,              help="Existing build bundle archive to replay remotely.")
    parser.add_argument("--output-dir",  default="build",           help="Local bundle output directory when creating an archive.")
    parser.add_argument("--root",        action="append", default=[], help="Directory root to archive when creating a bundle.")
    parser.add_argument("--include",     action="append", default=[], help="Extra file/directory to archive when creating a bundle.")
    parser.add_argument("--env",         action="append", default=[], help="Environment variable to record/pass (KEY or KEY=VALUE).")
    parser.add_argument("--strict",      default="warn", choices=["warn", "error"], help="Missing input handling.")
    parser.add_argument("--sync-back",   action="append", default=["build"], help="Root-relative path to copy back.")
    parser.add_argument("--keep-remote", action="store_true",       help="Keep remote work directory after completion.")
    parser.add_argument("--pty",         default="auto", choices=["auto", "yes", "no"], help="SSH TTY allocation policy.")
    parser.add_argument("command",       nargs=argparse.REMAINDER,  help="Command to bundle/replay, usually after '--'.")
    args = parser.parse_args()

    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if args.archive is None:
        if not args.command:
            raise SystemExit("A command is required when --archive is not provided.")
        bundle_result = _create_archive_from_command(args)
        archive_path  = bundle_result["archive"]
        manifest_path = bundle_result["manifest"]
    else:
        archive_path  = os.path.abspath(args.archive)
        manifest_path = archive_path + ".manifest.json"
        if not os.path.exists(manifest_path):
            raise SystemExit(f"Missing bundle sidecar manifest: {manifest_path}")

    manifest = _load_manifest(manifest_path)
    job_name = _default_job_name(archive_path)
    remote_work    = _remote_join(args.remote_root, job_name)
    remote_archive = _remote_join(remote_work, "input.tar.gz")
    remote_replay  = _remote_join(remote_work, "replay")

    mkdir_cmd = "mkdir -p {}".format(shlex.quote(remote_work))
    _run_ssh(args.host, mkdir_cmd, pty="no")
    _upload(args.host, archive_path, remote_archive)

    replay_cmd = "python3 -m litex.tools.litex_build_bundle --run-local {} --work-dir {}".format(
        shlex.quote(remote_archive),
        shlex.quote(remote_replay),
    )
    rc = _run_ssh(args.host, replay_cmd, pty=args.pty, check=False)

    root = _first_replay_root(manifest)
    remote_root = _remote_join(remote_replay, "src", root)
    for path in args.sync_back:
        remote_path = _remote_join(remote_root, path)
        local_path  = os.path.abspath(path)
        try:
            _download(args.host, remote_path, local_path)
        except subprocess.CalledProcessError:
            print(f"Warning: unable to sync back {remote_path}.")

    if not args.keep_remote:
        rm_cmd = "rm -rf {}".format(shlex.quote(remote_work))
        _run_ssh(args.host, rm_cmd, pty="no", check=False)

    sys.exit(rc)


if __name__ == "__main__":
    main()
