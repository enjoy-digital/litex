####################################################################################################
#       DISCLAIMER: Provides retro-compatibility layer for SoCCore deprecated methods.
#              Will soon no longer work, please don't use in new designs.
####################################################################################################

#
# This file is part of LiteX.
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
# This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
# This file is Copyright (c) 2019 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2020 Raptor Engineering, LLC <sales@raptorengineering.com>
# This file is Copyright (c) 2015 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2018 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Stafford Horne <shorne@gmail.com>
# This file is Copyright (c) 2018-2017 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *


from litex.compat import compat_notice
from litex.soc.integration.soc import *

__all__ = [
    "mem_decoder",
    "SoCCoreCompat",
]

# Helpers ------------------------------------------------------------------------------------------

def mem_decoder(address, size=0x10000000):
    size = 2**log2_int(size, False)
    assert (address & (size - 1)) == 0
    address >>= 2 # bytes to words aligned
    size    >>= 2 # bytes to words aligned
    return lambda a: (a[log2_int(size):] == (address >> log2_int(size)))

# SoCCoreCompat -------------------------------------------------------------------------------------

class SoCCoreCompat:
    # Methods --------------------------------------------------------------------------------------
    def add_interrupt(self, interrupt_name, interrupt_id=None, use_loc_if_exists=False):
        compat_notice("SoCCore.add_interrupt", date="2022-11-03", info="Switch to SoC.irq.add(...)")
        self.irq.add(interrupt_name, interrupt_id, use_loc_if_exists=use_loc_if_exists)

    def add_wb_master(self, wbm):
        compat_notice("SoCCore.add_wb_master", date="2022-11-03", info="Switch to SoC.bus.add_master(...).")
        self.bus.add_master(master=wbm)

    def add_wb_slave(self, address, interface, size=None):
        compat_notice("SoCCore.add_wb_slave", date="2022-11-03", info="Switch to SoC.bus.add_slave(...).")
        wb_name = None
        for name, region in self.bus.regions.items():
            if address == region.origin:
                wb_name = name
                break
        if wb_name is None:
            self.wb_slaves[address] = interface
        else:
            self.bus.add_slave(name=wb_name, slave=interface)

    def register_mem(self, name, address, interface, size=0x10000000):
        compat_notice("SoCCore.register_mem", date="2022-11-03", info="Switch to SoC.bus.add_slave(...)")
        from litex.soc.integration.soc import SoCRegion
        self.bus.add_slave(name, interface, SoCRegion(origin=address, size=size))

    def register_rom(self, interface, rom_size=0xa000):
        compat_notice("SoCCore.register_mem", date="2022-11-03", info="Switch to SoC.bus.add_slave(...)")
        from litex.soc.integration.soc import SoCRegion
        self.bus.add_slave("rom", interface, SoCRegion(origin=self.cpu.reset_address, size=rom_size))

    # Finalization ---------------------------------------------------------------------------------

    def finalize_wb_slaves(self):
        for address, interface in self.wb_slaves.items():
            wb_name = None
            for name, region in self.bus.regions.items():
                if address == region.origin:
                    wb_name = name
                    break
            self.bus.add_slave(name=wb_name, slave=interface)

    def finalize_csr_regions(self):
        for region in self.bus.regions.values():
            region.length = region.size
            region.type   = "cached" if region.cached else "io"
            if region.linker:
                region.type += "+linker"
        self.csr_regions = self.csr.regions
        for name, value in self.config.items():
            self.add_config(name, value)
