from misoclib.mem.litesata.common import *
from migen.genlib.cdc import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bank.description import *

from misoclib.soc import SoC

from misoclib.tools.litescope.common import *
from misoclib.tools.litescope.frontend.la import LiteScopeLA
from misoclib.tools.litescope.core.port import LiteScopeTerm

from misoclib.com.uart.bridge import UARTWishboneBridge

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.phy import LiteSATAPHY
from misoclib.mem.litesata.core import LiteSATACore
from misoclib.mem.litesata.frontend.crossbar import LiteSATACrossbar
from misoclib.mem.litesata.frontend.mirroring import LiteSATAMirroring
from misoclib.mem.litesata.frontend.bist import LiteSATABIST

from misoclib.mem.litesata.example_designs.targets.bist import CRG, StatusLeds


class MirroringSoC(SoC, AutoCSR):
    default_platform = "kc705"
    csr_map = {
        "sata_bist0": 16,
        "sata_bist1": 17,
        "sata_bist2": 18,
        "sata_bist3": 19,
    }
    csr_map.update(SoC.csr_map)
    def __init__(self, platform):
        clk_freq = 200*1000000
        SoC.__init__(self, platform, clk_freq,
            cpu_type="none",
            with_csr=True, csr_data_width=32,
            with_uart=False,
            with_identifier=True,
            with_timer=False
        )
        self.add_cpu_or_bridge(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)
        self.submodules.crg = CRG(platform)

        # SATA PHYs
        sata_phy0 = LiteSATAPHY(platform.device, platform.request("sata_clocks"), platform.request("sata", 0), "sata_gen3", clk_freq)
        sata_phy1 = LiteSATAPHY(platform.device, sata_phy0.crg.refclk, platform.request("sata", 1), "sata_gen3", clk_freq)
        sata_phy2 = LiteSATAPHY(platform.device, sata_phy0.crg.refclk, platform.request("sata", 2), "sata_gen3", clk_freq)
        sata_phy3 = LiteSATAPHY(platform.device, sata_phy0.crg.refclk, platform.request("sata", 3), "sata_gen3", clk_freq)
        sata_phys = [sata_phy0, sata_phy1, sata_phy2, sata_phy3]
        for i, sata_phy in enumerate(sata_phys):
            sata_phy = RenameClockDomains(sata_phy, {"sata_rx": "sata_rx{}".format(str(i)),
                                                     "sata_tx": "sata_tx{}".format(str(i))})
            setattr(self.submodules, "sata_phy{}".format(str(i)), sata_phy)

        # SATA Cores
        self.submodules.sata_core0 = LiteSATACore(self.sata_phy0)
        self.submodules.sata_core1 = LiteSATACore(self.sata_phy1)
        self.submodules.sata_core2 = LiteSATACore(self.sata_phy2)
        self.submodules.sata_core3 = LiteSATACore(self.sata_phy3)
        sata_cores = [self.sata_core0, self.sata_core1, self.sata_core2, self.sata_core3]

        # SATA Frontend
        self.submodules.sata_mirroring = LiteSATAMirroring(sata_cores)
        self.submodules.sata_crossbar0 = LiteSATACrossbar(self.sata_mirroring.ports[0])
        self.submodules.sata_crossbar1 = LiteSATACrossbar(self.sata_mirroring.ports[1])
        self.submodules.sata_crossbar2 = LiteSATACrossbar(self.sata_mirroring.ports[2])
        self.submodules.sata_crossbar3 = LiteSATACrossbar(self.sata_mirroring.ports[3])

        # SATA Application
        self.submodules.sata_bist0 = LiteSATABIST(self.sata_crossbar0, with_csr=True)
        self.submodules.sata_bist1 = LiteSATABIST(self.sata_crossbar1, with_csr=True)
        self.submodules.sata_bist2 = LiteSATABIST(self.sata_crossbar2, with_csr=True)
        self.submodules.sata_bist3 = LiteSATABIST(self.sata_crossbar3, with_csr=True)

        # Status Leds
        self.submodules.status_leds = StatusLeds(platform, sata_phys)


        platform.add_platform_command("""
create_clock -name sys_clk -period 5 [get_nets sys_clk]
""")

        for i in range(len(sata_phys)):
            platform.add_platform_command("""
create_clock -name {sata_rx_clk} -period 3.33 [get_nets {sata_rx_clk}]
create_clock -name {sata_tx_clk} -period 3.33 [get_nets {sata_tx_clk}]

set_false_path -from [get_clocks sys_clk] -to [get_clocks {sata_rx_clk}]
set_false_path -from [get_clocks sys_clk] -to [get_clocks {sata_tx_clk}]
set_false_path -from [get_clocks {sata_rx_clk}] -to [get_clocks sys_clk]
set_false_path -from [get_clocks {sata_tx_clk}] -to [get_clocks sys_clk]
""".format(sata_rx_clk="sata_rx{}_clk".format(str(i)),
           sata_tx_clk="sata_tx{}_clk".format(str(i))))


default_subtarget = MirroringSoC