#
# This file is part of LiteX.
#
# Copyright (c) 2019-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from enum import IntEnum

from migen import *

from migen.genlib.cdc import PulseSynchronizer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

# Constants ----------------------------------------------------------------------------------------

# ICAP Words

ICAP_DUMMY = 0xffffffff
ICAP_SYNC  = 0xaa995566
ICAP_NOOP  = 0x20000000
ICAP_WRITE = 0x30000000
ICAP_READ  = 0x28000000

# Configuration Registers (from UG470).

class ICAPRegisters(IntEnum):
    CRC     = 0b00000 # CRC Register.
    FAR     = 0b00001 # Frame Address Register.
    FDRI    = 0b00010 # Frame Data Register, Input Register.
    FDRO    = 0b00011 # Frame Data Register, Output Register.
    CMD     = 0b00100 # Command Register.
    CTL0    = 0b00101 # Control Register 0.
    MASK    = 0b00110 # Masking Register for CTL0 and CTL1.
    STAT    = 0b00111 # Status Register.
    LOUT    = 0b01000 # Legacy Output Register for daisy chain.
    COR0    = 0b01001 # Configuration Option Register 0.
    MFWR    = 0b01010 # Multiple Frame Write Register.
    CBC     = 0b01011 # Initial CBC Value Register.
    IDCODE  = 0b01100 # Device ID Register.
    AXSS    = 0b01101 # User Access Register.
    COR1    = 0b01110 # Configuration Option Register 1.
    WBSTAR  = 0b10000 # Warm Boot Start Address Register.
    TIMER   = 0b10001 # Watchdog Timer Register.
    BOOTSTS = 0b10110 # Boot History Status Register.
    CTL1    = 0b11000 # Control Register 1.
    BSPI    = 0b11111 # BPI/SPI Configuration Options Register.

# Commands (from UG470).

class ICAPCMDs(IntEnum):
    MFW       = 0b00010 # Multiple Frame Write.
    LFRM      = 0b00011 # Last Frame.
    RCFG      = 0b00100 # Reads Configuration Data.
    START     = 0b00101 # Begins the Startup Sequence.
    RCAP      = 0b00110 # Resets the CAPTURE signal.
    RCRC      = 0b00111 # Resets CRC.
    AGHIGH    = 0b01000 # Asserts the GHIGH_B signal.
    SWITCH    = 0b01001 # Switches the CCLK frequency.
    GRESTORE  = 0b01010 # Pulses the GRESTORE signal.
    SHUTDOWN  = 0b01011 # Begin Shutdown Sequence.
    GCAPTURE  = 0b01100 # Pulses GCAPTURE.
    DESYNC    = 0b01101 # Resets the DALIGN signal.
    IPROG     = 0b01111 # Internal PROG for triggering a warm boot.
    CRCC      = 0b10000 # Recalculates the first readback CRC value after reconfiguration
    LTIMER    = 0b10001 # Reload Watchdog timer.
    BSPI_READ = 0b10010 # BPI/SPI re-initiate bitstream read.
    FALL_EDGE = 0b10011 # Switch to negative-edge clocking.

# Xilinx 7-series ----------------------------------------------------------------------------------

class ICAP(Module, AutoCSR):
    """ICAP

    Allow writing/reading ICAPE2's registers of Xilinx 7-Series FPGAs.

    A warm boot can for example be triggered by writing IPROG CMD (0xf) to CMD register (0b100).
    """
    def __init__(self, with_csr=True, simulation=False):
        self.write      = Signal()
        self.read       = Signal()
        self.done       = Signal()
        self.addr       = Signal(5)
        self.write_data = Signal(32)
        self.read_data  = Signal(32)

        # # #

        # Create slow ICAP Clk (sys_clk/16).
        self.clock_domains.cd_icap = ClockDomain()
        icap_clk_counter = Signal(4)
        self.sync += icap_clk_counter.eq(icap_clk_counter + 1)
        self.sync += self.cd_icap.clk.eq(icap_clk_counter[3])

        # Generate ICAP bitstream sequence.
        self._csib  = _csib  = Signal(reset=1)
        self._rdwrb = _rdwrb = Signal()
        self._i     = _i     = Signal(32)
        self._o     = _o     = Signal(32)

        count = Signal(4)
        fsm   = FSM(reset_state="WAIT")
        fsm   = ClockDomainsRenamer("icap")(fsm)
        fsm   = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(~(self.write | self.read))

        # Wait User Command.
        fsm.act("WAIT",
            # Set ICAP in IDLE state.
            _csib.eq(1),
            _rdwrb.eq(0),
            _i.eq(ICAP_DUMMY),

            # Wait User Command.
            If(self.write | self.read,
                NextValue(count, 0),
                NextState("SYNC")
            )
        )

        # Send ICAP Synchronization sequence.
        fsm.act("SYNC",
            _csib.eq(0),
            _rdwrb.eq(0),
            Case(count, {
                0 : _i.eq(ICAP_NOOP), # No Op.
                1 : _i.eq(ICAP_SYNC), # Sync Word.
                2 : _i.eq(ICAP_NOOP), # No Op.
                3 : _i.eq(ICAP_NOOP), # No Op.
            }),
            NextValue(count, count + 1),
            If(count == (4-1),
                NextValue(count, 0),
                If(self.write,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )

        # Send ICAP Write sequence.
        fsm.act("WRITE",
            _csib.eq(0),
            _rdwrb.eq(0),
            Case(count, {
                0 : _i.eq(ICAP_WRITE | (self.addr  << 13) | 1), # Set Register.
                1 : _i.eq(self.write_data),                     # Set Register Data.
                2 : _i.eq(ICAP_NOOP),                           # No Op.
                3 : _i.eq(ICAP_NOOP),                           # No Op.
            }),
            NextValue(count, count + 1),
            If(count == (4-1),
                NextValue(count, 0),
                NextState("DESYNC")
            )
        )

        # Send ICAP Read sequence.
        fsm.act("READ",
            _csib.eq(0),
            _rdwrb.eq(0),
            Case(count, {
                0 : _i.eq(ICAP_READ | (self.addr  << 13) | 1),     # Set Register.
                1 : _i.eq(ICAP_NOOP),                              # No Op.
                2 : _i.eq(ICAP_NOOP),                              # No Op.
                3 : [_csib.eq(1), _rdwrb.eq(1), _i.eq(ICAP_NOOP)], # Idle + No Op.
                4 : [_csib.eq(0), _rdwrb.eq(1), _i.eq(ICAP_NOOP)], # No Op.
                5 : [_csib.eq(0), _rdwrb.eq(1), _i.eq(ICAP_NOOP)], # No Op.
                6 : [_csib.eq(0), _rdwrb.eq(1), _i.eq(ICAP_NOOP)], # No Op.
                7 : [_csib.eq(0), _rdwrb.eq(1), _i.eq(ICAP_NOOP)], # No Op.
                8 : [_csib.eq(0), _rdwrb.eq(1), _i.eq(ICAP_NOOP)], # No Op.
            }),
            NextValue(count, count + 1),
            If(count == (8-1),
                NextValue(self.read_data, _o),
                NextValue(count, 0),
                NextState("DESYNC")
            )
        )

        # Send ICAP Desynchronization sequence.
        fsm.act("DESYNC",
            _csib.eq(0),
            _rdwrb.eq(0),
            Case(count, {
                0 : _i.eq(ICAP_WRITE | (ICAPRegisters.CMD << 13) | 1), # Write to CMD Register.
                1 : _i.eq(ICAPCMDs.DESYNC),                            # DESYNC CMD.
                2 : _i.eq(ICAP_NOOP),                                  # No Op.
                3 : _i.eq(ICAP_NOOP),                                  # No Op.
            }),
            NextValue(count, count + 1),
            If(count == (4-1),
                NextValue(count, 0),
                NextState("DONE")
            )
        )

        # Done
        fsm.act("DONE",
            # Set ICAP in IDLE state.
            _csib.eq(1),
            _rdwrb.eq(0),
            _i.eq(ICAP_DUMMY),
            self.done.eq(1)
        )

        # ICAP Instance.
        if not simulation:
            _i_icape2 = Signal(32)
            _o_icape2 = Signal(32)
            self.comb += _i_icape2.eq(Cat(*[_i[8*i:8*(i+1)][::-1] for i in range(4)])),
            self.comb += _o.eq(Cat(*[_o_icape2[8*i:8*(i+1)][::-1] for i in range(4)])),
            self.specials += Instance("ICAPE2",
                p_ICAP_WIDTH = "X32",
                i_CLK   = ClockSignal("icap"),
                i_CSIB  = _csib,
                i_RDWRB = _rdwrb,
                i_I     = _i_icape2,
                o_O     = _o_icape2,
            )

        # CSR.
        if with_csr:
            self.add_csr()

    def add_csr(self):
        self._addr  = CSRStorage(5,  reset_less=True, description="ICAP Address.")
        self._data  = CSRStorage(32, reset_less=True, description="ICAP Write/Read Data.", write_from_dev=True)
        self._write = CSRStorage(description="ICAP Control.\n\n Write ``1`` send a write to the ICAP.")
        self._done  = CSRStatus(reset=1, description="ICAP Status.\n\n Write command done when read as ``1``.")
        self._read  = CSRStorage(description="ICAP Control.\n\n Read ``1`` send a read from the ICAP.")

        self.comb += [
            self.addr.eq(self._addr.storage),
            self.write_data.eq(self._data.storage),
            self.write.eq(self._write.storage),
            self._done.status.eq(self.done),
            self.read.eq(self._read.storage),
            If(self.done,
                self._data.we.eq(1),
                self._data.dat_w.eq(self.read_data)
            )
        ]

    def add_reload(self):
        self.reload = Signal() # Set to 1 to reload FPGA from logic.

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.reload,
                NextState("RELOAD")
            )
        )
        fsm.act("RELOAD",
            self.addr.eq(ICAPRegisters.CMD),
            self.write.eq(1),
            self.write_data.eq(ICAPCMDs.IPROG),
        )

    def add_timing_constraints(self, platform, sys_clk_freq, sys_clk):
        platform.add_period_constraint(self.cd_icap.clk, 16*1e9/sys_clk_freq)
        platform.add_false_path_constraints(self.cd_icap.clk, sys_clk)


class ICAPBitstream(Module, AutoCSR):
    """ICAP Bitstream

    Allow sending bitstreams to ICAPE2 of Xilinx 7-Series FPGAs.

    The CPU can push stream of data to the ICAPE2 by reading `sink_ready` CSR to verify that there is
    space available in the FIFO; then write the data to `sink_data` register. Each word written to the
    FIFO is transmitted to the ICAPE2 using the slow icap_clk (with expected bit/byte reordering).

    The CPU accesses/FIFO must be fast/large enough to ensure there is no gap in the stream sent to
    the ICAPE2.
    """
    def __init__(self, fifo_depth=8, icap_clk_div=4, simulation=False):
        self.sink_data  = CSRStorage(32, reset_less=True)
        self.sink_ready = CSRStatus()

        # # #

        # Create slow icap_clk (sys_clk/4) ---------------------------------------------------------
        icap_clk_counter = Signal(log2_int(icap_clk_div))
        self.clock_domains.cd_icap = ClockDomain()
        self.sync += icap_clk_counter.eq(icap_clk_counter + 1)
        self.sync += self.cd_icap.clk.eq(icap_clk_counter[-1])

        # FIFO (sys_clk to icap_clk) ---------------------------------------------------------------
        fifo = stream.AsyncFIFO([("data", 32)], fifo_depth)
        fifo = ClockDomainsRenamer({"write": "sys", "read": "icap"})(fifo)
        self.submodules += fifo
        self.comb += [
            fifo.sink.valid.eq(self.sink_data.re),
            fifo.sink.data.eq(self.sink_data.storage),
            self.sink_ready.status.eq(fifo.sink.ready),
        ]

        # Generate ICAP commands -------------------------------------------------------------------
        self._csib = _csib = Signal(reset=1)
        self._i    =    _i = Signal(32, reset=0xffffffff)
        self.comb += [
            fifo.source.ready.eq(1),
            If(fifo.source.valid,
                _csib.eq(0),
                _i.eq(fifo.source.data)
            )
        ]

        # ICAP instance ----------------------------------------------------------------------------
        if not simulation:
            self.specials += Instance("ICAPE2",
                p_ICAP_WIDTH = "X32",
                i_CLK   = ClockSignal("icap"),
                i_CSIB  = _csib,
                i_RDWRB = 0,
                i_I     = Cat(*[_i[8*i:8*(i+1)][::-1] for i in range(4)])
            )

    def add_timing_constraints(self, platform, sys_clk_freq, sys_clk):
        platform.add_period_constraint(self.cd_icap.clk, 16*1e9/sys_clk_freq)
        platform.add_false_path_constraints(self.cd_icap.clk, sys_clk)
