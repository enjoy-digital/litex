#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import inspect
import os
import random

from migen import run_simulation


DEFAULT_PRNG_SEED = 42


def seeded_prng(seed=DEFAULT_PRNG_SEED):
    return random.Random(seed)


def simulation_vcd_path(name):
    dump_vcd = os.environ.get("LITEX_TEST_DUMP_VCD")
    if not dump_vcd:
        return None
    if dump_vcd == "1":
        return f"{name}.vcd"
    return os.path.join(dump_vcd, f"{name}.vcd")


def run_simulation_case(dut, generators, clocks=None, vcd_name=None, **kwargs):
    if vcd_name is None:
        vcd_name = simulation_vcd_path(inspect.stack()[1].function)
    if clocks is None:
        return run_simulation(dut, generators, vcd_name=vcd_name, **kwargs)
    return run_simulation(dut, generators, clocks=clocks, vcd_name=vcd_name, **kwargs)
