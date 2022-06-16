#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *

from litex.soc.interconnect import stream
from litex.build.generic_platform import *

from litex.soc.interconnect.axi.axi_common import *

# AXI-Stream Definition ----------------------------------------------------------------------------

class AXIStreamInterface(stream.Endpoint):
    def __init__(self, data_width=32, keep_width=0, user_width=0):
        self.data_width = data_width
        self.keep_width = keep_width
        self.user_width = user_width
        payload_layout = [("data", data_width)]
        if self.keep_width:
            payload_layout += [("keep", keep_width)]
        param_layout   = []
        if self.user_width:
            param_layout += [("user", user_width)]
        stream.Endpoint.__init__(self, stream.EndpointDescription(payload_layout, param_layout))

    def get_ios(self, bus_name="axi"):
        subsignals = [
            Subsignal("tvalid", Pins(1)),
            Subsignal("tlast",  Pins(1)),
            Subsignal("tready", Pins(1)),
            Subsignal("tdata",  Pins(self.data_width)),
        ]
        if self.keep_width:
            subsignals += [Subsignal("tkeep", Pins(self.keep_width))]
        if self.user_width:
            subsignals += [Subsignal("tuser", Pins(self.user_width))]
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        assert mode in ["slave", "master"]
        r = []
        if mode == "master":
            r.append(pads.tvalid.eq(self.valid))
            r.append(self.ready.eq(pads.tready))
            r.append(pads.tlast.eq(self.last))
            r.append(pads.tdata.eq(self.data))
            if self.keep_width:
                r.append(pads.tkeep.eq(self.keep))
            if self.user_width:
                r.append(pads.tuser.eq(self.user))
        if mode == "slave":
            r.append(self.valid.eq(pads.tvalid))
            r.append(pads.tready.eq(self.ready))
            r.append(self.last.eq(pads.tlast))
            r.append(self.data.eq(pads.tdata))
            if self.keep_width:
                r.append(self.keep.eq(pads.tkeep))
            if self.user_width:
                r.append(self.user.eq(pads.tuser))
        return r
