#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from migen.genlib.misc import timeline
from migen.genlib.cdc import PulseSynchronizer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

# Xilinx 7-series ----------------------------------------------------------------------------------

class ICAP(Module, AutoCSR):
    """ICAP

    Allow sending commands to ICAPE2 of Xilinx 7-Series FPGAs, the bistream can for example be
    reloaded from SPI Flash by writing 0x00000000 at address @0x4.
    """
    def __init__(self, with_csr=True, simulation=False):
        self.addr = Signal(5)
        self.data = Signal(32)
        self.send = Signal()
        self.done = Signal()

        # # #

        # Create slow icap clk (sys_clk/16) ---------------------------------------------------------
        self.clock_domains.cd_icap = ClockDomain()
        icap_clk_counter = Signal(4)
        self.sync += icap_clk_counter.eq(icap_clk_counter + 1)
        self.sync += self.cd_icap.clk.eq(icap_clk_counter[3])

        # Resynchronize send pulse to icap domain ---------------------------------------------------
        ps_send = PulseSynchronizer("sys", "icap")
        self.submodules += ps_send
        self.comb += ps_send.i.eq(self.send)

        # Generate icap bitstream write sequence
        self._csib = _csib = Signal(reset=1)
        self._i    = _i =  Signal(32)
        _addr      = self.addr << 13
        _data      = self.data
        self.sync.icap += [
            _i.eq(0xffffffff), # dummy
            timeline(ps_send.o, [
                (1,  [_csib.eq(1), self.done.eq(0)]),
                (2,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (3,  [_csib.eq(0), _i.eq(0xaa995566)]),         # sync word
                (4,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (5,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (6,  [_csib.eq(0), _i.eq(0x30000001 | _addr)]), # write command
                (7,  [_csib.eq(0), _i.eq(_data)]),              # write value
                (8,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (9,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (10, [_csib.eq(0), _i.eq(0x30008001)]),         # write to cmd register
                (11, [_csib.eq(0), _i.eq(0x0000000d)]),         # desync command
                (12, [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (13, [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (14, [_csib.eq(1), self.done.eq(1)]),
            ])
        ]

        # ICAP instance
        if not simulation:
            self.specials += [
                Instance("ICAPE2",
                    p_ICAP_WIDTH = "X32",
                    i_CLK   = ClockSignal("icap"),
                    i_CSIB  = _csib,
                    i_RDWRB = 0,
                    i_I     = Cat(*[_i[8*i:8*(i+1)][::-1] for i in range(4)]),
                )
            ]

        # CSR
        if with_csr:
            self.add_csr()

    def add_csr(self):
        self._addr = CSRStorage(5,  reset_less=True, description="ICAP Write Address.")
        self._data = CSRStorage(32, reset_less=True, description="ICAP Write Data.")
        self._send = CSRStorage(description="ICAP Control.\n\n Write ``1`` send a write command to the ICAP.")
        self._done = CSRStatus(reset=1, description="ICAP Status.\n\n Write command done when read as ``1``.")

        self.comb += [
            self.addr.eq(self._addr.storage),
            self.data.eq(self._data.storage),
            self.send.eq(self._send.re),
            self._done.status.eq(self.done)
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
            self.addr.eq(0x4),
            self.data.eq(0xf),
            self.send.eq(1),
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
            self.specials += [
                Instance("ICAPE2",
                    p_ICAP_WIDTH="X32",
                    i_CLK=ClockSignal("icap"),
                    i_CSIB=_csib,
                    i_RDWRB=0,
                    i_I=Cat(*[_i[8*i:8*(i+1)][::-1] for i in range(4)]),
                )
            ]

    def add_timing_constraints(self, platform, sys_clk_freq, sys_clk):
        platform.add_period_constraint(self.cd_icap.clk, 16*1e9/sys_clk_freq)
        platform.add_false_path_constraints(self.cd_icap.clk, sys_clk)
