import subprocess

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core.link.scrambler import *

from misoclib.mem.litesata.test.common import *


class TB(Module):
    def __init__(self, length):
        self.submodules.scrambler = InsertReset(Scrambler())
        self.length = length

    def get_c_values(self, length):
        stdin = "0x{:08x}".format(length)
        with subprocess.Popen("./scrambler", stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            process.stdin.write(stdin.encode("ASCII"))
            out, err = process.communicate()
        return [int(e, 16) for e in out.decode("ASCII").split("\n")[:-1]]

    def gen_simulation(self, selfp):
        # init CRC
        selfp.scrambler.ce = 1
        selfp.scrambler.reset = 1
        yield
        selfp.scrambler.reset = 0

        # log results
        yield
        sim_values = []
        for i in range(self.length):
            sim_values.append(selfp.scrambler.value)
            yield

        # stop
        selfp.scrambler.ce = 0
        for i in range(32):
            yield

        # get C code reference
        c_values = self.get_c_values(self.length)

        # check results
        s, l, e = check(c_values, sim_values)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    from migen.sim.generic import run_simulation
    length = 8192
    run_simulation(TB(length), ncycles=length+100, vcd_name="my.vcd")
