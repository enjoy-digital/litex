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

    r += "reg [" + str(memory.width-1) + ":0] " \
        + gn(memory) \
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
                    m = i*port.we_granularity
                    M = (i+1)*port.we_granularity-1
                    sl = "[" + str(M) + ":" + str(m) + "]"
                    r += "\tif (" + gn(port.we) + "[" + str(i) + "])\n"
                    r += "\t\t" + gn(memory) + "[" + gn(port.adr) + "]" + sl + " <= " + gn(port.dat_w) + sl + ";\n"
            else:
                r += "\tif (" + gn(port.we) + ")\n"
                r += "\t\t" + gn(memory) + "[" + gn(port.adr) + "] <= " + gn(port.dat_w) + ";\n"
        if not port.async_read:
            if port.mode == WRITE_FIRST:
                rd = "\t" + gn(adr_regs[id(port)]) + " <= " + gn(port.adr) + ";\n"
            else:
                bassign = gn(data_regs[id(port)]) + " <= " + gn(memory) + "[" + gn(port.adr) + "];\n"
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
                r += "assign " + gn(port.dat_r) + " = " + gn(memory) + "[" + gn(adr_regs[id(port)]) + "];\n"
            else:
                r += "assign " + gn(port.dat_r) + " = " + gn(data_regs[id(port)]) + ";\n"
    r += "\n"

    if memory.init is not None:
        content = ""
        formatter = "{:0" + str(int(memory.width / 4)) + "X}\n"
        for d in memory.init:
            content += formatter.format(d)
        memory_filename = add_data_file(gn(memory) + ".init", content)

        r += "initial begin\n"
        r += "\t$readmemh(\"" + memory_filename + "\", " + gn(memory) + ");\n"
        r += "end\n\n"

    return r
