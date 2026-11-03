#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC with a ticker peripheral, reachable through a UARTBone bridge:
#   ./target.py --uart-tcp-port=21100
#   litex_server --uart --uart-port=socket://localhost:21100 --bind-port=21101

import os
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import *
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

# Ticker -------------------------------------------------------------------------------------------

class Ticker(LiteXModule):
    """Down-counter decremented at each tick (every prescaler + 1 cycles).

    Writing load loads the counter; the counter then counts down to 0 and stops there (one-shot)
    or reloads (periodic, control.reload=1).
    """
    def __init__(self):
        self.control = CSRStorage(fields=[
            CSRField("enable", size=1, description="Ticker enable."),
            CSRField("reload", size=1, description="Reload the counter at 0 (periodic mode)."),
        ])
        self.prescaler = CSRStorage(16, reset=999, description="Tick period - 1 (in sys_clk cycles).")
        self.load      = CSRStorage(32, description="Counter value, loaded on write.")
        self.value     = CSRStatus(32, description="Counter value.")
        self.status    = CSRStatus(fields=[
            CSRField("zero", size=1, description="Counter is 0."),
        ])

        # # #

        tick      = Signal()
        prescaler = Signal(16)
        counter   = Signal(32)
        self.sync += [
            tick.eq(0),
            If(prescaler == 0,
                tick.eq(1),
                prescaler.eq(self.prescaler.storage),
            ).Else(
                prescaler.eq(prescaler - 1),
            ),
            If(self.load.re,
                counter.eq(self.load.storage),
            ).Elif(tick & self.control.fields.enable,
                If(counter != 0,
                    counter.eq(counter - 1),
                ).Elif(self.control.fields.reload,
                    counter.eq(self.load.storage),
                )
            )
        ]
        self.comb += [
            self.value.status.eq(counter),
            self.status.fields.zero.eq(counter == 0),
        ]

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with a ticker peripheral.")
    parser.add_argument("--uart-tcp-port", default=21100, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    args = parser.parse_args()

    # SoC.
    soc = SimSoC(cpu_type=None, with_uart=False, with_uartbone=True)
    soc.ticker = Ticker()

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False)

if __name__ == "__main__":
    main()
