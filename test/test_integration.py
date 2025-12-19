#
# This file is part of LiteX.
#
# Copyright (c) 2021 Navaneeth Bhardwaj <navan93@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import pexpect
import os
import sys
import tempfile
import itertools
import pytest

def boot_test(cpu_type="vexriscv", cpu_variant="standard", args=""):
    cmd = f'litex_sim --cpu-type={cpu_type} --cpu-variant={cpu_variant} {args} --opt-level=O0 --jobs {os.cpu_count()}'
    litex_prompt = [r'\033\[[0-9;]+mlitex\033\[[0-9;]+m>']
    is_success = True

    with tempfile.TemporaryFile(mode='w+', prefix="litex_test") as log_file:
        log_file.writelines(f"Command: {cmd}")
        log_file.flush()

        p = pexpect.spawn(cmd, timeout=None, encoding=sys.getdefaultencoding(), logfile=log_file)
        try:
            match_id = p.expect(litex_prompt, timeout=1200)
        except pexpect.EOF:
            print('\n*** Premature termination')
            is_success = False
        except pexpect.TIMEOUT:
            print('\n*** Timeout ')
            is_success = False

        if not is_success:
            print(f'*** Boot Failure: {cmd}')
            log_file.seek(0)
            print(log_file.read())
        else:
            p.terminate(force=True)
            print(f'*** Boot Success: {cmd}')

    return is_success

TESTED_CPUS = [
    "coreblocks",   # (riscv   / softcore)
    #"cv32e40p",     # (riscv   / softcore)
    "femtorv",      # (riscv   / softcore)
    "firev",        # (riscv   / softcore)
    "marocchino",   # (or1k    / softcore)
    "naxriscv",     # (riscv   / softcore)
    "serv",         # (riscv   / softcore)
    "vexiiriscv",   # (riscv   / softcore)
    "vexriscv",     # (riscv   / softcore)
    "vexriscv_smp", # (riscv   / softcore)
    #"microwatt",    # (ppc64   / softcore)
    "neorv32",      # (riscv   / softcore)
    "ibex",         # (riscv   / softcore)
]
UNTESTED_CPUS = [
    "blackparrot",  # (riscv   / softcore) -> Broken install?
    "cortex_m1",    # (arm     / softcore) -> Proprietary code.
    "cortex_m3",    # (arm     / softcore) -> Proprieraty code.
    "cv32e41p",     # (riscv   / softcore) -> Broken?
    "cva5",         # (riscv   / softcore) -> Needs to be tested.
    "cva6",         # (riscv   / softcore) -> Needs to be tested.
    "eos_s3",       # (arm     / hardcore) -> Hardcore.
    "gowin_emcu",   # (arm     / hardcore) -> Hardcore.
    "lm32",         # (lm32    / softcore) -> Requires LM32 toolchain.
    "minerva",      # (riscv   / softcore) -> Broken install? (Amaranth?)
    "mor1kx",       # (or1k    / softcore) -> Verilator compilation issue.
    "picorv32",     # (riscv   / softcore) -> Verilator compilation issue.
    "rocket",       # (riscv   / softcore) -> Not enough RAM in CI.
    "zynq7000",     # (arm     / hardcore) -> Hardcore.
    "zynqmp",       # (aarch64 / hardcore) -> Hardcore.
]

@pytest.mark.parametrize("cpu", TESTED_CPUS)
def test_cpu(cpu, request):
    assert boot_test(cpu_type=cpu)

BUS_OPTIONS = [
    ("--bus-standard", ["wishbone", "axi-lite", "axi"]),
    ("--bus-data-width", [32, 64]),
    ("--bus-address-width", [32, 64]),
    ("--bus-interconnect", ["shared", "crossbar"])
]
BUS_BLACKLISTS = [
    # AXI-Lite with 64-bit data width and crossbar
    [
        ("--bus-standard", ["axi-lite"]),
        ("--bus-data-width", [64]),
        ("--bus-interconnect", ["crossbar"])
    ],
    # AXI with 64-bit data width
    [
        ("--bus-standard", ["axi"]),
        ("--bus-data-width", [64])
    ]
]

def _bus_is_blacklisted(config):
    for blacklist in BUS_BLACKLISTS:
        matches = True
        for opt, values in blacklist:
            cfg_value = next(v for k,v in config if k == opt)
            if cfg_value not in values:
                matches = False
                break
        if matches:
            return True
    return False

def _build_bus_cases():
    keys = [k for k, _ in BUS_OPTIONS]
    values = [v for _, v in BUS_OPTIONS]

    cases = []
    for combination in itertools.product(*values):
        config = list(zip(keys, combination))
        if _bus_is_blacklisted(config):
            continue
        args = " ".join(f"{k}={v}" for k, v in config)
        cases.append(args)
    return cases

BUS_CASES = _build_bus_cases()

@pytest.mark.parametrize("args", BUS_CASES)
def test_buses(args, request):
    assert boot_test(args=args)
