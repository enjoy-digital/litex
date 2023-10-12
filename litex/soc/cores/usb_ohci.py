#
# This file is part of LiteX.
#
# Copyright (c) 2021 Dolu1990 <charles.papon.90@gmail.com>
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2023 Lone Dynamics Corporation <info@lonedynamics.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex import get_data_mod

from litex.gen import *

from litex.soc.interconnect import wishbone

from litex.build.io import SDRTristate

# USB OHCI -----------------------------------------------------------------------------------------

class USBOHCI(LiteXModule):
    def __init__(self, platform, pads, usb_clk_freq=48e6, dma_data_width=32):
        self.pads           = pads
        self.usb_clk_freq   = int(usb_clk_freq)
        self.dma_data_width = dma_data_width

        self.wb_ctrl = wb_ctrl = wishbone.Interface(data_width=32)
        self.wb_dma  = wb_dma  = wishbone.Interface(data_width=dma_data_width)

        self.interrupt = Signal()

        # # #

        # Parameters.
        nports = len(pads.dp)

        # USB IOs.
        usb_ios = {}
        for i in range(nports):
            usb_ios[i] = Record([
                ("dp_i", 1), ("dp_o", 1), ("dp_oe", 1),
                ("dm_i", 1), ("dm_o", 1), ("dm_oe", 1),
            ])

        # USB OHCI Core Instance.
        self.specials += Instance(self.get_netlist_name(),
            # Clk / Rst.
            i_phy_clk    = ClockSignal("usb"),
            i_phy_reset  = ResetSignal("usb"),
            i_ctrl_clk   = ClockSignal("sys"),
            i_ctrl_reset = ResetSignal("sys"),

            # Wishbone Control.
            i_io_ctrl_CYC      = wb_ctrl.cyc,
            i_io_ctrl_STB      = wb_ctrl.stb,
            o_io_ctrl_ACK      = wb_ctrl.ack,
            i_io_ctrl_WE       = wb_ctrl.we,
            i_io_ctrl_ADR      = wb_ctrl.adr,
            o_io_ctrl_DAT_MISO = wb_ctrl.dat_r,
            i_io_ctrl_DAT_MOSI = wb_ctrl.dat_w,
            i_io_ctrl_SEL      = wb_ctrl.sel,

            # Wishbone DMA.
            o_io_dma_CYC      = wb_dma.cyc,
            o_io_dma_STB      = wb_dma.stb,
            i_io_dma_ACK      = wb_dma.ack,
            o_io_dma_WE       = wb_dma.we,
            o_io_dma_ADR      = wb_dma.adr,
            i_io_dma_DAT_MISO = wb_dma.dat_r,
            o_io_dma_DAT_MOSI = wb_dma.dat_w,
            o_io_dma_SEL      = wb_dma.sel,
            i_io_dma_ERR      = wb_dma.err,
            o_io_dma_CTI      = wb_dma.cti,
            o_io_dma_BTE      = wb_dma.bte,

            # Interrupt.
            o_io_interrupt = self.interrupt,

            # USB
            **{f"i_io_usb_{n}_dp_read"        : usb_ios[n].dp_i  for n in range(nports)},
            **{f"o_io_usb_{n}_dp_write"       : usb_ios[n].dp_o  for n in range(nports)},
            **{f"o_io_usb_{n}_dp_writeEnable" : usb_ios[n].dp_oe for n in range(nports)},
            **{f"i_io_usb_{n}_dm_read"        : usb_ios[n].dm_i  for n in range(nports)},
            **{f"o_io_usb_{n}_dm_write"       : usb_ios[n].dm_o  for n in range(nports)},
            **{f"o_io_usb_{n}_dm_writeEnable" : usb_ios[n].dm_oe for n in range(nports)},

        )

        # USB Tristates.
        for i in range(nports):
            self.specials += SDRTristate(
                io = pads.dp[i],
                o  = usb_ios[i].dp_o,
                oe = usb_ios[i].dp_oe,
                i  = usb_ios[i].dp_i,
            )
            self.specials += SDRTristate(
                io = pads.dm[i],
                o  = usb_ios[i].dm_o,
                oe = usb_ios[i].dm_oe,
                i  = usb_ios[i].dm_i,
            )

        self.add_sources(platform)

    def get_netlist_name(self):
        return "UsbOhciWishbone"    \
        f"_Dw{self.dma_data_width}" \
        f"_Pc{len(self.pads.dp)}"   \
        f"_Pf{self.usb_clk_freq}"

    def add_sources(self, platform):
        vdir = get_data_mod("misc", "usb_ohci").data_location
        netlist_name = self.get_netlist_name()

        print(f"USB OHCI netlist : {netlist_name}")
        if not os.path.exists(os.path.join(vdir, netlist_name + ".v")):
            self.generate_netlist()

        platform.add_source(os.path.join(vdir,  netlist_name + ".v"), "verilog")

    def generate_netlist(self):
        print(f"Generating USB OHCI netlist")
        vdir = get_data_mod("misc", "usb_ohci").data_location
        gen_args = []
        gen_args.append(f"--port-count={len(self.pads.dp)}")
        gen_args.append(f"--phy-frequency={self.usb_clk_freq}")
        gen_args.append(f"--dma-width={self.dma_data_width}")
        gen_args.append(f"--netlist-name={self.get_netlist_name()}")
        gen_args.append(f"--netlist-directory={vdir}")

        cmd = 'cd {path} && sbt "lib/runMain spinal.lib.com.usb.ohci.UsbOhciWishbone {args}"'.format(
            path=os.path.join(vdir, "ext", "SpinalHDL"), args=" ".join(gen_args))
        print("!!! "   + cmd)
        if os.system(cmd) != 0:
            raise OSError('Failed to run sbt')
