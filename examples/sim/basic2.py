from migen import *


# A slightly more elaborate counter.
# Has a clock enable (CE) signal, counts on more bits
# and resets with a negative number.
class Counter(Module):
    def __init__(self):
        self.ce = Signal()
        # Demonstrate negative numbers and signals larger than 32 bits.
        self.count = Signal((37, True), reset=-5)

        self.sync += If(self.ce, self.count.eq(self.count + 1))


def counter_test(dut):
    for cycle in range(20):
        # Only assert CE every second cycle.
        # => each counter value is held for two cycles.
        if cycle % 2:
            yield dut.ce.eq(0)  # This is how you write to a signal.
        else:
            yield dut.ce.eq(1)
        print("Cycle: {} Count: {}".format(cycle, (yield dut.count)))
        yield

# Output is:
# Cycle: 0 Count: -5
# Cycle: 1 Count: -5
# Cycle: 2 Count: -4
# Cycle: 3 Count: -4
# Cycle: 4 Count: -3
# ...

if __name__ == "__main__":
    dut = Counter()
    run_simulation(dut, counter_test(dut), vcd_name="basic2.vcd")
