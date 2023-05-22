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
    def __init__(self, data_width=32, avalon_address_width=32, wishbone_address_width=32, wishbone_base_address=0x0, burst_increment=1, avoid_combinatorial_loop=False):
        self.a2w_avl = avl = AvalonMMInterface (data_width=data_width, adr_width=avalon_address_width)
        self.a2w_wb  = wb  = wishbone.Interface(data_width=data_width, adr_width=wishbone_address_width, bursting=True)

        read_access   = Signal()
        readdatavalid = Signal()
        readdata      = Signal(data_width)

        burst_cycle      = Signal()
        burst_cycle_last = Signal()
        burst_count      = Signal(len(avl.burstcount))
        burst_address    = Signal(wishbone_address_width)
        burst_read       = Signal()

        self.sync += burst_cycle_last.eq(burst_cycle)

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
        ]

        # Avalon -> Wishbone
        self.comb += [
            # Avalon is byte addresses, Wishbone word addressed
            wb.adr.eq(avl.address + wishbone_base_address),
            If(burst_cycle & burst_cycle_last,
                wb.adr.eq(burst_address + wishbone_base_address)
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
            avl.readdatavalid.eq(readdatavalid),
            wb.sel.eq(avl.byteenable),
            wb.cti.eq(wishbone.CTI_BURST_NONE),
            If(avl.burstcount > 1,
                wb.cti.eq(wishbone.CTI_BURST_INCREMENTING)
            ),
            If(~avl.waitrequest & (avl.burstcount > 1),
                burst_cycle.eq(1),
                NextValue(burst_count, avl.burstcount - 1),
                NextValue(burst_address, avl.address + burst_increment),
                If(avl.write,
                    NextState("BURST-WRITE")
                ),
                If(avl.read,
                    NextState("BURST-READ")
                )
            )
        )
        fsm.act("BURST-WRITE",
            avl.readdatavalid.eq(0),
            burst_cycle.eq(1),
            wb.sel.eq(avl.byteenable),
            wb.cti.eq(wishbone.CTI_BURST_INCREMENTING),
            If(burst_count == 1,
                wb.cti.eq(wishbone.CTI_BURST_END)
            ),
            If(~avl.waitrequest & avl.write,
                NextValue(burst_address, burst_address + burst_increment),
                NextValue(burst_count, burst_count - 1),
            ),
            If(burst_count == 0,
                burst_cycle.eq(0),
                NextState("SINGLE")
            )
        )
        fsm.act("BURST-READ",
            avl.readdatavalid.eq(0),
            burst_cycle.eq(1),
            burst_read.eq(1),
            wb.stb.eq(1),
            wb.sel.eq(2**len(wb.sel) - 1),
            wb.cti.eq(wishbone.CTI_BURST_INCREMENTING),
            If(burst_count == 1,
                wb.cti.eq(wishbone.CTI_BURST_END)
            ),
            If(wb.ack,
                avl.readdatavalid.eq(1),
                NextValue(burst_address, burst_address + burst_increment),
                NextValue(burst_count, burst_count - 1)
            ),
            If(burst_count == 0,
                avl.readdatavalid.eq(int(avoid_combinatorial_loop)),
                wb.cyc.eq(0),
                wb.stb.eq(0),
                NextState("SINGLE"))
        )
