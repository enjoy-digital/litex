#!/usr/bin/env python3

from collections import namedtuple


class SpiProtocol(namedtuple("SpiProtocol", "command address data")):
    pass


class SpiProtocols:
    """SPI protocols.

    Number of data pins used to send;
     * Command
     * Address
     * Data

    FIXME: What does DTR mean?
    """

    # Basic protocols which only send / receive data with multiple pins.
    PROTO_1_1_1 = SpiProtocol(1, 1, 1)
    PROTO_1_1_2 = SpiProtocol(1, 1, 2)
    PROTO_1_1_4 = SpiProtocol(1, 1, 4)
    PROTO_1_1_8 = SpiProtocol(1, 1, 8)

    # Slightly more advanced protocols which also use multiple pins for sending
    # the address.
    PROTO_1_2_2 = SpiProtocol(1, 2, 2)
    PROTO_1_4_4 = SpiProtocol(1, 4, 4)
    PROTO_1_8_8 = SpiProtocol(1, 8, 8)

    # Protocol which uses multiple pins for everything. Not compatible with
    # other SPI commands.
    PROTO_2_2_2 = SpiProtocol(2, 2, 2)
    PROTO_4_4_4 = SpiProtocol(4, 4, 4)
    PROTO_8_8_8 = SpiProtocol(8, 8, 8)

    PROTO_1_1_1_DTR = SpiProtocol(1, 1, 1)
    PROTO_1_2_2_DTR = SpiProtocol(1, 2, 2)
    PROTO_1_4_4_DTR = SpiProtocol(1, 4, 4)
    PROTO_1_8_8_DTR = SpiProtocol(1, 8, 8)
