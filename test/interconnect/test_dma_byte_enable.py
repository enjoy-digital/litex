#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.dma import WishboneDMAWriter
from litex.soc.interconnect import wishbone


class TestDMAByteEnable(unittest.TestCase):
    def test_write_masks_and_byte_order(self):
        for width in [8, 32, 64]:
            for endianness, swap in [("big", None), ("little", None), ("big", True), ("little", False)]:
                for control in ["raw", "ctrl", "csr"]:
                    with self.subTest(width=width, endianness=endianness, swap=swap, control=control):
                        lanes = width//8
                        bus = wishbone.Interface(data_width=width, address_width=32, addressing="word", bursting=True)
                        dut = WishboneDMAWriter(bus, endianness=endianness, with_byteswap=swap,
                            with_be=True, with_csr=control == "csr")
                        if control == "ctrl":
                            dut.add_ctrl()
                        masks = [0, (1 << lanes) - 1, 1, 1 << (lanes - 1), 0x55 & ((1 << lanes) - 1)]
                        data = int.from_bytes(bytes(range(1, lanes + 1)), "little")
                        memory = {}
                        captured = []
                        base = 32//lanes
                        byte_swap = endianness == "little" if swap is None else swap

                        @passive
                        def slave():
                            while True:
                                yield bus.ack.eq(0)
                                yield
                                if (yield bus.cyc) and (yield bus.stb):
                                    word = ((yield bus.adr), (yield bus.dat_w), (yield bus.sel), (yield bus.cti))
                                    for _ in range(3):
                                        yield
                                        self.assertEqual(((yield bus.adr), (yield bus.dat_w), (yield bus.sel), (yield bus.cti)), word)
                                    address, value, mask, cti = word
                                    result = bytearray([0xaa]*lanes)
                                    for i in range(lanes):
                                        if mask & (1 << i):
                                            result[i] = (value >> (8*i)) & 0xff
                                    memory[address] = bytes(result)
                                    captured.append(word)
                                    yield bus.ack.eq(1)
                                    yield

                        def producer():
                            if control == "ctrl":
                                yield dut.base.eq(32)
                                yield dut.length.eq(len(masks)*lanes)
                                yield dut.enable.eq(1)
                            elif control == "csr":
                                yield dut._base.storage.eq(32)
                                yield dut._length.storage.eq(len(masks)*lanes)
                                yield dut._enable.storage.eq(1)
                            # Let the controller leave IDLE before presenting a beat.
                            for _ in range(3):
                                yield
                            for n, mask in enumerate(masks):
                                if control == "raw":
                                    yield dut.sink.address.eq(base + n)
                                yield dut.sink.data.eq(data)
                                yield dut.sink.be.eq(mask)
                                yield dut.sink.last.eq(n == len(masks) - 1)
                                yield dut.sink.valid.eq(1)
                                yield
                                for _ in range(100):
                                    if (yield dut.sink.ready):
                                        break
                                    yield
                                else:
                                    self.fail("DMA writer stalled")
                                yield dut.sink.valid.eq(0)
                                yield
                            for _ in range(5):
                                yield
                            if control != "raw":
                                self.assertEqual((yield dut.done), 1)
                                self.assertEqual((yield dut.error), 0)

                        run_simulation(dut, [producer(), slave()])
                        self.assertEqual(len(captured), len(masks))
                        for n, mask in enumerate(masks):
                            expected = bytearray([0xaa]*lanes)
                            for i in range(lanes):
                                if mask & (1 << i):
                                    expected[lanes - 1 - i if byte_swap else i] = i + 1
                            self.assertEqual(memory[base + n], bytes(expected))
                        self.assertEqual([v[3] for v in captured],
                            [wishbone.CTI_BURST_INCREMENTING]*(len(masks) - 1) + [wishbone.CTI_BURST_END])
