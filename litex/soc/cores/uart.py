#
# This file is part of LiteX.
#
# Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

from math import log2

from migen import *
from migen.genlib.record import Record
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import stream

# Common -------------------------------------------------------------------------------------------

def UARTPads():
    return Record([("tx", 1), ("rx", 1)])

class UARTInterface:
    def __init__(self):
        self.sink   = stream.Endpoint([("data", 8)])
        self.source = stream.Endpoint([("data", 8)])

# RS232 PHY ----------------------------------------------------------------------------------------

RS232_IDLE  = 1
RS232_START = 0
RS232_STOP  = 1

class RS232PHYInterface(UARTInterface): pass


class RS232ClkPhaseAccum(Module):
    def __init__(self, tuning_word, mode="tx"):
        assert mode in ["tx", "rx"]
        self.enable = Signal()
        self.tick   = Signal()

        # # #

        phase = Signal(32, reset_less=True)
        self.sync += Cat(phase, self.tick).eq(tuning_word if mode == "tx" else 2**31)
        self.sync += If(self.enable, Cat(phase, self.tick).eq(phase + tuning_word))


class RS232PHYTX(Module):
    def __init__(self, pads, tuning_word):
        self.sink = sink = stream.Endpoint([("data", 8)])

        # # #

        pads.tx.reset = 1

        data  = Signal(8, reset_less=True)
        count = Signal(4, reset_less=True)

        # Clock Phase Accumulator.
        clk_phase_accum = RS232ClkPhaseAccum(tuning_word, mode="tx")
        self.submodules += clk_phase_accum


        # FSM
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # Reset Count and set TX to Idle.
            NextValue(count,   0),
            NextValue(pads.tx, RS232_IDLE),
            # Wait for TX data to transmit.
            If(sink.valid,
                NextValue(pads.tx, RS232_START),
                NextValue(data, sink.data),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            # Enable Clock Phase Accumulator.
            clk_phase_accum.enable.eq(1),
            # On Clock Phase Accumulator tick:
            If(clk_phase_accum.tick,
                # Set TX data.
                NextValue(pads.tx, data),
                # Increment Count.
                NextValue(count, count + 1),
                # Shift TX data.
                NextValue(data, Cat(data[1:], RS232_STOP)),
                # When 10-bit have been transmitted...
                If(count == (10 - 1),
                    # Ack sink and return to Idle.
                    sink.ready.eq(1),
                    NextState("IDLE")
                )
            )
        )


class RS232PHYRX(Module):
    def __init__(self, pads, tuning_word):
        self.source = source = stream.Endpoint([("data", 8)])

        # # #

        data  = Signal(8, reset_less=True)
        count = Signal(4, reset_less=True)

        # Clock Phase Accumulator.
        clk_phase_accum = RS232ClkPhaseAccum(tuning_word, mode="rx")
        self.submodules += clk_phase_accum

        # Resynchronize pads.rx and generate delayed version.
        rx   = Signal()
        rx_d = Signal()
        self.specials += MultiReg(pads.rx, rx)
        self.sync += rx_d.eq(rx)

        # FSM
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # Reset Count.
            NextValue(count, 0),
            # Wait for RX Start bit.
            If((rx == RS232_START) & (rx_d == RS232_IDLE),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            # Enable Clock Phase Accumulator.
            clk_phase_accum.enable.eq(1),
            # On Clock Phase Accumulator tick:
            If(clk_phase_accum.tick,
                # Increment Count.
                NextValue(count, count + 1),
                # Shift RX data.
                NextValue(data, Cat(data[1:], rx)),
                # When 10-bit have been received...
                If(count == (10 - 1),
                    # Produce data (but only when RX Stop bit is seen).
                    source.valid.eq(rx == RS232_STOP),
                    source.data.eq(data),
                    NextState("IDLE")
                )
            )
        )


class RS232PHY(Module, AutoCSR):
    def __init__(self, pads, clk_freq, baudrate=115200, with_dynamic_baudrate=False):
        tuning_word = int((baudrate/clk_freq)*2**32)
        if with_dynamic_baudrate:
            self._tuning_word  = CSRStorage(32, reset=tuning_word)
            tuning_word = self._tuning_word.storage
        self.submodules.tx = RS232PHYTX(pads, tuning_word)
        self.submodules.rx = RS232PHYRX(pads, tuning_word)
        self.sink, self.source = self.tx.sink, self.rx.source


class RS232PHYMultiplexer(Module):
    def __init__(self, phys, phy):
        self.sel = Signal(max=len(phys))

        # # #

        cases = {}
        for n in range(len(phys)):
            # don't stall uarts when not selected
            self.comb += phys[n].sink.ready.eq(1)
            # connect core to phy
            cases[n] = [
                phy.source.connect(phys[n].source),
                phys[n].sink.connect(phy.sink)
            ]
        self.comb += Case(self.sel, cases)


class RS232PHYModel(Module):
    def __init__(self, pads):
        self.sink   = stream.Endpoint([("data", 8)])
        self.source = stream.Endpoint([("data", 8)])

        self.comb += [
            pads.source_valid.eq(self.sink.valid),
            pads.source_data.eq(self.sink.data),
            self.sink.ready.eq(pads.source_ready),

            self.source.valid.eq(pads.sink_valid),
            self.source.data.eq(pads.sink_data),
            pads.sink_ready.eq(self.source.ready)
        ]

# UART ---------------------------------------------------------------------------------------------

def _get_uart_fifo(depth, sink_cd="sys", source_cd="sys"):
    if sink_cd != source_cd:
        fifo = stream.AsyncFIFO([("data", 8)], depth)
        return ClockDomainsRenamer({"write": sink_cd, "read": source_cd})(fifo)
    else:
        return stream.SyncFIFO([("data", 8)], depth, buffered=True)

def UARTPHY(pads, clk_freq, baudrate):
    # FT245 Asynchronous FIFO mode (baudrate ignored)
    if hasattr(pads, "rd_n") and hasattr(pads, "wr_n"):
        from litex.soc.cores.usb_fifo import FT245PHYAsynchronous
        return FT245PHYAsynchronous(pads, clk_freq)
    # RS232
    else:
        return  RS232PHY(pads, clk_freq, baudrate)

class UART(Module, AutoCSR, UARTInterface):
    def __init__(self, phy=None,
            tx_fifo_depth = 16,
            rx_fifo_depth = 16,
            rx_fifo_rx_we = False,
            phy_cd        = "sys"):
        self._rxtx    = CSR(8) # RX/TX Data.
        self._txfull  = CSRStatus(description="TX FIFO Full.")
        self._rxempty = CSRStatus(description="RX FIFO Empty.")

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourceProcess(edge="rising")
        self.ev.rx = EventSourceProcess(edge="rising")
        self.ev.finalize()

        self._txempty = CSRStatus(description="TX FIFO Empty.")
        self._rxfull  = CSRStatus(description="RX FIFO Full.")

        # # #

        UARTInterface.__init__(self)

        # PHY
        # ---
        if phy is not None:
            self.comb += phy.source.connect(self.sink)
            self.comb += self.source.connect(phy.sink)

        # TX
        # --
        self.submodules.tx_fifo = tx_fifo = _get_uart_fifo(tx_fifo_depth, source_cd=phy_cd)
        self.comb += [
            # CSR --> FIFO.
            tx_fifo.sink.valid.eq(self._rxtx.re),
            tx_fifo.sink.data.eq(self._rxtx.r),

            # FIFO --> Source.
            tx_fifo.source.connect(self.source),

            # CSR Status.
            self._txfull.status.eq(~tx_fifo.sink.ready),
            self._txempty.status.eq(~tx_fifo.source.valid),

            # IRQ (When FIFO becomes non-full).
            self.ev.tx.trigger.eq(tx_fifo.sink.ready)
        ]

        # RX
        # --
        self.submodules.rx_fifo = rx_fifo = _get_uart_fifo(rx_fifo_depth, sink_cd=phy_cd)
        self.comb += [
            # Sink --> FIFO.
            self.sink.connect(rx_fifo.sink),

            # FIFO --> CSR.
            self._rxtx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ready.eq(self.ev.rx.clear | (rx_fifo_rx_we & self._rxtx.we)),

            # Status.
            self._rxempty.status.eq(~rx_fifo.source.valid),
            self._rxfull.status.eq(~rx_fifo.sink.ready),

            # IRQ (When FIFO becomes non-empty).
            self.ev.rx.trigger.eq(rx_fifo.source.valid)
        ]

    def add_auto_tx_flush(self, sys_clk_freq, timeout=1e-2, interval=2):
        # Add automatic TX flush when ready is not active for a long time (timeout), this can prevent
        # stalling the UART (and thus CPU) when the PHY is not operational at startup.

        flush_ep    = stream.Endpoint([("data", 8)])
        flush_count = Signal(int(log2(interval)))

        # Insert Flush Endpoint between TX FIFO and Source.
        self.comb += self.tx_fifo.source.connect(flush_ep)
        self.comb += flush_ep.connect(self.source)

        # Flush TX FIFO when Source.ready is inactive for timeout (with interval cycles between
        # each ready).
        self.submodules.timer = timer = WaitTimer(int(timeout*sys_clk_freq))
        self.comb += timer.wait.eq(~self.source.ready)
        self.sync += flush_count.eq(flush_count + 1)
        self.comb += If(timer.done, flush_ep.ready.eq(flush_count == 0))
        #self.sync += If(flush_ep.valid & flush_ep.ready, Display("%c", flush_ep.data))

# UART Bone ----------------------------------------------------------------------------------------

CMD_WRITE_BURST_INCR  = 0x01
CMD_READ_BURST_INCR   = 0x02
CMD_WRITE_BURST_FIXED = 0x03
CMD_READ_BURST_FIXED  = 0x04

class Stream2Wishbone(Module):
    def __init__(self, phy=None, clk_freq=None, data_width=32, address_width=32):
        self.sink     = sink   = stream.Endpoint([("data", 8)]) if phy is None else phy.source
        self.source   = source = stream.Endpoint([("data", 8)]) if phy is None else phy.sink
        self.wishbone = wishbone.Interface(data_width=data_width, adr_width=address_width)

        # # #
        assert data_width    in [8, 16, 32]
        assert address_width in [8, 16, 32]

        cmd              = Signal(8,                           reset_less=True)
        incr             = Signal()
        length           = Signal(8,                           reset_less=True)
        address          = Signal(address_width,               reset_less=True)
        data             = Signal(data_width,                  reset_less=True)
        data_bytes_count = Signal(int(log2(data_width//8)),    reset_less=True)
        addr_bytes_count = Signal(int(log2(address_width//8)), reset_less=True)
        words_count      = Signal(8,                           reset_less=True)

        data_bytes_count_done  = (data_bytes_count == (data_width//8 - 1))
        addr_bytes_count_done  = (addr_bytes_count == (address_width//8 - 1))
        words_count_done  = (words_count == (length - 1))

        self.submodules.fsm   = fsm   = ResetInserter()(FSM(reset_state="RECEIVE-CMD"))
        self.submodules.timer = timer = WaitTimer(int(100e-3*clk_freq))
        self.comb += timer.wait.eq(~fsm.ongoing("RECEIVE-CMD"))
        self.comb += fsm.reset.eq(timer.done)
        fsm.act("RECEIVE-CMD",
            sink.ready.eq(1),
            NextValue(data_bytes_count, 0),
            NextValue(addr_bytes_count, 0),
            NextValue(words_count, 0),
            If(sink.valid,
                NextValue(cmd, sink.data),
                NextState("RECEIVE-LENGTH")
            )
        )
        fsm.act("RECEIVE-LENGTH",
            sink.ready.eq(1),
            If(sink.valid,
                NextValue(length, sink.data),
                NextState("RECEIVE-ADDRESS")
            )
        )
        fsm.act("RECEIVE-ADDRESS",
            sink.ready.eq(1),
            If(sink.valid,
                NextValue(address, Cat(sink.data, address)),
                NextValue(addr_bytes_count, addr_bytes_count + 1),
                If(addr_bytes_count_done,
                    If((cmd == CMD_WRITE_BURST_INCR) | (cmd == CMD_WRITE_BURST_FIXED),
                        NextValue(incr, cmd == CMD_WRITE_BURST_INCR),
                        NextState("RECEIVE-DATA")
                    ).Elif((cmd == CMD_READ_BURST_INCR) | (cmd == CMD_READ_BURST_FIXED),
                        NextValue(incr, cmd == CMD_READ_BURST_INCR),
                        NextState("READ-DATA")
                    ).Else(
                        NextState("RECEIVE-CMD")
                    )
                )
            )
        )
        fsm.act("RECEIVE-DATA",
            sink.ready.eq(1),
            If(sink.valid,
                NextValue(data, Cat(sink.data, data)),
                NextValue(data_bytes_count, data_bytes_count + 1),
                If(data_bytes_count_done,
                    NextState("WRITE-DATA")
                )
            )
        )
        self.comb += [
            self.wishbone.adr.eq(address),
            self.wishbone.dat_w.eq(data),
            self.wishbone.sel.eq(2**(data_width//8) - 1)
        ]
        fsm.act("WRITE-DATA",
            sink.ready.eq(0),
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                NextValue(words_count, words_count + 1),
                NextValue(address, address + incr),
                If(words_count_done,
                    NextState("RECEIVE-CMD")
                ).Else(
                    NextState("RECEIVE-DATA")
                )
            )
        )
        fsm.act("READ-DATA",
            sink.ready.eq(0),
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(0),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                NextValue(data, self.wishbone.dat_r),
                NextState("SEND-DATA")
            )
        )
        cases = {}
        for i, n in enumerate(reversed(range(data_width//8))):
            cases[i] = source.data.eq(data[8*n:])
        self.comb += Case(data_bytes_count, cases)
        fsm.act("SEND-DATA",
            sink.ready.eq(0),
            source.valid.eq(1),
            If(source.ready,
                NextValue(data_bytes_count, data_bytes_count + 1),
                If(data_bytes_count_done,
                    NextValue(words_count, words_count + 1),
                    NextValue(address, address + incr),
                    If(words_count_done,
                        NextState("RECEIVE-CMD")
                    ).Else(
                        NextState("READ-DATA")
                    )
                )
            )
        )
        self.comb += source.last.eq(data_bytes_count_done & words_count_done)
        if hasattr(source, "length"):
            self.comb += source.length.eq((data_width//8)*length)


class UARTBone(Stream2Wishbone):
    def __init__(self, phy, clk_freq, cd="sys"):
        if cd == "sys":
            self.submodules.phy = phy
            Stream2Wishbone.__init__(self, self.phy, clk_freq=clk_freq)
        else:
            self.submodules.phy = ClockDomainsRenamer(cd)(phy)
            self.submodules.tx_cdc = stream.ClockDomainCrossing([("data", 8)], cd_from="sys", cd_to=cd)
            self.submodules.rx_cdc = stream.ClockDomainCrossing([("data", 8)], cd_from=cd,    cd_to="sys")
            self.comb += self.phy.source.connect(self.rx_cdc.sink)
            self.comb += self.tx_cdc.source.connect(self.phy.sink)
            Stream2Wishbone.__init__(self, clk_freq=clk_freq)
            self.comb += self.rx_cdc.source.connect(self.sink)
            self.comb += self.source.connect(self.tx_cdc.sink)

class UARTWishboneBridge(UARTBone):
    def __init__(self, pads, clk_freq, baudrate=115200, cd="sys"):
        self.submodules.phy = RS232PHY(pads, clk_freq, baudrate)
        UARTBone.__init__(self, self.phy, clk_freq, cd)

# UART Multiplexer ---------------------------------------------------------------------------------

class UARTMultiplexer(Module):
    def __init__(self, uarts, uart):
        self.sel = Signal(max=len(uarts))

        # # #

        cases = {}
        for n in range(len(uarts)):
            cases[n] = [
                uart.tx.eq(uarts[n].tx),
                uarts[n].rx.eq(uart.rx)
            ]
        self.comb += Case(self.sel, cases)

# UART Crossover -----------------------------------------------------------------------------------

class UARTCrossover(UART):
    """
    UART crossover trough Wishbone bridge.

    Creates a fully compatible UART that can be used by the CPU as a regular UART and adds a second
    UART, cross-connected to the main one to allow terminal emulation over a Wishbone bridge.
    """
    def __init__(self, **kwargs):
        assert kwargs.get("phy", None) == None
        UART.__init__(self, **kwargs)
        self.submodules.xover = UART(tx_fifo_depth=1, rx_fifo_depth=16, rx_fifo_rx_we=True)
        self.comb += [
            self.source.connect(self.xover.sink),
            self.xover.source.connect(self.sink)
        ]
