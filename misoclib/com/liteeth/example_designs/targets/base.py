from migen.bus import wishbone
from migen.genlib.io import CRG
from migen.fhdl.specials import Keep
from mibuild.xilinx.vivado import XilinxVivadoToolchain

from misoclib.soc import SoC
from misoclib.tools.litescope.common import *
from misoclib.tools.litescope.frontend.la import LiteScopeLA
from misoclib.tools.litescope.core.port import LiteScopeTerm

from misoclib.com.uart.bridge import UARTWishboneBridge

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.phy import LiteEthPHY
from misoclib.com.liteeth.core import LiteEthUDPIPCore


class BaseSoC(SoC):
    csr_map = {
        "phy":  11,
        "core": 12
    }
    csr_map.update(SoC.csr_map)
    def __init__(self, platform, clk_freq=166*1000000,
            mac_address=0x10e2d5000000,
            ip_address="192.168.0.42"):
        clk_freq = int((1/(platform.default_clk_period))*1000000000)
        SoC.__init__(self, platform, clk_freq,
            cpu_type="none",
            with_csr=True, csr_data_width=32,
            with_uart=False,
            with_identifier=True,
            with_timer=False
        )
        self.add_cpu_or_bridge(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        # wishbone SRAM (to test Wishbone over UART and Etherbone)
        self.submodules.sram = wishbone.SRAM(1024)
        self.add_wb_slave(lambda a: a[23:25] == 1, self.sram.bus)

        # ethernet PHY and UDP/IP stack
        self.submodules.phy = LiteEthPHY(platform.request("eth_clocks"), platform.request("eth"), clk_freq=clk_freq)
        self.submodules.core = LiteEthUDPIPCore(self.phy, mac_address, convert_ip(ip_address), clk_freq)

        if isinstance(platform.toolchain, XilinxVivadoToolchain):
            self.specials += [
                Keep(self.crg.cd_sys.clk),
                Keep(self.phy.crg.cd_eth_rx.clk),
                Keep(self.phy.crg.cd_eth_tx.clk)
            ]
            platform.add_platform_command("""
create_clock -name sys_clk -period 6.0 [get_nets sys_clk]
create_clock -name eth_rx_clk -period 8.0 [get_nets eth_rx_clk]
create_clock -name eth_tx_clk -period 8.0 [get_nets eth_tx_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks eth_rx_clk]
set_false_path -from [get_clocks eth_rx_clk] -to [get_clocks sys_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks eth_tx_clk]
set_false_path -from [get_clocks eth_tx_clk] -to [get_clocks sys_clk]
""")


class BaseSoCDevel(BaseSoC):
    csr_map = {
        "la":            20
    }
    csr_map.update(BaseSoC.csr_map)
    def __init__(self, platform):
        BaseSoC.__init__(self, platform)

        self.core_icmp_rx_fsm_state = Signal(4)
        self.core_icmp_tx_fsm_state = Signal(4)
        self.core_udp_rx_fsm_state = Signal(4)
        self.core_udp_tx_fsm_state = Signal(4)
        self.core_ip_rx_fsm_state = Signal(4)
        self.core_ip_tx_fsm_state = Signal(4)
        self.core_arp_rx_fsm_state = Signal(4)
        self.core_arp_tx_fsm_state = Signal(4)
        self.core_arp_table_fsm_state = Signal(4)

        debug = (
            # MAC interface
            self.core.mac.core.sink.stb,
            self.core.mac.core.sink.sop,
            self.core.mac.core.sink.eop,
            self.core.mac.core.sink.ack,
            self.core.mac.core.sink.data,

            self.core.mac.core.source.stb,
            self.core.mac.core.source.sop,
            self.core.mac.core.source.eop,
            self.core.mac.core.source.ack,
            self.core.mac.core.source.data,

            # ICMP interface
            self.core.icmp.echo.sink.stb,
            self.core.icmp.echo.sink.sop,
            self.core.icmp.echo.sink.eop,
            self.core.icmp.echo.sink.ack,
            self.core.icmp.echo.sink.data,

            self.core.icmp.echo.source.stb,
            self.core.icmp.echo.source.sop,
            self.core.icmp.echo.source.eop,
            self.core.icmp.echo.source.ack,
            self.core.icmp.echo.source.data,

            # IP interface
            self.core.ip.crossbar.master.sink.stb,
            self.core.ip.crossbar.master.sink.sop,
            self.core.ip.crossbar.master.sink.eop,
            self.core.ip.crossbar.master.sink.ack,
            self.core.ip.crossbar.master.sink.data,
            self.core.ip.crossbar.master.sink.ip_address,
            self.core.ip.crossbar.master.sink.protocol,

            # State machines
            self.core_icmp_rx_fsm_state,
            self.core_icmp_tx_fsm_state,

            self.core_arp_rx_fsm_state,
            self.core_arp_tx_fsm_state,
            self.core_arp_table_fsm_state,

            self.core_ip_rx_fsm_state,
            self.core_ip_tx_fsm_state,

            self.core_udp_rx_fsm_state,
            self.core_udp_tx_fsm_state
        )
        self.submodules.la = LiteScopeLA(debug, 4096)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def do_finalize(self):
        BaseSoC.do_finalize(self)
        self.comb += [
            self.core_icmp_rx_fsm_state.eq(self.core.icmp.rx.fsm.state),
            self.core_icmp_tx_fsm_state.eq(self.core.icmp.tx.fsm.state),

            self.core_arp_rx_fsm_state.eq(self.core.arp.rx.fsm.state),
            self.core_arp_tx_fsm_state.eq(self.core.arp.tx.fsm.state),
            self.core_arp_table_fsm_state.eq(self.core.arp.table.fsm.state),

            self.core_ip_rx_fsm_state.eq(self.core.ip.rx.fsm.state),
            self.core_ip_tx_fsm_state.eq(self.core.ip.tx.fsm.state),

            self.core_udp_rx_fsm_state.eq(self.core.udp.rx.fsm.state),
            self.core_udp_tx_fsm_state.eq(self.core.udp.tx.fsm.state)
        ]

    def do_exit(self, vns):
        self.la.export(vns, "test/la.csv")

default_subtarget = BaseSoC
