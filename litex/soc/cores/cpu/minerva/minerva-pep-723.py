#
# This file is part of LiteX.
#
# Copyright (c) 2025 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

"""PEP-723-aware script for installing Minerva."""

# Deps must be kept in sync with Minerva's pyproject.toml.
# /// script
# requires-python = "~=3.8"
# dependencies = [
#     "amaranth[builtin-yosys]<0.6,>=0.5",
#     "amaranth_soc @ git+https://github.com/amaranth-lang/amaranth-soc",
#     "yowasp-yosys",
# ]
# ///

import os
import sys
from pathlib import Path

# Must be run from Minerva's source root.
sys.path += [str(Path(os.getcwd())), str(Path(os.getcwd()) / "minerva")]

import cli  # noqa: E402

if __name__ == "__main__":
    cli.main()
