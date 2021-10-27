#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2017 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2021 Gregory Davill <greg.davill@gmail.com>
# Copyright (c) 2021 Gabriel L. Somlo <somlo@cmu.edu>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import AsyncResetSynchronizer, MultiReg

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

# ECP5 JTAG ----------------------------------------------------------------------------------------

class ECP5JTAG(Module):
    def __init__(self, tck_delay_luts=8):
        self.reset   = Signal()
        self.capture = Signal()
        self.shift   = Signal()
        self.update  = Signal()

        self.tck = Signal()
        self.tdi = Signal()
        self.tdo = Signal()

        # # #

        rst_n  = Signal()
        tck    = Signal()
        jce1   = Signal()
        jce1_d = Signal()

        self.sync.jtag += jce1_d.eq(jce1)
        self.comb += self.capture.eq(jce1 & ~jce1_d) # First cycle jce1 is high we're in Capture-DR.
        self.comb += self.reset.eq(~rst_n)

        self.specials += Instance("JTAGG",
            o_JRSTN   = rst_n,
            o_JSHIFT  = self.shift,
            o_JUPDATE = self.update,

            o_JTCK  = tck,
            o_JTDI  = self.tdi, # JTDI = FF(posedge TCK, TDI)
            o_JCE1  = jce1,     # (FSM==Capture-DR || Shift-DR) & (IR==0x32)
            i_JTDO1 = self.tdo, # FF(negedge TCK, JTDO1) if (IR==0x32 && FSM==Shift-DR)
        )

        # TDI/TCK are synchronous on JTAGG output (TDI being registered with TCK). Introduce a delay
        # on TCK with multiple LUT4s to allow its use as the JTAG Clk.
        for i in range(tck_delay_luts):
            new_tck = Signal()
            self.specials += Instance("LUT4",
                attr   = {"keep"},
                p_INIT = 2,
                i_A = tck,
                i_B = 0,
                i_C = 0,
                i_D = 0,
                o_Z = new_tck
            )
            tck = new_tck
        self.comb += self.tck.eq(tck)

# JTAG PHY -----------------------------------------------------------------------------------------

class JTAGPHY(Module):
    def __init__(self, jtag=None, device=None, data_width=8, clock_domain="sys", chain=1):
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
                jtag = S6JTAG(chain=chain)
            elif device[:3] == "xc7":
                jtag = S7JTAG(chain=chain)
            elif device[:4] in ["xcku", "xcvu"]:
                jtag = USJTAG(chain=chain)
            elif device[:5] == "LFE5U":
                jtag = ECP5JTAG()
            else:
                print(device)
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
