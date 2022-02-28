#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Mikołaj Sowiński <msowinski@technosystem.com.pl>
# SPDX-License-Identifier: BSD-2-Clause

# Small tool generate repo definitions overlay for litex_setup.

import os
import subprocess
import argparse
import json

# Freeze -------------------------------------------------------------------------------------------

def freeze(install_path, output=None, allow_dirty=False):
    dirs = [d for d in os.listdir(install_path) if os.path.isdir(d)]
    repos = {}
    for d in dirs:
        dir_path = os.path.join(install_path, d)
        # Check if directory is Git repo
        gitcmd = subprocess.run(['git', 'diff', '--stat'],
                                cwd=dir_path, capture_output=True)
        if gitcmd.returncode != 0:
            continue

        # Check if repo is clean
        if gitcmd.stdout and not allow_dirty:
            raise RuntimeError(f"Repository {d} is dirty!")

        # Get origin url
        gitcmd = subprocess.run(['git', 'remote', 'get-url', "origin"],
                                cwd=dir_path, capture_output=True)
        if gitcmd.returncode != 0:
            raise RuntimeError(f"Repository {d} has no remotes!")
        origin_url = gitcmd.stdout.decode().strip()

        # Get SHA1 of the current commit
        gitcmd = subprocess.run(['git', 'rev-parse', "--short=11", "HEAD"],
                                cwd=dir_path, capture_output=True)
        if gitcmd.returncode != 0:
            raise RuntimeError(f"Failed to get commit SHA1 for {d}")
        sha1 = gitcmd.stdout.decode().strip()

        # Store repo data
        repos[d] = {
            "url": origin_url,
            "sha1": sha1
        }

    # Output
    if output is None:
        print(json.dumps(repos, indent=4, sort_keys=True))
    else:
        with open(output, 'w+') as fp:
            json.dump(repos, fp, indent=4, sort_keys=True)

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Small tool generate repo definitions overlay for litex_setup.")
    parser.add_argument("--install-path", default="./", help="Path to the directory where repositories were installed.")
    parser.add_argument("--output", default=None, help="Output JSON path, defaults to stdout.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow freezing dirty repository.")
    args = parser.parse_args()

    freeze(install_path=args.install_path, output=args.output, allow_dirty=args.allow_dirty)

if __name__ == "__main__":
    main()