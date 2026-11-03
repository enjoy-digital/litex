#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Generator of the opaque scaler IP of the opaque_gain and ecpix5_scaler tasks (hidden from the
# agent): the RTL of the IP, converted to Verilog and synthesized/flattened/anonymized with Yosys
# into <task>/workspace/ip/acme_scaler.v. Regenerate with:
#   python3 test/agent_eval/tasks/opaque_gain/ip_src/gen_ip.py
#
# Netlist revisions vs rev 1.0 (the datasheet given to the agent):
# - opaque_gain   (rev 1.1): GAIN is Q4.12 (reset 0x1000), not Q8.8 (reset 0x0100); new LIMIT
#   register at 0x18 (reserved in 1.0), reset 0x0fff: the output clamps at 4095 unless LIMIT is
#   written; ID 0xac5c0101.
# - ecpix5_scaler (rev 1.2): GAIN is Q2.14 (reset 0x4000), LIMIT resets to 0x3fff; ID 0xac5c0102.

import os
import subprocess
import tempfile

from migen import *
from migen.fhdl.verilog import convert

REVISIONS = {
    "opaque_gain"   : dict(ident=0xac5c0101, frac=12, limit_reset=0x0fff),
    "ecpix5_scaler" : dict(ident=0xac5c0102, frac=14, limit_reset=0x3fff),
}

class AcmeScaler(Module):
    def __init__(self, ident, frac, limit_reset):
        self.adr   = Signal(3)
        self.we    = Signal()
        self.dat_w = Signal(32)
        self.dat_r = Signal(32)

        # # #

        enable = Signal()
        gain   = Signal(16, reset=1 << frac)
        offset = Signal(16)
        limit  = Signal(16, reset=limit_reset)
        din    = Signal(16)
        dout   = Signal(16)
        valid  = Signal()

        # Registers.
        self.sync += [
            If(self.we,
                Case(self.adr, {
                    1: enable.eq(self.dat_w[0]),
                    2: gain.eq(self.dat_w[:16]),
                    3: offset.eq(self.dat_w[:16]),
                    6: limit.eq(self.dat_w[:16]),
                })
            )
        ]

        # Datapath (2 stages): y = min(((x*gain) >> frac) + offset, limit).
        start  = Signal()
        stage1 = Signal()
        prod   = Signal(32)
        self.sync += [
            start.eq(0),
            If(self.we & (self.adr == 4),
                din.eq(self.dat_w[:16]),
                start.eq(1),
                valid.eq(0),
            ),
            stage1.eq(start),
            prod.eq(din*gain),
            If(stage1,
                If(~enable,
                    dout.eq(0),
                ).Elif((prod[frac:] + offset) > limit,
                    dout.eq(limit),
                ).Else(
                    dout.eq(prod[frac:] + offset),
                ),
                valid.eq(1),
            ),
        ]

        # Read mux.
        self.comb += Case(self.adr, {
            0: self.dat_r.eq(ident),
            1: self.dat_r.eq(enable),
            2: self.dat_r.eq(gain),
            3: self.dat_r.eq(offset),
            4: self.dat_r.eq(din),
            5: self.dat_r.eq(dout),
            6: self.dat_r.eq(limit),
            7: self.dat_r.eq(valid),
        })

YOSYS_SCRIPT = """
read_verilog {rtl}
hierarchy -top acme_scaler
synth -flatten -top acme_scaler
abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX
opt_clean -purge
rename -hide w:*_*
rename -hide w:\\\\*
rename -enumerate -pattern n%_ w:$*
rename -enumerate -pattern c%_ c:*
opt_clean -purge
write_verilog -noattr -norename {out}
"""

def generate(task, **kwargs):
    ip  = AcmeScaler(**kwargs)
    ios = {ip.adr, ip.we, ip.dat_w, ip.dat_r}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", task, "workspace", "ip", "acme_scaler.v")
    out = os.path.normpath(out)
    with tempfile.TemporaryDirectory() as tmp:
        rtl = os.path.join(tmp, "acme_scaler_rtl.v")
        convert(ip, ios=ios, name="acme_scaler").write(rtl)
        ys = os.path.join(tmp, "gen.ys")
        with open(ys, "w") as f:
            f.write(YOSYS_SCRIPT.format(rtl=rtl, out=os.path.join(tmp, "net.v")))
        subprocess.run(["yosys", "-q", "-s", ys], check=True)
        with open(os.path.join(tmp, "net.v")) as f:
            net = f.read()
    with open(out, "w") as f:
        f.write("// ACME scaler IP - synthesized netlist, do not edit.\n")
        f.write(net)
    print(f"{out}: {len(net.splitlines())} lines")

def main():
    for task, revision in REVISIONS.items():
        generate(task, **revision)

if __name__ == "__main__":
    main()
