import csv
from struct import *
from migen.fhdl.structure import *
from misoclib.tools.litescope.host.dump import *
from misoclib.tools.litescope.host.driver.truthtable import *


class LiteScopeLADriver():
    def __init__(self, regs, name, config_csv=None, clk_freq=None, debug=False):
        self.regs = regs
        self.name = name
        if config_csv is None:
            self.config_csv = name + ".csv"
        if clk_freq is None:
            try:
                self.clk_freq = regs.identifier_frequency.read()
            except:
                self.clk_freq = None
            self.samplerate = self.clk_freq
        else:
            self.clk_freq = clk_freq
            self.samplerate = clk_freq
        self.debug = debug
        self.get_config()
        self.get_layout()
        self.build()
        self.data = Dat(self.dw)

    def get_config(self):
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            t, n, v = item
            if t == "config":
                setattr(self, n, int(v))

    def get_layout(self):
        self.layout = []
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            t, n, v = item
            if t == "layout":
                self.layout.append((n, int(v)))

    def build(self):
        for key, value in self.regs.d.items():
            if self.name == key[:len(self.name)]:
                key = key.replace(self.name + "_", "")
                setattr(self, key, value)
        value = 1
        for name, length in self.layout:
            setattr(self, name + "_o", value)
            value = value*(2**length)
        value = 0
        for name, length in self.layout:
            setattr(self, name + "_m", (2**length-1) << value)
            value += length

    def configure_term(self, port, trigger=0, mask=0, cond=None):
        if cond is not None:
            for k, v in cond.items():
                trigger |= getattr(self, k + "_o")*v
                mask |= getattr(self, k + "_m")
        t = getattr(self, "trigger_port{d}_trig".format(d=int(port)))
        m = getattr(self, "trigger_port{d}_mask".format(d=int(port)))
        t.write(trigger)
        m.write(mask)

    def configure_range_detector(self, port, low, high):
        l = getattr(self, "trigger_port{d}_low".format(d=int(port)))
        h = getattr(self, "trigger_port{d}_high".format(d=int(port)))
        l.write(low)
        h.write(high)

    def configure_edge_detector(self, port, rising_mask, falling_mask, both_mask):
        rm = getattr(self, "trigger_port{d}_rising_mask".format(d=int(port)))
        fm = getattr(self, "trigger_port{d}_falling_mask".format(d=int(port)))
        bm = getattr(self, "trigger_port{d}_both_mask".format(d=int(port)))
        rm.write(rising_mask)
        fm.write(falling_mask)
        bm.write(both_mask)

    def configure_sum(self, equation):
        datas = gen_truth_table(equation)
        for adr, dat in enumerate(datas):
            self.trigger_sum_prog_adr.write(adr)
            self.trigger_sum_prog_dat.write(dat)
            self.trigger_sum_prog_we.write(1)

    def configure_subsampler(self, n):
        self.subsampler_value.write(n-1)
        if self.clk_freq is not None:
            self.samplerate = self.clk_freq//n
        else:
            self.samplerate = None

    def configure_qualifier(self, v):
        self.recorder_qualifier.write(v)

    def configure_rle(self, v):
        self.rle_enable.write(v)

    def done(self):
        return self.recorder_done.read()

    def run(self, offset, length):
        if self.debug:
            print("running")
        self.recorder_offset.write(offset)
        self.recorder_length.write(length)
        self.recorder_trigger.write(1)

    def upload(self):
        if self.debug:
            print("uploading")
        while self.recorder_source_stb.read():
            self.data.append(self.recorder_source_data.read())
            self.recorder_source_ack.write(1)
        if self.with_rle:
            if self.rle_enable.read():
                self.data = self.data.decode_rle()
        return self.data

    def save(self, filename):
        if self.debug:
            print("saving to " + filename)
        name, ext = os.path.splitext(filename)
        if ext == ".vcd":
            from misoclib.tools.litescope.host.dump.vcd import VCDDump
            dump = VCDDump()
        elif ext == ".csv":
            from misoclib.tools.litescope.host.dump.csv import CSVDump
            dump = CSVDump()
        elif ext == ".py":
            from misoclib.tools.litescope.host.dump.python import PythonDump
            dump = PythonDump()
        elif ext == ".sr":
            from misoclib.tools.litescope.host.dump.sigrok import SigrokDump
            if self.samplerate is None:
                raise ValueError("Unable to automatically retrieve clk_freq, clk_freq parameter required")
            dump = SigrokDump(samplerate=self.samplerate)
        else:
            raise NotImplementedError
        dump.add_from_layout(self.layout, self.data)
        dump.write(filename)
