#
# 1:1 frequency-ratio Generic SDR PHY
#
# The GENSDRPHY is validated on CycloneIV (Altera) but since it does
# not use vendor-dependent code, it can also be used on other architectures.
#
# The PHY needs 2 Clock domains:
#  - sys_clk    : The System Clock domain
#  - sys_clk_ps : The System Clock domain with its phase shifted
#                 (-3ns on C4@100MHz)
#
# Assert dfi_wrdata_en and present the data
# on dfi_wrdata_mask/dfi_wrdata in the same
# cycle as the write command.
#
# Assert dfi_rddata_en in the same cycle as the read
# command. The data will come back on dfi_rddata
# 4 cycles later, along with the assertion of
# dfi_rddata_valid.
#
# This PHY only supports CAS Latency 2.
#

from migen import *
from migen.genlib.record import *
from migen.fhdl.specials import Tristate

from misoc.interconnect.dfi import *
from misoc.cores import sdram_settings


class GENSDRPHY(Module):
    def __init__(self, pads):
        addressbits = len(pads.a)
        bankbits = len(pads.ba)
        databits = len(pads.dq)

        self.settings = sdram_settings.PhySettings(
            memtype="SDR",
            dfi_databits=databits,
            nphases=1,
            rdphase=0,
            wrphase=0,
            rdcmdphase=0,
            wrcmdphase=0,
            cl=2,
            read_latency=4,
            write_latency=0
        )

        self.dfi = Interface(addressbits, bankbits, databits)

        ###

        #
        # Command/address
        #
        self.sync += [
            pads.a.eq(self.dfi.p0.address),
            pads.ba.eq(self.dfi.p0.bank),
            pads.cke.eq(self.dfi.p0.cke),
            pads.cas_n.eq(self.dfi.p0.cas_n),
            pads.ras_n.eq(self.dfi.p0.ras_n),
            pads.we_n.eq(self.dfi.p0.we_n)
        ]
        if hasattr(pads, "cs_n"):
            self.sync += pads.cs_n.eq(self.dfi.p0.cs_n)

        #
        # DQ/DQS/DM data
        #
        sd_dq_out = Signal(databits)
        drive_dq = Signal()
        self.sync += sd_dq_out.eq(self.dfi.p0.wrdata)
        self.specials += Tristate(pads.dq, sd_dq_out, drive_dq)
        self.sync += \
            If(self.dfi.p0.wrdata_en,
                pads.dm.eq(self.dfi.p0.wrdata_mask)
            ).Else(
                pads.dm.eq(0)
            )
        sd_dq_in_ps = Signal(databits)
        self.sync.sys_ps += sd_dq_in_ps.eq(pads.dq)
        self.sync += self.dfi.p0.rddata.eq(sd_dq_in_ps)

        #
        # DQ/DM control
        #
        d_dfi_wrdata_en = Signal()
        self.sync += d_dfi_wrdata_en.eq(self.dfi.p0.wrdata_en)
        self.comb += drive_dq.eq(d_dfi_wrdata_en)

        rddata_sr = Signal(4)
        self.comb += self.dfi.p0.rddata_valid.eq(rddata_sr[3])
        self.sync += rddata_sr.eq(Cat(self.dfi.p0.rddata_en, rddata_sr[:3]))
