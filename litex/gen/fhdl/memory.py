#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.fhdl.bitcontainer import bits_for
from migen.fhdl.tools import *
from migen.fhdl.verilog import _printexpr as verilog_printexpr
from migen.fhdl.specials import *

def memory_emit_verilog(memory, ns, add_data_file):
    # Helpers.
    # --------
    def gn(e):
        if isinstance(e, Memory):
            return ns.get_name(e)
        else:
            return verilog_printexpr(ns, e)[0]

    # Parameters.
    # -----------
    r         = ""
    adrbits   = bits_for(memory.depth-1)
    adr_regs  = {}
    data_regs = {}

    # Ports Transformations.
    # ----------------------
    # https://github.com/enjoy-digital/litex/issues/1003
    # FIXME: Verify behaviour with the different FPGA toolchains.
    clocks = [port.clock for port in memory.ports]
    if clocks.count(clocks[0]) != len(clocks):
        for port in memory.ports:
            port.mode = READ_FIRST

    # Memory Description.
    # -------------------
    r += "//" + "-"*80 + "\n"
    r += f"// Memory {gn(memory)}: {memory.depth}-words x {memory.width}-bit\n"
    r += "//" + "-"*80 + "\n"
    for n, port in enumerate(memory.ports):
        r += f"// Port {n} | "
        if port.async_read:
            r += "Read: Async | "
        else:
            r += "Read: Sync  | "
        if port.we is None:
            r += "Write: ---- | "
        else:
            r += "Write: Sync | "
            r += "Mode: "
            if port.mode == WRITE_FIRST:
                r += "Write-First | "
            elif port.mode == READ_FIRST:
                r += "Read-First  | "
            elif port.mode == NO_CHANGE:
                r += "No-Change | "
            r += f"Write-Granularity: {port.we_granularity} "
        r += "\n"

    # Memory Logic Declaration/Initialization.
    # ----------------------------------------
    r += f"reg [{memory.width-1}:0] {gn(memory)}[0:{memory.depth-1}];\n"
    if memory.init is not None:
        content = ""
        formatter = f"{{:0{int(memory.width/4)}x}}\n"
        for d in memory.init:
            content += formatter.format(d)
        memory_filename = add_data_file(f"{gn(memory)}.init", content)

        r += "initial begin\n"
        r += f"\t$readmemh(\"{memory_filename}\", {gn(memory)});\n"
        r += "end\n"

    # Port Intermediate Signals.
    # --------------------------
    for port in memory.ports:
        # No Intermediate Signal for Async Read.
        if port.async_read:
            continue

        # Create Address Register in Write-First mode.
        if port.mode in [WRITE_FIRST]:
            adr_reg = Signal(name_override="memadr")
            r += f"reg [{adrbits-1}:0] {gn(adr_reg)};\n"
            adr_regs[id(port)] = adr_reg

        # Create Data Register in Read-First/No Change mode.
        if port.mode in [READ_FIRST, NO_CHANGE]:
            data_reg = Signal(name_override="memdat")
            r += f"reg [{memory.width-1}:0] {gn(data_reg)};\n"
            data_regs[id(port)] = data_reg

    # Ports Write/Read Logic.
    # -----------------------
    for port in memory.ports:
        r += f"always @(posedge {gn(port.clock)}) begin\n"
        # Write Logic.
        if port.we is not None:
            # Split Write Logic when Granularity.
            if port.we_granularity:
                n = memory.width//port.we_granularity
                for i in range(n):
                    m = i*port.we_granularity
                    M = (i+1)*port.we_granularity-1
                    sl = f"[{M}:{m}]"
                    r += f"\tif ({gn(port.we)}[{i}])\n"
                    r += f"\t\t{gn(memory)}[{gn(port.adr)}]{sl} <= {gn(port.dat_w)}{sl};\n"
            # Else use common Write Logic.
            else:
                r += f"\tif ({gn(port.we)})\n"
                r += f"\t\t{gn(memory)}[{gn(port.adr)}] <= {gn(port.dat_w)};\n"

        # Read Logic.
        if not port.async_read:
            # In Write-First mode, Read from Address Register.
            if port.mode in [WRITE_FIRST]:
                rd = f"\t{gn(adr_regs[id(port)])} <= {gn(port.adr)};\n"

            # In Write-First/No Change mode:
            if port.mode in [READ_FIRST, NO_CHANGE]:
                bassign = f"{gn(data_regs[id(port)])} <= {gn(memory)} [{gn(port.adr)}];\n"
                # Always Read in Read-First mode.
                if port.mode == READ_FIRST:
                    rd = f"\t{bassign}"
                # Only Read in No-Change mode when no Write.
                elif port.mode == NO_CHANGE:
                    rd = f"\tif (!{gn(port.we)})\n\t\t{bassign}"

            # Add Read-Enable Logic.
            if port.re is None:
                r += rd
            else:
                r += f"\tif ({gn(port.re)})\n"
                r += "\t" + rd.replace("\n\t", "\n\t\t")
        r += "end\n"

    # Ports Read Mapping.
    # -------------------
    for port in memory.ports:
        # Direct (Asynchronous) Read on Async-Read mode.
        if port.async_read:
            r += f"assign {gn(port.dat_r)} = {gn(memory)}[{gn(port.adr)}];\n"
            continue

        # Write-First mode: Do Read through Address Register.
        if port.mode in [WRITE_FIRST]:
            r += f"assign {gn(port.dat_r)} = {gn(memory)}[{gn(adr_regs[id(port)])}];\n"

        # Read-First/No-Change mode: Data already Read on Data Register.
        if port.mode in [READ_FIRST, NO_CHANGE]:
             r += f"assign {gn(port.dat_r)} = {gn(data_regs[id(port)])};\n"
    r +=  "//" + "-"*80 + "\n\n"

    return r
