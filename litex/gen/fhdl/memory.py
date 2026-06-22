#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2021-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.structure    import *
from migen.fhdl.module       import *
from migen.fhdl.bitcontainer import bits_for
from migen.fhdl.tools        import *
from migen.fhdl.verilog      import _printexpr as verilog_printexpr
from migen.fhdl.specials     import *

# LiteX Memory Verilog Generation ------------------------------------------------------------------

def _memory_generate_verilog(name, memory, namespace, add_data_file):
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

    # Memory Description.
    # -------------------
    r += "//" + "-"*78 + "\n"
    r += f"// Memory {_get_name(memory)}: {memory.depth}-words x {memory.width}-bit\n"
    r += "//" + "-"*78 + "\n"
    for n, port in enumerate(memory.ports):
        r += f"// Port {n} | "
        if port.dat_r is None:
            r += "Read: ----  | "
        elif port.async_read:
            r += "Read: Async | "
        else:
            r += "Read: Sync  | "
        if port.we is None:
            r += "Write: ---- | "
        else:
            r += "Write: Sync | "
            r += "Mode: "
            if port.mode == WRITE_FIRST:
                r += "Write-First"
            elif port.mode == READ_FIRST:
                r += "Read-First "
            elif port.mode == NO_CHANGE:
                r += "No-Change"
            if port.we_granularity != 0:
                r += f" | Write-Granularity: {port.we_granularity}"
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
        if port.dat_r is None or port.async_read:
            continue

        split_write = port.we is not None and port.we_granularity != 0

        # Create Address Register for split Write-First mode.
        if port.mode in [WRITE_FIRST] and split_write:
            adr_regs[n] = Signal(name_override=f"{_get_name(memory)}_adr{n}")
            r += f"reg [{bits_for(memory.depth-1)-1}:0] {_get_name(adr_regs[n])};\n"

        # Create Data Register for Sync Read.
        if port.mode in [READ_FIRST, NO_CHANGE] or (port.mode in [WRITE_FIRST] and not split_write):
            data_regs[n] = Signal(name_override=f"{_get_name(memory)}_dat{n}")
            r += f"reg [{memory.width-1}:0] {_get_name(data_regs[n])};\n"

    # Ports Write/Read Logic.
    # -----------------------
    for n, port in enumerate(memory.ports):
        split_write = port.we is not None and port.we_granularity != 0

        # This block has to be named to use a integer variable in it.
        rd = f" : {_get_name(Signal(name_override='mem_write_block'))}" if split_write else ""
        r += f"always @(posedge {_get_name(port.clock)}) begin{rd}\n"
        we_index = None

        # Write Logic.
        if port.we is not None:
            # Split Write Logic.
            if split_write:
                m = memory.width//port.we_granularity
                we_index = Signal(name_override="we_index")
                we_index_name = _get_name(we_index)

                r += f"\tinteger {we_index_name};\n"
                sl = f"[{we_index_name}*{port.we_granularity} +: {port.we_granularity}]"
                r += f"\tfor({we_index_name} = 0; {we_index_name} < {m}; {we_index_name}={we_index_name}+1)\n"
                r += f"\t\tif ({_get_name(port.we)}[{we_index_name}])\n"
                r += f"\t\t\t{_get_name(memory)}[{_get_name(port.adr)}]{sl} <= {_get_name(port.dat_w)}{sl};\n"
            else:
                r += f"\tif ({_get_name(port.we)})\n"
                r += f"\t\t{_get_name(memory)}[{_get_name(port.adr)}] <= {_get_name(port.dat_w)};\n"

        # Read Logic.
        if port.dat_r is not None and not port.async_read:
            # In Write-First mode, Read the written Data or Memory Data.
            if port.mode in [WRITE_FIRST]:
                if split_write:
                    rd = f"\t{_get_name(adr_regs[n])} <= {_get_name(port.adr)};\n"
                elif port.we is not None:
                    rd = f"\tif ({_get_name(port.we)})\n"
                    rd += f"\t\t{_get_name(data_regs[n])} <= {_get_name(port.dat_w)};\n"
                    rd += "\telse\n"
                    rd += f"\t\t{_get_name(data_regs[n])} <= {_get_name(memory)}[{_get_name(port.adr)}];\n"
                else:
                    rd = f"\t{_get_name(data_regs[n])} <= {_get_name(memory)}[{_get_name(port.adr)}];\n"

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
                r += f"\tif ({_get_name(port.re)}) begin\n"
                for line in rd.splitlines():
                    r += "\t" + line + "\n"
                r += "\tend\n"
        r += "end\n"

    # Ports Read Mapping.
    # -------------------
    for n, port in enumerate(memory.ports):
        if port.dat_r is None:
            continue

        # Direct (Asynchronous) Read on Async-Read mode.
        if port.async_read:
            r += f"assign {_get_name(port.dat_r)} = {_get_name(memory)}[{_get_name(port.adr)}];\n"
            continue

        split_write = port.we is not None and port.we_granularity != 0

        # Write-First split-write mode: Do Read through Address Register.
        if port.mode in [WRITE_FIRST] and split_write:
            r += f"assign {_get_name(port.dat_r)} = {_get_name(memory)}[{_get_name(adr_regs[n])}];\n"

        # Sync-Read modes: Data already Read on Data Register.
        if port.mode in [READ_FIRST, NO_CHANGE] or (port.mode in [WRITE_FIRST] and not split_write):
             r += f"assign {_get_name(port.dat_r)} = {_get_name(data_regs[n])};\n"
    r += "\n\n"

    return r
