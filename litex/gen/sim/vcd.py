from itertools import count
import tempfile
import os
from collections import OrderedDict
import shutil

from litex.gen.fhdl.namer import build_namespace


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
    def __init__(self, filename):
        self.filename = filename
        self.out_file = open(self.filename, "w")
        self.codegen = vcd_codes()
        self.codes = OrderedDict()
        self.signal_values = dict()
        self.t = 0

    def _write_value(self, f, signal, value):
        l = len(signal)
        if value < 0:
            value += 2**l
        if l > 1:
            fmtstr = "b{:0" + str(l) + "b} {}\n"
        else:
            fmtstr = "{}{}\n"
        code = self.codes[signal]
        f.write(fmtstr.format(value, code))

    def init(self, signals):
        # generate codes
        for signal in signals:
            try:
                code = self.codes[signal]
            except KeyError:
                code = next(self.codegen)
                self.codes[signal] = code

        # write vcd header
        out = self.out_file
        ns = build_namespace(self.codes.keys())
        for signal, code in self.codes.items():
            name = ns.get_name(signal)
            out.write("$var wire {len} {code} {name} $end\n"
                      .format(name=name, code=code, len=len(signal)))
        out.write("$dumpvars\n")
        for signal in self.codes.keys():
            self._write_value(out, signal, signal.reset.value)
        out.write("$end\n")
        out.write("#0\n")

    def set(self, signal, value):
        if (signal not in self.signal_values
                or self.signal_values[signal] != value):
            self._write_value(self.out_file, signal, value)
            self.signal_values[signal] = value

    def delay(self, delay):
        self.t += delay
        self.out_file.write("#{}\n".format(self.t))

    def close(self):
        self.out_file.close()


class DummyVCDWriter:
    def init(self):
        pass

    def set(self, signal, value):
        pass

    def delay(self, delay):
        pass

    def close(self):
        pass
