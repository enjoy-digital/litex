from migen import *


class Mem(Module):
    def __init__(self):
        # Initialize the beginning of the memory with integers
        # from 0 to 19.
        self.specials.mem = Memory(16, 2**12, init=list(range(20)))


def memory_test(dut):
    # write (only first 5 values)
    for i in range(5):
        yield dut.mem[i].eq(42 + i)
    # remember: values are written after the tick, and read before the tick.
    # wait one tick for the memory to update.
    yield
    # read what we have written, plus some initialization data
    for i in range(10):
        value = yield dut.mem[i]
        print(value)


if __name__ == "__main__":
    dut = Mem()
    run_simulation(dut, memory_test(dut))
