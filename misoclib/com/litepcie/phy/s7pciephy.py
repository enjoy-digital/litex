import os
from migen.fhdl.std import *
from migen.bank.description import *

from misoclib.com.litepcie.common import *


def get_gt(device):
            if device[:4] == "xc7k":
                return "GTX"
            elif device[:4] == "xc7a":
                return "GTP"
            else:
                raise ValueError("Unsupported device"+device)


class S7PCIEPHY(Module, AutoCSR):
    def __init__(self, platform, dw=64, link_width=2, bar0_size=1*MB):
        pads = platform.request("pcie_x"+str(link_width))
        device = platform.device
        self.dw = dw
        self.link_width = link_width

        self.sink = Sink(phy_layout(dw))
        self.source = Source(phy_layout(dw))
        self.interrupt = Sink(interrupt_layout())

        self.id = Signal(16)

        self.tx_buf_av = Signal(8)
        self.tx_terr_drop = Signal()
        self.tx_cfg_req = Signal()
        self.tx_cfg_gnt = Signal(reset=1)

        self.rx_np_ok = Signal(reset=1)
        self.rx_np_req = Signal(reset=1)

        self.cfg_to_turnoff = Signal()

        self._lnk_up = CSRStatus()
        self._msi_enable = CSRStatus()
        self._bus_master_enable = CSRStatus()
        self._max_request_size = CSRStatus(16)
        self._max_payload_size = CSRStatus(16)
        self.max_request_size = self._max_request_size.status
        self.max_payload_size = self._max_payload_size.status

        self.bar0_size = bar0_size
        self.bar0_mask = get_bar_mask(bar0_size)

        # SHARED clock
        # In case we want to use the second QPLL of the quad
        self.shared_qpll_pd = Signal(reset=1)
        self.shared_qpll_rst = Signal(reset=1)
        self.shared_qpll_refclk = Signal()
        self.shared_qpll_outclk = Signal()
        self.shared_qpll_outrefclk = Signal()
        self.shared_qpll_lock = Signal()

        # # #

        clk100 = Signal()
        self.specials += Instance("IBUFDS_GTE2",
                i_CEB=0,
                i_I=pads.clk_p,
                i_IB=pads.clk_n,
                o_O=clk100,
                o_ODIV2=Signal()
        )

        bus_number = Signal(8)
        device_number = Signal(5)
        function_number = Signal(3)
        command = Signal(16)
        dcommand = Signal(16)

        self.specials += Instance("pcie_phy",
                p_C_DATA_WIDTH=dw,
                p_C_PCIE_GT_DEVICE=get_gt(device),
                p_C_BAR0=get_bar_mask(self.bar0_size),

                i_sys_clk=clk100,
                i_sys_rst_n=pads.rst_n,

                o_pci_exp_txp=pads.tx_p,
                o_pci_exp_txn=pads.tx_n,

                i_pci_exp_rxp=pads.rx_p,
                i_pci_exp_rxn=pads.rx_n,

                o_user_clk=ClockSignal("clk125"),
                o_user_reset=ResetSignal("clk125"),
                o_user_lnk_up=self._lnk_up.status,

                o_tx_buf_av=self.tx_buf_av,
                o_tx_terr_drop=self.tx_terr_drop,
                o_tx_cfg_req=self.tx_cfg_req,
                i_tx_cfg_gnt=self.tx_cfg_gnt,

                i_s_axis_tx_tvalid=self.sink.stb,
                i_s_axis_tx_tlast=self.sink.eop,
                o_s_axis_tx_tready=self.sink.ack,
                i_s_axis_tx_tdata=self.sink.dat,
                i_s_axis_tx_tkeep=self.sink.be,
                i_s_axis_tx_tuser=0,

                i_rx_np_ok=self.rx_np_ok,
                i_rx_np_req=self.rx_np_req,

                o_m_axis_rx_tvalid=self.source.stb,
                o_m_axis_rx_tlast=self.source.eop,
                i_m_axis_rx_tready=self.source.ack,
                o_m_axis_rx_tdata=self.source.dat,
                o_m_axis_rx_tkeep=self.source.be,
                o_m_axis_rx_tuser=Signal(4),

                o_cfg_to_turnoff=self.cfg_to_turnoff,
                o_cfg_bus_number=bus_number,
                o_cfg_device_number=device_number,
                o_cfg_function_number=function_number,
                o_cfg_command=command,
                o_cfg_dcommand=dcommand,
                o_cfg_interrupt_msienable=self._msi_enable.status,

                i_cfg_interrupt=self.interrupt.stb,
                o_cfg_interrupt_rdy=self.interrupt.ack,
                i_cfg_interrupt_di=self.interrupt.dat,

                i_SHARED_QPLL_PD=self.shared_qpll_pd,
                i_SHARED_QPLL_RST=self.shared_qpll_rst,
                i_SHARED_QPLL_REFCLK=self.shared_qpll_refclk,
                o_SHARED_QPLL_OUTCLK=self.shared_qpll_outclk,
                o_SHARED_QPLL_OUTREFCLK=self.shared_qpll_outrefclk,
                o_SHARED_QPLL_LOCK=self.shared_qpll_lock,
        )

    # id
        self.comb += self.id.eq(Cat(function_number, device_number, bus_number))

    # config
        def convert_size(command, size):
            cases = {}
            value = 128
            for i in range(6):
                cases[i] = size.eq(value)
                value = value*2
            return Case(command, cases)

        self.sync += [
            self._bus_master_enable.status.eq(command[2]),
            convert_size(dcommand[12:15], self.max_request_size),
            convert_size(dcommand[5:8], self.max_payload_size)
        ]

        extcores_path = "extcores"
        # XXX find a better way to do this?
        current_path = os.getcwd()
        current_path = current_path.replace("\\", "/")
        if "litepcie/example_designs" in current_path:
            extcores_path = os.path.join("..", "..", "..", "..", extcores_path)
        platform.add_source_dir(os.path.join(extcores_path, "litepcie_phy_wrappers", "xilinx", "7-series", "common"))
        if device[:4] == "xc7k":
            platform.add_source_dir(os.path.join(extcores_path, "litepcie_phy_wrappers", "xilinx", "7-series", "kintex7"))
        elif device[:4] == "xc7a":
            platform.add_source_dir(os.path.join(extcores_path, "litepcie_phy_wrappers", "xilinx", "7-series", "artix7"))
