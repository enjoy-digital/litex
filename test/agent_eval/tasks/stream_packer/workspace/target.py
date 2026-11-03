#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC with a test harness of the stream packer (packer.py): a packet generator, the
# packer and a checker with a back-pressure generator, reachable through a UARTBone bridge, with
# an optional LiteScope analyzer (analyzer.csv in the output directory):
#   ./target.py --uart-tcp-port=21600 [--with-analyzer]
#   litex_server --uart --uart-port=socket://localhost:21600 --bind-port=21601

import os
import sys
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from packer import Packer

# Helpers ------------------------------------------------------------------------------------------

class LFSR(LiteXModule):
    """32-bit Galois LFSR (x^32 + x^22 + x^2 + x + 1), advances when ce."""
    def __init__(self, seed, ce=1):
        self.value = value = Signal(32, reset=seed)
        self.sync += If(ce, If(value[0],
                value.eq((value >> 1) ^ 0x80200003),
            ).Else(
                value.eq(value >> 1),
            )
        )

# Packer Test Harness ------------------------------------------------------------------------------

class PackerTest(LiteXModule):
    """Packer test: sends packets of random lengths (length_min + (random & length_mask) bytes,
    the bytes are a running 8-bit counter) to the packer, back-pressures its output (the output
    is ready with a probability of (16 - backpressure)/16) and checks the received words.

    Writing control.start clears the counters and sends packets packets; status.done is set when
    all the bytes are received (or on timeout).
    """
    def __init__(self, packer):
        self.control      = CSRStorage(fields=[
            CSRField("start", size=1, pulse=True, description="Start a test."),
        ])
        self.packets      = CSRStorage(16, reset=1000, description="Number of packets to send.")
        self.length_min   = CSRStorage(8,  reset=1,    description="Minimum packet length (bytes, >= 1).")
        self.length_mask  = CSRStorage(8,  reset=63,   description="Random length mask.")
        self.backpressure = CSRStorage(4,  reset=8,    description="Back-pressure level (0: none, 15: max).")
        self.status       = CSRStatus(fields=[
            CSRField("busy", size=1, description="Test in progress."),
            CSRField("done", size=1, description="Test done."),
        ])
        self.tx_packets  = CSRStatus(32, description="Packets sent.")
        self.tx_bytes    = CSRStatus(32, description="Bytes sent.")
        self.rx_packets  = CSRStatus(32, description="Packets received (words with last).")
        self.rx_bytes    = CSRStatus(32, description="Bytes received.")
        self.data_errors = CSRStatus(32, description="Received bytes not matching the counter.")
        self.cycles      = CSRStatus(32, description="Test duration (cycles).")

        # # #

        sink, source = packer.sink, packer.source

        # Generator.
        self.gen_lfsr = gen_lfsr = LFSR(seed=0x1234567)
        busy      = Signal()
        remaining = Signal(16)
        length    = Signal(9)
        tx_data   = Signal(8)
        tx_done   = Signal()
        self.comb += [
            sink.valid.eq(busy & ~tx_done & (remaining != 0)),
            sink.data.eq(tx_data),
            sink.last.eq(length == 1),
        ]
        start = self.control.fields.start
        self.sync += [
            If(start,
                busy.eq(1),
                tx_done.eq(0),
                remaining.eq(self.packets.storage),
                length.eq(self.length_min.storage + (gen_lfsr.value[:8] & self.length_mask.storage)),
                tx_data.eq(0),
                self.tx_packets.status.eq(0),
                self.tx_bytes.status.eq(0),
            ).Elif(sink.valid & sink.ready,
                tx_data.eq(tx_data + 1),
                self.tx_bytes.status.eq(self.tx_bytes.status + 1),
                If(sink.last,
                    remaining.eq(remaining - 1),
                    self.tx_packets.status.eq(self.tx_packets.status + 1),
                    length.eq(self.length_min.storage + (gen_lfsr.value[:8] & self.length_mask.storage)),
                    If(remaining == 1, tx_done.eq(1)),
                ).Else(
                    length.eq(length - 1),
                )
            )
        ]

        # Back-pressure.
        self.bp_lfsr = bp_lfsr = LFSR(seed=0x89abcdef)
        self.comb += source.ready.eq(bp_lfsr.value[:4] >= self.backpressure.storage)

        # Checker.
        rx_data = Signal(8)
        error   = Signal()
        self.error = error
        bytes_ok = Signal(4)
        for i in range(4):
            self.comb += bytes_ok[i].eq((i >= source.count) | (source.data[8*i:8*(i+1)] == (rx_data + i)[:8]))
        self.comb += error.eq(source.valid & source.ready & (bytes_ok != 0xf))
        timeout = Signal(24)
        self.sync += [
            If(start,
                rx_data.eq(0),
                timeout.eq(0),
                self.rx_packets.status.eq(0),
                self.rx_bytes.status.eq(0),
                self.data_errors.status.eq(0),
                self.cycles.status.eq(0),
            ).Elif(busy,
                self.cycles.status.eq(self.cycles.status + 1),
                timeout.eq(timeout + 1),
                If(source.valid & source.ready,
                    timeout.eq(0),
                    rx_data.eq(rx_data + source.count),
                    self.rx_bytes.status.eq(self.rx_bytes.status + source.count),
                    If(source.last, self.rx_packets.status.eq(self.rx_packets.status + 1)),
                    If(error, self.data_errors.status.eq(self.data_errors.status + 1)),
                ),
                If((tx_done & (self.rx_bytes.status == self.tx_bytes.status)) | (timeout == 100000),
                    busy.eq(0),
                )
            )
        ]
        self.comb += [
            self.status.fields.busy.eq(busy),
            self.status.fields.done.eq(~busy & tx_done),
        ]

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with a stream packer test harness.")
    parser.add_argument("--uart-tcp-port", default=21600, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    parser.add_argument("--with-analyzer", action="store_true",     help="Add a LiteScope analyzer on the packer.")
    args = parser.parse_args()

    # SoC.
    soc = SimSoC(cpu_type=None, with_uart=False, with_uartbone=True)
    soc.packer = packer = Packer()
    soc.test   = test   = PackerTest(packer)

    # LiteScope analyzer (analyzer.csv is written before the simulation runs).
    analyzer_csv = os.path.join(os.path.abspath(args.output_dir), "analyzer.csv")
    if args.with_analyzer:
        from litescope import LiteScopeAnalyzer
        soc.analyzer = LiteScopeAnalyzer([
            packer.sink,
            packer.word,
            packer.skid,
            packer.source,
            test.error,
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
