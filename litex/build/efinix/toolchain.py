#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from pathlib import Path
from shutil import which


EFINITY_TOOLCHAIN_ERROR = "Unable to find or source Efinity toolchain, please either:\n"
EFINITY_TOOLCHAIN_ERROR += "- Set LITEX_ENV_EFINITY environment variable to the Efinity path.\n"
EFINITY_TOOLCHAIN_ERROR += "- Or add Efinity toolchain to your $PATH."


def find_efinity_path():
    efinity_path = os.getenv("LITEX_ENV_EFINITY")
    if efinity_path:
        return efinity_path.rstrip("/")

    for tool in ("efx_map", "efx_pnr", "efx_run.py"):
        tool_path = which(tool)
        if tool_path is None:
            continue
        root = Path(tool_path).resolve().parent.parent
        if (root / "bin" / "setup.sh").is_file():
            return str(root)

    raise OSError(EFINITY_TOOLCHAIN_ERROR)


def load_efinity_env(efinity_path):
    command = '. "%s" && env -0' % os.path.join(efinity_path, "bin", "setup.sh")
    pipe = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        shell=True,
        cwd=efinity_path,
        executable="/bin/bash",
    )
    output = pipe.communicate()[0].decode("utf-8")
    if pipe.returncode != 0:
        raise OSError(f"Error occurred while sourcing {efinity_path}/bin/setup.sh.")

    env = {}
    for line in output.rstrip("\x00").split("\x00"):
        if not line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env
