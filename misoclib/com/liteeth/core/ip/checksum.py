from misoclib.com.liteeth.common import *


class LiteEthIPV4Checksum(Module):
    def __init__(self, words_per_clock_cycle=1, skip_checksum=False):
        self.reset = Signal()  # XXX FIXME InsertReset generates incorrect verilog
        self.ce = Signal()     # XXX FIXME InsertCE generates incorrect verilog
        self.header = Signal(ipv4_header.length*8)
        self.value = Signal(16)
        self.done = Signal()

        # # #

        s = Signal(17)
        r = Signal(17)
        n_cycles = 0
        for i in range(ipv4_header.length//2):
            if skip_checksum and (i == ipv4_header.fields["checksum"].byte//2):
                pass
            else:
                s_next = Signal(17)
                r_next = Signal(17)
                self.comb += s_next.eq(r + self.header[i*16:(i+1)*16])
                r_next_eq = r_next.eq(Cat(s_next[:16]+s_next[16], Signal()))
                if (i%words_per_clock_cycle) != 0:
                    self.comb += r_next_eq
                else:
                    self.sync += \
                        If(self.reset,
                            r_next.eq(0)
                        ).Elif(self.ce & ~self.done,
                            r_next_eq
                        )
                    n_cycles += 1
                s, r = s_next, r_next
        self.comb += self.value.eq(~Cat(r[8:16], r[:8]))

        if not skip_checksum:
            n_cycles += 1
        self.submodules.counter = counter = Counter(max=n_cycles+1)
        self.comb += [
            counter.reset.eq(self.reset),
            counter.ce.eq(self.ce & ~self.done),
            self.done.eq(counter.value == n_cycles)
        ]
