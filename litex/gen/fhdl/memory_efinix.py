from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.fhdl.bitcontainer import bits_for
from migen.fhdl.tools import *
from migen.fhdl.verilog import _printexpr as verilog_printexpr
from migen.fhdl.specials import *

def memory_emit_verilog(memory, ns, add_data_file):
    r = ""
    def gn(e):
        if isinstance(e, Memory):
            return ns.get_name(e)
        else:
            return verilog_printexpr(ns, e)[0]
    adrbits = bits_for(memory.depth-1)

    for i in range(memory.width // 8):
        r += "reg [" + str((memory.width//4)-1) + ":0] " \
        + gn(memory) + '_' + str(i) \
        + "[0:" + str(memory.depth-1) + "];\n"

    adr_regs = {}
    data_regs = {}
    for port in memory.ports:
        if not port.async_read:
            if port.mode == WRITE_FIRST:
                adr_reg = Signal(name_override="memadr")
                r += "reg [" + str(adrbits-1) + ":0] " \
                    + gn(adr_reg) + ";\n"
                adr_regs[id(port)] = adr_reg
            else:
                data_reg = Signal(name_override="memdat")
                r += "reg [" + str(memory.width-1) + ":0] " \
                    + gn(data_reg) + ";\n"
                data_regs[id(port)] = data_reg

    for port in memory.ports:
        r += "always @(posedge " + gn(port.clock) + ") begin\n"
        if port.we is not None:
            if port.we_granularity:
                n = memory.width//port.we_granularity
                for i in range(n):
                    if (i > 0):
                        r += "always @(posedge " + gn(port.clock) + ") begin\n"
                    m = i*port.we_granularity
                    M = (i+1)*port.we_granularity-1
                    sl = "[" + str(M) + ":" + str(m) + "]"
                    r += "\tif (" + gn(port.we) + "[" + str(i) + "])\n"
                    r += "\t\t" + gn(memory) + '_' + str(i) + "[" + gn(port.adr) + "]" + " <= " + gn(port.dat_w) + sl + ";\n"
                    r += "end\n"
            else:
                r += "\tif (" + gn(port.we) + ")\n"
                r += "\t\t" + gn(memory) + "[" + gn(port.adr) + "] <= " + gn(port.dat_w) + ";\n"
        if not port.async_read:
            if port.mode == WRITE_FIRST:
                r += "always @(posedge " + gn(port.clock) + ") begin\n"
                rd = "\t" + gn(adr_regs[id(port)]) + " <= " + gn(port.adr) + ";\n"
            else:
                bassign = ""
                for i in range(memory.width // 8):
                    m = i*port.we_granularity
                    M = (i+1)*port.we_granularity-1
                    sl = "[" + str(M) + ":" + str(m) + "]"
                    bassign += gn(data_regs[id(port)]) + sl + " <= " + gn(memory) + "_" + str(i) + "[" + gn(port.adr) + "];\n"
                if port.mode == READ_FIRST:
                    rd = "\t" + bassign
                elif port.mode == NO_CHANGE:
                    rd = "\tif (!" + gn(port.we) + ")\n" \
                      + "\t\t" + bassign
            if port.re is None:
                r += rd
            else:
                r += "\tif (" + gn(port.re) + ")\n"
                r += "\t" + rd.replace("\n\t", "\n\t\t")
        r += "end\n\n"

    for port in memory.ports:
        if port.async_read:
                r += "assign " + gn(port.dat_r) + " = " + gn(memory) + "[" + gn(port.adr) + "];\n"
        else:
            if port.mode == WRITE_FIRST:
                for i in range(memory.width // 8):
                    m = i*port.we_granularity
                    M = (i+1)*port.we_granularity-1
                    sl = "[" + str(M) + ":" + str(m) + "]"
                    r += "assign " + gn(port.dat_r) + sl + " = " + gn(memory) + "_" + str(i) + "[" + gn(adr_regs[id(port)]) + "];\n"
            else:
                r += "assign " + gn(port.dat_r) + " = " + gn(data_regs[id(port)]) + ";\n"
    r += "\n"

    if memory.init is not None:
        content_7_0 = ""
        content_15_8 = ""
        content_23_16 = ""
        content_31_24 = ""
        formatter = "{:0" + str(int(memory.width / 4)) + "X}\n"

        init_7_0 = []
        init_15_8 = []
        init_23_16 = []
        init_31_24 = []

        for w in memory.init:
            init_7_0.append(w & 0xff)
            init_15_8.append((w >> 8) & 0xff)
            init_23_16.append((w >> 16) & 0xff)
            init_31_24.append((w >> 24) & 0xff)

        for d in init_7_0:
            content_7_0 += formatter.format(d)

        for d in init_15_8:
            content_15_8 += formatter.format(d)

        for d in init_23_16:
            content_23_16 += formatter.format(d)

        for d in init_31_24:
            content_31_24 += formatter.format(d)

        memory_filename1 = add_data_file(gn(memory) + "1.init", content_7_0)
        memory_filename2 = add_data_file(gn(memory) + "2.init", content_15_8)
        memory_filename3 = add_data_file(gn(memory) + "3.init", content_23_16)
        memory_filename4 = add_data_file(gn(memory) + "4.init", content_31_24)
        r += "initial begin\n"
        r += "\t$readmemh(\"" + memory_filename1 + "\", " + gn(memory)+ "_0" + ");\n"
        r += "\t$readmemh(\"" + memory_filename2 + "\", " + gn(memory)+ "_1" + ");\n"
        r += "\t$readmemh(\"" + memory_filename3 + "\", " + gn(memory)+ "_2" + ");\n"
        r += "\t$readmemh(\"" + memory_filename4 + "\", " + gn(memory)+ "_3" + ");\n"
        r += "end\n\n"

    return r
