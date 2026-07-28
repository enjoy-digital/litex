#
# This file is part of LiteX.
#
# Copyright (c) 2026 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import shutil
import subprocess

from litex.build.tools import write_to_file

# Xilinx libxil ------------------------------------------------------------------------------------

EMBEDDEDSW_GIT_URL = "https://github.com/Xilinx/embeddedsw"
EMBEDDEDSW_ENV_VAR = "XILINX_EMBEDDEDSW"

HEADERS = {
    "zynq7000": [
        "XilinxProcessorIPLib/drivers/uartps/src/xuartps_hw.h",
        "lib/bsp/standalone/src/common/xil_types.h",
        "lib/bsp/standalone/src/common/xil_assert.h",
        "lib/bsp/standalone/src/common/xil_io.h",
        "lib/bsp/standalone/src/common/xil_printf.h",
        "lib/bsp/standalone/src/common/xstatus.h",
        "lib/bsp/standalone/src/common/xdebug.h",
        "lib/bsp/standalone/src/arm/cortexa9/xpseudo_asm.h",
        "lib/bsp/standalone/src/arm/cortexa9/xreg_cortexa9.h",
        "lib/bsp/standalone/src/arm/cortexa9/xil_cache.h",
        "lib/bsp/standalone/src/arm/cortexa9/xparameters_ps.h",
        "lib/bsp/standalone/src/arm/cortexa9/xil_errata.h",
        "lib/bsp/standalone/src/arm/cortexa9/xtime_l.h",
        "lib/bsp/standalone/src/arm/common/xil_exception.h",
        "lib/bsp/standalone/src/arm/common/gcc/xpseudo_asm_gcc.h",
    ],
    "zynqmp": [
        "XilinxProcessorIPLib/drivers/uartps/src/xuartps_hw.h",
        "lib/bsp/standalone/src/common/xil_types.h",
        "lib/bsp/standalone/src/common/xil_assert.h",
        "lib/bsp/standalone/src/common/xil_io.h",
        "lib/bsp/standalone/src/common/xil_printf.h",
        "lib/bsp/standalone/src/common/xstatus.h",
        "lib/bsp/standalone/src/common/xdebug.h",
        "lib/bsp/standalone/src/arm/ARMv8/64bit/xpseudo_asm.h",
        "lib/bsp/standalone/src/arm/ARMv8/64bit/xreg_cortexa53.h",
        "lib/bsp/standalone/src/arm/ARMv8/64bit/xil_cache.h",
        "lib/bsp/standalone/src/arm/ARMv8/64bit/xil_errata.h",
        "lib/bsp/standalone/src/arm/ARMv8/64bit/platform/ZynqMP/xparameters_ps.h",
        "lib/bsp/standalone/src/arm/common/xil_exception.h",
        "lib/bsp/standalone/src/arm/common/gcc/xpseudo_asm_gcc.h",
    ],
}

BSPCONFIG = {
    "zynq7000": "#define FPU_HARD_FLOAT_ABI_ENABLED 1\n",
    "zynqmp": """\
#ifndef BSPCONFIG_H
#define BSPCONFIG_H

#define EL3 1
#define EL1_NONSECURE 0

#endif
""",
}

class LibXil:
    """
    Configure the Xilinx libxil software package
    Attributes
    ==========
    cpu: CPU
        CPU instance using libxil
    xparameters: dict
        xparameters.h defines
    bspconfig: str (optional)
        bspconfig.h contents (defaults: CPU-generic settings)
    embeddedsw_dir: str (optional)
        path to an existing Xilinx embeddedsw checkout
    embeddedsw_git_url: str (optional)
        embeddedsw git URL, used when no local checkout is provided
    """

    def __init__(self, cpu, xparameters, bspconfig=None, embeddedsw_dir=None, embeddedsw_git_url=None):
        assert cpu is not None, "CPU must be provided"
        assert cpu.name in HEADERS, f"Unsupported libxil CPU: {cpu.name}"

        self.cpu                = cpu
        self.xparameters        = xparameters
        self.bspconfig          = {True: BSPCONFIG[cpu.name], False: bspconfig}[bspconfig is None]
        self.embeddedsw_dir     = embeddedsw_dir
        self.embeddedsw_git_url = {True: EMBEDDEDSW_GIT_URL, False: embeddedsw_git_url}[embeddedsw_git_url is None]

    """
    Add libxil software package/library to Builder.
    """
    def add_software_packages(self, builder):
        assert builder is not None, "Error builder is None"

        if not builder._has_software_package("libxil"):
            builder.add_software_package("libxil")
        if "libxil" not in builder.software_libraries:
            builder.add_software_library("libxil")

    def _prepare_embeddedsw(self, libxil_path):
        os.makedirs(os.path.realpath(libxil_path), exist_ok=True)
        dst = os.path.join(libxil_path, "embeddedsw")
        if os.path.exists(dst):
            return dst

        src = dst
        if self.embeddedsw_dir is not None:
            src = self.embeddedsw_dir
        elif os.getenv(EMBEDDEDSW_ENV_VAR) is not None:
            src = os.getenv(EMBEDDEDSW_ENV_VAR)
        src = os.path.abspath(src)

        if not os.path.exists(src):
            os.makedirs(os.path.dirname(src), exist_ok=True)
            subprocess.check_call(["git", "clone", "--depth", "1", self.embeddedsw_git_url, src])
        if src != dst:
            os.symlink(src, dst)
        return dst

    """
    Prepare embeddedsw headers and generated libxil configuration files.
    """
    def prepare_software(self, builder):
        libxil_path = os.path.join(builder.software_dir, "libxil")
        lib         = self._prepare_embeddedsw(libxil_path)

        os.makedirs(os.path.realpath(builder.include_dir), exist_ok=True)
        for header in HEADERS[self.cpu.name]:
            shutil.copy(os.path.join(lib, header), builder.include_dir)

        write_to_file(os.path.join(builder.include_dir, "bspconfig.h"), self.bspconfig)
        write_to_file(os.path.join(builder.include_dir, "xparameters.h"), self.xparameters_h())

    def xparameters_h(self):
        contents = [
            "#ifndef XPARAMETERS_H",
            "#define XPARAMETERS_H",
            "",
            '#include "xparameters_ps.h"',
            "",
        ]
        for name, value in self.xparameters.items():
            val = f"0x{value:X}" if isinstance(value, int) else str(value)
            contents.append(f"#define {name} {val}")
        contents += [
            "",
            "#endif",
            "",
        ]
        return "\n".join(contents)

