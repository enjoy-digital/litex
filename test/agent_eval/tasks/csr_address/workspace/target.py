#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC with a temperature sensor model, reachable through a UARTBone bridge:
#   ./target.py --uart-tcp-port=21000
#   litex_server --uart --uart-port=socket://localhost:21000 --bind-port=21001

import os
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import *
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

# Sensor Model -------------------------------------------------------------------------------------

class SensorModel(LiteXModule):
    """Temperature sensor model: a conversion takes 64 cycles once enabled, value in 1/16 °C."""
    def __init__(self, raw=0x2a3):
        self.control = CSRStorage(fields=[
            CSRField("enable", size=1, description="Enable the conversions."),
        ])
        self.status = CSRStatus(fields=[
            CSRField("ready", size=1, description="Conversion done, value is valid."),
        ])
        self.value = CSRStatus(16, description="Temperature (1/16 °C).")
        self.id    = CSRStatus(32, reset=0x53454e53, description="Sensor identifier.")

        # # #

        timer = Signal(8)
        self.sync += [
            If(~self.control.fields.enable,
                timer.eq(0),
                self.status.fields.ready.eq(0),
                self.value.status.eq(0),
            ).Elif(timer != 64,
                timer.eq(timer + 1),
            ).Else(
                self.status.fields.ready.eq(1),
                self.value.status.eq(raw),
            )
        ]

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with a temperature sensor model.")
    parser.add_argument("--uart-tcp-port", default=21000, type=int,  help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",      help="Build directory.")
    parser.add_argument("--sensor-raw",    default=0x2a3, type=lambda s: int(s, 0), help="Sensor reading (1/16 °C).")
    args = parser.parse_args()

    # SoC.
    soc = SimSoC(cpu_type=None, with_uart=False, with_uartbone=True)
    soc.sensor = SensorModel(raw=args.sensor_raw)

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False)

if __name__ == "__main__":
    main()
