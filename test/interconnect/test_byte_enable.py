#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest

from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.packet import Header, HeaderField, Packetizer, Depacketizer

# Helpers ------------------------------------------------------------------------------------------

def description(width, qualifier="be", params=[]):
    return stream.EndpointDescription([("data", width), (qualifier, width//8)], params)


def beats(data, lanes, reverse=False):
    result = []
    for offset in range(0, len(data), lanes):
        word = data[offset:offset + lanes]
        mask = (1 << len(word)) - 1
        value = int.from_bytes(word, "little")
        if reverse:
            value <<= 8*(lanes - len(word))
            mask <<= lanes - len(word)
        result.append((value, mask, offset == 0, offset + lanes >= len(data)))
    return result


def simulate(test, dut, inputs, qualifier="be", seed=42, errors=None, output_errors=None):
    results = []
    done    = [False]

    def producer():
        prng = random.Random(seed)
        for n, (data, mask, first, last) in enumerate(inputs):
            for _ in range(prng.randrange(3)):
                yield
            yield dut.sink.data.eq(data)
            if errors is not None:
                yield dut.sink.error.eq(errors[n])
            yield getattr(dut.sink, qualifier).eq(mask)
            yield dut.sink.first.eq(first)
            yield dut.sink.last.eq(last)
            yield dut.sink.valid.eq(1)
            yield
            while not (yield dut.sink.ready):
                yield
            yield dut.sink.valid.eq(0)
        done[0] = True

    def consumer():
        prng    = random.Random(seed + 1)
        stalled = None
        idle    = 0
        for _ in range(10000):
            yield dut.source.ready.eq(prng.randrange(2))
            yield
            valid = (yield dut.source.valid)
            item = ((yield dut.source.data), (yield getattr(dut.source, qualifier)),
                (yield dut.source.first), (yield dut.source.last))
            if stalled is not None:
                test.assertTrue(valid)
                test.assertEqual(item, stalled, "Output changed under backpressure")
            stalled = item if valid and not (yield dut.source.ready) else None
            if valid and (yield dut.source.ready):
                results.append(item)
                if output_errors is not None:
                    output_errors.append((yield dut.source.error))
                idle = 0
            elif done[0]:
                idle += 1
                if idle == 16:
                    return
        test.fail("Stream did not drain")

    run_simulation(dut, [producer(), consumer()])
    return results


def qualified_bytes(words, lanes):
    return bytes((data >> (8*i)) & 0xff
        for data, mask, _, _ in words for i in range(lanes) if mask & (1 << i))

# Tests --------------------------------------------------------------------------------------------

class TestByteEnable(unittest.TestCase):
    def test_stride_converter_packets(self):
        for qualifier in ["be", "keep"]:
            for width_from, width_to in [(8, 64), (32, 64), (64, 32), (64, 8), (32, 32)]:
                with self.subTest(qualifier=qualifier, widths=(width_from, width_to)):
                    packets = [bytes((i + n) % 256 for i in range(n)) for n in range(1, 26)]
                    inputs  = [beat for packet in packets for beat in beats(packet, width_from//8)]
                    dut = stream.StrideConverter(description(width_from, qualifier), description(width_to, qualifier))
                    result = simulate(self, dut, inputs, qualifier)
                    expected = [beat for packet in packets for beat in beats(packet, width_to//8)]
                    self.assertEqual([(m, f, l) for _, m, f, l in result], [(m, f, l) for _, m, f, l in expected])
                    self.assertEqual(qualified_bytes(result, width_to//8), b"".join(packets))

    def test_stride_converter_sparse_and_empty(self):
        for qualifier in ["be", "keep"]:
            for reverse in [False, True]:
                with self.subTest(qualifier=qualifier, reverse=reverse):
                    dut = stream.StrideConverter(description(64, qualifier), description(16, qualifier), reverse=reverse)
                    inputs = [(0x8877665544332211, mask, 1, 1) for mask in [0xff, 0x81, 0x24, 0x3, 0xc0, 0]]
                    result = simulate(self, dut, inputs, qualifier)
                    expected = []
                    for data, mask, _, _ in inputs:
                        slices = list(range(4))
                        if reverse:
                            slices.reverse()
                        last = max([n for n, i in enumerate(slices) if (mask >> (2*i)) & 3] or [0])
                        expected += [((data >> (16*i)) & 0xffff, (mask >> (2*i)) & 3, n == 0, n == last)
                            for n, i in enumerate(slices[:last + 1])]
                    self.assertEqual(result, expected)

    def test_upconverter_reverse_clears_unused_masks(self):
        dut = stream.StrideConverter(description(8), description(64), reverse=True)
        inputs = [(n, 1, n == 0, n == 7) for n in range(8)] + [(0xaa, 1, 1, 1)]
        result = simulate(self, dut, inputs)
        self.assertEqual([m for _, m, _, _ in result], [0xff, 0x80])
        self.assertEqual(result[-1][0] >> 56, 0xaa)

    def test_packet_headers(self):
        for qualifier in ["be", "keep"]:
            for width in [8, 16, 32, 64]:
                lanes = width//8
                for header_length in range(lanes, 2*lanes):
                    header_data = bytes(range(header_length))
                    header = Header({"value" : HeaderField(0, 0, header_length*8)}, header_length, swap_field_bytes=False)
                    for cls in [Packetizer, Depacketizer]:
                        with self.subTest(qualifier=qualifier, width=width, header=header_length, cls=cls.__name__):
                            packets = [bytes((i + 40) % 256 for i in range(n)) for n in range(1, 2*lanes + 2)]
                            with_header = [header_data + packet for packet in packets]
                            sink_desc = description(width, qualifier, header.get_layout() if cls == Packetizer else [])
                            source_desc = description(width, qualifier, header.get_layout() if cls == Depacketizer else [])
                            dut = cls(sink_desc, source_desc, header)
                            if cls == Packetizer:
                                dut.comb += dut.sink.value.eq(int.from_bytes(header_data, "little"))
                            inputs = [beat for packet in (packets if cls == Packetizer else with_header) for beat in beats(packet, lanes)]
                            result = simulate(self, dut, inputs, qualifier)
                            expected = [beat for packet in (with_header if cls == Packetizer else packets) for beat in beats(packet, lanes)]
                            self.assertEqual([(m, f, l) for _, m, f, l in result], [(m, f, l) for _, m, f, l in expected])
                            self.assertEqual(qualified_bytes(result, lanes), qualified_bytes(expected, lanes))

    def test_header_byte_errors_follow_data(self):
        for width in [32, 64]:
            lanes = width//8
            for leftover in range(lanes):
                header = Header({}, lanes + leftover)
                for cls in [Packetizer, Depacketizer]:
                    with self.subTest(width=width, leftover=leftover, cls=cls.__name__):
                        layout = [("data", width), ("be", lanes), ("error", lanes)]
                        dut = cls(layout, layout, header)
                        # Distinct byte error positions across words, including a partial tail.
                        size = 4*lanes + 1
                        inputs = beats(bytes(range(size)), lanes)
                        error_bytes = [int(i % 3 == 1) for i in range(size)]
                        errors = [sum(v << i for i, v in enumerate(error_bytes[n:n + lanes]))
                            for n in range(0, size, lanes)]
                        output_errors = []
                        result = simulate(self, dut, inputs, errors=errors, output_errors=output_errors)
                        got = [bool(error & (1 << i))
                            for (_, mask, _, _), error in zip(result, output_errors)
                            for i in range(lanes) if mask & (1 << i)]
                        expected = ([0]*header.length + error_bytes) if cls == Packetizer else error_bytes[header.length:]
                        self.assertEqual(got, expected)

    def test_converter_verilog(self):
        from litex.gen.fhdl import verilog
        for qualifier in ["be", "keep"]:
            for reverse in [False, True]:
                for widths in [(8, 64), (64, 8), (32, 64), (64, 32)]:
                    with self.subTest(qualifier=qualifier, reverse=reverse, widths=widths):
                        dut = stream.StrideConverter(description(widths[0], qualifier), description(widths[1], qualifier), reverse=reverse)
                        dut.clock_domains.cd_sys = ClockDomain("sys")
                        verilog.convert(dut, ios=set(dut.sink.flatten() + dut.source.flatten()))

class TestByteEnableHelpers(unittest.TestCase):
    def test_mask_and_count(self):
        for width in [1, 2, 4, 8, 16]:
            with self.subTest(width=width):
                dut = Module()
                count = Signal(max=width + 2)
                mask = Signal(width)
                counted = Signal(max=width + 1)
                dut.comb += [mask.eq(stream.byte_mask(count, width)), counted.eq(stream.byte_count(mask))]
                def check():
                    for n in range(width + 2):
                        yield count.eq(n)
                        yield
                        self.assertEqual((yield mask), (1 << min(n, width)) - 1)
                        self.assertEqual((yield counted), min(n, width))
                run_simulation(dut, check())
        dut = Module()
        mask = Signal(8)
        count = Signal(4)
        dut.comb += count.eq(stream.byte_count(mask))
        def check_sparse():
            for value in range(256):
                yield mask.eq(value)
                yield
                self.assertEqual((yield count), bin(value).count("1"))
        run_simulation(dut, check_sparse())

    def test_qualifier_validation(self):
        for name in ["be", "keep"]:
            endpoint = stream.Endpoint([("data", 32), (name, 4)])
            self.assertEqual(stream.byte_enable_name(endpoint), name)
            for layout in [[("data", 32), (name, 1)], [("data", 9), (name, 1)]]:
                with self.subTest(layout=layout), self.assertRaises(ValueError):
                    stream.byte_enable_name(stream.Endpoint(layout))
        with self.assertRaises(ValueError):
            stream.byte_enable_name(stream.Endpoint([("data", 32), ("be", 4), ("keep", 4)]))
        # Protocol parameters are not per-beat byte qualifiers.
        endpoint = stream.Endpoint(stream.EndpointDescription([("data", 32)], [("be", 4)]))
        self.assertIsNone(stream.byte_enable_name(endpoint))
        self.assertIsNone(stream.byte_enable_name(stream.Endpoint([("data", 32)])))
        with self.assertRaises(ValueError):
            stream.StrideConverter(description(32), stream.EndpointDescription([("data", 8)]))
        with self.assertRaises(ValueError):
            stream.byte_mask(Signal(4), 0)
