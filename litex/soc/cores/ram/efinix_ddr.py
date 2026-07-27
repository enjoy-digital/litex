#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.build.generic_platform import Pins, Subsignal

from litex.soc.integration.soc import SoCRegion
from litex.soc.interconnect import axi


# Efinix DDR ---------------------------------------------------------------------------------------

class EfinixDDR(LiteXModule):
    """Efinix Titanium/Topaz hardened DDR controller."""
    def __init__(self, platform,
        memory_type,
        memory_density,
        clkin_sel,
        clock_domain   = "sys",
        location       = "DDR_0",
        name           = "ddr_inst1",
        interface_name = "ddr0",
        cfg_name       = "cfg",
        dq_width       = 32,
        physical_rank  = 1,
        data_width     = 512,
        address_width  = 33,
        id_width       = 8,
        pin_swizzle    = None,
        init_delay     = 256):

        if clock_domain not in platform.clks:
            raise ValueError("Efinix DDR clock domain {} has no Efinity clock.".format(clock_domain))
        if init_delay < 1:
            raise ValueError("Efinix DDR initialization delay must be positive.")

        self.clock_domain = clock_domain
        self.awallstrb    = Signal()
        self.init_done    = Signal()
        self.bus = axi.AXIInterface(
            data_width    = data_width,
            address_width = address_width,
            id_width      = id_width,
            clock_domain  = clock_domain,
        )

        # AXI Interface.
        # --------------
        axi_ios = self.bus.get_ios(interface_name)
        axi_ios[0] += (
            Subsignal("arapcmd",   Pins(1)),
            Subsignal("awallstrb", Pins(1)),
            Subsignal("awapcmd",   Pins(1)),
            Subsignal("awcobuf",   Pins(1)),
            Subsignal("resetn",    Pins(1)),
        )
        self.axi_pads = axi_pads = platform.add_iface_ios(axi_ios)
        self.comb += self.bus.connect_to_pads(axi_pads, mode="master")
        self.comb += [
            axi_pads.arapcmd.eq(0),
            axi_pads.awallstrb.eq(self.awallstrb),
            axi_pads.awapcmd.eq(0),
            axi_pads.awcobuf.eq(0),
            axi_pads.resetn.eq(~ResetSignal(clock_domain)),
        ]

        # Configuration Interface.
        # ------------------------
        cfg_ios = [(cfg_name, 0,
            Subsignal("start", Pins(1)),
            Subsignal("reset", Pins(1)),
            Subsignal("sel",   Pins(1)),
            Subsignal("done",  Pins(1)),
        )]
        self.cfg_pads = cfg_pads = platform.add_iface_ios(cfg_ios)

        cfg_count = Signal(max=init_delay)
        cfg_start = Signal()
        self.comb += [
            cfg_pads.sel.eq(0),
            cfg_pads.reset.eq(~cfg_start),
            cfg_pads.start.eq(cfg_start),
            self.init_done.eq(cfg_pads.done),
        ]
        self.sync += If(~cfg_start,
            If(cfg_count == (init_delay - 1),
                cfg_start.eq(1),
            ).Else(
                cfg_count.eq(cfg_count + 1),
            )
        )

        # Efinity Interface Designer Block.
        # ----------------------------------
        platform.toolchain.ifacewriter.blocks.append({
            "type"            : "DDR",
            "name"            : name,
            "location"        : location,
            "memory_type"     : memory_type,
            "memory_density"  : memory_density,
            "dq_width"        : dq_width,
            "physical_rank"   : physical_rank,
            "clkin_sel"       : clkin_sel,
            "axi"             : axi_pads,
            "axi_clk"         : platform.clks[clock_domain],
            "axi_data_width"  : data_width,
            "cfg"             : cfg_pads,
            "pin_swizzle"     : {} if pin_swizzle is None else pin_swizzle,
        })


# Efinix DDR SoC Integration -----------------------------------------------------------------------

def add_efinix_ddr(soc, ddr, size, origin=None):
    if origin is None:
        origin = soc.mem_map.get("main_ram", None)
    if origin is None:
        raise ValueError("Efinix DDR main RAM origin is not defined.")

    region = SoCRegion(
        origin = origin,
        size   = size,
        mode   = "rwx",
    )

    # Let CPUs with a native memory port create it at the hard controller's data width.
    if hasattr(soc.cpu, "add_memory_buses"):
        soc.cpu.add_memory_buses(
            address_width = min(soc.bus.address_width, ddr.bus.address_width),
            data_width    = ddr.bus.data_width,
        )

    memory_buses = getattr(soc.cpu, "memory_buses", [])
    if memory_buses:
        if len(memory_buses) != 1:
            raise ValueError("Efinix DDR requires exactly one CPU memory bus.")
        memory_bus = memory_buses[0]
        if not isinstance(memory_bus, axi.AXIInterface):
            raise TypeError("Efinix DDR CPU memory bus must use AXI.")
        if memory_bus.data_width != ddr.bus.data_width:
            raise ValueError(
                "Efinix DDR CPU memory bus data width must match the controller data width.")

        soc.submodules += axi.AXIRemapper(
            master = memory_bus,
            slave  = ddr.bus,
        )
        soc.comb += ddr.awallstrb.eq(getattr(soc.cpu, "mBus_awallStrb", 0))
        soc.bus.add_region("main_ram", region)
        return memory_bus

    # The SoC bus adapts its native standard/data width to this frontend. A separate 33-bit
    # interface then extends the address before conversion to the hard controller's AXI port.
    axi_lite_bus = axi.AXILiteInterface(
        data_width    = ddr.bus.data_width,
        address_width = soc.bus.address_width,
        clock_domain  = ddr.clock_domain,
    )
    axi_lite_ddr = axi.AXILiteInterface(
        data_width    = ddr.bus.data_width,
        address_width = ddr.bus.address_width,
        clock_domain  = ddr.clock_domain,
    )
    soc.submodules += axi.AXILiteRemapper(
        master = axi_lite_bus,
        slave  = axi_lite_ddr,
    )
    soc.submodules += axi.AXILite2AXI(axi_lite_ddr, ddr.bus)
    soc.comb += ddr.awallstrb.eq(0)
    soc.bus.add_slave("main_ram", axi_lite_bus, region)
    return axi_lite_bus
