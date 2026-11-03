#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC with a checksum engine, reachable through a UARTBone bridge, with an optional
# LiteScope analyzer on the engine (analyzer.csv in the output directory):
#   ./target.py --uart-tcp-port=21200 [--with-analyzer]
#   litex_server --uart --uart-port=socket://localhost:21200 --bind-port=21201

import os
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import *
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

# Checksum Engine ----------------------------------------------------------------------------------

class ChecksumEngine(LiteXModule):
    """Sums length words of a pattern generator (seed, seed + 1, ...) into result.

    Writing control.start starts a run; status.busy is set during the run and status.done when
    result is valid.
    """
    def __init__(self):
        self.control = CSRStorage(fields=[
            CSRField("start", size=1, pulse=True, description="Start a run."),
        ])
        self.length = CSRStorage(16, reset=16, description="Number of words to sum.")
        self.seed   = CSRStorage(32, description="First word of the pattern.")
        self.status = CSRStatus(fields=[
            CSRField("busy", size=1, description="Run in progress."),
            CSRField("done", size=1, description="Result valid."),
        ])
        self.result = CSRStatus(32, description="Sum of the words (modulo 2^32).")

        # # #

        # Pattern generator.
        self.valid = valid = Signal()
        self.data  = data  = Signal(32)

        # Control.
        self.count = count = Signal(8)
        self.acc   = acc   = Signal(32)
        self.busy  = busy  = Signal()
        self.done  = done  = Signal()

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.control.fields.start,
                NextValue(count, 0),
                NextValue(acc,   0),
                NextValue(data,  self.seed.storage),
                NextValue(done,  0),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            busy.eq(1),
            valid.eq(1),
            NextValue(acc,   acc + data),
            NextValue(data,  data + 1),
            NextValue(count, count + 1),
            If(count == (self.length.storage - 1),
                NextState("DONE")
            )
        )
        fsm.act("DONE",
            NextValue(done, 1),
            NextState("IDLE")
        )
        self.comb += [
            self.status.fields.busy.eq(busy),
            self.status.fields.done.eq(done),
            self.result.status.eq(acc),
        ]

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with a checksum engine.")
    parser.add_argument("--uart-tcp-port", default=21200, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    parser.add_argument("--with-analyzer", action="store_true",     help="Add a LiteScope analyzer on the engine.")
    args = parser.parse_args()

    # SoC.
    soc = SimSoC(cpu_type=None, with_uart=False, with_uartbone=True)
    soc.engine = engine = ChecksumEngine()

    # LiteScope analyzer (analyzer.csv is written before the simulation runs).
    analyzer_csv = os.path.join(os.path.abspath(args.output_dir), "analyzer.csv")
    if args.with_analyzer:
        from litescope import LiteScopeAnalyzer
        soc.analyzer = LiteScopeAnalyzer([
            engine.control.fields.start,
            engine.fsm,
            engine.busy,
            engine.done,
            engine.valid,
            engine.count,
            engine.data,
            engine.length.storage,
        ], depth=512, clock_domain="sys", csr_csv=None)

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    def pre_run_callback(vns):
        if args.with_analyzer:
            soc.analyzer.export_csv(vns, analyzer_csv)
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False, pre_run_callback=pre_run_callback)

if __name__ == "__main__":
    main()
