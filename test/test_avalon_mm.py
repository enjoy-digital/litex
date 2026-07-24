#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect.avalon import Wishbone2AvalonMM

# Avalon-MM RAM Model ------------------------------------------------------------------------------

@passive
def avalon_mm_ram_generator(avl, mem, read_latency=2, wait_states=True):
    pending  = []
    wreq_now = 0 # Wait-Request value driven for the current cycle (reset value).
    toggle   = 0
    while True:
        read  = (yield avl.read)
        write = (yield avl.write)
        adr   = (yield avl.address)
        dat   = (yield avl.writedata)
        # Command acceptance (when Wait-Request is deasserted).
        if (read or write) and (wreq_now == 0):
            if write:
                mem[adr] = dat
            if read:
                pending.append([read_latency, adr])
        # Read-Data return (driven for the next cycle).
        pending = [[count - 1, adr] for count, adr in pending]
        if pending and (pending[0][0] <= 0):
            _, rd_adr = pending.pop(0)
            yield avl.readdata.eq(mem.get(rd_adr, 0))
            yield avl.readdatavalid.eq(1)
        else:
            yield avl.readdatavalid.eq(0)
        # Wait-Request (toggling pattern to exercise wait-states).
        toggle   += 1
        wreq_next = (toggle % 2) if wait_states else 0
        yield avl.waitrequest.eq(wreq_next)
        yield
        wreq_now = wreq_next

# TestAvalonMM -------------------------------------------------------------------------------------

class TestAvalonMM(unittest.TestCase):
    def test_wishbone2avalonmm(self):
        def generator(dut, base):
            # Writes.
            for i in range(8):
                yield from dut.w2a_wb.write(base + i, 0x1000_0000 + i)
            # Reads.
            for i in range(8):
                data = (yield from dut.w2a_wb.read(base + i))
                self.assertEqual(data, 0x1000_0000 + i)

        for data_width in [32, 64]:
            for base in [0x0000_0000, 0x0100_0000]:
                for wait_states in [False, True]:
                    dut = Wishbone2AvalonMM(data_width=data_width, avalon_base_address=base)
                    mem = {}
                    run_simulation(dut, [
                        generator(dut, base),
                        avalon_mm_ram_generator(dut.w2a_avl, mem, wait_states=wait_states),
                    ])
                    # Check the Avalon-side addresses (avalon_base_address subtracted).
                    self.assertEqual(sorted(mem.keys()), list(range(8)))
