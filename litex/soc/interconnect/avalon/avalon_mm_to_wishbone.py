#
# This file is part of LiteX.
#
# Copyright (c) 2023 Hans Baier <hansfbaier@gmail.com>
# Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Avalon support for LiteX"""

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.avalon import AvalonMMInterface

# Avalon MM <--> Wishbone Bridge -------------------------------------------------------------------

class AvalonMM2Wishbone(Module):
    def __init__(self, data_width=32, address_width=32, wishbone_base_address=0x0, wishbone_extend_address_bits=0, avoid_combinatorial_loop=True):
        word_width      = data_width // 8
        word_width_bits = log2_int(word_width)
        wishbone_address_width = address_width - word_width_bits + wishbone_extend_address_bits

        self.a2w_wb  = wb  = wishbone.Interface(data_width=data_width, adr_width=wishbone_address_width, bursting=True)
        self.a2w_avl = avl = AvalonMMInterface (data_width=data_width, adr_width=address_width)

        read_access   = Signal()
        readdatavalid = Signal()
        readdata      = Signal(data_width)

        last_burst_cycle = Signal()
        burst_cycle      = Signal()
        burst_counter    = Signal.like(avl.burstcount)
        burst_address    = Signal(address_width)
        burst_read       = Signal()
        burst_sel        = Signal.like(avl.byteenable)

        self.sync += last_burst_cycle.eq(burst_cycle)

        # Some designs might have trouble with the combinatorial loop created
        # by wb.ack, so cut it, incurring one clock cycle of overhead on each
        # bus transaction
        if avoid_combinatorial_loop:
            self.sync += [
                If(wb.ack | wb.err,
                    read_access.eq(0)
                ).Elif(avl.read,
                    read_access.eq(1)
                ),
                readdata.eq(wb.dat_r),
                readdatavalid.eq((wb.ack | wb.err) & read_access),
            ]
        else:
            self.comb += [
                read_access.eq(avl.read),
                readdata.eq(wb.dat_r),
                readdatavalid.eq((wb.ack | wb.err) & read_access),
            ]

        # Wishbone -> Avalon
        self.comb += [
            avl.waitrequest.eq(~(wb.ack | wb.err) | burst_read),
            avl.readdata.eq(readdata),
            avl.readdatavalid.eq(readdatavalid),
        ]

        # Avalon -> Wishbone
        self.comb += [
            # Avalon is byte addresses, Wishbone word addressed
            If(burst_cycle & last_burst_cycle,
                wb.adr.eq(burst_address[word_width_bits:] + wishbone_base_address)
            ).Else(
                wb.adr.eq(avl.address[word_width_bits:] + wishbone_base_address)
            ),
            wb.dat_w.eq(avl.writedata),
            wb.we.eq(avl.write),
            wb.cyc.eq(read_access | avl.write | burst_cycle),
            wb.stb.eq(read_access | avl.write),
            wb.bte.eq(0b00),
        ]

        self.submodules.fsm = fsm = FSM(reset_state="SINGLE")
        fsm.act("SINGLE",
            burst_cycle.eq(0),
            wb.sel.eq(avl.byteenable),
            If(avl.burstcount > 1,
                wb.cti.eq(wishbone.CTI_BURST_INCREMENTING)
            ).Else(
                wb.cti.eq(wishbone.CTI_BURST_NONE)
            ),
            If(~avl.waitrequest & (avl.burstcount > 1),
                burst_cycle.eq(1),
                NextValue(burst_counter, avl.burstcount - 1),
                NextValue(burst_address, avl.address + word_width),
                NextValue(burst_sel, avl.byteenable),
                If(avl.write,
                    NextState("BURST-WRITE")),
                If(avl.read,
                    NextValue(burst_read, 1),
                    NextState("BURST-READ"))
                )
        )
        fsm.act("BURST-WRITE",
            burst_cycle.eq(1),
            wb.sel.eq(burst_sel),
            If(burst_counter > 1,
                wb.cti.eq(wishbone.CTI_BURST_INCREMENTING)
            ).Else(
                If(burst_counter == 1,
                    wb.cti.eq(wishbone.CTI_BURST_END)
                ).Else(
                    wb.cti.eq(wishbone.CTI_BURST_NONE)
                )
            ),
            If(~avl.waitrequest,
                NextValue(burst_address, burst_address + word_width),
                NextValue(burst_counter, burst_counter - 1)),
            If(burst_counter == 0,
                burst_cycle.eq(0),
                wb.sel.eq(avl.byteenable),
                NextValue(burst_sel, 0),
                NextState("SINGLE")
            )
        )
        fsm.act("BURST-READ", # TODO
            burst_cycle.eq(1),
            wb.stb.eq(1),
            wb.sel.eq(burst_sel),
            If(burst_counter > 1,
                wb.cti.eq(wishbone.CTI_BURST_INCREMENTING),
            ).Else(
                If(burst_counter == 1,
                    wb.cti.eq(wishbone.CTI_BURST_END)
                ).Else(
                    wb.cti.eq(wishbone.CTI_BURST_NONE)
                )
            ),
            If(wb.ack,
                avl.readdatavalid.eq(1),
                NextValue(burst_address, burst_address + word_width),
                NextValue(burst_counter, burst_counter - 1)
            ),
            If(burst_counter == 0,
                wb.cyc.eq(0),
                wb.stb.eq(0),
                wb.sel.eq(avl.byteenable),
                NextValue(burst_sel,  0),
                NextValue(burst_read, 0),
                NextState("SINGLE"))
        )
