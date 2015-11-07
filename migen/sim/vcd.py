from itertools import count

from migen.fhdl.namer import build_namespace


def vcd_codes():
    codechars = [chr(i) for i in range(33, 127)]
    for n in count():
        q, r = divmod(n, len(codechars))
        code = codechars[r]
        while q > 0:
            q, r = divmod(q, len(codechars))
            code = codechars[r] + code
        yield code


class VCDWriter:
    def __init__(self, filename, signals):
        self.fo = open(filename, "w")
        self.codes = dict()
        self.signal_values = dict()
        self.t = 0

        try:
            ns = build_namespace(signals)
            codes = vcd_codes()
            for signal in signals:
                name = ns.get_name(signal)
                code = next(codes)
                self.codes[signal] = code
                self.fo.write("$var wire {len} {code} {name} $end\n"
                              .format(name=name, code=code, len=len(signal)))
            self.fo.write("$dumpvars\n")
            for signal in signals:
                value = signal.reset.value
                self._write_value(signal, value)
                self.signal_values[signal] = value
            self.fo.write("$end\n")
            self.fo.write("#0\n")
        except:
            self.close()
            raise

    def _write_value(self, signal, value):
        l = len(signal)
        if value < 0:
            value += 2**l
        if l > 1:
            fmtstr = "b{:0" + str(l) + "b} {}\n"
        else:
            fmtstr = "{}{}\n"
        self.fo.write(fmtstr.format(value, self.codes[signal]))

    def set(self, signal, value):
        if self.signal_values[signal] != value:
            self._write_value(signal, value)
            self.signal_values[signal] = value

    def delay(self, delay):
        self.t += delay
        self.fo.write("#{}\n".format(self.t))

    def close(self):
        self.fo.close()


class DummyVCDWriter:
    def set(self, signal, value):
        pass

    def delay(self, delay):
        pass

    def close(self):
        pass
