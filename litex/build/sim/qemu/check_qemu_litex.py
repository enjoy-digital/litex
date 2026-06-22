#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import shutil
import argparse
import subprocess
from pathlib import Path


def repo_root():
    return Path(__file__).resolve().parents[4]


def qemu_name(variant):
    return "qemu-system-riscv{}".format(64 if variant == "rv64" else 32)


def resolve_binary(args, variant):
    override = getattr(args, "qemu_binary_{}".format(variant))
    if override is not None:
        return override

    candidate = args.qemu_dir / qemu_name(variant)
    if candidate.exists():
        return candidate

    path_binary = shutil.which(qemu_name(variant))
    if path_binary is not None:
        return Path(path_binary)

    raise SystemExit("Could not find {}; use --qemu-dir or --qemu-binary-{}.".format(qemu_name(variant), variant))


def check_machine(binary):
    proc = subprocess.run(
        [str(binary), "-machine", "help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("{} -machine help failed:\n{}".format(binary, proc.stdout))
    if "litex-sim" not in proc.stdout:
        with open(binary, "rb") as f:
            has_litex_string = b"litex-sim" in f.read()
        raise SystemExit(
            "{} does not expose the litex-sim machine "
            "(binary contains litex-sim: {}).\n{}".format(
                binary,
                has_litex_string,
                proc.stdout,
            )
        )
    print("OK: {} exposes litex-sim".format(binary))


def litex_smoke(binary, variant):
    cmd = [
        sys.executable,
        "-m", "litex.tools.litex_sim",
        "--cpu-type=qemu",
        "--cpu-variant={}".format(variant),
        "--qemu-binary", str(binary),
        "--qemu-no-run",
        "--no-compile-gateware",
    ]
    print("+ {}".format(" ".join(cmd)))
    subprocess.run(cmd, check=True)


def main():
    qemu_dir = repo_root() / "build" / "qemu-litex" / "bin"
    parser = argparse.ArgumentParser(description="Check LiteX SIM patched QEMU binaries.")
    parser.add_argument("--qemu-dir", type=Path, default=qemu_dir, help="Directory containing qemu-system-riscv32/64.")
    parser.add_argument("--qemu-binary-rv32", type=Path, default=None, help="Explicit RV32 QEMU binary.")
    parser.add_argument("--qemu-binary-rv64", type=Path, default=None, help="Explicit RV64 QEMU binary.")
    parser.add_argument("--variants", default="rv32,rv64", help="Comma-separated variants to check.")
    parser.add_argument("--litex-smoke", action="store_true", help="Also run a LiteX --qemu-no-run build smoke.")
    args = parser.parse_args()

    variants = [variant.strip() for variant in args.variants.split(",") if variant.strip()]
    for variant in variants:
        if variant not in ["rv32", "rv64"]:
            raise SystemExit("Unsupported variant: {}".format(variant))
        binary = resolve_binary(args, variant)
        check_machine(binary)
        if args.litex_smoke:
            litex_smoke(binary, variant)


if __name__ == "__main__":
    main()
