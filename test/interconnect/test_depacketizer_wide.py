#
# This file is part of LiteX.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest

from migen import *
from litex.gen.fhdl import verilog
from litex.soc.interconnect import stream
from litex.soc.interconnect.packet import Header, HeaderField, Depacketizer
from test.interconnect.test_byte_enable import beats, description, qualified_bytes, simulate


class TestDepacketizerWide(unittest.TestCase):
    def test_packets_and_metadata(self):
        for width in [32, 64, 128, 256, 512]:
            lanes = width//8
            for length in sorted({1, lanes - 1, lanes, lanes + 1, 8, 14, 20}):
                for qualifier in ["be", "keep"]:
                    with self.subTest(width=width, length=length, qualifier=qualifier):
                        header = Header({"value" : HeaderField(0, 0, length*8)}, length, swap_field_bytes=False)
                        dut = Depacketizer(description(width, qualifier),
                            description(width, qualifier, header.get_layout()), header)
                        inputs, expected, headers = [], [], []
                        # Alternate truncated/header-only packets and good packets. Every packet
                        # has different metadata, including when it fits in a single input beat.
                        for n, size in enumerate([0, 1, lanes - 1, lanes, lanes + 1, 2*lanes + 1]):
                            head = bytes((i + n) % 256 for i in range(length))
                            payload = bytes((i + 80) % 256 for i in range(size))
                            for short in [head[:max(1, length - 1)], head]:
                                inputs += beats(short, lanes)
                            inputs += beats(head + payload, lanes)
                            expected += beats(payload, lanes)
                            headers += [int.from_bytes(head, "little")]*len(beats(payload, lanes))
                        actual, metadata = [], []
                        done = [False]

                        def producer():
                            prng = random.Random(42)
                            for data, mask, first, last in inputs:
                                for _ in range(prng.randrange(2)):
                                    yield
                                yield dut.sink.valid.eq(1)
                                yield dut.sink.data.eq(data)
                                yield getattr(dut.sink, qualifier).eq(mask)
                                yield dut.sink.first.eq(first)
                                yield dut.sink.last.eq(last)
                                yield
                                for _ in range(100):
                                    if (yield dut.sink.ready):
                                        break
                                    yield
                                else:
                                    self.fail("Input stalled")
                                yield dut.sink.valid.eq(0)
                            done[0] = True

                        def consumer():
                            prng = random.Random(43)
                            stalled = None
                            idle = 0
                            for _ in range(3000):
                                yield dut.source.ready.eq(prng.randrange(2))
                                yield
                                valid = (yield dut.source.valid)
                                item = ((yield dut.source.data), (yield getattr(dut.source, qualifier)),
                                    (yield dut.source.first), (yield dut.source.last), (yield dut.source.value))
                                if stalled is not None:
                                    self.assertTrue(valid)
                                    self.assertEqual(item, stalled)
                                stalled = item if valid and not (yield dut.source.ready) else None
                                if valid and (yield dut.source.ready):
                                    actual.append(item[:4])
                                    metadata.append(item[4])
                                    idle = 0
                                elif done[0]:
                                    idle += 1
                                    if idle == 12:
                                        return
                            self.fail("Output did not drain")

                        run_simulation(dut, [producer(), consumer()])
                        self.assertEqual([(m, f, l) for _, m, f, l in actual],
                            [(m, f, l) for _, m, f, l in expected])
                        self.assertEqual(qualified_bytes(actual, lanes), qualified_bytes(expected, lanes))
                        self.assertEqual(metadata, headers)

    def test_byte_errors(self):
        for width in [64, 128, 256, 512]:
            lanes = width//8
            for length in [1, lanes - 1]:
                with self.subTest(width=width, length=length):
                    layout = [("data", width), ("be", lanes), ("error", lanes)]
                    dut = Depacketizer(layout, layout, Header({}, length))
                    inputs, errors, expected = [], [], []
                    for size in [length + 1, lanes, lanes + 1, 3*lanes + 1]:
                        packet = bytes(i % 256 for i in range(size))
                        inputs += beats(packet, lanes)
                        flags = [int(i % 3 == 1) for i in range(size)]
                        errors += [sum(v << i for i, v in enumerate(flags[n:n + lanes]))
                            for n in range(0, size, lanes)]
                        expected += flags[length:]
                    output_errors = []
                    actual = simulate(self, dut, inputs, errors=errors, output_errors=output_errors)
                    flags = [int(bool(error & (1 << i)))
                        for (_, mask, _, _), error in zip(actual, output_errors)
                        for i in range(lanes) if mask & (1 << i)]
                    self.assertEqual(flags, expected)

    def test_verilog(self):
        for width in [128, 256, 512]:
            for length in [8, 14, 20]:
                with self.subTest(width=width, length=length):
                    dut = Depacketizer(description(width), description(width), Header({}, length))
                    dut.clock_domains.cd_sys = ClockDomain("sys")
                    verilog.convert(dut, ios=set(dut.sink.flatten() + dut.source.flatten()),
                        comb_cycle_policy="error")

    def test_without_byte_qualifier(self):
        from litex.soc.interconnect.packet import Packetizer
        for width in [128, 256, 512]:
            with self.subTest(width=width):
                header = Header({}, 14)
                dut = Module()
                dut.submodules.tx = tx = Packetizer([('data', width)], [('data', width)], header)
                dut.submodules.rx = rx = Depacketizer([('data', width)], [('data', width)], header)
                dut.comb += tx.source.connect(rx.sink)
                received = []
                words = [(0x1234, 1), (0xabcd, 0), (0x9876, 1)]
                def producer():
                    for data, last in words:
                        yield tx.sink.valid.eq(1)
                        yield tx.sink.data.eq(data)
                        yield tx.sink.last.eq(last)
                        yield
                        for _ in range(100):
                            if (yield tx.sink.ready):
                                break
                            yield
                        else:
                            self.fail('Input stalled')
                    yield tx.sink.valid.eq(0)
                def consumer():
                    for cycle in range(100):
                        yield rx.source.ready.eq(cycle % 3 != 0)
                        yield
                        if (yield rx.source.valid) and (yield rx.source.ready):
                            received.append(((yield rx.source.data), (yield rx.source.last)))
                run_simulation(dut, [producer(), consumer()])
                self.assertEqual(received, words)

    def test_reset_drops_pending_payload(self):
        for width in [128, 256, 512]:
            with self.subTest(width=width):
                header = Header({}, 14)
                dut = ResetInserter()(Depacketizer(description(width), description(width), header))
                def check():
                    yield dut.source.ready.eq(0)
                    yield dut.sink.valid.eq(1)
                    yield dut.sink.last.eq(1)
                    yield dut.sink.be.eq((1 << 15) - 1)
                    yield dut.sink.data.eq(0xaa << 112)
                    yield
                    yield
                    yield dut.sink.valid.eq(0)
                    yield
                    self.assertEqual((yield dut.source.valid), 1)
                    yield dut.reset.eq(1)
                    yield
                    yield
                    yield dut.reset.eq(0)
                    yield dut.source.ready.eq(1)
                    yield
                    self.assertEqual((yield dut.source.valid), 0)
                    yield dut.source.ready.eq(0)
                    yield dut.sink.data.eq(0xbb << 112)
                    yield dut.sink.valid.eq(1)
                    yield
                    yield
                    yield dut.sink.valid.eq(0)
                    yield
                    self.assertEqual((yield dut.source.valid), 1)
                    self.assertEqual((yield dut.source.data), 0xbb)
                    self.assertEqual((yield dut.source.be), 1)
                    self.assertEqual((yield dut.source.last), 1)
                run_simulation(dut, check())

    def test_generated_verilog(self):
        import shutil
        import tempfile
        import subprocess
        from pathlib import Path
        if not shutil.which('iverilog') or not shutil.which('vvp'):
            self.skipTest('Icarus Verilog is required')
        for width in [128, 256, 512]:
            with self.subTest(width=width):
                lanes = width//8
                header = Header({'value': HeaderField(0, 0, 112)}, 14, swap_field_bytes=False)
                dut = Depacketizer(description(width), description(width, params=header.get_layout()), header)
                dut.clock_domains.cd_sys = ClockDomain('sys')
                inputs = dict(i_valid=dut.sink.valid, i_data=dut.sink.data, i_be=dut.sink.be,
                    i_last=dut.sink.last, o_ready=dut.source.ready)
                outputs = dict(i_ready=dut.sink.ready, o_valid=dut.source.valid, o_data=dut.source.data,
                    o_be=dut.source.be, o_last=dut.source.last, o_header=dut.source.value)
                ios = {dut.cd_sys.clk, dut.cd_sys.rst}
                declarations, ports = [], ['.sys_clk(clk)', '.sys_rst(rst)']
                for signals, kind in [(inputs, 'reg'), (outputs, 'wire')]:
                    for name, signal in signals.items():
                        signal.name_override = name
                        ios.add(signal)
                        declarations.append(f'{kind} [{len(signal)-1}:0] {name};')
                        ports.append(f'.{name}({name})')
                bench = f'''
module tb;
reg clk=0, rst=1;
always #5 clk=~clk;
integer cycles=0, received=0;
{chr(10).join(declarations)}
dut dut({', '.join(ports)});
always @(posedge clk) begin
    cycles <= cycles+1;
    if (cycles == 100) $fatal(1, "Timed out");
    if (!rst && o_valid && o_ready) begin
        if (o_data !== {width}'hbb || o_be !== 1 || !o_last || o_header !== 112'h1234)
            $fatal(1, "Incorrect payload/header");
        received <= received+1;
    end
end
initial begin
    i_valid=0; i_last=1; i_be=0; i_data=0; o_ready=0;
    repeat(3) @(negedge clk); rst=0;
    // Header-only packet followed immediately by a one-byte payload packet.
    i_valid=1; i_be={lanes}'h3fff; i_data=0;
    @(posedge clk); while(!i_ready) @(posedge clk);
    @(negedge clk); i_be={lanes}'h7fff; i_data={width}'hbb0000000000000000000000001234;
    @(posedge clk); while(!i_ready) @(posedge clk);
    @(negedge clk); i_valid=0;
    repeat(5) @(negedge clk);
    if (!o_valid || o_data !== {width}'hbb || o_header !== 112'h1234) $fatal(1, "Stall");
    o_ready=1;
    repeat(5) @(negedge clk);
    if(received != 1) $fatal(1, "Incorrect packet count");
    $finish;
end
endmodule
'''
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)
                    verilog.convert(dut, ios=ios, name='dut', comb_cycle_policy='error').write(str(path/'dut.v'))
                    (path/'tb.v').write_text(bench)
                    for command in [['iverilog', '-g2012', '-s', 'tb', '-o', 'sim', 'dut.v', 'tb.v'], ['vvp', 'sim']]:
                        result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=20)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
