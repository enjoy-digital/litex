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
    def __init__(self, data_width=32, keep_width=0, id_width=0, dest_width=0, user_width=0):
        self.data_width = data_width
        self.keep_width = keep_width
        self.id_width   = id_width
        self.dest_width = dest_width
        self.user_width = user_width

        # Define Payload Layout.
        payload_layout = [("data", data_width)]
        if self.keep_width:
            payload_layout += [("keep", keep_width)]

        # Define Param Layout.
        param_layout   = []
        if self.id_width:
            param_layout += [("id", id_width)]
        if self.dest_width:
            param_layout += [("dest", dest_width)]
        if self.user_width:
            param_layout += [("user", user_width)]

        # Create Endpoint.
        stream.Endpoint.__init__(self, stream.EndpointDescription(payload_layout, param_layout))

    def get_ios(self, bus_name="axi"):
        # Control Signals.
        subsignals = [
            Subsignal("tvalid", Pins(1)),
            Subsignal("tlast",  Pins(1)),
            Subsignal("tready", Pins(1)),
        ]

        # Payload Signals.
        subsignals += [Subsignal("tdata",  Pins(self.data_width))]
        if self.keep_width:
            subsignals += [Subsignal("tkeep", Pins(self.keep_width))]

        # Param Signals.
        if self.id_width:
            subsignals += [Subsignal("tid", Pins(self.id_width))]
        if self.dest_width:
            subsignals += [Subsignal("tdest", Pins(self.dest_width))]
        if self.user_width:
            subsignals += [Subsignal("tuser", Pins(self.user_width))]
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
            if self.keep_width:
                r.append(pads.tkeep.eq(self.keep))
            # Param Signals.
            if self.id_width:
                r.append(pads.tid.eq(self.id))
            if self.dest_width:
                r.append(pads.tdest.eq(self.dest))
            if self.user_width:
                r.append(pads.tuser.eq(self.user))
        if mode == "slave":
            # Control Signals.
            r.append(self.valid.eq(pads.tvalid))
            r.append(pads.tready.eq(self.ready))
            r.append(self.last.eq(pads.tlast))
            # Payload Signals.
            r.append(self.data.eq(pads.tdata))
            if self.keep_width:
                r.append(self.keep.eq(pads.tkeep))
            # Param Signals.
            if self.id_width:
                r.append(self.id.eq(pads.tid))
            if self.dest_width:
                r.append(self.dest.eq(pads.tdest))
            if self.user_width:
                r.append(self.user.eq(pads.tuser))
        return r
