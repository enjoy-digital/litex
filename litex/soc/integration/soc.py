#!/usr/bin/env python3

# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import logging
import time
import datetime

from migen import *

from litex.soc.cores.identifier import Identifier
from litex.soc.cores.timer import Timer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import csr_bus
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import wishbone2csr

# TODO:
# - replace raise with exit on logging error.
# - add configurable CSR paging.
# - manage IO/Linker regions.

logging.basicConfig(level=logging.INFO)

# Helpers ------------------------------------------------------------------------------------------
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
    return datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

# SoCConstant --------------------------------------------------------------------------------------

def SoCConstant(value):
    return value

# SoCRegion ----------------------------------------------------------------------------------------

class SoCRegion:
    def __init__(self, origin=None, size=None, mode="rw", cached=True):
        self.logger    = logging.getLogger("SoCRegion")
        self.origin    = origin
        self.size      = size
        self.mode      = mode
        self.cached    = cached

    def decoder(self):
        origin = self.origin
        size   = self.size
        origin &= ~0x80000000
        size   = 2**log2_int(size, False)
        if (origin & (size - 1)) != 0:
            self.logger.error("Origin needs to be aligned on size:")
            self.logger.error(self)
            raise
        origin >>= 2 # bytes to words aligned
        size   >>= 2 # bytes to words aligned
        return lambda a: (a[log2_int(size):-1] == (origin >> log2_int(size)))

    def __str__(self):
        r = ""
        if self.origin is not None:
            r += "Origin: {}, ".format(colorer("0x{:08x}".format(self.origin)))
        if self.size is not None:
            r += "Size: {}, ".format(colorer("0x{:08x}".format(self.size)))
        r += "Mode: {}, ".format(colorer(self.mode.upper()))
        r += "Cached: {}".format(colorer(self.cached))
        return r


class SoCLinkerRegion(SoCRegion):
    pass

# SoCBusHandler ------------------------------------------------------------------------------------

class SoCBusHandler(Module):
    supported_standard      = ["wishbone"]
    supported_data_width    = [32, 64]
    supported_address_width = [32]

    # Creation -------------------------------------------------------------------------------------
    def __init__(self, standard, data_width=32, address_width=32, timeout=1e6, reserved_regions={}):
        self.logger = logging.getLogger("SoCBusHandler")
        self.logger.info(colorer("Creating new Bus Handler...", color="cyan"))

        # Check Standard
        if standard not in self.supported_standard:
            self.logger.error("Unsupported Standard: {} supporteds: {:s}".format(
                colorer(standard, color="red"),
                colorer(", ".join(self.supported_standard), color="green")))
            raise

        # Check Data Width
        if data_width not in self.supported_data_width:
            self.logger.error("Unsupported Data_Width: {} supporteds: {:s}".format(
                colorer(data_width, color="red"),
                colorer(", ".join(str(x) for x in self.supported_data_width), color="green")))
            raise

        # Check Address Width
        if address_width not in self.supported_address_width:
            self.logger.error("Unsupported Address Width: {} supporteds: {:s}".format(
                colorer(data_width, color="red"),
                colorer(", ".join(str(x) for x in self.supported_address_width), color="green")))
            raise

        # Create Bus
        self.standard      = standard
        self.data_width    = data_width
        self.address_width = address_width
        self.masters       = {}
        self.slaves        = {}
        self.regions       = {}
        self.timeout       = timeout
        self.logger.info("{}-bit {} Bus, {}GiB Address Space.".format(
            colorer(data_width), colorer(standard), colorer(2**address_width/2**30)))

        # Adding reserved regions
        self.logger.info("Adding {} Regions...".format(colorer("reserved")))
        for name, region in reserved_regions.items():
            if isinstance(region, int):
                region = SoCRegion(origin=region, size=0x1000000)
            self.add_region(name, region)

        self.logger.info(colorer("Bus Handler created.", color="cyan"))

    # Add/Allog/Check Regions ----------------------------------------------------------------------
    def add_region(self, name, region):
        allocated = False
        # Check if SoCLinkerRegion
        if isinstance(region, SoCLinkerRegion):
            self.logger.info("FIXME: SoCLinkerRegion")
        # Check if SoCRegion
        elif isinstance(region, SoCRegion):
            # If no origin specified, allocate region.
            if region.origin is None:
                allocated = True
                region    = self.alloc_region(region.size, region.cached)
                self.regions[name] = region
            # Else add region and check for overlaps.
            else:
                self.regions[name] = region
                overlap = self.check_region(self.regions)
                if overlap is not None:
                    self.logger.error("Region overlap between {} and {}:".format(
                        colorer(overlap[0], color="red"),
                        colorer(overlap[1], color="red")))
                    self.logger.error(str(self.regions[overlap[0]]))
                    self.logger.error(str(self.regions[overlap[1]]))
                    raise
            self.logger.info("{} Region {} {}.".format(
                colorer(name, color="underline"),
                colorer("allocated" if allocated else "added", color="yellow" if allocated else "green"),
                str(region)))
        else:
            self.logger.error("{} is not a supported Region".format(colorer(name, color="red")))
            raise

    def alloc_region(self, size, cached=True):
        self.logger.info("Allocating {} Region of size {}...".format(
            colorer("Cached" if cached else "IO"),
            colorer("0x{:08x}".format(size))))

        # Limit Search Regions
        uncached_regions = {}
        for _, region in self.regions.items():
            if region.cached == False:
                uncached_regions[name] = region
        if cached == False:
            search_regions = uncached_regions
        else:
            search_regions = {"main": SoCRegion(origin=0x00000000, size=2**self.address_width-1)}

        # Iterate on Search_Regions to find a Candidate
        for _, search_region in search_regions.items():
            origin = search_region.origin
            while (origin + size) < (search_region.origin + search_region.size):
                # Create a Candicate.
                candidate = SoCRegion(origin=origin, size=size, cached=cached)
                overlap   = False
                # Check Candidate does not overlap with allocated existing regions
                for _, allocated in self.regions.items():
                    if self.check_region({"0": allocated, "1": candidate}) is not None:
                        origin  = allocated.origin + allocated.size
                        overlap = True
                        break
                if not overlap:
                    # If no overlap, the Candidate is selected
                    return candidate

        self.logger.error("Not enough Address Space to allocate Region")
        raise

    def check_region(self, regions):
        i = 0
        while i < len(regions):
            n0 =  list(regions.keys())[i]
            r0 = regions[n0]
            for n1 in list(regions.keys())[i+1:]:
                r1 = regions[n1]
                if isinstance(r0, SoCLinkerRegion) or isinstance(r1, SoCLinkerRegion):
                    continue
                if r0.origin >= (r1.origin + r1.size):
                    continue
                if r1.origin >= (r0.origin + r0.size):
                    continue
                return (n0, n1)
            i += 1
        return None

    # Add Master/Slave -----------------------------------------------------------------------------
    def add_master(self, name=None, master=None, io_regions={}):
        if name is None:
            name = "master{:d}".format(len(self.masters))
        if name in self.masters.keys():
            self.logger.error("{} already declared as Bus Master:".format(colorer(name, color="red")))
            self.logger.error(self)
            raise
        if master.data_width != self.data_width:
            self.logger.error("{} Bus Master {} from {}-bit to {}-bit.".format(
                colorer(name),
                colorer("converted", color="yellow"),
                colorer(master.data_width),
                colorer(self.data_width)))
            new_master = wishbone.Interface(data_width=self.data_width)
            self.submodules += wishbone.Converter(master, new_master)
            master = new_master
        self.masters[name] = master
        self.logger.info("{} {} as Bus Master.".format(colorer(name, color="underline"), colorer("added", color="green")))
        # FIXME: handle IO regions

    def add_slave(self, name=None, slave=None, region=None):
        no_name   = name is None
        no_region = region is None
        if no_name and no_region:
            self.logger.error("Please specify at least {} or {} of Bus Slave".format(
                colorer("name",   color="red"),
                colorer("region", color="red")))
            raise
        if no_name:
            name = "slave{:d}".format(len(self.slaves))
        if no_region:
            region = self.regions.get(name, None)
            if region is None:
                self.logger.error("Unable to find Region {}".format(colorer(name, color="red")))
                raise
        else:
             self.add_region(name, region)
        if name in self.slaves.keys():
            self.logger.error("{} already declared as Bus Slave:".format(colorer(name, color="red")))
            self.logger.error(self)
            raise
        if slave.data_width != self.data_width:
            self.logger.error("{} Bus Slave {} from {}-bit to {}-bit.".format(
                colorer(name),
                colorer("converted", color="yellow"),
                colorer(slave.data_width),
                colorer(self.data_width)))
            new_slave = wishbone.Interface(data_width=self.data_width)
            self.submodules += wishbone.Converter(slave, new_slave)
            slave = new_slave
        self.slaves[name] = slave
        self.logger.info("{} {} as Bus Slave.".format(
            colorer(name, color="underline"),
            colorer("added", color="green")))

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r = "{}-bit {} Bus, {}GiB Address Space.\n".format(
            colorer(self.data_width), colorer(self.standard), colorer(2**self.address_width/2**30))
        r += "Bus Regions: ({})\n".format(len(self.regions.keys())) if len(self.regions.keys()) else ""
        for name, region in self.regions.items():
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
                self.logger.error("{} {} name already used.".format(colorer(name, "red"), self.name))
                self.logger.error(self)
                raise
            if n in self.locs.values():
                self.logger.error("{} {} Location already used.".format(colorer(n, "red"), self.name))
                self.logger.error(self)
                raise
            if n is None:
                allocated = True
                n = self.alloc(name)
            else:
                if n < 0:
                    self.logger.error("{} {} Location should be positive.".format(
                        colorer(n, color="red"),
                        self.name))
                    raise
                if n > self.n_locs:
                    self.logger.error("{} {} Location too high (Up to {}).".format(
                        colorer(n, color="red"),
                        self.name,
                        colorer(self.n_csrs, color="green")))
                    raise
            self.locs[name] = n
        else:
            n = self.locs[name]
        self.logger.info("{} {} {} at Location {}.".format(
            colorer(name, color="underline"),
            self.name,
            colorer("allocated" if allocated else "added", color="yellow" if allocated else "green"),
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
        for name in self.locs.keys():
           r += "- {}{}: {}\n".format(colorer(name, color="underline"), " "*(20-len(name)), colorer(self.locs[name]))
        return r

# SoCCSRHandler ------------------------------------------------------------------------------------

class SoCCSRHandler(SoCLocHandler):
    supported_data_width    = [8, 32]
    supported_address_width = [14, 15]
    supported_alignment     = [32, 64]
    supported_paging        = [0x800]

    # Creation -------------------------------------------------------------------------------------
    def __init__(self, data_width=32, address_width=14, alignment=32, paging=0x800, reserved_csrs={}):
        SoCLocHandler.__init__(self, "CSR", n_locs=4*2**address_width//paging) # FIXME
        self.logger = logging.getLogger("SoCCSRHandler")
        self.logger.info(colorer("Creating new CSR Handler...", color="cyan"))

        # Check Data Width
        if data_width not in self.supported_data_width:
            self.logger.error("Unsupported data_width: {} supporteds: {:s}".format(
                colorer(data_width, color="red"),
                colorer(", ".join(str(x) for x in self.supported_data_width)), color="green"))
            raise

        # Check Address Width
        if address_width not in self.supported_address_width:
            self.logger.error("Unsupported address_width: {} supporteds: {:s}".format(
                colorer(address_width, color="red"),
                colorer(", ".join(str(x) for x in self.supported_address_width), color="green")))
            raise

        # Check Alignment
        if alignment not in self.supported_alignment:
            self.logger.error("Unsupported alignment: {} supporteds: {:s}".format(
                colorer(alignment, color="red"),
                colorer(", ".join(str(x) for x in self.supported_alignment), color="green")))
            raise
        if data_width > alignment:
            self.logger.error("Alignment ({}) should be >= data_width ({})".format(
                colorer(alignment,  color="red"),
                colorer(data_width, color="red")))
            raise

        # Check Paging
        if paging not in self.supported_paging:
            self.logger.error("Unsupported paging: {} supporteds: {:s}".format(
                colorer(paging, color="red"),
                colorer(", ".join(str(x) for x in self.supported_paging), color="green")))
            raise

        # Create CSR Handler
        self.data_width    = data_width
        self.address_width = address_width
        self.alignment     = alignment
        self.paging        = paging
        self.logger.info("{}-bit CSR Bus, {}KiB Address Space, {}B Paging (Up to {} Locations).\n".format(
            colorer(self.data_width),
            colorer(2**self.address_width/2**10),
            colorer(self.paging),
            colorer(self.n_locs)))

        # Adding reserved CSRs
        self.logger.info("Adding {} CSRs...".format(colorer("reserved")))
        for name, n in reserved_csrs.items():
            self.add(name, n)

        self.logger.info(colorer("CSR Bus Handler created.", color="cyan"))

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r = "{}-bit CSR Bus, {}KiB Address Space, {}B Paging (Up to {} Locations).\n".format(
            colorer(self.data_width),
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
        self.logger.info(colorer("Creating new SoC IRQ Handler...", color="cyan"))

        # Check IRQ Number
        if n_irqs > 32:
            self.logger.error("Unsupported IRQs number: {} supporteds: {:s}".format(
                colorer(n, color="red"), colorer("Up to 32", color="green")))
            raise

        # Create IRQ Handler
        self.logger.info("IRQ Handler (up to {} Locations).".format(colorer(n_irqs)))

        # Adding reserved IRQs
        self.logger.info("Adding {} IRQs...".format(colorer("reserved")))
        for name, n in reserved_irqs.items():
            self.add(name, n)

        self.logger.info(colorer("IRQ Handler created.", color="cyan"))

    # Str ------------------------------------------------------------------------------------------
    def __str__(self):
        r ="IRQ Handler (up to {} Locations).\n".format(colorer(self.n_locs))
        r += SoCLocHandler.__str__(self)
        r = r[:-1]
        return r

# SoCController ------------------------------------------------------------------------------------

class SoCController(Module, AutoCSR):
    def __init__(self):
        self._reset      = CSRStorage(1, description="""
            Write a ``1`` to this register to reset the SoC.""")
        self._scratch    = CSRStorage(32, reset=0x12345678, description="""
            Use this register as a scratch space to verify that software read/write accesses
            to the Wishbone/CSR bus are working correctly. The initial reset value of 0x1234578
            can be used to verify endianness.""")
        self._bus_errors = CSRStatus(32, description="""
            Total number of Wishbone bus errors (timeouts) since last reset.""")

        # # #

        # Reset
        self.reset = Signal()
        self.comb += self.reset.eq(self._reset.re)

        # Bus errors
        self.bus_error = Signal()
        bus_errors     = Signal(32)
        self.sync += \
            If(bus_errors != (2**len(bus_errors)-1),
                If(self.bus_error, bus_errors.eq(bus_errors + 1))
            )
        self.comb += self._bus_errors.status.eq(bus_errors)

# SoC ----------------------------------------------------------------------------------------------

class SoC(Module):
    def __init__(self,
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
        self.logger.info(colorer("Creating new SoC... ({})".format(build_time()), color="cyan"))
        self.logger.info(colorer("-"*80, color="bright"))

        # SoC attributes ---------------------------------------------------------------------------
        self.constants = {}

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
        self.logger.info(colorer("Initial SoC:", color="cyan"))
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(self.bus)
        self.logger.info(self.csr)
        self.logger.info(self.irq)
        self.logger.info(colorer("-"*80, color="bright"))


    # SoC Helpers ----------------------------------------------------------------------------------
    def check_if_exists(self, name):
        if hasattr(self, name):
            self.logger.error("{} SubModule already declared.".format(colorer(name, "red")))
            raise

    def add_constant(self, name, value=None):
        name = name.upper()
        if name in self.constants.keys():
            self.logger.error("{} Constant already declared.".format(colorer(name, "red")))
            raise
        self.constants[name] = SoCConstant(value)

    def add_config(self, name, value):
        name = "CONFIG_" + name
        if isinstance(value, str):
            self.add_constant(name + "_" + value)
        else:
            self.add_constant(name, value)

    # SoC Main components --------------------------------------------------------------------------
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

    def add_controller(self, name="ctrl"):
        self.check_if_exists(name)
        setattr(self.submodules, name, SoCController())
        self.csr.add(name, use_loc_if_exists=True)

    def add_identifier(self, name="identifier", identifier="LiteX SoC", with_build_time=True):
        self.check_if_exists(name)
        if with_build_time:
            identifier += " " + build_time()
        setattr(self.submodules, name, Identifier(ident))
        self.csr.add(name + "_mem", use_loc_if_exists=True)

    def add_timer(self, name="timer0"):
        self.check_if_exists(name)
        setattr(self.submodules, name, Timer())
        self.csr.add(name, use_loc_if_exists=True)
        self.irq.add(name, use_loc_if_exists=True)

    def add_csr_bridge(self, origin):
        self.submodules.csr_bridge = wishbone2csr.WB2CSR(
            bus_csr       = csr_bus.Interface(
            address_width = self.csr.address_width,
            data_width    = self.csr.data_width))
        csr_size = 2**(self.csr.address_width + 2)
        self.bus.add_slave("csr", self.csr_bridge.wishbone, SoCRegion(origin=origin, size=csr_size))

    # SoC finalization -----------------------------------------------------------------------------
    def do_finalize(self):
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(colorer("Finalized SoC:", color="cyan"))
        self.logger.info(colorer("-"*80, color="bright"))
        self.logger.info(self.bus)
        self.logger.info(self.csr)
        self.logger.info(self.irq)
        self.logger.info(colorer("-"*80, color="bright"))

        # SoC Bus Interconnect ---------------------------------------------------------------------
        bus_masters = self.bus.masters.values()
        bus_slaves  = [(self.bus.regions[n].decoder(), s) for n, s in self.bus.slaves.items()]
        if len(bus_masters) and len(bus_slaves):
            self.submodules.bus_interconnect = wishbone.InterconnectShared(
                masters        = bus_masters,
                slaves         = bus_slaves,
                register       = True,
                timeout_cycles = self.bus.timeout)

# Test (FIXME: move to litex/text and improve) -----------------------------------------------------

if __name__ == "__main__":
    bus = SoCBusHandler("wishbone", reserved_regions={
        "rom": SoCRegion(origin=0x00000100, size=1024),
        "ram": SoCRegion(size=512),
        }
    )
    bus.add_master("cpu", None)
    bus.add_slave("rom", None, SoCRegion(size=1024))
    bus.add_slave("ram", None, SoCRegion(size=1024))


    csr = SoCCSRHandler(reserved_csrs={"ctrl": 0, "uart": 1})
    csr.add("csr0")
    csr.add("csr1", 0)
    #csr.add("csr2", 46)
    csr.add("csr3", -1)
    print(bus)
    print(csr)

    irq = SoCIRQHandler(reserved_irqs={"uart": 1})

    soc = SoC()
