#
# This file is part of LiteX.
#
# Copyright (c) 2018-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *
from migen.genlib import roundrobin

from litex.gen.genlib.misc import WaitTimer

from litex.build.generic_platform import *

from litex.soc.interconnect import stream


# AXI Constants ------------------------------------------------------------------------------------

BURST_FIXED    = 0b00 # FIXED    : No address increment in burst.
BURST_INCR     = 0b01 # INCR     : Increment address per transfer in burst.
BURST_WRAP     = 0b10 # WRAP     : Wrap address back to boundary after set transfers.
BURST_RESERVED = 0b11 # RESERVED : Future use.

RESP_OKAY      = 0b00 # OKAY   : Operation completed successfully.
RESP_EXOKAY    = 0b01 # EXOKAY : Operation success, exclusive access granted.
RESP_SLVERR    = 0b10 # SLVERR : Slave not responding/cannot complete request.
RESP_DECERR    = 0b11 # DECERR : Decoding error occurred, operation not routed to a slave.

# AXI transaction size (AXSIZE) constants (left: bytes, right: AXI representation).
AXSIZE = {
     1 : 0b000, #  1-byte transaction.
     2 : 0b001, #  2-byte transaction.
     4 : 0b010, #  4-byte transaction.
     8 : 0b011, #  8-byte transaction.
    16 : 0b100, # 16-byte transaction.
    32 : 0b110, # 32-byte transaction.
    64 : 0b111, # 64-byte transaction.
}

# AXI Connection Helpers ---------------------------------------------------------------------------

def connect_axi(master, slave, keep=None, omit=None, axi_full=False):
    """
    Connect AXI master to slave channels.

    This function connects the AXI channels from the master and slave taking into account their
    respective roles for each channel type.

    Parameters:
        master : AXI master interface.
        slave  : AXI slave interface.
        keep   : Optional parameter to keep some signals while connecting.
        omit   : Optional parameter to omit some signals while connecting.

    Returns:
        list: List of statements to create the necessary connections.
    """
    channel_modes = {
        "aw": "master",
        "w" : "master",
        "b" : "slave",
        "ar": "master",
        "r" : "slave",
    }
    if "r" not in master.mode or "r" not in slave.mode:
        channel_modes.pop("r")
        channel_modes.pop("ar")
    if "w"  not in master.mode or "w" not in slave.mode:
        channel_modes.pop("w")
        channel_modes.pop("aw")
        channel_modes.pop("b")
    assert len(channel_modes) > 0, "No AXI channels to connect."
    r = []
    if omit is None:
        omit = set()
    elif isinstance(omit, list):
        omit = set(omit)
    omit.add("first")
    omit.add("last")

    for channel, mode in channel_modes.items():
        if axi_full and (channel in ["w", "r"]):
            new_omit = omit - {"last"}
        else:
            new_omit = omit 
        if mode == "master":
            m, s = getattr(master, channel), getattr(slave, channel)
        else:
            s, m = getattr(master, channel), getattr(slave, channel)
        r.extend(m.connect(s, keep=keep, omit=new_omit))
    return r

def connect_to_pads(bus, pads, mode="master", axi_full=False):
    """
    Connect to pads (I/O pins) on the Platform.

    This function connects the AXI bus signals to the respective pads on the Platform, taking into
    account their roles (master or slave) for each channel type.

    Parameters:
        bus      : AXI bus interface.
        pads     : FPGA pad interface.
        mode     : Role for connection (master or slave).
        axi_full : Boolean flag to indicate if AXI full is being used.

    Returns:
        list: List of statements to create the necessary connections.
    """
    assert mode in ["slave", "master"]
    r = []
    def swap_mode(mode): return "master" if mode == "slave" else "slave"
    channel_modes = {
        "aw": mode,
        "w" : mode,
        "b" : swap_mode(mode),
        "ar": mode,
        "r" : swap_mode(mode),
    }
    if "r" not in bus.mode:
        channel_modes.pop("r")
        channel_modes.pop("ar")
    if "w" not in bus.mode:
        channel_modes.pop("w")
        channel_modes.pop("aw")
        channel_modes.pop("b")
    # Loop to connect each channel.
    for channel, mode in channel_modes.items():
        ch = getattr(bus, channel)
        sig_list = [("valid", 1)] + ch.description.payload_layout + ch.description.param_layout
        if channel in ["w", "r"] and axi_full:
            sig_list += [("last",  1)]
        # Loop to connect each signal within a channel.
        for name, width in sig_list:
            if (name == "dest"):
                continue # No DEST.
            if (channel == "w") and (name == "id") and (bus.version == "axi4"):
                continue # No WID on AXI4.
            sig  = getattr(ch, name)
            pad  = getattr(pads, channel + name)
            if mode == "master":
                r.append(pad.eq(sig))
            else:
                r.append(sig.eq(pad))
        for name, width in [("ready", 1)]:
            sig  = getattr(ch, name)
            pad  = getattr(pads, channel + name)
            if mode == "master":
                r.append(sig.eq(pad))
            else:
                r.append(pad.eq(sig))
    return r

def axi_layout_flat(axi, axi_full=False):
    """
    Generator that yields a flat layout of each AXI signal's channel, name, and direction.

    This function is a generator that iterates over each AXI channel ("aw", "w", "b", "ar", "r"),
    then over each group in the channel's layout.

    Parameters:
        axi: AXI interface object.

    Yields:
        tuple: A tuple of (channel, name, direction), where:
           - channel is the name of the AXI channel,
           - name is the name of the signal within that channel,
           - direction is the direction of the signal (DIR_M_TO_S or DIR_S_TO_M).
    """

    # Helper function to correctly set the direction for "b" and "r" channels.
    def get_dir(channel, direction):
        if channel in ["b", "r"]:
            return {DIR_M_TO_S: DIR_S_TO_M, DIR_S_TO_M: DIR_M_TO_S}[direction]
        return direction
    
    channels = []
    if "r" in axi.mode:
        channels.append("ar")
        channels.append("r")
    if "w" in axi.mode:
        channels.append("aw")
        channels.append("w")
        channels.append("b")

    # Iterate over each channel.
    for ch in channels:
        channel = getattr(axi, ch)

        # Iterate over each group in the channel's layout.
        for group in channel.layout:
            if (ch not in ["w", "r"]) or not axi_full:
                omit_names = ["first", "last"]
            else:
                omit_names = ["first"]

            if len(group) == 3:
                name, _, direction = group
                if name in omit_names:
                    continue
                yield ch, name, get_dir(ch, direction)
            else:
                _, subgroups = group
                # Iterate over each subgroup in the group.
                for subgroup in subgroups:
                    name, _, direction = subgroup
                    if name in omit_names:
                        continue
                    yield ch, name, get_dir(ch, direction)
