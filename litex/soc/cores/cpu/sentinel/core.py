#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Greg Davill <greg.davill@gmail.com>
# Copyright (c) 2025 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

import os
from pathlib import Path
import shutil
import sys
import subprocess
import logging

from migen import *

from litex.build.generic_platform import Pins, IOStandard
from litex.gen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# GCC Flags ----------------------------------------------------------------------------------------

# SERV ---------------------------------------------------------------------------------------------

class Sentinel(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "sentinel"
    human_name           = "Sentinel"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x0000_0000: 0x1000_0000,  # Private data area.
                            0x8000_0000: 0x8000_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-march=rv32i2p0 "
        flags += "-mabi=ilp32 "
        flags += "-D__sentinel__ "
        return flags

    @property
    def mem_map(self):
        return {
            "private"  : 0x0000_0000,
            "spiflash" : 0x1000_0000,
            "rom"      : 0x2000_0000,
            "sram"     : 0x2100_0000,
            "main_ram" : 0x4000_0000,
            "csr"      : 0x8200_0000
        }

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(32)

        self.bridge = bridge = SentinelLitexBridge(self.io_regions[0x0000_0000])
        self.submodules += bridge

        self.periph_buses = [bridge.litex_bus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM)
        self.logger = logging.getLogger("Sentinel")
        # # #

        self.comb += bridge.litex_interrupts.eq(self.interrupt)

        self.cpu_params = dict(
            # Clk / Rst
            i_clk   = ClockSignal("sys"),
            i_rst = ResetSignal("sys") | self.reset,

            i_irq = bridge.sentinel_irq,

            o_bus__adr = bridge.sentinel_bus.adr,
            o_bus__cyc = bridge.sentinel_bus.cyc,
            o_bus__stb = bridge.sentinel_bus.stb,
            o_bus__sel = bridge.sentinel_bus.sel,
            o_bus__we = bridge.sentinel_bus.we,
            o_bus__dat_w = bridge.sentinel_bus.dat_w,
            i_bus__dat_r = bridge.sentinel_bus.dat_r,
            i_bus__ack = bridge.sentinel_bus.ack,
        )

    def set_reset_address(self, reset_address):
        self.logger.info(f"Reset Address is hardcoded to 0. Generating trampoline to {reset_address:#08x}")
        self.reset_address = reset_address
        self.bridge.reset_vector = reset_address

    @staticmethod
    def elaborate(verilog_filename):
        pipx_or_pdm = shutil.which("pipx") or shutil.which("pdm")

        if not pipx_or_pdm:
            raise OSError("Unable to elaborate Sentinel CPU. Make sure \"pipx\" or \"pdm\" is installed.")

        this_dir = Path(__file__).resolve().parent
        sdir = get_data_mod("cpu", "sentinel").data_location

        if subprocess.call([pipx_or_pdm, "run", this_dir / "sentinel-pep-723.py", "-n", "sentinel_cpu"],
                            stdout=open(verilog_filename, "w"),
                            cwd=sdir):
            raise OSError("Unable to elaborate Sentinel CPU, please check your Amaranth/Yosys install")

    def do_finalize(self):
        verilog_filename = os.path.join(self.platform.output_dir, "gateware", "sentinel.v")
        self.elaborate(verilog_filename = verilog_filename)
        self.platform.add_source(verilog_filename)
        self.specials += Instance("sentinel_cpu", **self.cpu_params)


class SentinelLitexBridge(LiteXModule):
    """Provide a trampoline (addresses 0x0 to 0xf) to LiteX's reset vector
       from Sentinel's hardcoded vector at 0x0.

       Additionally, provide 32 interrupt sources connected to the
       Machine External interrupt line for maximum software compatibility.
       The interrupt pending register is at address 0x10, and the mask register
       is at address 0x14.
    """

    def __init__(self, io_lim):
        self.sentinel_bus = bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.litex_bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.reset_vector = None
        self.io_lim = io_lim
        self.litex_interrupts = Signal(32)
        self.sentinel_irq = Signal()

        # Most connections are pass-through. We're effectively injecting a
        # private peripheral before any of the LiteX interconnect. LiteX
        # doesn't know about the trampoline, but it knows about the extra
        # interrupt registers via interrupt masking/clearing functions.
        self.comb += self.sentinel_bus.connect(self.litex_bus)

        # 4 opcodes to jump to the actual start program from 0. Only
        # 2 are needed, 4 are used for alignment.
        self.trampoline = Array(Signal(32) for _ in range(4))
        interrupt_reg = Signal(32)
        interrupt_mask = Signal(32)

        bus_dat_r_override = Signal(32)
        bus_ack_override = Signal()

        decode_expr = bus.adr[-4:] == 0

        self.comb += [
            bus.ack.eq(self.litex_bus.ack | bus_ack_override),
            bus.dat_r.eq(Mux(decode_expr, bus_dat_r_override,
                             self.litex_bus.dat_r)),
            # If we match our private area, make sure LiteX never sees the
            # xfer.
            self.litex_bus.cyc.eq(bus.cyc & ~decode_expr),
            self.litex_bus.stb.eq(bus.stb & ~decode_expr),

            self.sentinel_irq.eq((interrupt_reg & interrupt_mask) != 0),
        ]

        def dat_r_sel(reg_inp):
            return [
                If(bus.sel & 0x01,
                    bus_dat_r_override[0:8].eq(reg_inp[0:8])
                ),
                If(bus.sel & 0x02,
                    bus_dat_r_override[8:16].eq(reg_inp[8:16])
                ),
                If(bus.sel & 0x04,
                    bus_dat_r_override[16:24].eq(reg_inp[16:24])
                ),
                If(bus.sel & 0x08,
                    bus_dat_r_override[24:32].eq(reg_inp[24:32])
                )
            ]

        def dat_w_sel(reg_outp):
            return [
                If(bus.sel & 0x01,
                    reg_outp[0:8].eq(bus.dat_w[0:8])
                ),
                If(bus.sel & 0x02,
                    reg_outp[8:16].eq(bus.dat_w[8:16])
                ),
                If(bus.sel & 0x04,
                    reg_outp[16:24].eq(bus.dat_w[16:24])
                ),
                If(bus.sel & 0x08,
                    reg_outp[24:32].eq(bus.dat_w[24:32])
                ),
            ]

        self.sync += [
            bus_ack_override.eq(0),
            If(bus.cyc & bus.stb & ~bus.ack,
                If(~bus.we,
                    If((bus.adr >= 0) & (bus.adr < 4),
                        *dat_r_sel(self.trampoline[bus.adr]),
                        bus_ack_override.eq(1),
                    ).Elif(bus.adr == 4,
                        *dat_r_sel(interrupt_reg),
                        bus_ack_override.eq(1),
                    ).Elif(bus.adr == 5,
                        *dat_r_sel(interrupt_mask),
                        bus_ack_override.eq(1),
                    )
                )
            ),

            # This is a write to our private I/O space, so prepare the
            # ACK signal.
            If(bus.cyc & bus.stb & bus.we & decode_expr,
                bus_ack_override.eq(1)
            ),

            # Sample interrupts...
            interrupt_reg.eq(self.litex_interrupts),

            If(bus.cyc & bus.stb & bus.ack & bus.we,
                # Unless we are writing to the interrupt reg this cycle.
                # The OR-ing would reduce latency by one cycle if interrupt
                # is still active, but not sure if it's worth it.
                If(bus.adr == 4,
                    *dat_w_sel(interrupt_reg)  # | self.interrupt)
                ).Elif(bus.adr == 5,
                    *dat_w_sel(interrupt_mask)
                )
            ),
        ]

    def do_finalize(self):
        # Nothing good will happen if our trampoline jumps into the private
        # I/O area.
        assert self.reset_vector and (self.reset_vector > self.io_lim)
        reset_addr = C(self.reset_vector, 32)

        # Assemble the trampoline; it's called a "tail offset" pseudo-
        # instruction.
        self.comb += [
            self.trampoline[0].eq(Cat(C(0b00110_0010111, 12), reset_addr[12:32] + reset_addr[11])),  # AUIPC x6, offset[31:12] + offset[11]
            self.trampoline[1].eq(Cat(C(0b00110_000_00000_1100111), reset_addr[0:12]))  # JALR x0, offset[11:0](x6)
        ]
