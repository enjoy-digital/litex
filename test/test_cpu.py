#
# This file is part of LiteX.
#
# Copyright (c) 2021 Navaneeth Bhardwaj <navan93@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import pexpect
import sys
import os

class TestCPU(unittest.TestCase):
    def boot_test(self, cpu_type, jobs, cpu_variant="standard"):
        cmd = f'litex_sim --cpu-type={cpu_type} --cpu-variant={cpu_variant} --opt-level=O0 --jobs {jobs}'
        litex_prompt = [b'\033\[[0-9;]+mlitex\033\[[0-9;]+m>']
        is_success = True
        with open("/tmp/test_boot_log", "wb") as result_file:
            p = pexpect.spawn(cmd, timeout=None, logfile=result_file)
            try:
                match_id = p.expect(litex_prompt, timeout=1200)
            except pexpect.EOF:
                print('\n*** Premature termination')
                is_success = False
            except pexpect.TIMEOUT:
                print('\n*** Timeout ')
                is_success = False

        if not is_success:
            print(f'*** {cpu_type} Boot Failure')
            with open("/tmp/test_boot_log", "r") as result_file:
                print(result_file.read())
        else:
            p.terminate(force=True)
            print(f'*** {cpu_type} Boot Success')

        return is_success

    def test_cpu(self):
        tested_cpus = [
            "cv32e40p",     # (riscv   / softcore)
            "femtorv",      # (riscv   / softcore)
            "firev",        # (riscv   / softcore)
            "marocchino",   # (or1k    / softcore)
            "naxriscv",     # (riscv   / softcore)
            "serv",         # (riscv   / softcore)
            "vexriscv",     # (riscv   / softcore)
            "vexriscv_smp", # (riscv   / softcore)
        ]
        untested_cpus = [
            "microwatt",    # (ppc64   / softcore) -> Broken 2022.01.12 -> https://github.com/enjoy-digital/litex/actions/runs/3900056883/jobs/6662146988
            "neorv32",      # (riscv   / softcore) -> Broken 2022.01.20 -> https://github.com/enjoy-digital/litex/actions/runs/3970180588/jobs/6805602574
            "blackparrot",  # (riscv   / softcore) -> Broken install?
            "cortex_m1",    # (arm     / softcore) -> Proprietary code.
            "cortex_m3",    # (arm     / softcore) -> Proprieraty code.
            "cv32e41p",     # (riscv   / softcore) -> Broken?
            "cva5",         # (riscv   / softcore) -> Needs to be tested.
            "cva6",         # (riscv   / softcore) -> Needs to be tested.
            "eos_s3",       # (arm     / hardcore) -> Hardcore.
            "gowin_emcu",   # (arm     / hardcore) -> Hardcore.
            "ibex",         # (riscv   / softcore) -> Broken since 2022.11.12.
            "lm32",         # (lm32    / softcore) -> Requires LM32 toolchain.
            "minerva",      # (riscv   / softcore) -> Broken install? (Amaranth?)
            "mor1kx",       # (or1k    / softcore) -> Verilator compilation issue.
            "picorv32",     # (riscv   / softcore) -> Verilator compilation issue.
            "rocket",       # (riscv   / softcore) -> Not enough RAM in CI.
            "zynq7000",     # (arm     / hardcore) -> Hardcore.
            "zynqmp",       # (aarch64 / hardcore) -> Hardcore.
        ]
        jobs = os.cpu_count()
        for cpu in tested_cpus:
             with self.subTest(target=cpu):
                self.assertTrue(self.boot_test(cpu, jobs))
