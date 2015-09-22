from fractions import Fraction
from math import ceil

from migen import *

from misoc import sdram

MHz = 1000000
clk_freq = (83 + Fraction(1, 3))*MHz

clk_period_ns = 1000000000/clk_freq


def ns(t, margin=True):
    if margin:
        t += clk_period_ns/2
    return ceil(t/clk_period_ns)

sdram_phy = sdram.PhySettings(
    memtype="DDR",
    dfi_databits=64,
    nphases=2,
    rdphase=0,
    wrphase=1,
    rdcmdphase=1,
    wrcmdphase=0,
    cl=3,
    read_latency=5,
    write_latency=0
)

sdram_geom = sdram.GeomSettings(
    bankbits=2,
    rowbits=13,
    colbits=10
)
sdram_timing = sdram.TimingSettings(
    tRP=ns(15),
    tRCD=ns(15),
    tWR=ns(15),
    tWTR=2,
    tREFI=ns(7800, False),
    tRFC=ns(70),

    req_queue_size=8,
    read_time=32,
    write_time=16
)


def decode_sdram(ras_n, cas_n, we_n, bank, address):
    elts = []
    if not ras_n and cas_n and we_n:
        elts.append("ACTIVATE")
        elts.append("BANK " + str(bank))
        elts.append("ROW " + str(address))
    elif ras_n and not cas_n and we_n:
        elts.append("READ\t")
        elts.append("BANK " + str(bank))
        elts.append("COL " + str(address))
    elif ras_n and not cas_n and not we_n:
        elts.append("WRITE\t")
        elts.append("BANK " + str(bank))
        elts.append("COL " + str(address))
    elif ras_n and cas_n and not we_n:
        elts.append("BST")
    elif not ras_n and not cas_n and we_n:
        elts.append("AUTO REFRESH")
    elif not ras_n and cas_n and not we_n:
        elts.append("PRECHARGE")
        if address & 2**10:
            elts.append("ALL")
        else:
            elts.append("BANK " + str(bank))
    elif not ras_n and not cas_n and not we_n:
        elts.append("LMR")
    return elts


class CommandLogger(Module):
    def __init__(self, cmd, rw=False):
        self.cmd = cmd
        if rw:
            self.comb += self.cmd.ack.eq(1)

    def do_simulation(self, selfp):
        elts = ["@" + str(selfp.simulator.cycle_counter)]
        cmdp = selfp.cmd
        elts += decode_sdram(cmdp.ras_n, cmdp.cas_n, cmdp.we_n, cmdp.ba, cmdp.a)
        if len(elts) > 1:
            print("\t".join(elts))
    do_simulation.passive = True


class DFILogger(Module):
    def __init__(self, dfi):
        self.dfi = dfi

    def do_simulation(self, selfp):
        dfip = selfp.dfi
        for i, p in enumerate(dfip.phases):
            elts = ["@" + str(selfp.simulator.cycle_counter) + ":" + str(i)]
            elts += decode_sdram(p.ras_n, p.cas_n, p.we_n, p.bank, p.address)
            if len(elts) > 1:
                print("\t".join(elts))
    do_simulation.passive = True
