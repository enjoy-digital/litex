from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.phy import *
from misoclib.mem.litesata.core import *
from misoclib.mem.litesata.frontend import *

from migen.bank.description import *

class LiteSATA(Module, AutoCSR):
    def __init__(self, phy, buffer_depth=2*fis_max_dwords,
            with_bist=False, with_bist_csr=False):
        # phy
        self.phy = phy

        # core
        self.submodules.core = LiteSATACore(self.phy, buffer_depth)

        # frontend
        self.submodules.crossbar = LiteSATACrossbar(self.core)
        if with_bist:
            self.submodules.bist = LiteSATABIST(self.crossbar, with_bist_csr)

