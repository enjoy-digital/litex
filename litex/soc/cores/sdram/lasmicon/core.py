from litex.gen import *

from litex.soc.interconnect import dfi, lasmi_bus
from litex.soc.cores.sdram.lasmicon.refresher import *
from litex.soc.cores.sdram.lasmicon.bankmachine import *
from litex.soc.cores.sdram.lasmicon.multiplexer import *


class ControllerSettings:
    def __init__(self, req_queue_size=8, read_time=32, write_time=16, with_bandwidth=False):
        self.req_queue_size = req_queue_size
        self.read_time = read_time
        self.write_time = write_time
        self.with_bandwidth = with_bandwidth


class LASMIcon(Module):
    def __init__(self, phy_settings, geom_settings, timing_settings,
                 controller_settings=None):
        if controller_settings is None:
            controller_settings = ControllerSettings()
        if phy_settings.memtype in ["SDR"]:
            burst_length = phy_settings.nphases*1  # command multiplication*SDR
        elif phy_settings.memtype in ["DDR", "LPDDR", "DDR2", "DDR3"]:
            burst_length = phy_settings.nphases*2  # command multiplication*DDR
        address_align = log2_int(burst_length)

        self.dfi = dfi.Interface(geom_settings.addressbits,
            geom_settings.bankbits,
            phy_settings.dfi_databits,
            phy_settings.nphases)
        self.lasmic = lasmi_bus.Interface(
            aw=geom_settings.rowbits + geom_settings.colbits - address_align,
            dw=phy_settings.dfi_databits*phy_settings.nphases,
            nbanks=2**geom_settings.bankbits,
            req_queue_size=controller_settings.req_queue_size,
            read_latency=phy_settings.read_latency+1,
            write_latency=phy_settings.write_latency+1)
        self.nrowbits = geom_settings.colbits - address_align

        ###

        self.submodules.refresher = Refresher(geom_settings.addressbits, geom_settings.bankbits,
            timing_settings.tRP, timing_settings.tREFI, timing_settings.tRFC)
        self.submodules.bank_machines = [BankMachine(geom_settings, timing_settings, controller_settings, address_align, i,
                getattr(self.lasmic, "bank"+str(i)))
            for i in range(2**geom_settings.bankbits)]
        self.submodules.multiplexer = Multiplexer(phy_settings, geom_settings, timing_settings, controller_settings,
            self.bank_machines, self.refresher,
            self.dfi, self.lasmic)

    def get_csrs(self):
        return self.multiplexer.get_csrs()
