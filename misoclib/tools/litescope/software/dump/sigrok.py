import os
import math
import shutil
import zipfile
import re
from collections import OrderedDict

from misoclib.tools.litescope.software.dump import *


class SigrokDump(Dump):
    def __init__(self, init_dump=None, samplerate=50000000):
        Dump.__init__(self)
        if init_dump:
            self.vars = init_dump.vars
        self.samplerate = samplerate

    def write_version(self):
        f = open("version", "w")
        f.write("1")
        f.close()

    def write_metadata(self, name):
        f = open("metadata", "w")
        r = """
[global]
sigrok version = 0.2.0
[device 1]
driver = litescope
capturefile = logic-1
unitsize = 1
total probes = {}
samplerate = {} KHz
""".format(
        len(self.vars),
        self.samplerate//1000,
    )
        for i, var in enumerate(self.vars):
            r += "probe{} = {}\n".format(i+1, var.name)
        f.write(r)
        f.close()

    def write_data(self):
        # XXX are probes limited to 1 bit?
        data_bits = math.ceil(len(self.vars)/8)*8
        data_len = 0
        for var in self.vars:
            data_len = max(data_len, len(var))
        datas = []
        for i in range(data_len):
            data = 0
            for j, var in enumerate(reversed(self.vars)):
                data = data << 1
                try:
                    data |= var.values[i] % 2
                except:
                    pass
            datas.append(data)
        f = open("logic-1", "wb")
        for data in datas:
            f.write(data.to_bytes(data_bits//8, "big"))
        f.close()

    def zip(self, name):
        f = zipfile.ZipFile(name + ".sr", "w")
        os.chdir(name)
        f.write("version")
        f.write("metadata")
        f.write("logic-1")
        os.chdir("..")
        f.close()

    def write(self, filename):
        name, ext = os.path.splitext(filename)
        if os.path.exists(name):
            shutil.rmtree(name)
        os.makedirs(name)
        os.chdir(name)
        self.write_version()
        self.write_metadata(name)
        self.write_data()
        os.chdir("..")
        self.zip(name)
        shutil.rmtree(name)

    def unzip(self, filename, name):
        f = open(filename, "rb")
        z = zipfile.ZipFile(f)
        if os.path.exists(name):
            shutil.rmtree(name)
            os.makedirs(name)
        for file in z.namelist():
            z.extract(file, name)
        f.close()

    def read_metadata(self):
        probes = OrderedDict()
        f = open("metadata", "r")
        for l in f:
            m = re.search("probe([0-9]+) = (\w+)", l, re.I)
            if m is not None:
                index = int(m.group(1))
                name = m.group(2)
                probes[name] = index
            m = re.search("samplerate = ([0-9]+) kHz", l, re.I)
            if m is not None:
                self.samplerate = int(m.group(1))*1000
            m = re.search("samplerate = ([0-9]+) mHz", l, re.I)
            if m is not None:
                self.samplerate = int(m.group(1))*1000000
        f.close()
        return probes

    def read_data(self, name, nprobes):
        datas = []
        f = open("logic-1", "rb")
        while True:
            data = f.read(math.ceil(nprobes/8))
            if data == bytes('', "utf-8"):
                break
            data = int.from_bytes(data, "big")
            datas.append(data)
        f.close()
        return datas

    def read(self, filename):
        self.vars = []
        name, ext = os.path.splitext(filename)
        self.unzip(filename, name)
        os.chdir(name)
        probes = self.read_metadata()
        datas = self.read_data(name, len(probes.keys()))
        os.chdir("..")
        shutil.rmtree(name)

        for k, v in probes.items():
            probe_data = []
            for data in datas:
                probe_data.append((data >> (v-1)) & 0x1)
            self.add(Var(k, 1, probe_data))

if __name__ == '__main__':
    dump = SigrokDump()
    dump.add(Var("foo1", 1, [0, 1, 0, 1, 0, 1]))
    dump.add(Var("foo2", 2, [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]))
    ramp = [i%128 for i in range(1024)]
    dump.add(Var("ramp", 16, ramp))
    dump.write("dump.sr")
    dump.read("dump.sr")
    dump.write("dump_copy.sr")
