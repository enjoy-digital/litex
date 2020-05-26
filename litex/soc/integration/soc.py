# This file is Copyright (c) 2014-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2019 Gabriel L. Somlo <somlo@cmu.edu>
# License: BSD

import logging
import time
import datetime
from math import log2, ceil

from migen import *

from litex.soc.cores import cpu
from litex.soc.cores.identifier import Identifier
from litex.soc.cores.timer import Timer
from litex.soc.cores.spi_flash import SpiFlash
from litex.soc.cores.spi import SPIMaster

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import csr_bus
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import wishbone2csr
from litex.soc.interconnect import axi

logging.basicConfig(level=logging.INFO)

# Helpers ------------------------------------------------------------------------------------------

def auto_int(x):
    return int(x, 0)

def colorer(s, color="bright"):
    header  = {
        "bright": "\x1b[1m",
        "green":  "\x1b[32m",
        "cyan":   "\x1b[36m",
        "red":    "\x1b[31m",
        "yellow": "\x1b[33m",
        "underline": "\x1b[4m"}[color]
    trailer = "\x1b[0m"
    return header + str(s) + trailer

def build_time(with_time=True):
    fmt = "%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d"
    return datetime.datetime.fromtimestamp(time.time()).strftime(fmt)

# SoCConstant --------------------------------------------------------------------------------------

def SoCConstant(value):
    return value

# SoCRegion ----------------------------------------------------------------------------------------

class SoCRegion:
    def __init__(self, origin=None, size=None, mode="rw", cached=True, linker=False):
        self.logger    = logging.getLogger("SoCRegion")
        self.origin    = origin
        self.size      = size
        if size != 2**log2_int(size, False):
            self.logger.info("Region size {} internally from {} to {}.".format(
                colorer("rounded", color="cyan"),
                colorer("0x{:08x}".format(size)),
                colorer("0x{:08x}".format(2**log2_int(size, False)))))
        self.size_pow2 = 2**log2_int(size, False)
        self.mode      = mode
        self.cached    = cached
        self.linker    = linker

    def decoder(self, bus):
        origin = self.origin
        size   = self.size_pow2
        if (origin & (size - 1)) != 0:
            self.logger.error("Origin needs to be aligned on size:")
            self.logger.error(self)
            raise
        origin >>= int(log2(bus.data_width//8)) # bytes to words aligned
        size   >>= int(log2(bus.data_width//8)) # bytes to words aligned
        return lambda a: (a[log2_int(size):] == (origin >> log2_int(size)))

    def __str__(self):
        r = ""
        if self.origin is not None:
            r += "Origin: {}, ".format(colorer("0x{:08x}".format(self.origin)))
        if self.size is not None:
            r += "Size: {}, ".format(colorer("0x{:08x}".format(self.size)))
        r += "Mode: {}, ".format(colorer(self.mode.upper()))
        r += "Cached: {} ".format(colorer(self.cached))
        r += "Linker: {}".format(colorer(self.linker))
        return r

class SoCIORegion(SoCRegion): pass

# SoCCSRRegion -------------------------------------------------------------------------------------

class SoCCSRRegion:
    def __init__(self, origin, busword, obj):
        self.origin  = origin
        self.busword = busword
        self.obj     = obj

# SoCBusHandler ------------------------------------------------------------------------------------

class SoCBusHandler(Module):
    supported_standard      = ["wishbone"]
    supported_data_width    = [32, 64]
    supported_address_width = [32]

    # Creation -------------------------------------------------------------------------------------
    def __init__(self, standard, data_width=32, address_width=32, timeout=1e6, reserved_regions={}):
        self.logger = logging.getLogger("SoCBusHandler")
        self.logger.info("Creating Bus Handler...")

        # Check Standard
        if standard not in self.supported_standard:
            self.logger.error("Unsupported {} {}, supporteds: {:s}".format(
                colorer("Bus standard", color="red"),
                colorer(standard),
                colorer(", ".join(self.supported_standard))))
            raise

        # Check Data Width
        if data_width not in self.supported_data_width:
            self.logger.error("Unsupported {} {}, supporteds: {:s}".format(
                colorer("Data Width", color="red"),
                colorer(data_width),
                colorer(", ".join(str(x) for x in self.supported_data_width))))
            raise

        # Check Address Width
        if address_width not in self.supported_address_width:
            self.logger.error("Unsupported {} {}, supporteds: {:s}".format(
                colorer("Address Width", color="red"),
                colorer(data_width),
                colorer(", ".join(str(x) for x in self.supported_address_width))))
            raise

        # Create Bus
        self.standard      = standard
        self.data_width    = data_width
        self.address_width = address_width
        self.masters       = {}
        self.slaves        = {}
        self.regions       = {}
        self.io_regions    = {}
        self.timeout       = timeout
        self.logger.info("{}-bit {} Bus, {}GiB Address Space.".format(
            colorer(data_width), colorer(standard), colorer(2**address_width/2**30)))

        # Adding reserved regions
        self.logger.info("Adding {} Bus Regions...".format(colorer("reserved", color="cyan")))
        for name, region in reserved_regions.items():
            if isinstance(region, int):
                region = SoCRegion(origin=region, size=0x1000000)
            self.add_region(name, region)

        self.logger.info("Bus Handler {}.".format(colorer("created", color="green")))

    # Add/Allog/Check Regions ----------------------------------------------------------------------
    def add_region(self, name, region):
        allocated = False
        if name in self.regions.keys() or name in self.io_regions.keys():
            self.logger.error("{} already declared as Region:".format(colorer(name, color="red")))
            self.logger.error(self)
            raise
        # Check if SoCIORegion
        if isinstance(region, SoCIORegion):
            self.io_regions[name] = region
            overlap = self.check_regions_overlap(self.io_regions)
            if overlap is not None:
                self.logger.error("IO Region {} between {} and {}:".format(
                    colorer("overlap", color="red"),
                    colorer(overlap[0]),
                    colorer(overlap[1])))
                self.logger.error(str(self.io_regions[overlap[0]]))
                self.logger.error(str(self.io_regions[overlap[1]]))
                raise
            self.logger.info("{} Region {} at {}.".format(
                colorer(name,    color="underline"),
                colorer("added", color="green"),
                str(region)))
        # Check if SoCRegion
        elif isinstance(region, SoCRegion):
            # If no origin specified, allocate region.
            if region.origin is None:
                allocated = True
                region    = self.alloc_region(name, region.size, region.cached)
                self.regions[name] = region
            # Else add region and check for overlaps.
            else:
                if not region.cached:
                    if not self.check_region_is_io(region):
                        self.logger.error("{} Region {}: {}.".format(
                            colorer(name),
                            colorer("not in IO region", color="red"),
                            str(region)))
                        self.logger.error(self)
                        raise
                self.regions[name] = region
                overlap = self.check_regions_overlap(self.regions)
                if overlap is not None:
                    self.logger.error("Region {} between {} and {}:".format(
                        colorer("overlap", color="red"),
                        colorer(overlap[0]),
                        colorer(overlap[1])))
                    self.logger.error(str(self.regions[overlap[0]]))
                    self.logger.error(str(self.regions[overlap[1]]))
                    raise
            self.logger.info("{} Region {} at {}.".format(
                colorer(name, color="underline"),
                colorer("allocated" if allocated else "added", color="cyan" if allocated else "green"),
                str(region)))
        else:
            self.logger.error("{} is not a supported Region.".format(colorer(name, color="red")))
            raise

    def alloc_region(self, name, size, cached=True):
        self.logger.info("Allocating {} Region of size {}...".format(
            colorer("Cached" if cached else "IO"),
            colorer("0x{:08x}".format(size))))

        # Limit Search Regions
        if cached == False:
            search_regions = self.io_regions
        else:
            search_regions = {"main": SoCRegion(origin=0x00000000, size=2**self.address_width-1)}

        # Iterate on Search_Regions to find a Candidate
        for _, search_region in search_regions.items():
            origin = search_region.origin
            while (origin + size) < (search_region.origin + search_region.size_pow2):
                # Create a Candicate.
                candidate = SoCRegion(origin=origin, size=size, cached=cached)
                overlap   = False
                # Check Candidate does not overlap with allocated existing regions
                for _, allocated in self.regions.items():
                    if self.check_regions_overlap({"0": allocated, "1": candidate}) is not None:
                        origin  = allocated.origin + allocated.size_pow2
                        overlap = True
                        break
                if not overlap:
                    # If no overlap, the Candidate is selected
                    return candidate

        self.logger.error("Not enough Address Space to allocate Region.")
        raise

    def check_regions_overlap(self, regions, check_linker=False):
        i = 0
        while i < len(regions):
            n0 =  list(regions.keys())[i]
            r0 = regions[n0]
            for n1 in list(regions.keys())[i+1:]:
                r1 = regions[n1]
                if r0.linker or r1.linker:
                    if not check_linker:
                        continue
                if r0.origin >= (r1.origin + r1.size_pow2):
                    continue
                if r1.origin >= (r0.origin + r0.size_pow2):
                    continue
                return (n0, n1)
            i += 1
        return None

    def check_region_is_in(self, region, container):
        is_in = True
        if not (region.origin >= container.origin):
            is_in = False
        if not ((region.origin + region.size) < (container.origin + container.size)):
            is_in = False
        return is_in

    def check_region_is_io(self, region):
        is_io = False
        for _, io_region in self.io_regions.items():
            if self.check_region_is_in(region, io_region):
                is_io = True
        return is_io

    # Add Master/Slave -----------------------------------------------------------------------------
    def add_adapter(self, name, interface, direction="m2s"):
        assert direction in ["m2s", "s2m"]
        if interface.data_width != self.data_width:
            self.logger.info("{} Bus {} from {}-bit to {}-bit.".format(
                colorer(name),
                colorer("converted", color="cyan"),
                colorer(interface.data_width),
                colorer(self.data_width)))
            new_interface = wishbone.Interface(data_width=self.data_width)
            if direction == "m2s":
                converter = wishbone.Converter(master=interface, slave=new_interface)
            if direction == "s2m":
                converter = wishbone.Converter(master=new_interface, slave=interface)
            self.submodules += converter
            return new_interface
        else:
            return interface

    def add_master(self, name=None, master=None):
        if name is None:
            name = "master{:d}".format(len(self.masters))
        if name in self.masters.keys():
            self.logger.error("{} {} as Bus Master:".format(
                colorer(name),
                colorer("already declared", color="red")))
            self.logger.error(self)
            raise
        master = self.add_adapter(name, master, "m2s")
        self.masters[name] = master
        self.logger.info("{} {} as Bus Master.".format(
            colorer(name,    color="underline"),
            colorer("added", color="green")))

    def add_slave(self, name=None, slave=None, region=None):
        no_name   = name is None
        no_region = region is None
        if no_name and no_region:
            self.logger.error("Please {} {} or/and {} of Bus Slave.".format(
                colorer("specify", color="red"),
                colorer("name"),
                colorer("region")))
            raise
        if no_name:
            name = "slave{:d}".format(len(self.slaves))
        if no_region:
            region = self.regions.get(name, None)
            if region is None:
                self.logger.error("{} Region {}.".format(
                    colorer(name),
                    colorer("not found", color="red")))
                raise
        else:
             self.add_region(name, region)
        if name in self.slaves.keys():
            self.logger.error("{} {} as Bus Slave:".format(
                colorer(name),
                colorer("already declared", color="red")))
            self.logger.error(self)
            raise
        slave = self.add_adapter(name, slave, "s2m")
        self.slaves[name] = slave
        self.logger.info("{} {} as Bus Slave.".format(
            colorer(name, color="underline"),
            colorer("added", color="green")))

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r = "{}-bit {} Bus, {}GiB Address Space.\n".format(
            colorer(self.data_width), colorer(self.standard), colorer(2**self.address_width/2**30))
        r += "IO Regions: ({})\n".format(len(self.io_regions.keys())) if len(self.io_regions.keys()) else ""
        io_regions = {k: v for k, v in sorted(self.io_regions.items(), key=lambda item: item[1].origin)}
        for name, region in io_regions.items():
           r += colorer(name, color="underline") + " "*(20-len(name)) + ": " + str(region) + "\n"
        r += "Bus Regions: ({})\n".format(len(self.regions.keys())) if len(self.regions.keys()) else ""
        regions = {k: v for k, v in sorted(self.regions.items(), key=lambda item: item[1].origin)}
        for name, region in regions.items():
           r += colorer(name, color="underline") + " "*(20-len(name)) + ": " + str(region) + "\n"
        r += "Bus Masters: ({})\n".format(len(self.masters.keys())) if len(self.masters.keys()) else ""
        for name in self.masters.keys():
           r += "- {}\n".format(colorer(name, color="underline"))
        r += "Bus Slaves: ({})\n".format(len(self.slaves.keys())) if len(self.slaves.keys()) else ""
        for name in self.slaves.keys():
           r += "- {}\n".format(colorer(name, color="underline"))
        r = r[:-1]
        return r

# SoCLocHandler --------------------------------------------------------------------------------------

class SoCLocHandler(Module):
    # Creation -------------------------------------------------------------------------------------
    def __init__(self, name, n_locs):
        self.name   = name
        self.locs   = {}
        self.n_locs = n_locs

    # Add ------------------------------------------------------------------------------------------
    def add(self, name, n=None, use_loc_if_exists=False):
        allocated = False
        if not (use_loc_if_exists and name in self.locs.keys()):
            if name in self.locs.keys():
                self.logger.error("{} {} name {}.".format(
                    colorer(name), self.name, colorer("already used", color="red")))
                self.logger.error(self)
                raise
            if n in self.locs.values():
                self.logger.error("{} {} Location {}.".format(
                    colorer(n), self.name, colorer("already used", color="red")))
                self.logger.error(self)
                raise
            if n is None:
                allocated = True
                n = self.alloc(name)
            else:
                if n < 0:
                    self.logger.error("{} {} Location should be {}.".format(
                        colorer(n),
                        self.name,
                        colorer("positive", color="red")))
                    raise
                if n > self.n_locs:
                    self.logger.error("{} {} Location {} than maximum: {}.".format(
                        colorer(n),
                        self.name,
                        colorer("higher", color="red"),
                        colorer(self.n_locs)))
                    raise
            self.locs[name] = n
        else:
            n = self.locs[name]
        self.logger.info("{} {} {} at Location {}.".format(
            colorer(name, color="underline"),
            self.name,
            colorer("allocated" if allocated else "added", color="cyan" if allocated else "green"),
            colorer(n)))

    # Alloc ----------------------------------------------------------------------------------------
    def alloc(self, name):
        for n in range(self.n_locs):
            if n not in self.locs.values():
                return n
        self.logger.error("Not enough Locations.")
        self.logger.error(self)
        raise

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r = "{} Locations: ({})\n".format(self.name, len(self.locs.keys())) if len(self.locs.keys()) else ""
        locs = {k: v for k, v in sorted(self.locs.items(), key=lambda item: item[1])}
        length = 0
        for name in locs.keys():
            if len(name) > length: length = len(name)
        for name in locs.keys():
           r += "- {}{}: {}\n".format(colorer(name, color="underline"), " "*(length + 1 - len(name)), colorer(self.locs[name]))
        return r

# SoCCSRHandler ------------------------------------------------------------------------------------

class SoCCSRHandler(SoCLocHandler):
    supported_data_width    = [8, 32]
    supported_address_width = [14+i for i in range(4)]
    supported_alignment     = [32, 64]
    supported_paging        = [0x800*2**i for i in range(4)]

    # Creation -------------------------------------------------------------------------------------
    def __init__(self, data_width=32, address_width=14, alignment=32, paging=0x800, reserved_csrs={}):
        SoCLocHandler.__init__(self, "CSR", n_locs=alignment//8*(2**address_width)//paging)
        self.logger = logging.getLogger("SoCCSRHandler")
        self.logger.info("Creating CSR Handler...")

        # Check Data Width
        if data_width not in self.supported_data_width:
            self.logger.error("Unsupported {} {}, supporteds: {:s}".format(
                colorer("Data Width", color="red"),
                colorer(data_width),
                colorer(", ".join(str(x) for x in self.supported_data_width))))
            raise

        # Check Address Width
        if address_width not in self.supported_address_width:
            self.logger.error("Unsupported {} {} supporteds: {:s}".format(
                colorer("Address Width", color="red"),
                colorer(address_width),
                colorer(", ".join(str(x) for x in self.supported_address_width))))
            raise

        # Check Alignment
        if alignment not in self.supported_alignment:
            self.logger.error("Unsupported {}: {} supporteds: {:s}".format(
                colorer("Alignment", color="red"),
                colorer(alignment),
                colorer(", ".join(str(x) for x in self.supported_alignment))))
            raise
        if data_width > alignment:
            self.logger.error("Alignment ({}) {} Data Width ({})".format(
                colorer(alignment),
                colorer("should be >=", color="red"),
                colorer(data_width)))
            raise

        # Check Paging
        if paging not in self.supported_paging:
            self.logger.error("Unsupported {} 0x{}, supporteds: {:s}".format(
                colorer("Paging", color="red"),
                colorer("{:x}".format(paging)),
                colorer(", ".join("0x{:x}".format(x) for x in self.supported_paging))))
            raise

        # Create CSR Handler
        self.data_width    = data_width
        self.address_width = address_width
        self.alignment     = alignment
        self.paging        = paging
        self.masters       = {}
        self.regions       = {}
        self.logger.info("{}-bit CSR Bus, {}-bit Aligned, {}KiB Address Space, {}B Paging (Up to {} Locations).".format(
            colorer(self.data_width),
            colorer(self.alignment),
            colorer(2**self.address_width/2**10),
            colorer(self.paging),
            colorer(self.n_locs)))

        # Adding reserved CSRs
        self.logger.info("Adding {} CSRs...".format(colorer("reserved", color="cyan")))
        for name, n in reserved_csrs.items():
            self.add(name, n)

        self.logger.info("CSR Handler {}.".format(colorer("created", color="green")))

    # Update CSR Alignment ----------------------------------------------------------------------------
    def update_alignment(self, alignment):
        # Check Alignment
        if alignment not in self.supported_alignment:
            self.logger.error("Unsupported {}: {} supporteds: {:s}".format(
                colorer("Alignment", color="red"),
                colorer(alignment),
                colorer(", ".join(str(x) for x in self.supported_alignment))))
            raise
        self.logger.info("Alignment {} from {}-bit to {}-bit.".format(
            colorer("updated", color="cyan"),
            colorer(self.alignment),
            colorer(alignment)))
        self.alignment = alignment

    # Add Master -----------------------------------------------------------------------------------
    def add_master(self, name=None, master=None):
        if name is None:
            name = "master{:d}".format(len(self.masters))
        if name in self.masters.keys():
            self.logger.error("{} {} as CSR Master:".format(
                colorer(name),
                colorer("already declared", color="red")))
            self.logger.error(self)
            raise
        if master.data_width != self.data_width:
            self.logger.error("{} Master/Handler Data Width {} ({} vs {}).".format(
                colorer(name),
                colorer("missmatch", color="red"),
                colorer(master.data_width),
                colorer(self.data_width)))
            raise
        self.masters[name] = master
        self.logger.info("{} {} as CSR Master.".format(
            colorer(name,    color="underline"),
            colorer("added", color="green")))

    # Add Region -----------------------------------------------------------------------------------
    def add_region(self, name, region):
        # FIXME: add checks
        self.regions[name] = region

    # Address map ----------------------------------------------------------------------------------
    def address_map(self, name, memory):
        if memory is not None:
            name = name + "_" + memory.name_override
        if self.locs.get(name, None) is None:
            self.logger.error("CSR {} {}.".format(
                colorer(name),
                colorer("not found", color="red")))
            self.logger.error(self)
            raise
        return self.locs[name]

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r = "{}-bit CSR Bus, {}-bit Aligned, {}KiB Address Space, {}B Paging (Up to {} Locations).\n".format(
            colorer(self.data_width),
            colorer(self.alignment),
            colorer(2**self.address_width/2**10),
            colorer(self.paging),
            colorer(self.n_locs))
        r += SoCLocHandler.__str__(self)
        r = r[:-1]
        return r

# SoCIRQHandler ------------------------------------------------------------------------------------

class SoCIRQHandler(SoCLocHandler):
    # Creation -------------------------------------------------------------------------------------
    def __init__(self, n_irqs=32, reserved_irqs={}):
        SoCLocHandler.__init__(self, "IRQ", n_locs=n_irqs)
        self.logger = logging.getLogger("SoCIRQHandler")
        self.logger.info("Creating IRQ Handler...")

        # Check IRQ Number
        if n_irqs > 32:
            self.logger.error("Unsupported IRQs number: {} supporteds: {:s}".format(
                colorer(n, color="red"), colorer("Up to 32", color="green")))
            raise

        # Create IRQ Handler
        self.logger.info("IRQ Handler (up to {} Locations).".format(colorer(n_irqs)))

        # Adding reserved IRQs
        self.logger.info("Adding {} IRQs...".format(colorer("reserved", color="cyan")))
        for name, n in reserved_irqs.items():
            self.add(name, n)

        self.logger.info("IRQ Handler {}.".format(colorer("created", color="green")))

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r ="IRQ Handler (up to {} Locations).\n".format(colorer(self.n_locs))
        r += SoCLocHandler.__str__(self)
        r = r[:-1]
        return r

# SoCController ------------------------------------------------------------------------------------

class SoCController(Module, AutoCSR):
    def __init__(self,
        with_reset    = True,
        with_scratch  = True,
        with_errors   = True):

        if with_reset:
            self._reset = CSRStorage(1, description="""Write a ``1`` to this register to reset the SoC.""")
        if with_scratch:
            self._scratch = CSRStorage(32, reset=0x12345678, description="""
                Use this register as a scratch space to verify that software read/write accesses
                to the Wishbone/CSR bus are working correctly. The initial reset value of 0x1234578
                can be used to verify endianness.""")
        if with_errors:
            self._bus_errors = CSRStatus(32, description="Total number of Wishbone bus errors (timeouts) since start.")

        # # #

        # Reset
        if with_reset:
            self.reset = Signal()
            self.comb += self.reset.eq(self._reset.re)

        # Errors
        if with_errors:
            self.bus_error = Signal()
            bus_errors     = Signal(32)
            self.sync += [
                If(bus_errors != (2**len(bus_errors)-1),
                    If(self.bus_error, bus_errors.eq(bus_errors + 1))
                )
            ]
            self.comb += self._bus_errors.status.eq(bus_errors)

# SoC ----------------------------------------------------------------------------------------------

class SoC(Module):
    mem_map = {}
    def __init__(self, platform, sys_clk_freq,

        bus_standard         = "wishbone",
        bus_data_width       = 32,
        bus_address_width    = 32,
        bus_timeout          = 1e6,
        bus_reserved_regions = {},

        csr_data_width       = 32,
        csr_address_width    = 14,
        csr_alignment        = 32,
        csr_paging           = 0x800,
        csr_reserved_csrs    = {},

        irq_n_irqs           = 32,
        irq_reserved_irqs    = {},
        ):

        self.logger = logging.getLogger("SoC")
        self.logger.info(colorer("        __   _ __      _  __  ", color="bright"))
        self.logger.info(colorer("       / /  (_) /____ | |/_/  ", color="bright"))
        self.logger.info(colorer("      / /__/ / __/ -_)>  <    ", color="bright"))
        self.logger.info(colorer("     /____/_/\\__/\\__/_/|_|  ", color="bright"))
        self.logger.info(colorer("  Build your hardware, easily!", color="bright"))

        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(colorer("Creating SoC... ({})".format(build_time())))
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info("FPGA device : {}.".format(platform.device))
        self.logger.info("System clock: {:3.2f}MHz.".format(sys_clk_freq/1e6))

        # SoC attributes ---------------------------------------------------------------------------
        self.platform     = platform
        self.sys_clk_freq = sys_clk_freq
        self.constants    = {}
        self.csr_regions  = {}

        # SoC Bus Handler --------------------------------------------------------------------------
        self.submodules.bus = SoCBusHandler(
            standard         = bus_standard,
            data_width       = bus_data_width,
            address_width    = bus_address_width,
            timeout          = bus_timeout,
            reserved_regions = bus_reserved_regions,
           )

        # SoC Bus Handler --------------------------------------------------------------------------
        self.submodules.csr = SoCCSRHandler(
            data_width    = csr_data_width,
            address_width = csr_address_width,
            alignment     = csr_alignment,
            paging        = csr_paging,
            reserved_csrs = csr_reserved_csrs,
        )

        # SoC IRQ Handler --------------------------------------------------------------------------
        self.submodules.irq = SoCIRQHandler(
            n_irqs        = irq_n_irqs,
            reserved_irqs = irq_reserved_irqs
        )

        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(colorer("Initial SoC:"))
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(self.bus)
        self.logger.info(self.csr)
        self.logger.info(self.irq)
        self.logger.info(colorer("-"*80, color="bright"))

        self.add_config("CLOCK_FREQUENCY", int(sys_clk_freq))

    # SoC Helpers ----------------------------------------------------------------------------------
    def check_if_exists(self, name):
        if hasattr(self, name):
            self.logger.error("{} SubModule already {}.".format(
                colorer(name),
                colorer("declared", color="red")))
            raise

    def add_constant(self, name, value=None):
        name = name.upper()
        if name in self.constants.keys():
            self.logger.error("{} Constant already {}.".format(
                colorer(name),
                colorer("declared", color="red")))
            raise
        self.constants[name] = SoCConstant(value)

    def add_config(self, name, value=None):
        name = "CONFIG_" + name
        if isinstance(value, str):
            self.add_constant(name + "_" + value)
        else:
            self.add_constant(name, value)

    # SoC Main Components --------------------------------------------------------------------------
    def add_controller(self, name="ctrl", **kwargs):
        self.check_if_exists(name)
        setattr(self.submodules, name, SoCController(**kwargs))
        self.csr.add(name, use_loc_if_exists=True)

    def add_ram(self, name, origin, size, contents=[], mode="rw"):
        ram_bus = wishbone.Interface(data_width=self.bus.data_width)
        ram     = wishbone.SRAM(size, bus=ram_bus, init=contents, read_only=(mode == "r"))
        self.bus.add_slave(name, ram.bus, SoCRegion(origin=origin, size=size, mode=mode))
        self.check_if_exists(name)
        self.logger.info("RAM {} {} {}.".format(
            colorer(name),
            colorer("added", color="green"),
            self.bus.regions[name]))
        setattr(self.submodules, name, ram)

    def add_rom(self, name, origin, size, contents=[]):
        self.add_ram(name, origin, size, contents, mode="r")

    def add_csr_bridge(self, origin):
        self.submodules.csr_bridge = wishbone2csr.WB2CSR(
            bus_csr       = csr_bus.Interface(
                address_width = self.csr.address_width,
                data_width    = self.csr.data_width))
        csr_size   = 2**(self.csr.address_width + 2)
        csr_region = SoCRegion(origin=origin, size=csr_size, cached=False)
        self.bus.add_slave("csr", self.csr_bridge.wishbone, csr_region)
        self.csr.add_master(name="bridge", master=self.csr_bridge.csr)
        self.add_config("CSR_DATA_WIDTH", self.csr.data_width)
        self.add_config("CSR_ALIGNMENT",  self.csr.alignment)

    def add_cpu(self, name="vexriscv", variant="standard", cls=None, reset_address=None):
        if name not in cpu.CPUS.keys():
            self.logger.error("{} CPU {}, supporteds: {}.".format(
                colorer(name),
                colorer("not supported", color="red"),
                colorer(", ".join(cpu.CPUS.keys()))))
            raise
        # Add CPU
        cpu_cls = cls if cls is not None else cpu.CPUS[name]
        if variant not in cpu_cls.variants:
            self.logger.error("{} CPU variant {}, supporteds: {}.".format(
                colorer(variant),
                colorer("not supported", color="red"),
                colorer(", ".join(cpu_cls.variants))))
            raise
        self.submodules.cpu = cpu_cls(self.platform, variant)
        # Update SoC with CPU constraints
        for n, (origin, size) in enumerate(self.cpu.io_regions.items()):
            self.bus.add_region("io{}".format(n), SoCIORegion(origin=origin, size=size, cached=False))
        self.mem_map.update(self.cpu.mem_map) # FIXME
        # Add Bus Masters/CSR/IRQs
        if not isinstance(self.cpu, cpu.CPUNone):
            self.csr.update_alignment(self.cpu.data_width)
            if reset_address is None:
                reset_address = self.mem_map["rom"]
            self.cpu.set_reset_address(reset_address)
            for n, cpu_bus in enumerate(self.cpu.periph_buses):
                self.bus.add_master(name="cpu_bus{}".format(n), master=cpu_bus)
            self.csr.add("cpu", use_loc_if_exists=True)
            if hasattr(self.cpu, "interrupt"):
                for name, loc in self.cpu.interrupts.items():
                    self.irq.add(name, loc)
                self.add_config("CPU_HAS_INTERRUPT")


            if hasattr(self, "ctrl"):
                if hasattr(self.ctrl, "reset"):
                    self.comb += self.cpu.reset.eq(self.ctrl.reset)
            self.add_config("CPU_RESET_ADDR", reset_address)
        # Add constants
        self.add_config("CPU_TYPE",    str(name))
        self.add_config("CPU_VARIANT", str(variant.split('+')[0]))
        self.add_constant("CONFIG_CPU_HUMAN_NAME", getattr(self.cpu, "human_name", "Unknown"))
        if hasattr(self.cpu, "nop"):
            self.add_constant("CONFIG_CPU_NOP", self.cpu.nop)

    def add_timer(self, name="timer0"):
        self.check_if_exists(name)
        setattr(self.submodules, name, Timer())
        self.csr.add(name, use_loc_if_exists=True)
        if hasattr(self.cpu, "interrupt"):
            self.irq.add(name, use_loc_if_exists=True)

    # SoC finalization -----------------------------------------------------------------------------
    def do_finalize(self):
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(colorer("Finalized SoC:"))
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(self.bus)
        self.logger.info(self.csr)
        self.logger.info(self.irq)
        self.logger.info(colorer("-"*80, color="bright"))

        # SoC Bus Interconnect ---------------------------------------------------------------------
        if len(self.bus.masters) and len(self.bus.slaves):
            # If 1 bus_master, 1 bus_slave and no address translation, use InterconnectPointToPoint.
            if ((len(self.bus.masters) == 1)  and
                (len(self.bus.slaves)  == 1)  and
                (next(iter(self.bus.regions.values())).origin == 0)):
                self.submodules.bus_interconnect = wishbone.InterconnectPointToPoint(
                    master = next(iter(self.bus.masters.values())),
                    slave  = next(iter(self.bus.slaves.values())))
            # Otherwise, use InterconnectShared.
            else:
                self.submodules.bus_interconnect = wishbone.InterconnectShared(
                    masters        = self.bus.masters.values(),
                    slaves         = [(self.bus.regions[n].decoder(self.bus), s) for n, s in self.bus.slaves.items()],
                    register       = True,
                    timeout_cycles = self.bus.timeout)
                if hasattr(self, "ctrl") and self.bus.timeout is not None:
                    if hasattr(self.ctrl, "bus_error"):
                        self.comb += self.ctrl.bus_error.eq(self.bus_interconnect.timeout.error)
            self.bus.logger.info("Interconnect: {} ({} <-> {}).".format(
                colorer(self.bus_interconnect.__class__.__name__),
                colorer(len(self.bus.masters)),
                colorer(len(self.bus.slaves))))

        # SoC CSR Interconnect ---------------------------------------------------------------------
        self.submodules.csr_bankarray = csr_bus.CSRBankArray(self,
            address_map        = self.csr.address_map,
            data_width         = self.csr.data_width,
            address_width      = self.csr.address_width,
            alignment          = self.csr.alignment,
            paging             = self.csr.paging,
            soc_bus_data_width = self.bus.data_width)
        if len(self.csr.masters):
            self.submodules.csr_interconnect = csr_bus.InterconnectShared(
                masters = list(self.csr.masters.values()),
                slaves  = self.csr_bankarray.get_buses())

        # Add CSRs regions
        for name, csrs, mapaddr, rmap in self.csr_bankarray.banks:
            self.csr.add_region(name, SoCCSRRegion(
                origin   = (self.bus.regions["csr"].origin + self.csr.paging*mapaddr),
                busword  = self.csr.data_width,
                obj      = csrs))

        # Add Memory regions
        for name, memory, mapaddr, mmap in self.csr_bankarray.srams:
            self.csr.add_region(name + "_" + memory.name_override, SoCCSRRegion(
                origin  = (self.bus.regions["csr"].origin + self.csr.paging*mapaddr),
                busword = self.csr.data_width,
                obj     = memory))

        # Sort CSR regions by origin
        self.csr.regions = {k: v for k, v in sorted(self.csr.regions.items(), key=lambda item: item[1].origin)}

        # Add CSRs / Config items to constants
        for name, constant in self.csr_bankarray.constants:
            self.add_constant(name + "_" + constant.name, constant.value.value)

        # SoC CPU Check ----------------------------------------------------------------------------
        if not isinstance(self.cpu, cpu.CPUNone):
            if "sram" not in self.bus.regions.keys():
                self.logger.error("CPU needs {} Region to be {} as Bus or Linker Region.".format(
                    colorer("sram"),
                    colorer("defined", color="red")))
                self.logger.error(self.bus)
                raise
            cpu_reset_address_valid = False
            for name, container in self.bus.regions.items():
                if self.bus.check_region_is_in(
                    region    = SoCRegion(origin=self.cpu.reset_address, size=self.bus.data_width//8),
                    container = container):
                    cpu_reset_address_valid = True
                    if name == "rom":
                        self.cpu.use_rom = True
            if not cpu_reset_address_valid:
                self.logger.error("CPU needs {} to be in a {} Region.".format(
                    colorer("reset address 0x{:08x}".format(self.cpu.reset_address)),
                    colorer("defined", color="red")))
                self.logger.error(self.bus)
                raise

        # SoC IRQ Interconnect ---------------------------------------------------------------------
        if hasattr(self, "cpu"):
            if hasattr(self.cpu, "interrupt"):
                for name, loc in sorted(self.irq.locs.items()):
                    if name in self.cpu.interrupts.keys():
                        continue
                    if hasattr(self, name):
                        module = getattr(self, name)
                        if not hasattr(module, "ev"):
                            self.logger.error("EventManager {} in {} SubModule.".format(
                                colorer("not found", color="red"),
                                colorer(name)))
                            raise
                        self.comb += self.cpu.interrupt[loc].eq(module.ev.irq)
                    self.add_constant(name + "_INTERRUPT", loc)

    # SoC build ------------------------------------------------------------------------------------
    def build(self, *args, **kwargs):
        self.build_name = kwargs.pop("build_name", self.platform.name)
        kwargs.update({"build_name": self.build_name})
        return self.platform.build(self, *args, **kwargs)

# LiteXSoC -----------------------------------------------------------------------------------------

class LiteXSoC(SoC):
    # Add Identifier -------------------------------------------------------------------------------
    def add_identifier(self, name="identifier", identifier="LiteX SoC", with_build_time=True):
        self.check_if_exists(name)
        if with_build_time:
            identifier += " " + build_time()
        setattr(self.submodules, name, Identifier(identifier))
        self.csr.add(name + "_mem", use_loc_if_exists=True)

    # Add UART -------------------------------------------------------------------------------------
    def add_uart(self, name, baudrate=115200, fifo_depth=16):
        from litex.soc.cores import uart

        # Stub / Stream
        if name in ["stub", "stream"]:
            self.submodules.uart = uart.UART(tx_fifo_depth=0, rx_fifo_depth=0)
            if name == "stub":
                self.comb += self.uart.sink.ready.eq(1)

        # UARTBone / Bridge
        elif name in ["uartbone", "bridge"]:
            self.add_uartbone(baudrate=baudrate)

        # Crossover
        elif name in ["crossover"]:
            self.submodules.uart = uart.UARTCrossover()

        # Model/Sim
        elif name in ["model", "sim"]:
            self.submodules.uart_phy = uart.RS232PHYModel(self.platform.request("serial"))
            self.submodules.uart = ResetInserter()(uart.UART(self.uart_phy,
                tx_fifo_depth = fifo_depth,
                rx_fifo_depth = fifo_depth))

        # JTAG Atlantic
        elif name in ["jtag_atlantic"]:
            from litex.soc.cores.jtag import JTAGAtlantic
            self.submodules.uart_phy = JTAGAtlantic()
            self.submodules.uart = ResetInserter()(uart.UART(self.uart_phy,
                tx_fifo_depth = fifo_depth,
                rx_fifo_depth = fifo_depth))

        # JTAG UART
        elif name in ["jtag_uart"]:
            from litex.soc.cores.jtag import JTAGPHY
            self.submodules.uart_phy = JTAGPHY(device=self.platform.device)
            self.submodules.uart = ResetInserter()(uart.UART(self.uart_phy,
                tx_fifo_depth = fifo_depth,
                rx_fifo_depth = fifo_depth))

        # USB ACM (with ValentyUSB core)
        elif name in ["usb_acm"]:
            import valentyusb.usbcore.io as usbio
            import valentyusb.usbcore.cpu.cdc_eptri as cdc_eptri
            usb_pads = self.platform.request("usb")
            usb_iobuf = usbio.IoBuf(usb_pads.d_p, usb_pads.d_n, usb_pads.pullup)
            self.submodules.uart = cdc_eptri.CDCUsb(usb_iobuf)

        # Classic UART
        else:
            self.submodules.uart_phy = uart.UARTPHY(
                pads     = self.platform.request(name),
                clk_freq = self.sys_clk_freq,
                baudrate = baudrate)
            self.submodules.uart = ResetInserter()(uart.UART(self.uart_phy,
                tx_fifo_depth = fifo_depth,
                rx_fifo_depth = fifo_depth))

        self.csr.add("uart_phy", use_loc_if_exists=True)
        self.csr.add("uart", use_loc_if_exists=True)
        if hasattr(self.cpu, "interrupt"):
            self.irq.add("uart", use_loc_if_exists=True)
        else:
            self.add_constant("UART_POLLING")

    # Add UARTbone ---------------------------------------------------------------------------------
    def add_uartbone(self, name="serial", baudrate=115200):
        from litex.soc.cores import uart
        self.submodules.uartbone = uart.UARTBone(
            pads     = self.platform.request(name),
            clk_freq = self.sys_clk_freq,
            baudrate = baudrate)
        self.bus.add_master(name="uartbone", master=self.uartbone.wishbone)

    # Add SDRAM ------------------------------------------------------------------------------------
    def add_sdram(self, name, phy, module, origin, size=None, with_soc_interconnect=True,
        l2_cache_size           = 8192,
        l2_cache_min_data_width = 128,
        l2_cache_reverse        = True,
        l2_cache_full_memory_we = True,
        **kwargs):

        # Imports
        from litedram.common import LiteDRAMNativePort
        from litedram.core import LiteDRAMCore
        from litedram.frontend.wishbone import LiteDRAMWishbone2Native
        from litedram.frontend.axi import LiteDRAMAXI2Native

        # LiteDRAM core
        self.submodules.sdram = LiteDRAMCore(
            phy             = phy,
            geom_settings   = module.geom_settings,
            timing_settings = module.timing_settings,
            clk_freq        = self.sys_clk_freq,
            **kwargs)
        self.csr.add("sdram")

        if not with_soc_interconnect: return

        # Compute/Check SDRAM size
        sdram_size = 2**(module.geom_settings.bankbits +
                         module.geom_settings.rowbits +
                         module.geom_settings.colbits)*phy.settings.databits//8
        if size is not None:
            sdram_size = min(sdram_size, size)

        # Add SDRAM region
        self.bus.add_region("main_ram", SoCRegion(origin=origin, size=sdram_size))

        # SoC [<--> L2 Cache] <--> LiteDRAM --------------------------------------------------------
        if len(self.cpu.memory_buses):
            # When CPU has at least a direct memory bus, connect them directly to LiteDRAM.
            for mem_bus in self.cpu.memory_buses:
                # Request a LiteDRAM native port.
                port = self.sdram.crossbar.get_port()
                port.data_width = 2**int(log2(port.data_width)) # Round to nearest power of 2.

                # Check if bus is an AXI bus and connect it.
                if isinstance(mem_bus, axi.AXIInterface):
                    # If same data_width, connect it directly.
                    if port.data_width == mem_bus.data_width:
                        self.logger.info("Matching AXI MEM data width ({})\n".format(port.data_width))
                        self.submodules += LiteDRAMAXI2Native(
                            axi          = self.cpu.mem_axi,
                            port         = port,
                            base_address = self.bus.regions["main_ram"].origin)
                    # If different data_width, do the adaptation and connect it via Wishbone.
                    else:
                        self.logger.info("Converting MEM data width: {} to {} via Wishbone".format(
                            port.data_width,
                            self.cpu.mem_axi.data_width))
                        # FIXME: replace WB data-width converter with native AXI converter!!!
                        mem_wb  = wishbone.Interface(
                            data_width = self.cpu.mem_axi.data_width,
                            adr_width  = 32-log2_int(self.cpu.mem_axi.data_width//8))
                        # NOTE: AXI2Wishbone FSMs must be reset with the CPU!
                        mem_a2w = ResetInserter()(axi.AXI2Wishbone(
                            axi          = self.cpu.mem_axi,
                            wishbone     = mem_wb,
                            base_address = 0))
                        self.comb += mem_a2w.reset.eq(ResetSignal() | self.cpu.reset)
                        self.submodules += mem_a2w
                        litedram_wb = wishbone.Interface(port.data_width)
                        self.submodules += LiteDRAMWishbone2Native(
                            wishbone     = litedram_wb,
                            port         = port,
                            base_address = origin)
                        self.submodules += wishbone.Converter(mem_wb, litedram_wb)
                # Check if bus is a Native bus and connect it.
                if isinstance(mem_bus, LiteDRAMNativePort):
                    # If same data_width, connect it directly.
                    if port.data_width == mem_bus.data_width:
                        self.comb += mem_bus.cmd.connect(port.cmd)
                        self.comb += mem_bus.wdata.connect(port.wdata)
                        self.comb += port.rdata.connect(mem_bus.rdata)
                    # Else raise Error.
                    else:
                        raise NotImplementedError
        else:
            # When CPU has no direct memory interface, create a Wishbone Slave interface to LiteDRAM.

            # Request a LiteDRAM native port.
            port = self.sdram.crossbar.get_port()
            port.data_width = 2**int(log2(port.data_width)) # Round to nearest power of 2.

            # Create Wishbone Slave.
            wb_sdram = wishbone.Interface()
            self.bus.add_slave("main_ram", wb_sdram)

            # L2 Cache
            if l2_cache_size != 0:
                # Insert L2 cache inbetween Wishbone bus and LiteDRAM
                l2_cache_size = max(l2_cache_size, int(2*port.data_width/8)) # Use minimal size if lower
                l2_cache_size = 2**int(log2(l2_cache_size))                  # Round to nearest power of 2
                l2_cache_data_width = max(port.data_width, l2_cache_min_data_width)
                l2_cache            = wishbone.Cache(
                    cachesize = l2_cache_size//4,
                    master    = wb_sdram,
                    slave     = wishbone.Interface(l2_cache_data_width),
                    reverse   = l2_cache_reverse)
                if l2_cache_full_memory_we:
                    l2_cache = FullMemoryWE()(l2_cache)
                self.submodules.l2_cache = l2_cache
                litedram_wb = self.l2_cache.slave
            else:
                litedram_wb     = wishbone.Interface(port.data_width)
                self.submodules += wishbone.Converter(wb_sdram, litedram_wb)
            self.add_config("L2_SIZE", l2_cache_size)

            # Wishbone Slave <--> LiteDRAM bridge
            self.submodules.wishbone_bridge = LiteDRAMWishbone2Native(litedram_wb, port,
                base_address = self.bus.regions["main_ram"].origin)

    # Add Ethernet ---------------------------------------------------------------------------------
    def add_ethernet(self, name="ethmac", phy=None):
        # Imports
        from liteeth.mac import LiteEthMAC
        # MAC
        ethmac = LiteEthMAC(
            phy        = phy,
            dw         = 32,
            interface  = "wishbone",
            endianness = self.cpu.endianness)
        setattr(self.submodules, name, ethmac)
        ethmac_region = SoCRegion(origin=self.mem_map.get(name, None), size=0x2000, cached=False)
        self.bus.add_slave(name=name, slave=ethmac.bus, region=ethmac_region)
        self.add_csr(name)
        self.add_interrupt(name)
        # Timing constraints
        if hasattr(phy, "crg"):
            eth_rx_clk = phy.crg.cd_eth_rx.clk
            eth_tx_clk = phy.crg.cd_eth_tx.clk
        else:
            eth_rx_clk = phy.cd_eth_rx.clk
            eth_tx_clk = phy.cd_eth_tx.clk
        self.platform.add_period_constraint(eth_rx_clk, 1e9/phy.rx_clk_freq)
        self.platform.add_period_constraint(eth_tx_clk, 1e9/phy.tx_clk_freq)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            eth_rx_clk,
            eth_tx_clk)

    # Add Etherbone --------------------------------------------------------------------------------
    def add_etherbone(self, name="etherbone", phy=None, clock_domain=None,
        mac_address = 0x10e2d5000000,
        ip_address  = "192.168.1.50",
        udp_port    = 1234):
        # Imports
        from liteeth.core import LiteEthUDPIPCore
        from liteeth.frontend.etherbone import LiteEthEtherbone
        # Core
        ethcore = LiteEthUDPIPCore(
            phy         = self.ethphy,
            mac_address = mac_address,
            ip_address  = ip_address,
            clk_freq    = self.clk_freq)
        if clock_domain is not None: # FIXME: Could probably be avoided.
            ethcore = ClockDomainsRenamer("eth_tx")(ethcore)
        self.submodules += ethcore

        # Clock domain renaming
        if clock_domain is not None: # FIXME: Could probably be avoided.
            self.clock_domains.cd_etherbone = ClockDomain("etherbone")
            self.comb += self.cd_etherbone.clk.eq(ClockSignal(clock_domain))
            self.comb += self.cd_etherbone.rst.eq(ResetSignal(clock_domain))
            clock_domain = "etherbone"
        else:
            clock_domain = "sys"

        # Etherbone
        etherbone = LiteEthEtherbone(ethcore.udp, udp_port, cd=clock_domain)
        setattr(self.submodules, name, etherbone)
        self.add_wb_master(etherbone.wishbone.bus)
        # Timing constraints
        if hasattr(phy, "crg"):
            eth_rx_clk = phy.crg.cd_eth_rx.clk
            eth_tx_clk = phy.crg.cd_eth_tx.clk
        else:
            eth_rx_clk = phy.cd_eth_rx.clk
            eth_tx_clk = phy.cd_eth_tx.clk
        self.platform.add_period_constraint(eth_rx_clk, 1e9/phy.rx_clk_freq)
        self.platform.add_period_constraint(eth_tx_clk, 1e9/phy.tx_clk_freq)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            eth_rx_clk,
            eth_tx_clk)

    # Add SPI Flash --------------------------------------------------------------------------------
    def add_spi_flash(self, name="spiflash", mode="4x", dummy_cycles=None, clk_freq=None):
        assert dummy_cycles is not None                 # FIXME: Get dummy_cycles from SPI Flash
        assert mode in ["1x", "4x"]
        if clk_freq is None: clk_freq = self.clk_freq/2 # FIXME: Get max clk_freq from SPI Flash
        spiflash = SpiFlash(
            pads         = self.platform.request(name if mode == "1x" else name + mode),
            dummy        = dummy_cycles,
            div          = ceil(self.clk_freq/clk_freq),
            with_bitbang = True,
            endianness   = self.cpu.endianness)
        spiflash.add_clk_primitive(self.platform.device)
        setattr(self.submodules, name, spiflash)
        self.add_memory_region(name, self.mem_map[name], 0x1000000) # FIXME: Get size from SPI Flash
        self.add_wb_slave(self.mem_map[name], spiflash.bus)
        self.add_csr(name)

    # Add SPI SDCard -------------------------------------------------------------------------------
    def add_spi_sdcard(self, name="spisdcard", clk_freq=400e3):
        pads = self.platform.request(name)
        if hasattr(pads, "rst"):
            self.comb += pads.rst.eq(0)
        spisdcard = SPIMaster(pads, 8, self.sys_clk_freq, 400e3)
        spisdcard.add_clk_divider()
        setattr(self.submodules, name, spisdcard)
        self.add_csr(name)
