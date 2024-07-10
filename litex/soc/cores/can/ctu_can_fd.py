#
# CTU CAN-FD Core Wrapper for LiteX.
#
# Copyright (c) 2021      Andrew Dennison <andrew@motec.com.au>
# Copyright (c) 2021-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2024      Gwenhael Goavec-Merou <gwenhael@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Documentation at https://canbus.pages.fel.cvut.cz/

import os
import subprocess

from migen import *

from litex.gen import *

from litex.build import tools
from litex.build.vhd2v_converter import VHD2VConverter

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr_eventmanager import *

# CTU CAN-FD ---------------------------------------------------------------------------------------

class CTUCANFD(LiteXModule, EventManager):
    def __init__(self, platform, pads, timestamp=0, force_convert=False):
        # Parameters.
        self.platform       = platform
        self.pads           = pads
        self._force_convert = force_convert

        # Wishbone Bus.
        self.bus = wishbone.Interface(data_width=32)

        # CSRs.
        self.control = CSRStorage(32, fields=[
            CSRField("reset", size=1, values=[
                ("``0b0``", "Normal Operation."),
                ("``0b1`",  "Hold the Core in Reset."),
            ], reset=0b0),
            CSRField("reserved",size=31),
        ])
        self.status = CSRStatus(32, fields=[
            CSRField("ready", size=1, values=[
                ("``0b0``", "Core in Reset."),
                ("``0b1`",  "Core Ready."),
            ]),
        ])

        # IRQs.
        self.irq = Signal()

        # CTU CAN-FD Instance ----------------------------------------------------------------------
        self.core_params = dict()

        # Wishbone to CTU CAN-FD Memory Bus adaptation.
        self.mem_scs      = mem_scs      = Signal()
        self.mem_srd      = mem_srd      = Signal()
        self.mem_swr      = mem_swr      = Signal()
        self.mem_sbe      = mem_sbe      = Signal(4)
        self.mem_adress   = mem_adress   = Signal(16)
        self.mem_data_in  = mem_data_in  = Signal(32)
        self.mem_data_out = mem_data_out = Signal(32)

        self.comb += [
            # On Wishbone Access cycle...
            mem_scs.eq(self.bus.cyc & self.bus.stb),
            mem_srd.eq(mem_scs & ~self.bus.we & ~self.bus.ack),
            mem_swr.eq(mem_scs & self.bus.we),
            mem_sbe.eq(self.bus.sel),
            # Connect data_in/out.
            mem_data_in.eq(self.bus.dat_w),
            self.bus.dat_r.eq(mem_data_out),
            # Convert 32-bit word addressing to bytes addressing.
            mem_adress.eq(Cat(Signal(2), self.bus.adr)),
        ]
        self.sync += [
            self.bus.ack.eq(0),
            If(mem_scs & ~self.bus.ack, self.bus.ack.eq(1)),
        ]

        # CTU CAN-FD Parameters.
        self.core_params.update(
            # Target technology (ASIC or FPGA)
            #p_target_technology = C_TECH_FPGA

            # TX/RX Buffers.
            p_txt_buffer_count      = 4,  # Number of TX Buffers.
            p_rx_buffer_size        = 32, # RX Buffer size (in 32-bit words).

            # Filter A-C.
            p_sup_filtA             = False,
            p_sup_filtB             = False,
            p_sup_filtC             = False,

            # Range Filter.
            #p_sup_filtV            = False,

            # Synthesize Range Filter
            p_sup_range             = False,

            # Test registers.
            p_sup_test_registers = True, # True to have access to 0x9XX Tests registers

            # Traffic counters.
            p_sup_traffic_ctrs      = False,

            # Add parity bit to TXT Buffer and RX Buffer RAMs
            p_sup_parity            = False,

            # Number of active timestamp bits
            p_active_timestamp_bits = 63,

            # Reset TXT / RX Buffer RAMs
            p_reset_buffer_rams     = False,
        )

        # CTU CAN-FD Signals.
        self.core_params.update(
            # Clk / Rst.
            i_clk_sys   = ClockSignal("sys"),
            i_res_n     = ~(ResetSignal("sys") | self.control.fields.reset),
            o_res_n_out = self.status.fields.ready,

            # DFT support (ASIC only).
            i_scan_enable = 0,

            # Timestamp (For time based transmission / reception).
            i_timestamp = timestamp,

            # Memory interface.
            i_scs      = mem_scs,
            i_srd      = mem_srd,
            i_swr      = mem_swr,
            i_sbe      = mem_sbe,
            i_adress   = mem_adress,
            i_data_in  = mem_data_in,
            o_data_out = mem_data_out,

            # Interrupt.
            o_int = self.irq,

            # CAN Bus.
            o_can_tx = pads.tx,
            i_can_rx = pads.rx,

            # Debug.
            #o_test_probe = ,
        )

    def add_sources(self, platform):
        sources = []
        sdir = "CTU-CAN-FD"
        cdir = os.path.dirname(__file__)
        if not os.path.exists(sdir):
            os.system(f"git clone https://github.com/enjoy-digital/CTU-CAN-FD")
        with open(os.path.join(cdir, 'rtl_lst.txt')) as f:
            for line in f:
                srcfile = os.path.join(sdir, line.strip().replace('rtl', 'src'))
                self.vhd2v_converter.add_source(srcfile)

    def do_finalize(self):
        # CAN Core instance
        self.vhd2v_converter = VHD2VConverter(self.platform,
            top_entity    = "can_top_level",
            build_dir     = os.path.abspath(os.path.dirname(__file__)),
            work_package  = "ctu_can_fd_rtl",
            force_convert = self._force_convert,
            params        = self.core_params,
            add_instance  = True,
        )

        # Add Sources.
        self.add_sources(self.platform)
