from random import Random

from migen.fhdl.std import *
from migen.bus.transactions import *
from migen.bus import wishbone
from migen.sim.generic import run_simulation


# Our bus master.
# Python generators let us program bus transactions in an elegant sequential style.
def my_generator():
    prng = Random(92837)

    # Write to the first addresses.
    for x in range(10):
        t = TWrite(x, 2*x)
        yield t
        print("Wrote in " + str(t.latency) + " cycle(s)")
        # Insert some dead cycles to simulate bus inactivity.
        for delay in range(prng.randrange(0, 3)):
            yield None

    # Read from the first addresses.
    for x in range(10):
        t = TRead(x)
        yield t
        print("Read " + str(t.data) + " in " + str(t.latency) + " cycle(s)")
        for delay in range(prng.randrange(0, 3)):
            yield None


# Our bus slave.
class MyModelWB(wishbone.TargetModel):
    def __init__(self):
        self.prng = Random(763627)

    def read(self, address):
        return address + 4

    def can_ack(self, bus):
        # Simulate variable latency.
        return self.prng.randrange(0, 2)


class TB(Module):
    def __init__(self):
        # The "wishbone.Initiator" library component runs our generator
        # and manipulates the bus signals accordingly.
        self.submodules.master = wishbone.Initiator(my_generator())
        # The "wishbone.Target" library component examines the bus signals
        # and calls into our model object.
        self.submodules.slave = wishbone.Target(MyModelWB())
        # The "wishbone.Tap" library component examines the bus at the slave port
        # and displays the transactions on the console (<TRead...>/<TWrite...>).
        self.submodules.tap = wishbone.Tap(self.slave.bus)
        # Connect the master to the slave.
        self.submodules.intercon = wishbone.InterconnectPointToPoint(self.master.bus, self.slave.bus)

if __name__ == "__main__":
    run_simulation(TB())

# Output:
# <TWrite adr:0x0 dat:0x0>
# Wrote in 0 cycle(s)
# <TWrite adr:0x1 dat:0x2>
# Wrote in 0 cycle(s)
# <TWrite adr:0x2 dat:0x4>
# Wrote in 0 cycle(s)
# <TWrite adr:0x3 dat:0x6>
# Wrote in 1 cycle(s)
# <TWrite adr:0x4 dat:0x8>
# Wrote in 1 cycle(s)
# <TWrite adr:0x5 dat:0xa>
# Wrote in 2 cycle(s)
# ...
# <TRead adr:0x0 dat:0x4>
# Read 4 in 2 cycle(s)
# <TRead adr:0x1 dat:0x5>
# Read 5 in 2 cycle(s)
# <TRead adr:0x2 dat:0x6>
# Read 6 in 1 cycle(s)
# <TRead adr:0x3 dat:0x7>
# Read 7 in 1 cycle(s)
# ...
