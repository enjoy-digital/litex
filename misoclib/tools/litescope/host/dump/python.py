from misoclib.tools.litescope.host.dump import *


class PythonDump(Dump):
    def __init__(self, init_dump=None):
        Dump.__init__(self)
        if init_dump:
            self.vars = init_dump.vars

    def generate_data(self):
        r = "dump = {\n"
        for var in self.vars:
            r += "\"" + var.name + "\""
            r += " : "
            r += str(var.values)
            r += ",\n"
        r += "}"
        return r

    def write(self, filename):
        f = open(filename, "w")
        f.write(self.generate_data())
        f.close()

    def read(self, filename):
        raise NotImplementedError("Python files can not (yet) be read, please contribute!")

if __name__ == '__main__':
    dump = PythonDump()
    dump.add(Var("foo1", 1, [0, 1, 0, 1, 0, 1]))
    dump.add(Var("foo2", 2, [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]))
    ramp = [i%128 for i in range(1024)]
    dump.add(Var("ramp", 16, ramp))
    dump.write("dump.py")
