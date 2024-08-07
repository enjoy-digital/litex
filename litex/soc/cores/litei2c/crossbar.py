#
# This file is part of LiteX.
#
# Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright from LiteSPI file added above
# 
# Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
# SPDX-License-Identifier: BSD-2-Clause

from collections import OrderedDict

from migen import *
from migen.genlib.roundrobin import RoundRobin
from litex.soc.cores.litei2c.common import *

from litex.soc.interconnect import stream


class LiteI2CMasterPort:
    def __init__(self):
        self.source = stream.Endpoint(i2c_core2phy_layout)
        self.sink   = stream.Endpoint(i2c_phy2core_layout)


class LiteI2CSlavePort:
    def __init__(self):
        self.source = stream.Endpoint(i2c_phy2core_layout)
        self.sink   = stream.Endpoint(i2c_core2phy_layout)


class LiteI2CCrossbar(Module):
    def __init__(self, cd):
        self.cd     = cd
        self.users  = []
        self.master = LiteI2CMasterPort()
        if cd != "sys":
            rx_cdc = stream.AsyncFIFO(i2c_phy2core_layout, 32, buffered=True)
            tx_cdc = stream.AsyncFIFO(i2c_core2phy_layout, 32, buffered=True)
            self.submodules.rx_cdc = ClockDomainsRenamer({"write": cd, "read": "sys"})(rx_cdc)
            self.submodules.tx_cdc = ClockDomainsRenamer({"write": "sys", "read": cd})(tx_cdc)
            self.comb += [
                self.rx_cdc.source.connect(self.master.sink),
                self.master.source.connect(self.tx_cdc.sink),
            ]

        self.enable           = Signal()
        self.user_enable      = []
        self.user_request = []

    def get_port(self, enable, request = None):
        user_port     = LiteI2CSlavePort()
        internal_port = LiteI2CSlavePort()

        tx_stream = user_port.sink

        self.comb += tx_stream.connect(internal_port.sink)

        rx_stream = internal_port.source

        self.comb += rx_stream.connect(user_port.source)

        if request is None:
            request = Signal()
            self.comb += request.eq(enable)

        self.users.append(internal_port)
        self.user_enable.append(self.enable.eq(enable))
        self.user_request.append(request)

        return user_port

    def do_finalize(self):
        self.submodules.rr = RoundRobin(len(self.users))

        # TX
        self.submodules.tx_mux = tx_mux = stream.Multiplexer(i2c_core2phy_layout, len(self.users))

        # RX
        self.submodules.rx_demux = rx_demux = stream.Demultiplexer(i2c_phy2core_layout, len(self.users))

        for i, user in enumerate(self.users):
            self.comb += [
                user.sink.connect(getattr(tx_mux, f"sink{i}")),
                getattr(rx_demux, f"source{i}").connect(user.source),
            ]

        self.comb += [
            self.rr.request.eq(Cat(self.user_request)),

            self.tx_mux.source.connect(self.master.source),
            self.tx_mux.sel.eq(self.rr.grant),

            self.master.sink.connect(self.rx_demux.sink),
            self.rx_demux.sel.eq(self.rr.grant),

            Case(self.rr.grant, dict(enumerate(self.user_enable))),
        ]
