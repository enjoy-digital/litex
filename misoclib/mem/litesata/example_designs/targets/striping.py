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
from misoclib.mem.litesata.frontend.striping import LiteSATAStriping
from misoclib.mem.litesata.frontend.bist import LiteSATABIST

from misoclib.mem.litesata.example_designs.targets.bist import CRG, StatusLeds


class StripingSoC(SoC, AutoCSR):
    default_platform = "kc705"
    csr_map = {
        "sata_bist": 16
    }
    csr_map.update(SoC.csr_map)
    def __init__(self, platform):
        clk_freq = 166*1000000
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
        sata_phy0 = LiteSATAPHY(platform.device, platform.request("sata_clocks"), platform.request("sata", 0), "sata_gen2", clk_freq)
        sata_phy1 = LiteSATAPHY(platform.device, sata_phy0.crg.refclk, platform.request("sata", 1), "sata_gen2", clk_freq)
        sata_phy2 = LiteSATAPHY(platform.device, sata_phy0.crg.refclk, platform.request("sata", 2), "sata_gen2", clk_freq)
        sata_phy3 = LiteSATAPHY(platform.device, sata_phy0.crg.refclk, platform.request("sata", 3), "sata_gen2", clk_freq)
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
        self.submodules.sata_striping = LiteSATAStriping(sata_cores)
        self.submodules.sata_crossbar = LiteSATACrossbar(self.sata_striping)

        # SATA Application
        self.submodules.sata_bist = LiteSATABIST(self.sata_crossbar, with_csr=True)

        # Status Leds
        self.submodules.status_leds = StatusLeds(platform, sata_phys)


        platform.add_platform_command("""
create_clock -name sys_clk -period 6 [get_nets sys_clk]
""")

        for i in range(len(sata_phys)):
            platform.add_platform_command("""
create_clock -name {sata_rx_clk} -period 6.66 [get_nets {sata_rx_clk}]
create_clock -name {sata_tx_clk} -period 6.66 [get_nets {sata_tx_clk}]

set_false_path -from [get_clocks sys_clk] -to [get_clocks {sata_rx_clk}]
set_false_path -from [get_clocks sys_clk] -to [get_clocks {sata_tx_clk}]
set_false_path -from [get_clocks {sata_rx_clk}] -to [get_clocks sys_clk]
set_false_path -from [get_clocks {sata_tx_clk}] -to [get_clocks sys_clk]
""".format(sata_rx_clk="sata_rx{}_clk".format(str(i)),
           sata_tx_clk="sata_tx{}_clk".format(str(i))))


class StripingSoCDevel(StripingSoC, AutoCSR):
    csr_map = {
        "la": 17
    }
    csr_map.update(StripingSoC.csr_map)
    def __init__(self, platform):
        StripingSoC.__init__(self, platform)

        self.sata_core0_link_tx_fsm_state = Signal(4)
        self.sata_core0_link_rx_fsm_state = Signal(4)

        self.sata_core1_link_tx_fsm_state = Signal(4)
        self.sata_core1_link_rx_fsm_state = Signal(4)

        self.sata_core2_link_tx_fsm_state = Signal(4)
        self.sata_core2_link_rx_fsm_state = Signal(4)

        self.sata_core3_link_tx_fsm_state = Signal(4)
        self.sata_core3_link_rx_fsm_state = Signal(4)

        debug = (
            self.sata_phy0.ctrl.ready,
            self.sata_phy1.ctrl.ready,
            self.sata_phy2.ctrl.ready,
            self.sata_phy3.ctrl.ready,

            self.sata_core0_link_tx_fsm_state,
            self.sata_core0_link_rx_fsm_state,

            self.sata_core0.sink.stb,
            self.sata_core0.source.stb,

            self.sata_phy0.source.stb,
            self.sata_phy0.source.data,
            self.sata_phy0.source.charisk,

            self.sata_phy0.sink.stb,
            self.sata_phy0.sink.data,
            self.sata_phy0.sink.charisk,

            self.sata_core1_link_tx_fsm_state,
            self.sata_core1_link_rx_fsm_state,

            self.sata_core1.sink.stb,
            self.sata_core1.source.stb,

            self.sata_phy1.source.stb,
            self.sata_phy1.source.data,
            self.sata_phy1.source.charisk,

            self.sata_phy1.sink.stb,
            self.sata_phy1.sink.data,
            self.sata_phy1.sink.charisk,

            self.sata_core2_link_tx_fsm_state,
            self.sata_core2_link_rx_fsm_state,

            self.sata_core2.sink.stb,
            self.sata_core2.source.stb,

            self.sata_phy2.source.stb,
            self.sata_phy2.source.data,
            self.sata_phy2.source.charisk,

            self.sata_phy2.sink.stb,
            self.sata_phy2.sink.data,
            self.sata_phy2.sink.charisk,

            self.sata_core3_link_tx_fsm_state,
            self.sata_core3_link_rx_fsm_state,

            self.sata_core3.sink.stb,
            self.sata_core3.source.stb,

            self.sata_phy3.source.stb,
            self.sata_phy3.source.data,
            self.sata_phy3.source.charisk,

            self.sata_phy3.sink.stb,
            self.sata_phy3.sink.data,
            self.sata_phy3.sink.charisk
        )

        self.submodules.la = LiteScopeLA(debug, 2048)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def do_finalize(self):
        StripingSoC.do_finalize(self)
        self.comb += [
            self.sata_core0_link_rx_fsm_state.eq(self.sata_core0.link.rx.fsm.state),
            self.sata_core0_link_tx_fsm_state.eq(self.sata_core0.link.tx.fsm.state),
            self.sata_core1_link_rx_fsm_state.eq(self.sata_core1.link.rx.fsm.state),
            self.sata_core1_link_tx_fsm_state.eq(self.sata_core1.link.tx.fsm.state),
            self.sata_core2_link_rx_fsm_state.eq(self.sata_core2.link.rx.fsm.state),
            self.sata_core2_link_tx_fsm_state.eq(self.sata_core2.link.tx.fsm.state),
            self.sata_core3_link_rx_fsm_state.eq(self.sata_core3.link.rx.fsm.state),
            self.sata_core3_link_tx_fsm_state.eq(self.sata_core3.link.tx.fsm.state),
        ]

    def do_exit(self, vns):
        self.la.export(vns, "test/la.csv")


default_subtarget = StripingSoC