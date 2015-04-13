from misoclib.tools.litescope.host.dump import *


class CSVDump(Dump):
    def __init__(self, init_dump=None):
        Dump.__init__(self)
        if init_dump:
            self.vars = init_dump.vars

    def  generate_vars(self):
        r = ""
        for var in self.vars:
            r += var.name
            r += ","
        r += "\n"
        for var in self.vars:
            r += str(var.width)
            r += ","
        r += "\n"
        return r

    def generate_dumpvars(self):
        r  = ""
        for i in range(len(self)):
            for var in self.vars:
                try:
                    var.val = var.values[i]
                except:
                    pass
                if var.val == "x":
                    r += "x"
                else:
                    r += dec2bin(var.val, var.width)
                r += ", "
            r += "\n"
        return r

    def write(self, filename):
        f = open(filename, "w")
        f.write(self.generate_vars())
        f.write(self.generate_dumpvars())
        f.close()

    def read(self, filename):
        raise NotImplementedError("CSV files can not (yet) be read, please contribute!")

if __name__ == '__main__':
    dump = CSVDump()
    dump.add(Var("foo1", 1, [0, 1, 0, 1, 0, 1]))
    dump.add(Var("foo2", 2, [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]))
    ramp = [i%128 for i in range(1024)]
    dump.add(Var("ramp", 16, ramp))
    dump.write("dump.csv")
