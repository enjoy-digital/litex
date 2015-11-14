import csv

# TODO: move

class MappedReg:
    def __init__(self, readfn, writefn, name, addr, length, busword, mode):
        self.readfn = readfn
        self.writefn = writefn
        self.addr = addr
        self.length = length
        self.busword = busword
        self.mode = mode

    def read(self):
        if self.mode not in ["rw", "ro"]:
            raise KeyError(name + "register not readable")
        datas = self.readfn(self.addr, burst_length=self.length)
        if isinstance(datas, int):
            return datas
        else:
            data = 0
            for i in range(self.length):
                data = data << self.busword
                data |= datas[i]
            return data

    def write(self, value):
        if self.mode not in ["rw", "wo"]:
            raise KeyError(name + "register not writable")
        datas = []
        for i in range(self.length):
            datas.append((value >> ((self.length-1-i)*self.busword)) & (2**self.busword-1))
        self.writefn(self.addr, datas)


class MappedElements:
    def __init__(self, d):
        self.d = d

    def __getattr__(self, attr):
        try:
            return self.__dict__['d'][attr]
        except KeyError:
            pass
        raise KeyError("No such element " + attr)


def build_csr_bases(addrmap):
    csv_reader = csv.reader(open(addrmap), delimiter=',', quotechar='#')
    d = {}
    for item in csv_reader:
        group, name, addr, dummy0, dummy1 = item
        if group == "csr_base":
            d[name] = int(addr.replace("0x", ""), 16)
    return MappedElements(d)

def build_csr_registers(addrmap, busword, readfn, writefn):
    csv_reader = csv.reader(open(addrmap), delimiter=',', quotechar='#')
    d = {}
    for item in csv_reader:
        group, name, addr, length, mode = item
        if group == "csr_register":
            addr = int(addr.replace("0x", ""), 16)
            length = int(length)
            d[name] = MappedReg(readfn, writefn, name, addr, length, busword, mode)
    return MappedElements(d)

def build_constants(addrmap):
    csv_reader = csv.reader(open(addrmap), delimiter=',', quotechar='#')
    d = {}
    for item in csv_reader:
        group, name, value, dummy0, dummy1 = item
        if group == "constant":
            try:
                d[name] = int(value)
            except:
                d[name] = value
    return MappedElements(d)
