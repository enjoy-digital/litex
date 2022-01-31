#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2017 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2021 Gregory Davill <greg.davill@gmail.com>
# Copyright (c) 2021 Gabriel L. Somlo <somlo@cmu.edu>
# Copyright (c) 2021 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import AsyncResetSynchronizer, MultiReg

from litex.gen.fhdl.fsm import CorrectedOngoingResetFSM
from litex.soc.interconnect import stream

# JTAG TAP FSM -------------------------------------------------------------------------------------

class JTAGTAPFSM(Module):
    def __init__(self, tms: Signal, tck: Signal, expose_signals=True):
        self.submodules.fsm = fsm = ClockDomainsRenamer("jtag")(CorrectedOngoingResetFSM())

        fsm.act("test_logic_reset",
            If(~tms, NextState("run_test_idle"))
        )
        fsm.act("run_test_idle",
            If( tms, NextState("select_dr_scan"))
        )

        # DR
        fsm.act("select_dr_scan",
            If(~tms, NextState("capture_dr")    ).Else(NextState("select_ir_scan"))
        )
        fsm.act("capture_dr",
            If(~tms, NextState("shift_dr")      ).Else(NextState("exit1_dr"))
        )
        fsm.act("shift_dr",
            If( tms, NextState("exit1_dr"))
        )
        fsm.act("exit1_dr",
            If(~tms, NextState("pause_dr")      ).Else(NextState("update_dr"))
        )
        fsm.act("pause_dr",
            If( tms, NextState("exit2_dr"))
        )
        fsm.act("exit2_dr",
            If( tms, NextState("update_dr")     ).Else(NextState("shift_dr"))
        )
        fsm.act("update_dr",
            If( tms, NextState("select_dr_scan")).Else(NextState("run_test_idle"))
        )

        # IR
        fsm.act("select_ir_scan",
            If(~tms, NextState("capture_ir")    ).Else(NextState("test_logic_reset"))
        )
        fsm.act("capture_ir",
            If(~tms, NextState("shift_ir")      ).Else(NextState("exit1_ir"))
        )
        fsm.act("shift_ir",
            If( tms, NextState("exit1_ir"))
        )
        fsm.act("exit1_ir",
            If(~tms, NextState("pause_ir")      ).Else(NextState("update_ir"))
        )
        fsm.act("pause_ir",
            If( tms, NextState("exit2_ir"))
        )
        fsm.act("exit2_ir",
            If( tms, NextState("update_ir")     ).Else(NextState("shift_ir"))
        )
        fsm.act("update_ir",
            If( tms, NextState("select_dr_scan")).Else(NextState("run_test_idle"))
        )

        if expose_signals:
            for state_name in fsm.actions:
                state_sig = fsm.ongoing(state_name)
                SHOUTING_NAME = state_name.upper()
                shouting_sig = Signal(name=SHOUTING_NAME)
                setattr(self, SHOUTING_NAME, shouting_sig)
                self.comb += shouting_sig.eq(state_sig)


# Altera JTAG --------------------------------------------------------------------------------------

class AlteraJTAG(Module):
    def __init__(self, primitive, reserved_pads):
        # Common with Xilinx
        self.reset   = reset   = Signal() # provided by our own TAP FSM
        self.capture = capture = Signal() # provided by our own TAP FSM
        self.shift   = shift   = Signal()
        self.update  = update  = Signal()
        # Unique to Altera
        self.runtest = runtest = Signal()
        self.drck    = drck    = Signal()
        self.sel     = sel     = Signal()

        self.tck = tck = Signal()
        self.tms = tms = Signal()
        self.tdi = tdi = Signal()
        self.tdo = tdo = Signal()

        # magic reserved signals that have to be routed to the top module
        self.altera_reserved_tck = rtck = Signal()
        self.altera_reserved_tms = rtms = Signal()
        self.altera_reserved_tdi = rtdi = Signal()
        self.altera_reserved_tdo = rtdo = Signal()

        # inputs
        self.tdouser = tdouser = Signal()

        # outputs
        self.tmsutap = tmsutap = Signal()
        self.tckutap = tckutap = Signal()
        self.tdiutap = tdiutap = Signal()

        # # #

        # create falling-edge JTAG clock domain for TAP FSM
        self.clock_domains.cd_jtag_inv = cd_jtag_inv = ClockDomain("jtag_inv")
        self.comb += ClockSignal("jtag_inv").eq(~ClockSignal("jtag"))
        self.comb += ResetSignal("jtag_inv").eq(ResetSignal("jtag"))

        # connect the TAP state signals that LiteX expects but the HW IP doesn't provide
        self.submodules.tap_fsm = JTAGTAPFSM(tms, tck)
        self.sync.jtag_inv += reset.eq(self.tap_fsm.TEST_LOGIC_RESET)
        self.sync.jtag_inv += capture.eq(self.tap_fsm.CAPTURE_DR)

        self.specials += Instance(primitive,
            # HW TAP FSM states
            o_shiftuser      = shift,
            o_updateuser     = update,
            o_runidleuser    = runtest,
            o_clkdruser      = drck,
            o_usr1user       = sel,
            # JTAG TAP IO
            i_tdouser = tdouser,
            o_tmsutap = tmsutap,
            o_tckutap = tckutap,
            o_tdiutap = tdiutap,
            # reserved pins
            i_tms = rtms,
            i_tck = rtck,
            i_tdi = rtdi,
            o_tdo = rtdo,
        )

        # connect magical reserved signals to top level pads
        self.comb += [
            rtms.eq(reserved_pads["altera_reserved_tms"]),
            rtck.eq(reserved_pads["altera_reserved_tck"]),
            rtdi.eq(reserved_pads["altera_reserved_tdi"]),
            reserved_pads["altera_reserved_tdo"].eq(rtdo),
        ]

        # connect TAP IO
        self.comb += [
            tck.eq(tckutap),
            tms.eq(tmsutap),
            tdi.eq(tdiutap),
        ]
        self.sync.jtag_inv += tdouser.eq(tdo)

class MAX10JTAG(AlteraJTAG):
    def __init__(self, reserved_pads, *args, **kwargs):
        AlteraJTAG.__init__(self, "fiftyfivenm_jtag", reserved_pads, *args, **kwargs)

class Cyclone10LPJTAG(AlteraJTAG):
    def __init__(self, reserved_pads, *args, **kwargs):
        AlteraJTAG.__init__(self, "cyclone10lp_jtag", reserved_pads, *args, **kwargs)

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
    def __init__(self, jtag=None, device=None, data_width=8, clock_domain="sys", chain=1, platform=None):
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
            elif device[:3].lower() in ["10m"]:
                assert platform is not None
                platform.add_reserved_jtag_decls()
                jtag = MAX10JTAG(reserved_pads=platform.get_reserved_jtag_pads())
            elif device[:4].lower() in ["10cl"]:
                assert platform is not None
                platform.add_reserved_jtag_decls()
                jtag = Cyclone10LPJTAG(reserved_pads=platform.get_reserved_jtag_pads())
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
