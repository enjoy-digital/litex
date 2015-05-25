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
from misoclib.mem.litesata.frontend.bist import LiteSATABIST


class CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()

        clk200 = platform.request("clk200")
        clk200_se = Signal()
        self.specials += Instance("IBUFDS", i_I=clk200.p, i_IB=clk200.n, o_O=clk200_se)

        pll_locked = Signal()
        pll_fb = Signal()
        pll_sys = Signal()
        self.specials += [
            Instance("PLLE2_BASE",
                p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                # VCO @ 1GHz
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=5.0,
                p_CLKFBOUT_MULT=5, p_DIVCLK_DIVIDE=1,
                i_CLKIN1=clk200_se, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

                # 166MHz
                p_CLKOUT0_DIVIDE=6, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

                p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, #o_CLKOUT1=,

                p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.0, #o_CLKOUT2=,

                p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

                p_CLKOUT4_DIVIDE=2, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
            ),
            Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll_locked | platform.request("cpu_reset")),
        ]


class StatusLeds(Module):
    def __init__(self, platform, sata_phys):
        for i, sata_phy in enumerate(sata_phys):
            # 1Hz blinking leds (sata_rx and sata_tx clocks)
            rx_led = platform.request("user_led", 2*i)

            rx_cnt = Signal(32)

            freq = int(frequencies[sata_phy.revision]*1000*1000)

            self.sync.sata_rx += \
                If(rx_cnt == 0,
                    rx_led.eq(~rx_led),
                    rx_cnt.eq(freq//2)
                ).Else(
                    rx_cnt.eq(rx_cnt-1)
                )

            # ready leds
            self.comb += platform.request("user_led", 2*i+1).eq(sata_phy.ctrl.ready)


class BISTSoC(SoC, AutoCSR):
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

        # SATA PHY/Core/Frontend
        self.submodules.sata_phy = LiteSATAPHY(platform.device, platform.request("sata_clocks"), platform.request("sata", 0), "sata_gen2", clk_freq)
        self.submodules.sata_core = LiteSATACore(self.sata_phy)
        self.submodules.sata_crossbar = LiteSATACrossbar(self.sata_core)
        self.submodules.sata_bist = LiteSATABIST(self.sata_crossbar, with_csr=True)

        # Status Leds
        self.submodules.leds = BISTLeds(platform, [self.sata_phy])

        platform.add_platform_command("""
create_clock -name sys_clk -period 6 [get_nets sys_clk]

create_clock -name sata_rx_clk -period 6.66 [get_nets sata_rx_clk]
create_clock -name sata_tx_clk -period 6.66 [get_nets sata_tx_clk]

set_false_path -from [get_clocks sys_clk] -to [get_clocks sata_rx_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks sata_tx_clk]
set_false_path -from [get_clocks sata_rx_clk] -to [get_clocks sys_clk]
set_false_path -from [get_clocks sata_tx_clk] -to [get_clocks sys_clk]
""")

class BISTSoCDevel(BISTSoC, AutoCSR):
    csr_map = {
        "la": 17
    }
    csr_map.update(BISTSoC.csr_map)
    def __init__(self, platform):
        BISTSoC.__init__(self, platform)

        self.sata_core_link_rx_fsm_state = Signal(4)
        self.sata_core_link_tx_fsm_state = Signal(4)
        self.sata_core_transport_rx_fsm_state = Signal(4)
        self.sata_core_transport_tx_fsm_state = Signal(4)
        self.sata_core_command_rx_fsm_state = Signal(4)
        self.sata_core_command_tx_fsm_state = Signal(4)

        debug = (
            self.sata_phy.ctrl.ready,

            self.sata_phy.source.stb,
            self.sata_phy.source.data,
            self.sata_phy.source.charisk,

            self.sata_phy.sink.stb,
            self.sata_phy.sink.data,
            self.sata_phy.sink.charisk,

            self.sata.core.command.sink.stb,
            self.sata.core.command.sink.sop,
            self.sata.core.command.sink.eop,
            self.sata.core.command.sink.ack,
            self.sata.core.command.sink.write,
            self.sata.core.command.sink.read,
            self.sata.core.command.sink.identify,

            self.sata.core.command.source.stb,
            self.sata.core.command.source.sop,
            self.sata.core.command.source.eop,
            self.sata.core.command.source.ack,
            self.sata.core.command.source.write,
            self.sata.core.command.source.read,
            self.sata.core.command.source.identify,
            self.sata.core.command.source.failed,
            self.sata.core.command.source.data,

            self.sata_core_link_rx_fsm_state,
            self.sata_core_link_tx_fsm_state,
            self.sata_core_transport_rx_fsm_state,
            self.sata_core_transport_tx_fsm_state,
            self.sata_core_command_rx_fsm_state,
            self.sata_core_command_tx_fsm_state,
        )

        self.submodules.la = LiteScopeLA(debug, 2048)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def do_finalize(self):
        BISTSoC.do_finalize(self)
        self.comb += [
            self.sata_core_link_rx_fsm_state.eq(self.sata.core.link.rx.fsm.state),
            self.sata_core_link_tx_fsm_state.eq(self.sata.core.link.tx.fsm.state),
            self.sata_core_transport_rx_fsm_state.eq(self.sata.core.transport.rx.fsm.state),
            self.sata_core_transport_tx_fsm_state.eq(self.sata.core.transport.tx.fsm.state),
            self.sata_core_command_rx_fsm_state.eq(self.sata.core.command.rx.fsm.state),
            self.sata_core_command_tx_fsm_state.eq(self.sata.core.command.tx.fsm.state)
        ]

    def do_exit(self, vns):
        self.la.export(vns, "test/la.csv")

default_subtarget = BISTSoC
