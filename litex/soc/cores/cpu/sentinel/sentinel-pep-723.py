#
# This file is part of LiteX.
#
# Copyright (c) 2025 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

"""PEP-723-aware script for installing Sentinel."""

# Deps must be kept in sync with Sentinel's pyproject.toml.
# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "m5meta>=1.0.4",
#    "m5pre>=1.0.3",
#    "amaranth[builtin-yosys]>=0.5.4",
#    "amaranth-soc @ git+https://github.com/amaranth-lang/amaranth-soc",
# ]
# ///

import os
import sys
from pathlib import Path

sys.path += [str(Path(os.getcwd()) / "src")]

import sentinel.gen  # noqa: E402

if __name__ == "__main__":
    sentinel.gen._main()
