from migen.genlib.resetsync import AsyncResetSynchronizer

from targets import *

from misoclib.soc import SoC

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.phy import LiteSATAPHY
from misoclib.mem.litesata.core import LiteSATACore
from misoclib.mem.litesata.frontend.crossbar import LiteSATACrossbar
from misoclib.mem.litesata.frontend.bist import LiteSATABIST


class Core(Module):
    default_platform = "verilog_backend"
    def __init__(self, platform, clk_freq=166*1000000, with_bist=True, nports=4):
        self.clk_freq = clk_freq

        # SATA PHY/Core/Frontend
        self.submodules.sata_phy = LiteSATAPHY(platform.device, platform.request("sata"), "sata_gen2", clk_freq)
        self.submodules.sata_core = LiteSATACore(self.sata_phy)
        self.submodules.sata_crossbar = LiteSATACrossbar(self.sata_core)

        # BIST
        if with_bist:
            self.submodules.sata_bist = LiteSATABIST(self.sata_crossbar)

        # Get user ports from crossbar
        self.user_ports = self.sata_crossbar.get_ports(nports)

    def get_ios(self):
        ios = set()

        # Transceiver
        for e in dir(self.sata_phy.pads):
            obj = getattr(self.sata_phy.pads, e)
            if isinstance(obj, Signal):
                ios = ios.union({obj})

        # Status
        ios = ios.union({
            self.sata_phy.crg.ready,
            self.sata_phy.ctrl.ready
        })

        # BIST
        if hasattr(self, "sata_bist"):
            for bist_unit in ["generator", "checker"]:
                for signal in ["start", "sector", "count", "random", "done", "aborted", "errors"]:
                    ios = ios.union({getattr(getattr(self.sata_bist, bist_unit), signal)})
            ios = ios.union({
                self.sata_bist.identify.start,
                self.sata_bist.identify.done,
                self.sata_bist.identify.source.stb,
                self.sata_bist.identify.source.data,
                self.sata_bist.identify.source.ack
            })

        # User ports
        def _iter_layout(layout):
            for e in layout:
                if isinstance(e[1], list):
                    yield from _iter_layout(e[1])
                else:
                    yield e

        for port in self.user_ports:
            for endpoint in [port.sink, port.source]:
                for e in _iter_layout(endpoint.layout):
                    obj = getattr(endpoint, e[0])
                    ios = ios.union({obj})
        return ios

default_subtarget = Core
