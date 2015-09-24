# This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

# SDRAM simulation PHY at DFI level
# tested with SDR/DDR/DDR2/LPDDR/DDR3
# TODO:
# - add $display support to Migen and manage timing violations?

from migen import *
from migen.fhdl.specials import *
from misoc.mem.sdram.phy.dfi import *
from misoc.mem import sdram


class Bank(Module):
    def __init__(self, data_width, nrows, ncols, burst_length):
        self.activate = Signal()
        self.activate_row = Signal(max=nrows)
        self.precharge = Signal()

        self.write = Signal()
        self.write_col = Signal(max=ncols)
        self.write_data = Signal(data_width)
        self.write_mask = Signal(data_width//8)

        self.read = Signal()
        self.read_col = Signal(max=ncols)
        self.read_data = Signal(data_width)

        ###
        active = Signal()
        row = Signal(max=nrows)

        self.sync += \
            If(self.precharge,
                active.eq(0),
            ).Elif(self.activate,
                active.eq(1),
                row.eq(self.activate_row)
            )

        self.specials.mem = mem = Memory(data_width, nrows*ncols//burst_length)
        self.specials.write_port = write_port = mem.get_port(write_capable=True,
                                                             we_granularity=8)
        self.specials.read_port = read_port = mem.get_port(async_read=True)
        self.comb += [
            If(active,
                write_port.adr.eq(row*ncols | self.write_col),
                write_port.dat_w.eq(self.write_data),
                write_port.we.eq(Replicate(self.write, data_width//8) & ~self.write_mask),
                If(self.read,
                    read_port.adr.eq(row*ncols | self.read_col),
                    self.read_data.eq(read_port.dat_r)
                )
            )
        ]


class DFIPhase(Module):
    def __init__(self, dfi, n):
        phase = getattr(dfi, "p"+str(n))

        self.bank = phase.bank
        self.address = phase.address

        self.wrdata = phase.wrdata
        self.wrdata_mask = phase.wrdata_mask

        self.rddata = phase.rddata
        self.rddata_valid = phase.rddata_valid

        self.activate = Signal()
        self.precharge = Signal()
        self.write = Signal()
        self.read = Signal()

        ###
        self.comb += [
            If(~phase.cs_n & ~phase.ras_n & phase.cas_n,
                self.activate.eq(phase.we_n),
                self.precharge.eq(~phase.we_n)
            ),
            If(~phase.cs_n & phase.ras_n & ~phase.cas_n,
                self.write.eq(~phase.we_n),
                self.read.eq(phase.we_n)
            )
        ]


class SDRAMPHYSim(Module):
    def __init__(self, module, settings):
        if settings.memtype in ["SDR"]:
            burst_length = settings.nphases*1  # command multiplication*SDR
        elif settings.memtype in ["DDR", "LPDDR", "DDR2", "DDR3"]:
            burst_length = settings.nphases*2  # command multiplication*DDR

        addressbits = module.geom_settings.addressbits
        bankbits = module.geom_settings.bankbits
        rowbits = module.geom_settings.rowbits
        colbits = module.geom_settings.colbits

        self.settings = settings
        self.module = module

        self.dfi = Interface(addressbits, bankbits, self.settings.dfi_databits, self.settings.nphases)

        ###
        nbanks = 2**bankbits
        nrows = 2**rowbits
        ncols = 2**colbits
        data_width = self.settings.dfi_databits*self.settings.nphases

        # DFI phases
        phases = [DFIPhase(self.dfi, n) for n in range(self.settings.nphases)]
        self.submodules += phases

        # banks
        banks = [Bank(data_width, nrows, ncols, burst_length) for i in range(nbanks)]
        self.submodules += banks

        # connect DFI phases to banks (cmds, write datapath)
        for nb, bank in enumerate(banks):
            # bank activate
            activates = Signal(len(phases))
            cases = {}
            for np, phase in enumerate(phases):
                self.comb += activates[np].eq(phase.activate)
                cases[2**np] = [
                    bank.activate.eq(phase.bank == nb),
                    bank.activate_row.eq(phase.address)
                ]
            self.comb += Case(activates, cases)

            # bank precharge
            precharges = Signal(len(phases))
            cases = {}
            for np, phase in enumerate(phases):
                self.comb += precharges[np].eq(phase.precharge)
                cases[2**np] = [
                    bank.precharge.eq((phase.bank == nb) | phase.address[10])
                ]
            self.comb += Case(precharges, cases)

            # bank writes
            writes = Signal(len(phases))
            cases = {}
            for np, phase in enumerate(phases):
                self.comb += writes[np].eq(phase.write)
                cases[2**np] = [
                    bank.write.eq(phase.bank == nb),
                    bank.write_col.eq(phase.address)
                ]
            self.comb += Case(writes, cases)
            self.comb += [
                bank.write_data.eq(Cat(*[phase.wrdata for phase in phases])),
                bank.write_mask.eq(Cat(*[phase.wrdata_mask for phase in phases]))
            ]

            # bank reads
            reads = Signal(len(phases))
            cases = {}
            for np, phase in enumerate(phases):
                self.comb += reads[np].eq(phase.read)
                cases[2**np] = [
                    bank.read.eq(phase.bank == nb),
                    bank.read_col.eq(phase.address)
            ]
            self.comb += Case(reads, cases)

        # connect banks to DFI phases (cmds, read datapath)
        banks_read = Signal()
        banks_read_data = Signal(data_width)
        self.comb += [
            banks_read.eq(optree("|", [bank.read for bank in banks])),
            banks_read_data.eq(optree("|", [bank.read_data for bank in banks]))
        ]
        # simulate read latency
        for i in range(self.settings.read_latency):
            new_banks_read = Signal()
            new_banks_read_data = Signal(data_width)
            self.sync += [
                new_banks_read.eq(banks_read),
                new_banks_read_data.eq(banks_read_data)
            ]
            banks_read = new_banks_read
            banks_read_data = new_banks_read_data

        self.comb += [
            Cat(*[phase.rddata_valid for phase in phases]).eq(banks_read),
            Cat(*[phase.rddata for phase in phases]).eq(banks_read_data)
        ]
