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


def memory_emit_verilog(name, memory, namespace, add_data_file):
    # Helpers.
    # --------

    def _get_name(e):
        if isinstance(e, Memory):
            return namespace.get_name(e)
        else:
            return verilog_printexpr(namespace, e)[0]

    # Parameters.
    # -----------
    r         = ""
    adr_regs  = {}
    data_regs = {}

    # Ports Transformations.
    # ----------------------

    # Set Port Mode to Read-First when several Ports with different Clocks.
    # FIXME: Verify behaviour with the different FPGA toolchains, try to avoid it.
    clocks = [port.clock for port in memory.ports]
    if clocks.count(clocks[0]) != len(clocks):
        for port in memory.ports:
            port.mode = READ_FIRST

    # Set Port Granularity when 0.
    for port in memory.ports:
        if port.we_granularity == 0:
            port.we_granularity = memory.width

    # Memory Description.
    # -------------------
    r += "//" + "-"*78 + "\n"
    r += f"// Memory {_get_name(memory)}: {memory.depth}-words x {memory.width}-bit\n"
    r += "//" + "-"*78 + "\n"
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
    r += f"reg [{memory.width-1}:0] {_get_name(memory)}[0:{memory.depth-1}];\n"
    if memory.init is not None:
        content = ""
        formatter = f"{{:0{int(memory.width/4)}x}}\n"
        for d in memory.init:
            content += formatter.format(d)
        memory_filename = add_data_file(f"{name}_{_get_name(memory)}.init", content)

        r += "initial begin\n"
        r += f"\t$readmemh(\"{memory_filename}\", {_get_name(memory)});\n"
        r += "end\n"

    # Port Intermediate Signals.
    # --------------------------
    for n, port in enumerate(memory.ports):
        # No Intermediate Signal for Async Read.
        if port.async_read:
            continue

        # Create Address Register in Write-First mode.
        if port.mode in [WRITE_FIRST]:
            adr_regs[n] = Signal(name_override=f"{_get_name(memory)}_adr{n}")
            r += f"reg [{bits_for(memory.depth-1)-1}:0] {_get_name(adr_regs[n])};\n"

        # Create Data Register in Read-First/No Change mode.
        if port.mode in [READ_FIRST, NO_CHANGE]:
            data_regs[n] = Signal(name_override=f"{_get_name(memory)}_dat{n}")
            r += f"reg [{memory.width-1}:0] {_get_name(data_regs[n])};\n"

    # Ports Write/Read Logic.
    # -----------------------
    for n, port in enumerate(memory.ports):
        r += f"always @(posedge {_get_name(port.clock)}) begin\n"
        # Write Logic.
        if port.we is not None:
            # Split Write Logic.
            for i in range(memory.width//port.we_granularity):
                wbit = f"[{i}]" if memory.width != port.we_granularity else ""
                r += f"\tif ({_get_name(port.we)}{wbit})\n"
                lbit =     i*port.we_granularity
                hbit = (i+1)*port.we_granularity-1
                dslc = f"[{hbit}:{lbit}]" if (memory.width != port.we_granularity) else ""
                r += f"\t\t{_get_name(memory)}[{_get_name(port.adr)}]{dslc} <= {_get_name(port.dat_w)}{dslc};\n"

        # Read Logic.
        if not port.async_read:
            # In Write-First mode, Read from Address Register.
            if port.mode in [WRITE_FIRST]:
                rd = f"\t{_get_name(adr_regs[n])} <= {_get_name(port.adr)};\n"

            # In Read-First/No Change mode:
            if port.mode in [READ_FIRST, NO_CHANGE]:
                rd = ""
                # Only Read in No-Change mode when no Write.
                if port.mode == NO_CHANGE:
                    rd += f"\tif (!{_get_name(port.we)})\n\t"
                # Read-First/No-Change Read logic.
                rd += f"\t{_get_name(data_regs[n])} <= {_get_name(memory)}[{_get_name(port.adr)}];\n"

            # Add Read-Enable Logic.
            if port.re is None:
                r += rd
            else:
                r += f"\tif ({_get_name(port.re)})\n"
                r += "\t" + rd.replace("\n\t", "\n\t\t")
        r += "end\n"

    # Ports Read Mapping.
    # -------------------
    for n, port in enumerate(memory.ports):
        # Direct (Asynchronous) Read on Async-Read mode.
        if port.async_read:
            r += f"assign {_get_name(port.dat_r)} = {_get_name(memory)}[{_get_name(port.adr)}];\n"
            continue

        # Write-First mode: Do Read through Address Register.
        if port.mode in [WRITE_FIRST]:
            r += f"assign {_get_name(port.dat_r)} = {_get_name(memory)}[{_get_name(adr_regs[n])}];\n"

        # Read-First/No-Change mode: Data already Read on Data Register.
        if port.mode in [READ_FIRST, NO_CHANGE]:
             r += f"assign {_get_name(port.dat_r)} = {_get_name(data_regs[n])};\n"
    r += "\n\n"

    return r
