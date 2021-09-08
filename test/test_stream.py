# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random
import itertools
import sys

from migen import *

from litex.soc.interconnect.stream import *

# Function to iterate over chunks of data, from
# https://docs.python.org/3/library/itertools.html#itertools-recipes
def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)

class StreamPacket:
    def __init__(self, data, params={}):
        # Data must be a list of bytes
        assert type(data) == list
        for b in data:
            assert type(b) == int and b >= 0 and b < 256

        # Params must be a dictionary of strings mapping to integers
        assert type(params) == dict
        for param_key, param_value in params.items():
            assert type(param_key) == str
            assert type(param_value) == int

        self.data = data
        self.params = params

    def compare(self, other, quiet=True, output_target=sys.stdout):
        if len(self.data) != len(other.data):
            if not quiet:
                print("Length mismatch in number of received bytes of packet:" \
                      " {} {}".format(len(self.data), len(other.data)),
                      file=sys.stdout)
            return False


        for nbyte, (byte_a, byte_b) in enumerate(zip(self.data, other.data)):
            if byte_a != byte_b:
                if not quiet:
                    print("Mismatch between sent and received bytes {}: " \
                          "0x{:02x} 0x{:02x}".format(nbyte, byte_a, byte_b),
                          file=sys.stdout)
                return False

        if set(self.params.keys()) != set(other.params.keys()):
            if not quiet:
                print("Sent and received packets have different param fields:" \
                      " {} {}".format(self.params.keys(), other.params.keys()),
                      file=sys.stdout)
            return False

        for param_name, self_param_value in self.params.items():
            other_param_value = other.params[param_name]
            if self_param_value != other_param_value:
                if not quiet:
                    print("Sent and received packets have different value for" \
                          " param signal \"{}\": 0x{:x} 0x{:x}".format(
                              param_name,
                              self_param_value,
                              other_param_value),
                          file=sys.stdout)
                return False

        return True

def stream_inserter(
        sink,
        src,
        seed=42,
        valid_rand=50,
        debug_print=False,
        broken_8bit_last_be=True):
    """Insert a list of packets of bytes on to the stream interface `sink`. If
    `sink` has a `last_be` signal, that is set accordingly.

    """

    prng = random.Random(seed)

    # Extract the data width from the provided sink Endpoint
    dw = len(sink.data)

    # Make sure dw is evenly divisible by 8 as the logic below relies on
    # that. Also, last_be wouldn't make much sense otherwise.
    assert dw % 8 == 0

    # If a last_be signal is provided, it must contain one bit per byte of data,
    # i.e. be dw // 8 long.
    if hasattr(sink, "last_be"):
        assert dw // 8 == len(sink.last_be)

    # src is a list of lists. Each list represents a packet of bytes. Send each
    # packet over the bus.
    for pi, packet in enumerate(src):
        assert len(packet.data) > 0, "Packets of length 0 are not compatible " \
            "with the ready/valid stream interface"

        # Each packet is a list. We must send dw // 8 bytes at a time. Use the
        # grouper method to get a chunked iterator over the packet bytes and
        # shift them to their correct position. Use a random filler byte to
        # complete a bus word.
        words = []
        for chunk in grouper(packet.data, dw // 8, prng.randrange(256)):
            word = 0
            for i, b in enumerate(chunk):
                assert b >= 0 and b < 256
                word |= b << (i * 8)
            words += [word]

        if hasattr(sink, "last_be"):
            encoded_last_be = Constant(
                1 << ((len(packet.data) - 1) % (dw // 8)),
                bits_sign=len(sink.last_be)
            )

            # In legacy code for 8bit data paths last_be might not be set
            # properly: while last_be should always be equal to last for 8bit
            # data paths, if new code interacts with old code which is not yet
            # last_be aware, it might always be deasserted. If
            # broken_8bit_last_be is set and we have an 8bit data path, randomly
            # set last_be to either one or zero to check whether the DUT handles
            # these cases properly.
            if broken_8bit_last_be and dw == 8:
                encoded_last_be = Constant(prng.randrange(2), bits_sign=1)

        # At the very beginning of the packet transmission, set the param
        # signals
        for param_signal, param_value in packet.params.items():
            yield getattr(sink, param_signal).eq(param_value)

        for i, word in enumerate(words):
            last = i == len(words) - 1

            # Place the word on the bus, if its the last word set last and
            # last_be accordingly and finally set sink to valid
            yield sink.data.eq(word)
            yield sink.last.eq(last)
            if hasattr(sink, "last_be"):
                if last:
                    yield sink.last_be.eq(encoded_last_be)
                else:
                    yield sink.last_be.eq(0)
            yield sink.valid.eq(1)
            yield

            # Wait until the sink has become ready for one clock cycle
            while not (yield sink.ready):
                yield

            # Set sink to not valid for a random amount of time
            yield sink.valid.eq(0)
            while prng.randrange(100) < valid_rand:
                yield

        # Okay, we've transmitted a packet. We must set sink.valid to false, for
        # good measure clear all other signals as well. We don't explicitly
        # yield, given a there might be a new packet waiting already.
        yield sink.data.eq(0)
        yield sink.last.eq(0)
        if hasattr(sink, "last_be"):
            yield sink.last_be.eq(0)
        for param_signal in packet.params.keys():
            yield getattr(sink, param_signal).eq(0)
        yield sink.valid.eq(0)

        if debug_print:
            print("Sent packet {}.".format(pi), file=sys.stderr)

    # All packets have been transmitted. sink.valid has already been
    # deasserted, yield once to properly apply that value.
    yield

def stream_collector(
        source,
        dest=[],
        expect_npackets=None,
        seed=42,
        ready_rand=50,
        debug_print=False):
    """Consume some packets of bytes from the stream interface
    `source`. If `source` has a `last_be` signal, that is respected
    properly.

    """

    prng = random.Random(seed)

    # Extract the data width from the provided source endpoint
    dw = len(source.data)

    # Make sure dw is evenly divisible by 8 as the logic below relies on
    # that. Also, last_be wouldn't make much sense otherwise.
    assert dw % 8 == 0

    # If a last_be signal is provided, it must contain one bit per byte of data,
    # i.e. be dw // 8 long.
    if hasattr(source, "last_be"):
        assert dw // 8 == len(source.last_be)

    # Extract "param_signals" from the source Endpoint. They are extracted on
    # the first valid word of a packet. If dest will be a list of tuples with
    # data and param signals if there are any, otherwise just a list of lists.
    param_signals = [
        signal_name for signal_name, _, _ in source.param.layout
    ] if hasattr(source, "param") else []

    # Loop for collecting individual packets, separated by source.last
    while expect_npackets == None or len(dest) < expect_npackets:
        # Buffer for the current packet
        collected_bytes = []
        param_signal_states = {}

        # Iterate until "last" has been seen. That concludes the end of a bus
        # transaction / packet.
        read_last = False
        first_word = True
        while not read_last:
            # We are ready to accept another bus word
            yield source.ready.eq(1)
            yield

            # Wait for data to become valid
            while (yield source.valid) == 0:
                yield

            # Data is now valid, read it byte by byte
            data = yield source.data
            for byte in range(dw // 8):
                if (yield source.last) == 1:
                    read_last = True
                    if hasattr(source, "last_be") and \
                       2**byte > (yield source.last_be):
                        break
                collected_bytes += [((data >> (byte * 8)) & 0xFF)]

            # Also, if this is the first loop iteration, latch all param signals
            for param_signal in param_signals:
                param_signal_states[param_signal] = \
                    yield getattr(source, param_signal)

            # Set source to not valid for a random amount of time
            yield source.ready.eq(0)
            while prng.randrange(100) < ready_rand:
                yield

            # This is no longer the first loop iteration
            first_word = False

        # A full packet has been read. Append it to dest.
        dest += [StreamPacket(collected_bytes, param_signal_states)]
        if debug_print:
            print("Received packet {}.".format(len(dest) - 1), file=sys.stderr)

def generate_test_packets(npackets, seed=42):
    # Generate a number of last-terminated bus transaction byte contents (dubbed
    # packets)
    prng = random.Random(42)

    packets = []
    for _ in range(npackets):
        # With a random number of bytes from [1, 1024)
        values = []
        for _ in range(prng.randrange(1023) + 1):
            # With random values from [0, 256).
            values += [prng.randrange(256)]
        packets += [StreamPacket(values)]

    return packets

def compare_packets(packets_a, packets_b):
    if len(packets_a) != len(packets_b):
        print("Length mismatch in number of received packets: {} {}"
              .format(len(packets_a), len(packets_b)), file=sys.stderr)
        return False

    for npacket, (packet_a, packet_b) in enumerate(zip(packets_a, packets_b)):
        if not packet_a.compare(packet_b):
            print("Error in packet", npacket)
            packet_a.compare(packet_b, quiet=False)
            return False

    return True

class TestStream(unittest.TestCase):
    def pipe_test(self, dut, seed=42, npackets=64, debug_print=False):
        # Get some data to test with
        packets = generate_test_packets(npackets, seed=seed)

        # Buffer for received packets (filled by collector)
        recvd_packets = []

        run_simulation(
            dut,
            [
                stream_inserter(
                    dut.sink,
                    src=packets,
                    debug_print=debug_print,
                    seed=seed,
                ),
                stream_collector(
                    dut.source,
                    dest=recvd_packets,
                    expect_npackets=npackets,
                    debug_print=debug_print,
                    seed=seed,
                ),
            ],
        )
        self.assertTrue(compare_packets(packets, recvd_packets))

    def test_pipe_valid(self):
        # PipeValid either connects the entire payload or not. Thus we don't
        # need to test for 8bit support or a missing last_be signal
        # specifically. This test does however ensure that last_be will continue
        # to be respected in the future.
        dut = PipeValid([("data", 32), ("last_be", 4)])
        self.pipe_test(dut)

    def test_pipe_ready(self):
        # PipeReady either connects the entire stream Endpoint or not. Thus we
        # don't need to test for 8bit support or a missing last_be signal
        # specifically. This test does however ensure that last_be will continue
        # to be respected in the future.
        dut = PipeReady([("data", 64), ("last_be", 8)])
        self.pipe_test(dut)
