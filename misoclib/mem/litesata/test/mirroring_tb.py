from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core import LiteSATACore
from misoclib.mem.litesata.frontend.common import *
from misoclib.mem.litesata.frontend.crossbar import LiteSATACrossbar
from misoclib.mem.litesata.frontend.bist import LiteSATABISTGenerator, LiteSATABISTChecker
from misoclib.mem.litesata.frontend.mirroring import LiteSATAMirroring

from misoclib.mem.litesata.test.common import *
from misoclib.mem.litesata.test.model.hdd import *


class TB(Module):
    def __init__(self):
        self.submodules.hdd0 = HDD(n=0,
                link_debug=False, link_random_level=0,
                transport_debug=False, transport_loopback=False,
                hdd_debug=True)
        self.submodules.core0 = LiteSATACore(self.hdd0.phy)

        self.submodules.hdd1 = HDD(n=1,
                link_debug=False, link_random_level=0,
                transport_debug=False, transport_loopback=False,
                hdd_debug=True)
        self.submodules.core1 = LiteSATACore(self.hdd1.phy)

        self.submodules.mirroring = LiteSATAMirroring([self.core0, self.core1])

        self.submodules.crossbar0 = LiteSATACrossbar(self.mirroring.ports[0])
        self.submodules.generator0 = LiteSATABISTGenerator(self.crossbar0.get_port())
        self.submodules.checker0 = LiteSATABISTChecker(self.crossbar0.get_port())

        self.submodules.crossbar1 = LiteSATACrossbar(self.mirroring.ports[1])
        self.submodules.generator1 = LiteSATABISTGenerator(self.crossbar1.get_port())
        self.submodules.checker1 = LiteSATABISTChecker(self.crossbar1.get_port())

    def gen_simulation(self, selfp):
        hdd0 = self.hdd0
        hdd0.malloc(0, 64)
        hdd1 = self.hdd1
        hdd1.malloc(0, 64)
        sector = 0
        count = 1
        checker0 = selfp.checker0
        checker1 = selfp.checker1
        while True:
            for generator in [selfp.generator0, selfp.generator1]:
                # write data (alternate generators)
                generator.sector = sector
                generator.count = count
                generator.start = 1
                yield
                generator.start = 0
                yield
                while generator.done == 0:
                    yield

                # verify data on the 2 hdds in //
                checker0.sector = sector
                checker0.count = count
                checker0.start = 1
                checker1.sector = sector
                checker1.count = count
                checker1.start = 1
                yield
                checker0.start = 0
                checker1.start = 0
                yield
                while (checker0.done == 0) or (checker1.done == 0):
                    yield
                print("errors {}".format(checker0.errors + checker1.errors))

                # prepare next iteration
                sector += 1

if __name__ == "__main__":
    run_simulation(TB(), ncycles=4096, vcd_name="my.vcd", keep_files=True)
