#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import *

from litex.soc.interconnect import wishbone


# Async SRAM ---------------------------------------------------------------------------------------

class AsyncSRAM(LiteXModule):
    """Wishbone bridge for 8-bit asynchronous SRAMs.

    The core exposes a word-addressed Wishbone slave and serializes each bus
    word into byte-wide async SRAM accesses. The external control pads are
    driven as active-low signals; pad names can either use the explicit
    ``*_n`` suffix or the shorter ``ce``/``oe``/``we`` names used by some
    existing board targets.
    """
    def __init__(self, pads, bus=None, data_width=32, address_width=None,
        read_cycles  = 2,
        write_cycles = 3):
        # Parameters.
        if read_cycles < 1:
            raise ValueError("AsyncSRAM read_cycles must be >= 1.")
        if write_cycles < 1:
            raise ValueError("AsyncSRAM write_cycles must be >= 1.")

        # Wishbone bus.
        if bus is None:
            bus = wishbone.Interface(data_width=data_width)
        if bus.addressing != "word":
            raise ValueError("AsyncSRAM only supports word-addressed Wishbone buses.")
        if bus.data_width != data_width:
            raise ValueError("AsyncSRAM data_width must match the Wishbone bus data width.")

        # Pads.
        if not hasattr(pads, "adr"):
            raise ValueError("AsyncSRAM pads must provide an adr signal.")
        if not hasattr(pads, "dat"):
            raise ValueError("AsyncSRAM pads must provide a dat signal.")

        self.bus = bus

        # # #

        # Geometry.
        sram_data_width = len(pads.dat)
        if sram_data_width != 8:
            raise ValueError("AsyncSRAM currently supports 8-bit SRAM data buses only.")
        if data_width % sram_data_width:
            raise ValueError("AsyncSRAM data_width must be a multiple of the SRAM data width.")

        ratio = data_width//sram_data_width
        if ratio & (ratio - 1):
            raise ValueError("AsyncSRAM Wishbone/SRAM width ratio must be a power of two.")
        if len(bus.sel) != ratio:
            raise ValueError("AsyncSRAM Wishbone select width must match the data width ratio.")
        ratio_bits = log2_int(ratio)

        if address_width is None:
            address_width = len(pads.adr)
        if address_width != len(pads.adr):
            raise ValueError("AsyncSRAM address_width must match the SRAM address pad width.")
        if address_width < ratio_bits:
            raise ValueError("AsyncSRAM address_width is too small for the bus/SRAM width ratio.")

        word_address_width = address_width - ratio_bits
        if len(bus.adr) < word_address_width:
            raise ValueError("AsyncSRAM Wishbone address width is too small for the SRAM address bus.")

        # Control pads.
        def _get_control_pad(*names):
            for name in names:
                if hasattr(pads, name):
                    return getattr(pads, name)
            raise ValueError("AsyncSRAM pads must provide one of: {}.".format(", ".join(names)))

        ce_n_pad = _get_control_pad("ce_n", "ce")
        oe_n_pad = _get_control_pad("oe_n", "oe")
        we_n_pad = _get_control_pad("we_n", "we")

        # Signals.
        ce_n  = Signal(reset=1)
        oe_n  = Signal(reset=1)
        we_n  = Signal(reset=1)
        dat_i = Signal(sram_data_width)
        dat_o = Signal(sram_data_width)
        dat_oe = Signal()

        self.dat_i  = dat_i
        self.dat_o  = dat_o
        self.dat_oe = dat_oe

        word_adr = Signal(len(bus.adr))
        byte     = Signal(max=max(ratio, 2))
        wait     = Signal(max=max(read_cycles, write_cycles, 2))
        sel      = Signal(ratio)
        data_w   = Signal(data_width)
        data_r   = Signal(data_width)
        byte_sel = Signal()
        mem_adr  = Signal(address_width)

        # SRAM data tristate.
        self.specials += Tristate(pads.dat, o=dat_o, oe=dat_oe, i=dat_i)

        # SRAM controls.
        self.comb += [
            ce_n_pad.eq(ce_n),
            oe_n_pad.eq(oe_n),
            we_n_pad.eq(we_n),
            pads.adr.eq(mem_adr),
        ]

        # SRAM address: Wishbone word address + current byte lane.
        if ratio_bits:
            self.comb += mem_adr.eq(Cat(byte[:ratio_bits], word_adr[:word_address_width]))
        else:
            self.comb += mem_adr.eq(word_adr[:word_address_width])

        # Byte lane decoding.
        dat_o_cases    = {}
        byte_sel_cases = {}
        read_cases     = {}
        for n in range(ratio):
            dat_o_cases[n] = dat_o.eq(data_w[n*sram_data_width:(n + 1)*sram_data_width])
            byte_sel_cases[n] = byte_sel.eq(sel[n])
            read_cases[n] = NextValue(data_r[n*sram_data_width:(n + 1)*sram_data_width], dat_i)

        # Defaults.
        self.comb += [
            bus.dat_r.eq(data_r),
            bus.ack.eq(0),
            bus.err.eq(0),
            ce_n.eq(1),
            oe_n.eq(1),
            we_n.eq(1),
            dat_oe.eq(0),
            dat_o.eq(0),
            byte_sel.eq(0),
            Case(byte, dat_o_cases),
            Case(byte, byte_sel_cases),
        ]

        byte_last  = byte == (ratio - 1)
        read_done  = wait == (read_cycles - 1)
        write_done = wait == (write_cycles - 1)

        # FSM.
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # Latch Wishbone command.
            If(bus.cyc & bus.stb,
                NextValue(word_adr, bus.adr),
                NextValue(sel,      bus.sel),
                NextValue(data_w,   bus.dat_w),
                NextValue(byte,     0),
                NextValue(wait,     0),
                If(bus.we,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )
        fsm.act("READ",
            # Read byte.
            ce_n.eq(0),
            oe_n.eq(0),
            If(read_done,
                Case(byte, read_cases),
                NextValue(wait, 0),
                If(byte_last,
                    NextState("ACK")
                ).Else(
                    NextValue(byte, byte + 1)
                )
            ).Else(
                NextValue(wait, wait + 1)
            )
        )
        fsm.act("WRITE",
            # Write byte.
            ce_n.eq(0),
            If(byte_sel,
                we_n.eq(0),
                dat_oe.eq(1),
                If(write_done,
                    NextValue(wait, 0),
                    If(byte_last,
                        NextState("ACK")
                    ).Else(
                        NextValue(byte, byte + 1)
                    )
                ).Else(
                    NextValue(wait, wait + 1)
                )
            ).Else(
                NextValue(wait, 0),
                If(byte_last,
                    NextState("ACK")
                ).Else(
                    NextValue(byte, byte + 1)
                )
            )
        )
        fsm.act("ACK",
            # Wishbone ack.
            bus.ack.eq(1),
            NextState("IDLE")
        )
