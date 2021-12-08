from enum import IntEnum
from migen import *


class TransferType(IntEnum):
    IDLE = 0
    BUSY = 1
    NONSEQUENTIAL = 2
    SEQUENTIAL = 3


class Interface(Record):
    adr_width = 32
    data_width = 32

    master_signals = [
        ('addr', adr_width),
        ('burst', 3),
        ('mastlock', 1),
        ('prot', 4),
        ('size', 3),
        ('trans', 2),
        ('wdata', data_width),
        ('write', 1),
        ('sel', 1),
    ]

    slave_signals = [
        ('rdata', data_width),
        ('readyout', 1),
        ('resp', 1),
    ]

    def __init__(self):
        Record.__init__(self, set_layout_parameters(self.master_signals + self.slave_signals))


class AHB2Wishbone(Module):
    def __init__(self, ahb, wishbone):
        wb = wishbone
        wishbone_adr_shift = log2_int(ahb.data_width // 8)
        assert ahb.data_width == wb.data_width
        assert ahb.adr_width == wb.adr_width + wishbone_adr_shift

        self.comb += [
            ahb.resp.eq(wb.err),
        ]

        self.submodules.fsm = fsm = FSM()
        fsm.act("IDLE",
            ahb.readyout.eq(1),
            If(ahb.sel & (ahb.size == wishbone_adr_shift) & (ahb.trans == TransferType.NONSEQUENTIAL),
               NextValue(wb.adr, ahb.addr[2:]),
               NextValue(wb.dat_w, ahb.wdata),
               NextValue(wb.we, ahb.write),
               NextValue(wb.sel, 2 ** len(wb.sel) - 1),
               NextState('ACT'),
            )
        )
        fsm.act("ACT",
            wb.stb.eq(1),
            wb.cyc.eq(1),
            If(wb.ack,
               If(~wb.we, NextValue(ahb.rdata, wb.dat_r)),
               NextState("IDLE")
            )
        )
