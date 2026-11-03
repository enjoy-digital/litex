#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC (VexRiscv CPU, BIOS) with a 4-channel ADC model, running the prebuilt sampler
# firmware (firmware/sampler.bin) from its main RAM. The CPU console is on a crossover UART, reached
# (as the SoC's bus) through a UARTBone bridge:
#   ./target.py --uart-tcp-port=21700
#   litex_server --uart --uart-port=socket://localhost:21700 --bind-port=21701
#   litex_term crossover --csr-csv=build/sim/csr.csv --port=21701

import os
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import *
from litex.soc.integration.common import get_mem_data
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

FIRMWARE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware", "sampler.bin")

# ADC Model ----------------------------------------------------------------------------------------

class ADCModel(LiteXModule):
    """4-channel ADC model: a conversion of the selected channel starts on control.start and takes
    32 cycles per sample (oversample: 2^oversample samples averaged); status.done is set when data
    holds the result."""
    def __init__(self, values):
        assert len(values) == 4
        self.control = CSRStorage(fields=[
            CSRField("start",      size=1, offset=0, pulse=True, description="Start a conversion."),
            CSRField("channel",    size=2, offset=4, description="Channel to convert."),
            CSRField("oversample", size=2, offset=8, description="Oversampling (2^oversample samples averaged)."),
        ])
        self.status = CSRStatus(fields=[
            CSRField("done", size=1, description="Conversion done, data is valid."),
        ])
        self.data = CSRStatus(12, description="Conversion result (12-bit).")

        # # #

        timer   = Signal(10)
        running = Signal()
        sample  = Signal(12)
        self.comb += Case(self.control.fields.channel, {i: sample.eq(v) for i, v in enumerate(values)})
        self.sync += [
            If(self.control.fields.start,
                running.eq(1),
                timer.eq((32 << self.control.fields.oversample) - 1),
                self.status.fields.done.eq(0),
            ).Elif(running,
                timer.eq(timer - 1),
                If(timer == 0,
                    running.eq(0),
                    self.data.status.eq(sample),
                    self.status.fields.done.eq(1),
                )
            )
        ]

# SoC ----------------------------------------------------------------------------------------------

class SamplerSoC(SimSoC):
    def __init__(self, firmware=FIRMWARE, adc_values=(0x0a5, 0x3c1, 0x7ff, 0x123)):
        main_ram_init = [] if firmware is None else get_mem_data(firmware, endianness="little", offset=0x40000000)
        SimSoC.__init__(self,
            cpu_type                 = "vexriscv",
            integrated_rom_size      = 0x20000,
            integrated_main_ram_size = 0x10000,
            integrated_main_ram_init = main_ram_init,
            uart_name                = "crossover",
            with_uartbone            = True,
        )
        self.add_constant("ROM_BOOT_ADDRESS", self.mem_map["main_ram"])
        self.adc = ADCModel(values=adc_values)

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC running the sampler firmware.")
    parser.add_argument("--uart-tcp-port", default=21700, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    parser.add_argument("--firmware",      default=FIRMWARE,        help="Firmware loaded in main RAM.")
    parser.add_argument("--adc-values",    default="0x0a5,0x3c1,0x7ff,0x123", help="ADC model channel values.")
    args = parser.parse_args()

    # SoC.
    soc = SamplerSoC(firmware=args.firmware, adc_values=[int(v, 0) for v in args.adc_values.split(",")])

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False)

if __name__ == "__main__":
    main()
