#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check (hardware, ECPIX-5): build the reference SoC (the task's target.py and IP netlist, not the
# workspace copies), load it to the FPGA SRAM (never to flash), configure the IP with
# driver.configure() of the workspace for several gains/offsets through the UARTBone bridge, then
# drive the IP registers directly and compare the results with the specification.
#
# Only runs with LITEX_AGENT_EVAL_HW=ecpix5 and LITEX_AGENT_EVAL_ECPIX5_BUSDEV=<bus:dev> (USB
# bus:dev of the board's FT2232, for openFPGALoader -c ft2232 --busdev-num);
# LITEX_AGENT_EVAL_ECPIX5_UART is the serial port of the FTDI UART (default below).
# dry_run() elaborates the workspace target without toolchain/board (and builds the bitstream
# without loading it with LITEX_AGENT_EVAL_HW_BUILD=1).

import os
import sys
import shutil
import tempfile
import subprocess
import importlib.util

from test.agent_eval.common import CheckResult, BoardSession, hardware_enabled

TIER         = "v2"            # Fault only visible at runtime.
HARDWARE     = "ecpix5"
AGENT_PORTS  = range(22000, 22050) # Ports given to the agent (litex_server, ...).
SERVER_PORT  = 22051
CSR_CSV      = os.path.join("build", "ecpix5", "csr.csv") # CSR file of the agent's build (MCP).
DEFAULT_UART = "/dev/serial/by-id/usb-FTDI_Dual_RS232-HS-if01-port0"

BASE    = 0x90000000
ID      = BASE + 0x00
DIN     = BASE + 0x10
DOUT    = BASE + 0x14
STATUS  = BASE + 0x1c
CONFIGS = [(1.5, 100), (0.75, 0), (3.0, 1000), (2.25, 7)]
SAMPLES = [0, 1, 999, 2730, 4000, 9000, 21000, 30000, 47000, 65535]

TASK_TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", "target.py")

def board_env():
    return {
        "ECPIX5_BUSDEV" : os.environ.get("LITEX_AGENT_EVAL_ECPIX5_BUSDEV", ""),
        "ECPIX5_UART"   : os.environ.get("LITEX_AGENT_EVAL_ECPIX5_UART", DEFAULT_UART),
    }

def setup(workdir):
    """Write board.env (board access of the prompt) in the workspace."""
    with open(os.path.join(workdir, "board.env"), "w") as f:
        f.write("# ECPIX-5 access: USB bus:dev of its FT2232 (JTAG) and serial port of its UART.\n")
        for k, v in board_env().items():
            f.write(f"{k}={v}\n")

def _load_driver(workdir):
    spec   = importlib.util.spec_from_file_location("agent_eval_ecpix5_scaler_driver", os.path.join(workdir, "driver.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _target(target, output_dir, args, timeout=1800):
    return subprocess.run([sys.executable, target, f"--output-dir={output_dir}"] + args,
        cwd=os.path.dirname(target), capture_output=True, text=True, timeout=timeout)

def dry_run(workdir):
    """Elaborate the workspace target (no toolchain, no board): gateware/software generated, IP
    netlist in the Yosys script, scaler region in the memory map."""
    result = CheckResult("ecpix5_scaler")
    build  = os.environ.get("LITEX_AGENT_EVAL_HW_BUILD") == "1"
    with tempfile.TemporaryDirectory(prefix="litex_agent_eval_ecpix5_") as tmp:
        r = _target(os.path.join(workdir, "target.py"), tmp, ["--build"] if build else [])
        result.add("elaborate", r.returncode == 0, (r.stdout + r.stderr)[-500:])
        if r.returncode != 0:
            return result
        gateware = os.path.join(tmp, "gateware")
        with open(os.path.join(gateware, "lambdaconcept_ecpix5.ys")) as f:
            result.add("ip_source", "acme_scaler.v" in f.read())
        with open(os.path.join(tmp, "csr.csv")) as f:
            csr = f.read()
        result.add("scaler_region", "memory_region,scaler,0x90000000" in csr)
        result.add("uartbone_crossover", "uart_xover_rxtx" in csr)
        if build:
            result.add("bitstream", os.path.exists(os.path.join(gateware, "lambdaconcept_ecpix5.bit")))
    return result

def check(workdir):
    result = CheckResult("ecpix5_scaler")
    env    = board_env()
    if not hardware_enabled(HARDWARE) or not env["ECPIX5_BUSDEV"]:
        result.error = ("Hardware task: needs an ECPIX-5, LITEX_AGENT_EVAL_HW=ecpix5 and "
            "LITEX_AGENT_EVAL_ECPIX5_BUSDEV=<bus:dev>.")
        return result
    try:
        driver = _load_driver(workdir)
    except Exception as e:
        result.add("driver_import", False, f"{type(e).__name__}: {e}")
        return result

    tmp = tempfile.mkdtemp(prefix="litex_agent_eval_ecpix5_")
    try:
        # Build the reference SoC and load it to SRAM.
        r = _target(TASK_TARGET, tmp, ["--build", "--load", f"--busdev={env['ECPIX5_BUSDEV']}"])
        if r.returncode != 0:
            result.error = f"Build/load failed:\n{(r.stdout + r.stderr)[-1000:]}"
            return result

        with BoardSession(env["ECPIX5_UART"], SERVER_PORT, os.path.join(tmp, "csr.csv")) as session:
            bus = session.bus
            ident = bus.read(ID)
            result.add("ip_id", ident == 0xac5c0102, f"{ident:#010x}")
            for gain, offset in CONFIGS:
                try:
                    driver.configure(bus, gain, offset)
                except Exception as e:
                    result.add(f"configure_{gain}_{offset}", False, f"{type(e).__name__}: {e}")
                    continue
                errors = []
                for x in SAMPLES:
                    bus.write(DIN, x)
                    for _ in range(10):
                        if bus.read(STATUS) & 0x1:
                            break
                    y        = bus.read(DOUT)
                    expected = min(int(x*gain) + offset, 0xffff)
                    if abs(y - expected) > 1:
                        errors.append(f"x={x} y={y} expected={expected}")
                result.add(f"gain_{gain}_offset_{offset}", not errors, errors[:4])
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return result
