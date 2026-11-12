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
    assert not parser.parse_args([]).l2_bursting
    assert parser.parse_args(["--l2-bursting"]).l2_bursting
    assert not parser.parse_args([]).l2_refill_bypass
    assert parser.parse_args(["--l2-refill-bypass"]).l2_refill_bypass


@pytest.mark.parametrize("enabled", [False, True])
def test_l2_bursting_reaches_cache(enabled):
    soc = SimSoC(cpu_type=None, integrated_rom_size=0,
        with_uart=False, with_timer=False, with_sdram=True, l2_bursting=enabled)
    assert ("BURST" in soc.l2_cache.fsm.actions) == enabled


@pytest.mark.parametrize("width", [32, 128, 256, 512])
def test_l2_refill_width_reaches_cache(width):
    soc = SimSoC(cpu_type=None, integrated_rom_size=0,
        with_uart=False, with_timer=False, with_sdram=True, min_l2_data_width=width)
    assert soc.l2_cache.slave.data_width == width


@pytest.mark.parametrize("width", [0, -32, 16, 96, 128.0])
def test_invalid_l2_refill_width(width):
    with pytest.raises(ValueError, match="min_l2_data_width"):
        SimSoC(min_l2_data_width=width)


def test_analyzer_samplerate_is_sys_clk_freq():
    pytest.importorskip("litescope")
    soc = SimSoC(uart_name="sim", with_analyzer=True)
    assert soc.analyzer.samplerate == int(1e6)


@pytest.mark.parametrize("no_compile", [False, True])
def test_uart_pty_socat_lifecycle(tmp_path, monkeypatch, no_compile):
    from litex.tools import litex_sim

    class FakeProc:
        terminated = False
        def poll(self):
            return None
        def terminate(self):
            self.terminated = True

    procs = []
    def fake_popen(cmd, *args, **kwargs):
        assert cmd[0] == "socat"
        procs.append(FakeProc())
        return procs[-1]

    class FakeBuilder:
        def __init__(self, soc, compile_gateware=True, **kwargs):
            self.compile_gateware = compile_gateware
        def build(self, pre_run_callback=None, **kwargs):
            # The simulation (and pre_run_callback) only runs when the gateware is compiled.
            if self.compile_gateware:
                pre_run_callback(None)

    monkeypatch.setattr(litex_sim.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(litex_sim, "Builder", FakeBuilder)
    monkeypatch.setattr("sys.argv", ["litex_sim",
        "--uart-name=crossover+uartbone", "--uart-pty",
        "--uart-pty-path", str(tmp_path / "pty"),
        "--output-dir", str(tmp_path / "build"),
    ] + (["--no-compile"] if no_compile else []))
    litex_sim.main()

    # socat only started when the simulation runs, and stopped when litex_sim exits.
    assert len(procs) == (0 if no_compile else 1)
    assert all(proc.terminated for proc in procs)
