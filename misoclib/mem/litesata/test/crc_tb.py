import subprocess

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core.link.crc import *

from misoclib.mem.litesata.test.common import *

class TB(Module):
    def __init__(self, length, random):
        self.submodules.crc = LiteSATACRC()
        self.length = length
        self.random = random

    def get_c_crc(self, datas):
        stdin = ""
        for data in datas:
            stdin += "0x%08x " %data
        stdin += "exit"
        with subprocess.Popen("./crc", stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            process.stdin.write(stdin.encode("ASCII"))
            out, err = process.communicate()
        return int(out.decode("ASCII"), 16)

    def gen_simulation(self, selfp):
        # init CRC
        selfp.crc.d = 0
        selfp.crc.ce = 1
        selfp.crc.reset = 1
        yield
        selfp.crc.reset = 0

        # feed CRC with datas
        datas = []
        for i in range(self.length):
            data = seed_to_data(i, self.random)
            datas.append(data)
            selfp.crc.d = data
            yield

        # log results
        yield
        sim_crc = selfp.crc.value

        # stop
        selfp.crc.ce = 0
        for i in range(32):
            yield

        # get C core reference
        c_crc = self.get_c_crc(datas)

        # check results
        s, l, e = check(c_crc, sim_crc)
        print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    from migen.sim.generic import run_simulation
    length = 8192
    run_simulation(TB(length, True), ncycles=length+100, vcd_name="my.vcd")
