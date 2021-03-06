#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse
from distutils.dir_util import copy_tree

def main():
    parser = argparse.ArgumentParser(description="LiteX Bare Metal Demo App.")
    parser.add_argument("--build-path", help="Target's build path (ex build/board_name).", required=True)
    parser.add_argument("--with-cxx",   action="store_true", help="Enable CXX support.")
    args = parser.parse_args()

    # Create demo directory
    os.makedirs("demo", exist_ok=True)

    # Copy contents to demo directory
    src = os.path.abspath(os.path.dirname(__file__))
    copy_tree(src, "demo")

    # Compile demo
    build_path = args.build_path if os.path.isabs(args.build_path) else os.path.join("..", args.build_path)
    os.system(f"export BUILD_DIR={build_path} && {'export WITH_CXX=1 &&' if args.with_cxx else ''} cd demo && make")

    # Copy demo.bin
    os.system("cp demo/demo.bin ./")

if __name__ == "__main__":
    main()

