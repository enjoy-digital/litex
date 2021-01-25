#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2017 Robert Jordens <jordens@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import AsyncResetSynchronizer

from litex.soc.interconnect import stream

# Altera Atlantic JTAG -----------------------------------------------------------------------------

class JTAGAtlantic(Module):
    def __init__(self):
        self.sink   =   sink = stream.Endpoint([("data", 8)])
        self.source = source = stream.Endpoint([("data", 8)])

        # # #

        self.specials += Instance("alt_jtag_atlantic",
            # Parameters
            p_LOG2_RXFIFO_DEPTH       = "5", # FIXME: expose?
            p_LOG2_TXFIFO_DEPTH       = "5", # FIXME: expose?
            p_SLD_AUTO_INSTANCE_INDEX = "YES",

            # Clk/Rst
            i_clk   = ClockSignal("sys"),
            i_rst_n = ~ResetSignal("sys"),

            # TX
            i_r_dat = sink.data,
            i_r_val = sink.valid,
            o_r_ena = sink.ready,

            # RX
            o_t_dat = source.data,
            i_t_dav = source.ready,
            o_t_ena = source.valid,
        )

# Xilinx JTAG --------------------------------------------------------------------------------------

class XilinxJTAG(Module):
    def __init__(self, primitive, chain=1):
        self.reset   = Signal()
        self.capture = Signal()
        self.shift   = Signal()
        self.update  = Signal()

        self.tck = Signal()
        self.tms = Signal()
        self.tdi = Signal()
        self.tdo = Signal()

        # # #

        self.specials += Instance(primitive,
            p_JTAG_CHAIN = chain,

            o_RESET   = self.reset,
            o_CAPTURE = self.capture,
            o_SHIFT   = self.shift,
            o_UPDATE  = self.update,

            o_TCK = self.tck,
            o_TMS = self.tms,
            o_TDI = self.tdi,
            i_TDO = self.tdo,
        )

class S6JTAG(XilinxJTAG):
    def __init__(self, *args, **kwargs):
        XilinxJTAG.__init__(self, primitive="BSCAN_SPARTAN6", *args, **kwargs)


class S7JTAG(XilinxJTAG):
    def __init__(self, *args, **kwargs):
        XilinxJTAG.__init__(self, primitive="BSCANE2", *args, **kwargs)


class USJTAG(XilinxJTAG):
    def __init__(self, *args, **kwargs):
        XilinxJTAG.__init__(self, primitive="BSCANE2", *args, **kwargs)

# JTAG PHY -----------------------------------------------------------------------------------------

class JTAGPHY(Module):
    def __init__(self, jtag=None, device=None, data_width=8, clock_domain="sys"):
        """JTAG PHY

        Provides a simple JTAG to LiteX stream module to easily stream data to/from the FPGA
        over JTAG.

        Wire format: data_width + 2 bits, LSB first.

        Host to Target:
          - TX ready : bit 0
          - RX data: : bit 1 to data_width
          - RX valid : bit data_width + 1

        Target to Host:
          - RX ready : bit 0
          - TX data  : bit 1 to data_width
          - TX valid : bit data_width + 1
        """
        self.sink   =   sink = stream.Endpoint([("data", data_width)])
        self.source = source = stream.Endpoint([("data", data_width)])

        # # #

        valid = Signal()
        data  = Signal(data_width)
        count = Signal(max=data_width)

        # JTAG TAP ---------------------------------------------------------------------------------
        if jtag is None:
            if device[:3] == "xc6":
                jtag = S6JTAG()
            elif device[:3] == "xc7":
                jtag = S7JTAG()
            elif device[:4] in ["xcku", "xcvu"]:
                jtag = USJTAG()
            else:
                raise NotImplementedError
            self.submodules.jtag = jtag

        # JTAG clock domain ------------------------------------------------------------------------
        self.clock_domains.cd_jtag = ClockDomain()
        self.comb += ClockSignal("jtag").eq(jtag.tck)
        self.specials += AsyncResetSynchronizer(self.cd_jtag, ResetSignal(clock_domain))

        # JTAG clock domain crossing ---------------------------------------------------------------
        if clock_domain != "jtag":
            tx_cdc = stream.AsyncFIFO([("data", data_width)], 4)
            tx_cdc = ClockDomainsRenamer({"write": clock_domain, "read": "jtag"})(tx_cdc)
            rx_cdc = stream.AsyncFIFO([("data", data_width)], 4)
            rx_cdc = ClockDomainsRenamer({"write": "jtag", "read": clock_domain})(rx_cdc)
            self.submodules.tx_cdc = tx_cdc
            self.submodules.rx_cdc = rx_cdc
            self.comb += [
                sink.connect(tx_cdc.sink),
                rx_cdc.source.connect(source)
            ]
            sink, source = tx_cdc.source, rx_cdc.sink

        # JTAG Xfer FSM ----------------------------------------------------------------------------
        fsm = FSM(reset_state="XFER-READY")
        fsm = ClockDomainsRenamer("jtag")(fsm)
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(jtag.reset | jtag.capture)
        fsm.act("XFER-READY",
            jtag.tdo.eq(source.ready),
            If(jtag.shift,
                sink.ready.eq(jtag.tdi),
                NextValue(valid, sink.valid),
                NextValue(data,  sink.data),
                NextValue(count, 0),
                NextState("XFER-DATA")
            )
        )
        fsm.act("XFER-DATA",
            jtag.tdo.eq(data),
            If(jtag.shift,
                NextValue(count, count + 1),
                NextValue(data, Cat(data[1:], jtag.tdi)),
                If(count == (data_width - 1),
                    NextState("XFER-VALID")
                )
            )
        )
        fsm.act("XFER-VALID",
            jtag.tdo.eq(valid),
            If(jtag.shift,
                source.valid.eq(jtag.tdi),
                NextState("XFER-READY")
            )
        )
        self.comb += source.data.eq(data)
