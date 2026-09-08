# SPDX-License-Identifier: BSD-2-Clause
import argparse
import subprocess

import pytest
from migen.sim import run_simulation

from litex.soc.software.bench.sim import (
    BenchmarkControl, cache_size, parse_results, positive_int, prepare_output, run_benchmark,
)


def output():
    rows = ["BENCH,overhead,0,0,7,00000000", "BENCH,compute,0,32768,196619,1c348001"]
    for size in [1024, 65536]:
        rows.append(f"BENCH,write,{size},{size//4},1000,00000000")
        for name in ["read_cold", "read_repeat"]:
            checksum = ((size//4)*0x12345678) & 0xffffffff
            rows.append(f"BENCH,{name},{size},{size//4},1000,{checksum:08x}")
        rows.append(f"BENCH,chase,{size},8192,1000,00000000")
    return "BENCH_BEGIN\n" + "\n".join(rows*3) + "\nBENCH_DONE\n"


def test_complete_benchmark_results():
    samples = parse_results(output())
    assert len(samples) == 10
    assert all(len(values) == 3 for values in samples.values())
    assert samples["compute_0"][0]["cycles"] == 196619


@pytest.mark.parametrize("old,new", [
    ("BENCH_DONE", ""),
    ("BENCH_BEGIN", ""),
    ("BENCH_DONE", "BENCH_DONE\nBENCH_DONE"),
    ("BENCH_BEGIN", "BENCH_ERROR,read_checksum"),
    (",196619,", ",0,"),
    (",196619,", ",4294967296,"),
    (",1c348001", ",00000000"),
    ("BENCH,write,1024,256,1000,00000000", ""),
    ("BENCH,chase,1024", "BENCH,unknown,1024"),
])
def test_invalid_benchmark_results(old, new):
    with pytest.raises(ValueError):
        parse_results(output().replace(old, new))


def test_latched_system_counter():
    dut = BenchmarkControl()

    def generator():
        yield dut.latch.wr_stb.eq(1)
        yield
        yield dut.latch.wr_stb.eq(0)
        yield
        first = yield dut.cycles.status
        for _ in range(10):
            yield
        assert (yield dut.cycles.status) == first
        yield dut.latch.wr_stb.eq(1)
        yield
        yield dut.latch.wr_stb.eq(0)
        yield
        assert (yield dut.cycles.status) - first == 12

    run_simulation(dut, generator())


@pytest.mark.parametrize("value", ["0", "-1"])
def test_invalid_positive_int(value):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int(value)


@pytest.mark.parametrize("value", ["-8", "4", "24"])
def test_invalid_cache_size(value):
    with pytest.raises(argparse.ArgumentTypeError):
        cache_size(value)


def test_numeric_options():
    assert positive_int("4") == 4
    assert cache_size("0") == 0
    assert cache_size("0x10000") == 65536


def test_existing_output_is_preserved(tmp_path):
    directory = tmp_path / "run"
    prepare_output(directory)
    result = directory / "benchmark.json"
    result.write_text("previous result")
    with pytest.raises(FileExistsError):
        prepare_output(directory)
    assert result.read_text() == "previous result"


def test_run_uses_noninteractive_pipe_and_preserves_output(tmp_path, monkeypatch):
    def run(command, **kwargs):
        assert command == [str(tmp_path / "gateware/obj_dir/Vsim")]
        assert kwargs["input"] == "" and "stdin" not in kwargs
        assert kwargs["timeout"] == 3
        return subprocess.CompletedProcess(command, 0, output())

    monkeypatch.setattr(subprocess, "run", run)
    assert len(run_benchmark(tmp_path, 3)) == 10
    assert (tmp_path / "benchmark.log").read_text() == output()


@pytest.mark.parametrize("failure", ["timeout", "exit", "checksum"])
def test_failed_run_retains_log(tmp_path, monkeypatch, failure):
    log = b"BENCH_ERROR,read_checksum\n"

    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=log)
        return subprocess.CompletedProcess(command, int(failure == "exit"), log.decode())

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ValueError if failure == "checksum" else RuntimeError):
        run_benchmark(tmp_path, 3)
    assert (tmp_path / "benchmark.log").read_bytes() == log
    assert not (tmp_path / "benchmark.json").exists()
