#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import csv
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# Parsing ------------------------------------------------------------------------------------------

SPEED_RE   = re.compile(r"^\s*(Write|Read) speed:\s*([0-9]+(?:\.[0-9]+)?)(B|KiB|MiB|GiB)/s")
MONITOR_RE = re.compile(r"^wishbone_burst_monitor\s+(\S+)(.*)$")

SIZE_UNITS = {
    "B"   : 1,
    "KiB" : 1024,
    "MiB" : 1024**2,
    "GiB" : 1024**3,
}


def parse_human_rate(value, unit):
    return float(value)*SIZE_UNITS[unit]


def parse_int_list(s):
    values = []
    for item in s.split(","):
        item = item.strip()
        if item:
            values.append(int(item, 0))
    return values


def parse_workload(s):
    workloads = []
    for workload in s.split(","):
        workload = workload.strip()
        if workload:
            workloads.append(workload)
    return workloads


def parse_litex_sim_output(output):
    result = {
        "read_speed"       : "",
        "read_speed_Bps"   : "",
        "write_speed"      : "",
        "write_speed_Bps"  : "",
        "monitors"         : {},
    }

    lines = output.splitlines()
    benchmark_lines = []
    in_benchmark = False
    for line in lines:
        if "Wishbone Burst Benchmark" in line:
            in_benchmark = True
        if in_benchmark:
            benchmark_lines.append(line)
    if not benchmark_lines:
        benchmark_lines = lines

    for line in benchmark_lines:
        speed = SPEED_RE.search(line)
        if speed:
            access, value, unit = speed.groups()
            key = access.lower()
            result[f"{key}_speed"]     = f"{value}{unit}/s"
            result[f"{key}_speed_Bps"] = int(parse_human_rate(value, unit))
            continue

        monitor = MONITOR_RE.search(line)
        if monitor:
            name, data = monitor.groups()
            values = {}
            for token in data.split():
                key, sep, value = token.partition("=")
                if sep:
                    values[key] = int(value, 0)
            result["monitors"][name] = values

    return result


def flatten_result(result):
    row = {
        "read_speed"      : result["read_speed"],
        "read_speed_Bps"  : result["read_speed_Bps"],
        "write_speed"     : result["write_speed"],
        "write_speed_Bps" : result["write_speed_Bps"],
    }
    for monitor_name, monitor_values in sorted(result["monitors"].items()):
        for key, value in sorted(monitor_values.items()):
            row[f"{monitor_name}_{key}"] = value
    return row


def markdown_table(rows, columns):
    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


# Benchmark ----------------------------------------------------------------------------------------

@dataclass
class BenchmarkCase:
    l2_width: int
    size: int
    workload: str

    @property
    def read_only(self):
        return self.workload.endswith("-read")

    @property
    def random(self):
        return self.workload.startswith("random-")

    @property
    def name(self):
        return f"l2w{self.l2_width}_size{self.size}_{self.workload}"


def build_litex_sim_command(args, case, output_dir):
    cmd = [
        sys.executable, "-m", "litex.tools.litex_sim",
        "--with-sdram",
        f"--sdram-data-width={args.sdram_data_width}",
        f"--l2-cache-min-data-width={case.l2_width}",
        "--wishbone-burst-benchmark",
        f"--wishbone-burst-benchmark-size={case.size}",
        f"--cpu-type={args.cpu_type}",
        f"--cpu-variant={args.cpu_variant}",
        f"--output-dir={output_dir}",
        f"--threads={args.threads}",
    ]
    if not args.no_bus_bursting:
        cmd.append("--bus-bursting")
    if not case.read_only:
        cmd.append("--wishbone-burst-benchmark-write")
    if case.random:
        cmd.append("--wishbone-burst-benchmark-random")
    for extra_arg in args.litex_sim_arg:
        cmd.append(extra_arg)
    return cmd


def run_case(args, case):
    case_dir = Path(args.output_dir)/case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_litex_sim_command(args, case, case_dir)

    if args.dry_run:
        return {
            "status"      : "dry-run",
            "command"     : " ".join(cmd),
            "l2_width"    : case.l2_width,
            "size"        : case.size,
            "workload"    : case.workload,
            "output_dir"  : str(case_dir),
        }

    env = os.environ.copy()
    if args.pythonpath:
        extra_pythonpath = os.pathsep.join(args.pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [extra_pythonpath, env.get("PYTHONPATH", "")]))

    try:
        process = subprocess.run(
            cmd,
            cwd       = args.cwd,
            env       = env,
            text      = True,
            stdout    = subprocess.PIPE,
            stderr    = subprocess.STDOUT,
            timeout   = args.timeout,
            check     = False,
        )
        output = process.stdout
        status = "ok" if process.returncode == 0 else f"failed:{process.returncode}"
    except subprocess.TimeoutExpired as e:
        output = e.stdout or ""
        status = "timeout"

    log_file = case_dir/"litex_sim.log"
    log_file.write_text(output)

    parsed = flatten_result(parse_litex_sim_output(output))
    row = {
        "status"      : status,
        "l2_width"    : case.l2_width,
        "size"        : case.size,
        "workload"    : case.workload,
        "output_dir"  : str(case_dir),
        "log"         : str(log_file),
        **parsed,
    }

    if status != "ok" and not args.continue_on_error:
        raise RuntimeError(f"{case.name} {status}; see {log_file}")

    return row


def write_csv(path, rows):
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return columns


def write_markdown(path, rows, csv_columns):
    preferred = [
        "status",
        "l2_width",
        "size",
        "workload",
        "write_speed",
        "read_speed",
        "main_ram_burst_count",
        "main_ram_burst_beats",
        "main_ram_max_burst_beats",
        "l2_slave_burst_count",
        "l2_slave_burst_beats",
        "l2_slave_max_burst_beats",
        "log",
    ]
    columns = [column for column in preferred if column in csv_columns]
    if not columns:
        columns = csv_columns

    with open(path, "w") as f:
        f.write("# Wishbone Burst Benchmark Sweep\n\n")
        f.write(markdown_table(rows, columns))


def main():
    parser = argparse.ArgumentParser(description="Run and summarize litex_sim Wishbone burst benchmark sweeps.")
    parser.add_argument("--output-dir", default="build/wishbone_burst_benchmark_sweep",
        help="Directory for per-case simulator outputs and summary files.")
    parser.add_argument("--sizes", default="8192,65536",
        help="Comma-separated benchmark sizes in bytes.")
    parser.add_argument("--l2-cache-min-data-widths", default="128,256",
        help="Comma-separated L2 minimum data widths to sweep.")
    parser.add_argument("--workloads", default="sequential-read,sequential-read-write,random-read",
        help="Comma-separated workloads: sequential-read, sequential-read-write, random-read, random-read-write.")
    parser.add_argument("--cpu-type", default="vexriscv",
        help="CPU type passed to litex_sim.")
    parser.add_argument("--cpu-variant", default="full",
        help="CPU variant passed to litex_sim.")
    parser.add_argument("--sdram-data-width", default="32",
        help="SDRAM data width passed to litex_sim.")
    parser.add_argument("--threads", default="1",
        help="Simulator build/run thread count.")
    parser.add_argument("--timeout", type=float, default=600,
        help="Timeout per benchmark case in seconds.")
    parser.add_argument("--cwd", default=os.getcwd(),
        help="Working directory for litex_sim.")
    parser.add_argument("--pythonpath", action="append", default=[],
        help="Extra PYTHONPATH entry for litex_sim. Can be repeated.")
    parser.add_argument("--litex-sim-arg", action="append", default=[],
        help="Extra argument appended to each litex_sim command. Can be repeated.")
    parser.add_argument("--no-bus-bursting", action="store_true",
        help="Do not pass --bus-bursting.")
    parser.add_argument("--continue-on-error", action="store_true",
        help="Continue the sweep if one benchmark case fails.")
    parser.add_argument("--dry-run", action="store_true",
        help="Print/report commands without running litex_sim.")
    args = parser.parse_args()

    valid_workloads = {
        "sequential-read",
        "sequential-read-write",
        "random-read",
        "random-read-write",
    }
    workloads = parse_workload(args.workloads)
    unknown_workloads = sorted(set(workloads) - valid_workloads)
    if unknown_workloads:
        parser.error("Unknown workload(s): " + ", ".join(unknown_workloads))

    cases = [
        BenchmarkCase(l2_width=l2_width, size=size, workload=workload)
        for l2_width in parse_int_list(args.l2_cache_min_data_widths)
        for size in parse_int_list(args.sizes)
        for workload in workloads
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in cases:
        print(f"[wishbone-burst-benchmark] {case.name}")
        rows.append(run_case(args, case))

    csv_path = output_dir/"summary.csv"
    md_path  = output_dir/"summary.md"
    columns = write_csv(csv_path, rows)
    write_markdown(md_path, rows, columns)

    print(f"[wishbone-burst-benchmark] Wrote {csv_path}")
    print(f"[wishbone-burst-benchmark] Wrote {md_path}")


if __name__ == "__main__":
    main()
