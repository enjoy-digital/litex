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
    """Wishbone bridge for 8-bit and 16-bit asynchronous SRAMs.

    The core exposes a word-addressed Wishbone slave and serializes each bus
    word into SRAM-wide async SRAM accesses. The external control pads are
    driven as active-low signals; pad names can either use the explicit
    ``*_n`` suffix or the shorter ``ce``/``oe``/``we`` names used by some
    existing board targets. The address and data pads are named ``adr``/``dat``
    or ``a``/``dq``.

    SRAMs wider than 8-bit need byte enable pads (``be_n``, or ``lb_n``/``ub_n``
    for 16-bit SRAMs): all the bytes are enabled on reads, the selected ones on
    writes.

    Each SRAM access lasts ``read_cycles``/``write_cycles`` with OE/WE asserted.
    ``setup_cycles``/``hold_cycles`` add cycles before/after them with only CE
    asserted and the address (and the write data) stable, for SRAMs/boards that
    need address setup/hold around the strobes.
    """
    def __init__(self, pads, bus=None, data_width=32, address_width=None,
        read_cycles  = 2,
        write_cycles = 3,
        setup_cycles = 0,
        hold_cycles  = 0):
        # Parameters.
        if read_cycles < 1:
            raise ValueError("AsyncSRAM read_cycles must be >= 1.")
        if write_cycles < 1:
            raise ValueError("AsyncSRAM write_cycles must be >= 1.")
        if setup_cycles < 0:
            raise ValueError("AsyncSRAM setup_cycles must be >= 0.")
        if hold_cycles < 0:
            raise ValueError("AsyncSRAM hold_cycles must be >= 0.")

        # Wishbone bus.
        if bus is None:
            bus = wishbone.Interface(data_width=data_width)
        if bus.addressing != "word":
            raise ValueError("AsyncSRAM only supports word-addressed Wishbone buses.")
        if bus.data_width != data_width:
            raise ValueError("AsyncSRAM data_width must match the Wishbone bus data width.")

        # Pads.
        def _get_pad(*names):
            for name in names:
                if hasattr(pads, name):
                    return getattr(pads, name)
            raise ValueError("AsyncSRAM pads must provide one of: {}.".format(", ".join(names)))

        adr_pad = _get_pad("adr", "a")
        dat_pad = _get_pad("dat", "dq")

        self.bus = bus

        # # #

        # Geometry.
        sram_data_width = len(dat_pad)
        if sram_data_width not in [8, 16]:
            raise ValueError("AsyncSRAM supports 8-bit and 16-bit SRAM data buses only.")
        if data_width % sram_data_width:
            raise ValueError("AsyncSRAM data_width must be a multiple of the SRAM data width.")
        sram_sel_width = sram_data_width//8

        ratio = data_width//sram_data_width
        if ratio & (ratio - 1):
            raise ValueError("AsyncSRAM Wishbone/SRAM width ratio must be a power of two.")
        if len(bus.sel) != ratio*sram_sel_width:
            raise ValueError("AsyncSRAM Wishbone select width must match the data width.")
        ratio_bits = log2_int(ratio)

        if address_width is None:
            address_width = len(adr_pad)
        if address_width != len(adr_pad):
            raise ValueError("AsyncSRAM address_width must match the SRAM address pad width.")
        if address_width < ratio_bits:
            raise ValueError("AsyncSRAM address_width is too small for the bus/SRAM width ratio.")

        word_address_width = address_width - ratio_bits
        if len(bus.adr) < word_address_width:
            raise ValueError("AsyncSRAM Wishbone address width is too small for the SRAM address bus.")

        # Control pads.
        ce_n_pad = _get_pad("ce_n", "ce")
        oe_n_pad = _get_pad("oe_n", "oe")
        we_n_pad = _get_pad("we_n", "we")

        # Byte enable pads (SRAMs wider than 8-bit).
        if sram_sel_width > 1:
            if hasattr(pads, "lb_n") and hasattr(pads, "ub_n"):
                be_n_pad = Cat(pads.lb_n, pads.ub_n)
            else:
                be_n_pad = _get_pad("be_n", "lb_n/ub_n")
            if len(be_n_pad) != sram_sel_width:
                raise ValueError("AsyncSRAM byte enable pads must match the SRAM data width.")

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

        # (byte/wait are named explicitly: Migen does not trace the names of the signals used by
        # the FSM helpers below.)
        word_adr = Signal(len(bus.adr))
        byte     = Signal(max=max(ratio, 2), name="byte")
        wait     = Signal(max=max(read_cycles, write_cycles, setup_cycles, hold_cycles, 2), name="wait")
        sel      = Signal(ratio*sram_sel_width)
        data_w   = Signal(data_width)
        data_r   = Signal(data_width)
        byte_sel = Signal(sram_sel_width)
        mem_adr  = Signal(address_width)

        # SRAM data tristate.
        self.specials += Tristate(dat_pad, o=dat_o, oe=dat_oe, i=dat_i)

        # SRAM controls.
        self.comb += [
            ce_n_pad.eq(ce_n),
            oe_n_pad.eq(oe_n),
            we_n_pad.eq(we_n),
            adr_pad.eq(mem_adr),
        ]

        # SRAM byte enables: all the bytes on reads, the selected ones on writes (dat_oe).
        if sram_sel_width > 1:
            self.comb += be_n_pad.eq(
                Replicate(ce_n, sram_sel_width) | (Replicate(dat_oe, sram_sel_width) & ~byte_sel))

        # SRAM address: Wishbone word address + current SRAM word (byte lane for 8-bit SRAMs).
        if ratio_bits:
            self.comb += mem_adr.eq(Cat(byte[:ratio_bits], word_adr[:word_address_width]))
        else:
            self.comb += mem_adr.eq(word_adr[:word_address_width])

        # Byte lane decoding (byte_sel: selected bytes of the current SRAM word).
        dat_o_cases    = {}
        byte_sel_cases = {}
        read_cases     = {}
        for n in range(ratio):
            dat_o_cases[n] = dat_o.eq(data_w[n*sram_data_width:(n + 1)*sram_data_width])
            byte_sel_cases[n] = byte_sel.eq(sel[n*sram_sel_width:(n + 1)*sram_sel_width])
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
        read_done  = wait == (read_cycles  - 1)
        write_done = wait == (write_cycles - 1)
        setup_done = wait == (setup_cycles - 1)
        hold_done  = wait == (hold_cycles  - 1)

        # FSM.
        # Each SRAM access is: optional setup cycles (CE), read/write cycles (CE + OE/WE) and
        # optional hold cycles (CE), a write of unselected bytes being skipped in its first state.
        read_first  = "READ-SETUP"  if setup_cycles else "READ"
        write_first = "WRITE-SETUP" if setup_cycles else "WRITE"

        def next_access(state, first_state):
            # Next SRAM access of the bus word or Wishbone ack after the last one.
            return [
                NextValue(wait, 0),
                If(byte_last,
                    NextState("ACK")
                ).Else(
                    NextValue(byte, byte + 1),
                    *([NextState(first_state)] if first_state != state else [])
                )
            ]

        def next_phase(state, hold_state, first_state):
            # Hold cycles when enabled, next SRAM access otherwise.
            if hold_cycles:
                return [NextValue(wait, 0), NextState(hold_state)]
            return next_access(state, first_state)

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
                    NextState(write_first)
                ).Else(
                    NextState(read_first)
                )
            )
        )
        if setup_cycles:
            fsm.act("READ-SETUP",
                # Address setup.
                ce_n.eq(0),
                If(setup_done,
                    NextValue(wait, 0),
                    NextState("READ")
                ).Else(
                    NextValue(wait, wait + 1)
                )
            )
        fsm.act("READ",
            # Read byte.
            ce_n.eq(0),
            oe_n.eq(0),
            If(read_done,
                Case(byte, read_cases),
                *next_phase("READ", "READ-HOLD", read_first)
            ).Else(
                NextValue(wait, wait + 1)
            )
        )
        if hold_cycles:
            fsm.act("READ-HOLD",
                # Address hold.
                ce_n.eq(0),
                If(hold_done,
                    *next_access("READ-HOLD", read_first)
                ).Else(
                    NextValue(wait, wait + 1)
                )
            )
        if setup_cycles:
            fsm.act("WRITE-SETUP",
                # Address/Data setup.
                ce_n.eq(0),
                If(byte_sel,
                    dat_oe.eq(1),
                    If(setup_done,
                        NextValue(wait, 0),
                        NextState("WRITE")
                    ).Else(
                        NextValue(wait, wait + 1)
                    )
                ).Else(
                    *next_access("WRITE-SETUP", write_first)
                )
            )
        fsm.act("WRITE",
            # Write byte.
            ce_n.eq(0),
            If(byte_sel,
                we_n.eq(0),
                dat_oe.eq(1),
                If(write_done,
                    *next_phase("WRITE", "WRITE-HOLD", write_first)
                ).Else(
                    NextValue(wait, wait + 1)
                )
            ).Else(
                *next_access("WRITE", write_first)
            )
        )
        if hold_cycles:
            fsm.act("WRITE-HOLD",
                # Address/Data hold.
                ce_n.eq(0),
                dat_oe.eq(1),
                If(hold_done,
                    *next_access("WRITE-HOLD", write_first)
                ).Else(
                    NextValue(wait, wait + 1)
                )
            )
        fsm.act("ACK",
            # Wishbone ack.
            bus.ack.eq(1),
            NextState("IDLE")
        )
