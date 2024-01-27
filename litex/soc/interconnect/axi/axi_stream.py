#
# This file is part of LiteX.
#
# Copyright (c) 2018-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream
from litex.build.generic_platform import *

from litex.soc.interconnect.axi.axi_common import *

# AXI-Stream Definition ----------------------------------------------------------------------------

class AXIStreamInterface(stream.Endpoint):
    def __init__(self, data_width=0, keep_width=None, id_width=0, dest_width=0, user_width=0, clock_domain="sys", layout=None, name=None):
        self.data_width   = data_width
        self.keep_width   = data_width//8 if keep_width is None else keep_width
        self.id_width     = id_width
        self.dest_width   = dest_width
        self.user_width   = user_width
        self.clock_domain = clock_domain

        # Define Payload Layout.
        if layout is not None:
            payload_layout = layout
        else:
            payload_layout =  [("data", max(1, self.data_width))]
            payload_layout += [("keep", max(1, self.keep_width))]

        # Define Param Layout.
        param_layout = []
        param_layout += [("id",   max(1,   self.id_width))]
        param_layout += [("dest", max(1, self.dest_width))]
        param_layout += [("user", max(1, self.user_width))]

        # Create Endpoint.
        stream.Endpoint.__init__(self, stream.EndpointDescription(payload_layout, param_layout), name=name)

    def get_ios(self, bus_name="axi"):
        # Control Signals.
        subsignals = [
            Subsignal("tvalid", Pins(1)),
            Subsignal("tlast",  Pins(1)),
            Subsignal("tready", Pins(1)),
        ]

        # Payload/Params Signals.
        channel_layout = (self.description.payload_layout + self.description.param_layout)
        for name, width in channel_layout:
            subsignals.append(Subsignal(f"t{name}", Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        assert mode in ["slave", "master"]
        r = []
        if mode == "master":
            # Control Signals.
            r.append(pads.tvalid.eq(self.valid))
            r.append(self.ready.eq(pads.tready))
            r.append(pads.tlast.eq(self.last))
            # Payload Signals.
            r.append(pads.tdata.eq(self.data))
            r.append(pads.tkeep.eq(self.keep))
            # Param Signals.
            r.append(pads.tid.eq(self.id))
            r.append(pads.tdest.eq(self.dest))
            r.append(pads.tuser.eq(self.user))
        if mode == "slave":
            # Control Signals.
            r.append(self.valid.eq(pads.tvalid))
            r.append(pads.tready.eq(self.ready))
            r.append(self.last.eq(pads.tlast))
            # Payload Signals.
            r.append(self.data.eq(pads.tdata))
            r.append(self.keep.eq(pads.tkeep))
            # Param Signals.
            r.append(self.id.eq(pads.tid))
            r.append(self.dest.eq(pads.tdest))
            r.append(self.user.eq(pads.tuser))
        return r
