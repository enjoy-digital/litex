#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
USB 2.0 soft UTMI PHY (High-Speed/Full-Speed/Low-Speed, UTMI 8-bit, 60 MHz).

Portable: the I/Os use LiteX generic specials (SerDesInput/SerDesOutput, DifferentialTristate,
Tristate) lowered to the vendor primitives by the platform.

Board circuit (pads):
- ``d_p``/``d_n``     : D+/D- High-Speed differential driver/receiver: High-Speed TX (16:1 serializer
                        at 1.92 Gbps, each line bit repeated 4 times) and RX (differential receiver,
                        4x oversampled with a 1:16 deserializer).
- ``se_dp``/``se_dn`` : D+/D- single-ended High-Speed level inputs (High-Speed line state: chirps,
                        SE0).
- ``fs_dp``/``fs_dn`` : D+/D- Full-Speed/Low-Speed transceiver (driven low: High-Speed terminations).
- ``pullup``          : D+ 1.5K pull-up control.

Clocks: ``cd_utmi`` (60 MHz), ``cd_hs`` (120 MHz, SerDes parallel clock) and ``cd_hs_fast`` (960 MHz,
SerDes serial clock, DDR), from the same source; ``serdes_rst`` resets the SerDes.

Full-Speed only (``with_hs=False``): ``fs_dp``/``fs_dn``/``pullup`` pads and ``cd_utmi`` only (no
SerDes, only Tristate needed: portable to any FPGA), High-Speed chirp not driven (the host keeps the
link at Full-Speed); High-Speed ``d_p``/``d_n`` pads, if provided, are released.

UTMI signals are exposed with LUNA names (compatible with LiteX LunaCDCACM's UTMI mode).
"""

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.build.io import SerDesInput, SerDesOutput, DifferentialTristate

from litex.soc.cores.usb2_phy.fs import USBFSPHY
from litex.soc.cores.usb2_phy.hs import USBHSPHY

# USB 2.0 PHY --------------------------------------------------------------------------------------

class USB2PHY(LiteXModule):
    """
    USB 2.0 UTMI PHY (``cd_utmi`` domain). ``reset`` holds the PHY in reset (pull-up disabled, lines
    released).

    XcvrSelect: 00 High-Speed (TX/RX on d_p/d_n, line state on se_dp/se_dn), 01 Full-Speed, 1x
    Low-Speed (fs_dp/fs_dn). TermSelect: 1 Full-Speed termination (1.5K pull-up), 0 High-Speed
    terminations (fs_dp/fs_dn driven low) in High-Speed.

    With ``with_hs=False``, XcvrSelect 00 is handled as Full-Speed with TX discarded (High-Speed
    chirp not sent, ``tx_ready`` acknowledged): the link stays at Full-Speed.
    """
    def __init__(self, pads, cd_utmi="usb", cd_hs="usb_hs", cd_hs_fast="usb_hs_fast", serdes_rst=0,
        tx_oe_extend=1, with_hs=True):
        self.reset = Signal()

        # UTMI.
        self.rx_data     = Signal(8)
        self.rx_valid    = Signal()
        self.rx_active   = Signal()
        self.rx_error    = Signal()
        self.line_state  = Signal(2)
        self.tx_data     = Signal(8)
        self.tx_valid    = Signal()
        self.tx_ready    = Signal()
        self.op_mode     = Signal(2)
        self.xcvr_select = Signal(2, reset=0b01)
        self.term_select = Signal()

        # # #

        hs_sel   = Signal()
        hs_terms = Signal()
        self.comb += hs_sel.eq(self.xcvr_select == 0b00)

        # High-Speed -------------------------------------------------------------------------------
        if with_hs:
            self.hs = hs = USBHSPHY(cd_utmi=cd_utmi, cd_hs=cd_hs)
            self.comb += [
                hs.tx_data.eq(self.tx_data),
                hs.tx_valid.eq(self.tx_valid & hs_sel),
                hs.op_mode.eq(self.op_mode),
            ]

            # TX: 16:1 serializer (each line bit x4), RX: 1:16 deserializer (4x oversampling).
            hs_txd = Signal()
            hs_rxd = Signal()
            hs_oe  = Signal()
            # Driver enable extended after the transmission (serializer latency margin, the enable
            # doesn't go through the serializer): extends the EOP by a few bits (allowed).
            sync_hs = getattr(self.sync, cd_hs)
            oe_sr   = Signal(tx_oe_extend)
            sync_hs += [
                oe_sr.eq(Cat(hs.tx_oe, oe_sr)),
                hs_oe.eq(hs.tx_oe | (oe_sr != 0)),
            ]
            self.specials += [
                SerDesOutput(
                    i        = Cat(*[Replicate(hs.tx_line[n], 4) for n in range(4)]),
                    o        = hs_txd,
                    clk      = ClockSignal(cd_hs),
                    clk_fast = ClockSignal(cd_hs_fast),
                    rst      = serdes_rst,
                ),
                SerDesInput(
                    i        = hs_rxd,
                    o        = hs.rx_samples,
                    clk      = ClockSignal(cd_hs),
                    clk_fast = ClockSignal(cd_hs_fast),
                    rst      = serdes_rst,
                ),
                DifferentialTristate(
                    io_p = pads.d_p,
                    io_n = pads.d_n,
                    o    = hs_txd,
                    oe   = hs_oe,
                    i    = hs_rxd,
                ),
            ]

            # High-Speed line state (single-ended High-Speed level inputs).
            hs_line_state = Signal(2)
            self.specials += MultiReg(Cat(pads.se_dp, pads.se_dn), hs_line_state, cd_utmi)

            # High-Speed terminations (fs_dp/fs_dn driven low).
            self.comb += hs_terms.eq(hs_sel & ~self.term_select)
        elif hasattr(pads, "d_p"):
            # High-Speed driver/receiver released.
            self.specials += DifferentialTristate(io_p=pads.d_p, io_n=pads.d_n, o=0, oe=0)

        # Full-Speed/Low-Speed ---------------------------------------------------------------------
        self.fs = fs = ClockDomainsRenamer(cd_utmi)(USBFSPHY())
        self.comb += [
            fs.tx_data.eq(self.tx_data),
            fs.tx_valid.eq(self.tx_valid & ~hs_sel),
            fs.op_mode.eq(self.op_mode),
            fs.xcvr_select.eq(Mux(hs_sel, 0b01, self.xcvr_select)),
        ]
        for pad, o, i in [(pads.fs_dp, fs.dp_o, fs.dp_i), (pads.fs_dn, fs.dn_o, fs.dn_i)]:
            t = TSTriple()
            self.specials += t.get_tristate(pad)
            self.comb += [
                i.eq(t.i),
                If(self.reset,
                    t.oe.eq(0),
                ).Elif(hs_terms,
                    t.oe.eq(1),
                    t.o.eq(0),
                ).Else(
                    t.oe.eq(fs.oe),
                    t.o.eq(o),
                ),
            ]

        # Pull-up: driven low in reset, high with the Full-Speed termination, released otherwise.
        pullup = TSTriple()
        self.specials += pullup.get_tristate(pads.pullup)
        self.comb += [
            pullup.oe.eq(self.reset | self.term_select),
            pullup.o.eq(~self.reset & self.term_select),
        ]

        # UTMI Mux ---------------------------------------------------------------------------------
        fs_utmi = [
            # Without High-Speed, High-Speed TX (chirp) discarded.
            self.tx_ready.eq(fs.tx_ready | hs_sel),
            self.rx_data.eq(fs.rx_data),
            self.rx_valid.eq(fs.rx_valid),
            self.rx_active.eq(fs.rx_active),
            self.rx_error.eq(fs.rx_error),
            self.line_state.eq(fs.line_state),
        ]
        if with_hs:
            self.comb += If(hs_sel,
                self.tx_ready.eq(hs.tx_ready),
                self.rx_data.eq(hs.rx_data),
                self.rx_valid.eq(hs.rx_valid),
                self.rx_active.eq(hs.rx_active),
                self.rx_error.eq(hs.rx_error),
                self.line_state.eq(hs_line_state),
            ).Else(*fs_utmi)
        else:
            self.comb += fs_utmi
