from migen.bank.description import *
from migen.genlib.io import CRG

from misoclib.soc import SoC
from misoclib.tools.litescope.common import *
from misoclib.tools.litescope.bridge.uart2wb import LiteScopeUART2WB
from misoclib.tools.litescope.frontend.io import LiteScopeIO
from misoclib.tools.litescope.frontend.la import LiteScopeLA
from misoclib.tools.litescope.core.port import LiteScopeTerm


class LiteScopeSoC(SoC, AutoCSR):
    csr_map = {
        "io":    16,
        "la":    17
    }
    csr_map.update(SoC.csr_map)

    def __init__(self, platform):
        clk_freq = int((1/(platform.default_clk_period))*1000000000)
        SoC.__init__(self, platform, clk_freq,
            cpu_type="none",
            with_csr=True, csr_data_width=32,
            with_uart=False,
            with_identifier=True,
            with_timer=False
        )
        self.add_cpu_or_bridge(LiteScopeUART2WB(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        self.submodules.io = LiteScopeIO(8)
        for i in range(8):
            try:
                self.comb += platform.request("user_led", i).eq(self.io.o[i])
            except:
                pass

        self.submodules.counter0 = counter0 = Counter(8)
        self.submodules.counter1 = counter1 = Counter(8)
        self.comb += [
            counter0.ce.eq(1),
            If(counter0.value == 16,
                counter0.reset.eq(1),
                counter1.ce.eq(1)
            )
        ]

        self.debug = (
            counter1.value
        )
        self.submodules.la = LiteScopeLA(self.debug, 512, with_rle=True, with_subsampler=True)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def do_exit(self, vns):
        self.la.export(vns, "test/la.csv")

default_subtarget = LiteScopeSoC
