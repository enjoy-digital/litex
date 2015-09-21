from migen import *


# Our simple counter, which increments at every cycle.
class Counter(Module):
    def __init__(self):
        self.count = Signal(4)

        # At each cycle, increase the value of the count signal.
        # We do it with convertible/synthesizable FHDL code.
        self.sync += self.count.eq(self.count + 1)


# Simply read the count signal and print it.
# The output is:
# Count: 0
# Count: 1
# Count: 2
# ...
def counter_test(dut):
    for i in range(20):
        print((yield dut.count))  # read and print
        yield  # next clock cycle
    # simulation ends with this generator


if __name__ == "__main__":
    dut = Counter()
    run_simulation(dut, counter_test(dut), vcd_name="basic1.vcd")
