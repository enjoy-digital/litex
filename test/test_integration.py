#
# This file is part of LiteX.
#
# Copyright (c) 2021 Navaneeth Bhardwaj <navan93@gmail.com>
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import pexpect
import os
import socket
import sys
import tempfile
import time
import itertools
import pytest

from litex.tools.litex_term import (
    SFLFrame,
    sfl_ack_error,
    sfl_ack_success,
    sfl_cmd_abort,
    sfl_magic_ack,
    sfl_magic_req,
)

def _sim_jobs():
    # When pytest-xdist is running several tests in parallel, divide the
    # available cores between workers to avoid oversubscribing the build.
    workers = int(os.environ.get("PYTEST_XDIST_WORKER_COUNT", "1") or "1")
    return max(1, (os.cpu_count() or 1) // max(1, workers))

def _get_free_tcp_port():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as e:
        pytest.skip(f"local TCP sockets are unavailable: {e}")

    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    except OSError as e:
        pytest.skip(f"local TCP bind is unavailable: {e}")
    finally:
        sock.close()

def _connect_tcp_uart(port, timeout=10):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=1)
            sock.settimeout(0.1)
            return sock
        except OSError as e:
            last_error = e
            time.sleep(0.1)
    raise TimeoutError(f"could not connect to litex_sim UART on port {port}: {last_error}")

def _recv_until(sock, needle, timeout=10):
    deadline = time.time() + timeout
    data = b""
    while time.time() < deadline:
        try:
            chunk = sock.recv(1)
            if not chunk:
                break
            data += chunk
            if needle in data:
                return data
        except socket.timeout:
            pass
    raise TimeoutError(f"did not receive {needle!r}; last data: {data[-200:]!r}")

def boot_test(cpu_type="vexriscv", cpu_variant="standard", args="", output_dir=None):
    output_arg = f' --output-dir={output_dir}' if output_dir else ''
    cmd = (
        f'litex_sim --cpu-type={cpu_type} --cpu-variant={cpu_variant} {args}'
        f'{output_arg} --opt-level=O0 --jobs {_sim_jobs()}'
    )
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

def test_serialboot_abort_recovers(tmp_path):
    port = _get_free_tcp_port()
    cmd = (
        "litex_sim --cpu-type=vexriscv --cpu-variant=standard "
        f"--uart-tcp --uart-tcp-port={port} "
        "--integrated-main-ram-size=65536 "
        f"--output-dir={tmp_path} --opt-level=O0 --jobs {_sim_jobs()} --non-interactive"
    )
    litex_prompt = b"litex"
    abort = SFLFrame()
    abort.cmd = sfl_cmd_abort
    sock = None
    is_success = True

    with tempfile.TemporaryFile(mode="w+", prefix="litex_test") as log_file:
        log_file.writelines(f"Command: {cmd}\n")
        log_file.flush()
        p = pexpect.spawn(cmd, timeout=None, encoding=sys.getdefaultencoding(), logfile=log_file)
        try:
            p.expect(f"Found port {port}", timeout=1200)
            sock = _connect_tcp_uart(port)

            _recv_until(sock, litex_prompt, timeout=20)
            sock.sendall(b"serialboot\n")
            _recv_until(sock, sfl_magic_req, timeout=10)

            sock.sendall(sfl_magic_ack)
            sock.sendall(b"\x10")
            _recv_until(sock, sfl_ack_error, timeout=10)

            sock.sendall(abort.encode())
            _recv_until(sock, sfl_ack_success, timeout=10)
            _recv_until(sock, litex_prompt, timeout=10)
        except (OSError, pexpect.EOF, pexpect.TIMEOUT, TimeoutError):
            is_success = False
            print(f"*** Serialboot abort recovery failure: {cmd}")
            log_file.seek(0)
            print(log_file.read())
        finally:
            if sock is not None:
                sock.close()
            p.terminate(force=True)

    assert is_success

TESTED_CPUS = [
    #"cv32e40p",     # (riscv   / softcore)
    "femtorv",      # (riscv   / softcore)
    "firev",        # (riscv   / softcore)
    "marocchino",   # (or1k    / softcore)
    "naxriscv",     # (riscv   / softcore)
    "serv",         # (riscv   / softcore)
    "sentinel",     # (riscv   / softcore)
    "vexiiriscv",   # (riscv   / softcore)
    "vexriscv",     # (riscv   / softcore)
    "vexriscv_smp", # (riscv   / softcore)
    #"microwatt",    # (ppc64   / softcore)
    "neorv32",      # (riscv   / softcore)
    "ibex",         # (riscv   / softcore)
    "minerva",      # (riscv   / softcore)
]
UNTESTED_CPUS = [
    "coreblocks",   # (riscv   / softcore) -> Broken install?
    "blackparrot",  # (riscv   / softcore) -> Broken install?
    "cortex_m1",    # (arm     / softcore) -> Proprietary code.
    "cortex_m3",    # (arm     / softcore) -> Proprieraty code.
    "cv32e41p",     # (riscv   / softcore) -> Broken?
    "cva5",         # (riscv   / softcore) -> Needs to be tested.
    "cva6",         # (riscv   / softcore) -> Needs to be tested.
    "eos_s3",       # (arm     / hardcore) -> Hardcore.
    "gowin_emcu",   # (arm     / hardcore) -> Hardcore.
    "lm32",         # (lm32    / softcore) -> Requires LM32 toolchain.
    "mor1kx",       # (or1k    / softcore) -> Verilator compilation issue.
    "picorv32",     # (riscv   / softcore) -> Verilator compilation issue.
    "rocket",       # (riscv   / softcore) -> Not enough RAM in CI.
    "zynq7000",     # (arm     / hardcore) -> Hardcore.
    "zynqmp",       # (aarch64 / hardcore) -> Hardcore.
]

@pytest.mark.parametrize("cpu", TESTED_CPUS)
def test_cpu(cpu, request, tmp_path):
    assert boot_test(cpu_type=cpu, output_dir=str(tmp_path))

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
def test_buses(args, request, tmp_path):
    assert boot_test(args=args, output_dir=str(tmp_path))
