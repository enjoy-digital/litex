import datetime
from misoclib.tools.litescope.host.dump import *


class VCDDump(Dump):
    def __init__(self, init_dump=None, timescale="1ps", comment=""):
        Dump.__init__(self)
        if init_dump:
            self.vars = init_dump.vars
        self.timescale = timescale
        self.comment = comment
        self.cnt = -1

    def change(self):
        r = ""
        c = ""
        for var in self.vars:
            c += var.change(self.cnt)
        if c != "":
            r += "#"
            r += str(self.cnt+1)
            r += "\n"
            r += c
        return r

    def generate_date(self):
        now = datetime.datetime.now()
        r = "$date\n"
        r += "\t"
        r += now.strftime("%Y-%m-%d %H:%M")
        r += "\n"
        r += "$end\n"
        return r

    def generate_version(self):
        r  = "$version\n"
        r += "\tmiscope VCD dump\n"
        r += "$end\n"
        return r

    def generate_comment(self):
        r  = "$comment\n"
        r += self.comment
        r += "\n$end\n"
        return r

    def generate_timescale(self):
        r  = "$timescale "
        r += self.timescale
        r += " $end\n"
        return r

    def generate_scope(self):
        r  = "$scope "
        r += self.timescale
        r += " $end\n"
        return r

    def generate_vars(self):
        r = ""
        for var in self.vars:
            r += "$var "
            r += var.type
            r += " "
            r += str(var.width)
            r += " "
            r += var.vcd_id
            r += " "
            r += var.name
            r += " $end\n"
        return r

    def generate_unscope(self):
        r  = "$unscope "
        r += " $end\n"
        return r

    def generate_enddefinitions(self):
        r  = "$enddefinitions "
        r += " $end\n"
        return r

    def generate_dumpvars(self):
        r  = "$dumpvars\n"
        for var in self.vars:
            r += "b"
            r += dec2bin(var.val, var.width)
            r += " "
            r += var.vcd_id
            r+= "\n"
        r += "$end\n"
        return r

    def generate_valuechange(self):
        r = ""
        for i in range(len(self)):
            r += self.change()
            self.cnt += 1
        return r

    def __repr__(self):
        r = ""

        return r

    def write(self, filename):
        f = open(filename, "w")
        f.write(self.generate_date())
        f.write(self.generate_comment())
        f.write(self.generate_timescale())
        f.write(self.generate_scope())
        f.write(self.generate_vars())
        f.write(self.generate_unscope())
        f.write(self.generate_enddefinitions())
        f.write(self.generate_dumpvars())
        f.write(self.generate_valuechange())
        f.close()

    def read(self, filename):
        raise NotImplementedError("VCD files can not (yet) be read, please contribute!")

if __name__ == '__main__':
    dump = VCDDump()
    dump.add(Var("foo1", 1, [0,1,0,1,0,1]))
    dump.add(Var("foo2", 2, [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]))
    ramp = [i%128 for i in range(1024)]
    dump.add(Var("ramp", 16, ramp))
    dump.write("dump.vcd")
