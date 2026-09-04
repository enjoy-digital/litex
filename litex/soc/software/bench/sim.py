#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Run CPU-cycle microbenchmarks using LiteX Sim's SoC and Verilator backend."""

import argparse
import hashlib
import json
import logging
from pathlib import Path
import statistics
import subprocess

from migen import Finish, If, Signal
from litex.gen import LiteXModule
from litex.build.sim.config import SimConfig
from litex.soc.integration.builder import Builder
from litex.soc.interconnect.csr import CSRStorage, CSRStatus
from litex.tools.litex_sim import SimSoC


def parse_results(output):
    """Reject incomplete, failed or unmeasured runs before comparing their cycle counts."""
    if "BENCH_ERROR" in output or "BENCH_DONE" not in output:
        raise ValueError("Benchmark did not complete successfully")
    expected = {"overhead_0": (0, 0), "compute_0": (32768, 0x1c348001)}
    for size in [1024, 65536]:
        expected[f"write_{size}"] = (size//4, 0)
        for name in ["read_cold", "read_repeat"]:
            expected[f"{name}_{size}"] = (size//4, ((size//4)*0x12345678) & 0xffffffff)
        expected[f"chase_{size}"] = (8192, 0)
    samples = {}
    for line in output.splitlines():
        if not line.startswith("BENCH,"):
            continue
        _, name, size, iterations, cycles, checksum = line.split(",")
        key = f"{name}_{size}"
        if key not in expected or (int(iterations), int(checksum, 16)) != expected[key]:
            raise ValueError(f"Unexpected benchmark result: {line}")
        if int(cycles) <= 0:
            raise ValueError("Benchmark cycle counter did not advance")
        samples.setdefault(key, []).append({
            "cycles": int(cycles), "iterations": int(iterations), "checksum": checksum})
    if set(samples) != set(expected) or any(len(values) != 3 for values in samples.values()):
        raise ValueError("Missing benchmark samples")
    return samples


class BenchmarkControl(LiteXModule):
    def __init__(self):
        self.finish = CSRStorage(name="finish")
        self.latch = CSRStorage(name="latch")
        self.cycles = CSRStatus(32, name="cycles")
        counter = Signal(32)
        self.sync += [counter.eq(counter + 1),
            If(self.latch.wr_stb, self.cycles.status.eq(counter))]
        self.sync += If(self.finish.storage, Finish())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cpu-variant", default="standard", choices=["standard", "full", "lite"])
    parser.add_argument("--bus-standard", default="wishbone", choices=["wishbone", "axi-lite", "axi"])
    parser.add_argument("--bus-data-width", default=32, type=int, choices=[32, 64, 128])
    parser.add_argument("--bus-interconnect", default="shared", choices=["shared", "crossbar"])
    parser.add_argument("--bus-bursting", action="store_true")
    parser.add_argument("--bus-low-latency", action="store_true")
    parser.add_argument("--no-interconnect-register", action="store_true")
    parser.add_argument("--with-sdram", action="store_true")
    parser.add_argument("--l2-size", default=8192, type=lambda v: int(v, 0))
    parser.add_argument("--min-l2-data-width", default=128, type=int,
        choices=[32, 64, 128, 256, 512, 1024])
    parser.add_argument("--jobs", default=4, type=int)
    parser.add_argument("--timeout", default=120, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    output = args.output_dir.resolve()
    soc = SimSoC(
        cpu_type="vexriscv", cpu_variant=args.cpu_variant, uart_name="sim",
        integrated_rom_size=0x10000, integrated_sram_size=0x8000,
        integrated_main_ram_size=0 if args.with_sdram else 0x40000,
        with_sdram=args.with_sdram, l2_size=args.l2_size, min_l2_data_width=args.min_l2_data_width,
        bus_standard=args.bus_standard, bus_data_width=args.bus_data_width,
        bus_interconnect=args.bus_interconnect, bus_bursting=args.bus_bursting,
        bus_low_latency=args.bus_low_latency)
    soc.bus.interconnect_register = not args.no_interconnect_register
    soc.bench = BenchmarkControl()
    config = SimConfig(default_clk="sys_clk")
    config.add_module("serial2console", "serial")
    builder = Builder(soc, output_dir=str(output), build_bundle=False)
    builder.add_software_package("bios", src_dir=str(Path(__file__).resolve().parent))
    builder.build(sim_config=config, interactive=False, run=False, jobs=args.jobs, opt_level="O3")
    with (output / "compile.log").open("w") as log:
        subprocess.run(["bash", "build_sim.sh"], cwd=output / "gateware",
            stdout=log, stderr=subprocess.STDOUT, check=True)
    try:
        completed = subprocess.run([str(output / "gateware/obj_dir/Vsim")],
            cwd=output / "gateware", input="", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired as error:
        (output / "benchmark.log").write_bytes(error.output or b"")
        raise RuntimeError(f"Benchmark timed out; see {output / 'benchmark.log'}") from error
    (output / "benchmark.log").write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f"Benchmark failed; see {output / 'benchmark.log'}")
    samples = parse_results(completed.stdout)
    result = {
        "configuration": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "firmware_source_sha256": hashlib.sha256(Path(__file__).with_name("main.c").read_bytes()).hexdigest(),
        "samples": samples,
        "median_cycles": {name: statistics.median(sample["cycles"] for sample in values)
                          for name, values in samples.items()},
    }
    (output / "benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["median_cycles"], indent=2))


if __name__ == "__main__":
    main()
