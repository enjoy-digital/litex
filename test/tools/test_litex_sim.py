# SPDX-License-Identifier: BSD-2-Clause
import argparse

import pytest

pytest.importorskip("liteeth")
pytest.importorskip("litedram")

from litex.tools.litex_sim import SimSoC, sim_args


def test_l2_refill_width_argument():
    parser = argparse.ArgumentParser()
    sim_args(parser)
    assert parser.parse_args([]).min_l2_data_width == 128
    assert parser.parse_args(["--min-l2-data-width=256"]).min_l2_data_width == 256


@pytest.mark.parametrize("width", [32, 128, 256, 512])
def test_l2_refill_width_reaches_cache(width):
    soc = SimSoC(cpu_type=None, integrated_rom_size=0,
        with_uart=False, with_timer=False, with_sdram=True, min_l2_data_width=width)
    assert soc.l2_cache.slave.data_width == width


@pytest.mark.parametrize("width", [0, -32, 16, 96, 128.0])
def test_invalid_l2_refill_width(width):
    with pytest.raises(ValueError, match="min_l2_data_width"):
        SimSoC(min_l2_data_width=width)
