# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# This file is Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD

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

class RS232PHYInterface(UARTInterface):
    pass

class RS232PHYRX(Module):
    def __init__(self, pads, tuning_word):
        self.source = stream.Endpoint([("data", 8)])

        # # #

        uart_clk_rxen        = Signal()
        phase_accumulator_rx = Signal(32, reset_less=True)

        rx          = Signal()
        rx_r        = Signal()
        rx_reg      = Signal(8, reset_less=True)
        rx_bitcount = Signal(4, reset_less=True)
        rx_busy     = Signal()
        rx_done     = self.source.valid
        rx_data     = self.source.data
        self.specials += MultiReg(pads.rx, rx)
        self.sync += [
            rx_done.eq(0),
            rx_r.eq(rx),
            If(~rx_busy,
                If(~rx & rx_r,  # look for start bit
                    rx_busy.eq(1),
                    rx_bitcount.eq(0),
                )
            ).Else(
                If(uart_clk_rxen,
                    rx_bitcount.eq(rx_bitcount + 1),
                    If(rx_bitcount == 0,
                        If(rx,  # verify start bit
                            rx_busy.eq(0)
                        )
                    ).Elif(rx_bitcount == 9,
                        rx_busy.eq(0),
                        If(rx,  # verify stop bit
                            rx_data.eq(rx_reg),
                            rx_done.eq(1)
                        )
                    ).Else(
                        rx_reg.eq(Cat(rx_reg[1:], rx))
                    )
                )
            )
        ]
        self.sync += \
                If(rx_busy,
                    Cat(phase_accumulator_rx, uart_clk_rxen).eq(phase_accumulator_rx + tuning_word)
                ).Else(
                    Cat(phase_accumulator_rx, uart_clk_rxen).eq(2**31)
                )


class RS232PHYTX(Module):
    def __init__(self, pads, tuning_word):
        self.sink = stream.Endpoint([("data", 8)])

        # # #

        uart_clk_txen        = Signal()
        phase_accumulator_tx = Signal(32, reset_less=True)

        pads.tx.reset = 1

        tx_reg      = Signal(8, reset_less=True)
        tx_bitcount = Signal(4, reset_less=True)
        tx_busy     = Signal()
        self.sync += [
            self.sink.ready.eq(0),
            If(self.sink.valid & ~tx_busy & ~self.sink.ready,
                tx_reg.eq(self.sink.data),
                tx_bitcount.eq(0),
                tx_busy.eq(1),
                pads.tx.eq(0)
            ).Elif(uart_clk_txen & tx_busy,
                tx_bitcount.eq(tx_bitcount + 1),
                If(tx_bitcount == 8,
                    pads.tx.eq(1)
                ).Elif(tx_bitcount == 9,
                    pads.tx.eq(1),
                    tx_busy.eq(0),
                    self.sink.ready.eq(1),
                ).Else(
                    pads.tx.eq(tx_reg[0]),
                    tx_reg.eq(Cat(tx_reg[1:], 0))
                )
            )
        ]
        self.sync += [
                If(tx_busy,
                    Cat(phase_accumulator_tx, uart_clk_txen).eq(phase_accumulator_tx + tuning_word)
                ).Else(
                    Cat(phase_accumulator_tx, uart_clk_txen).eq(tuning_word)
                )
        ]


class RS232PHY(Module, AutoCSR):
    def __init__(self, pads, clk_freq, baudrate=115200):
        self._tuning_word  = CSRStorage(32, reset=int((baudrate/clk_freq)*2**32))
        self.submodules.tx = RS232PHYTX(pads, self._tuning_word.storage)
        self.submodules.rx = RS232PHYRX(pads, self._tuning_word.storage)
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
    # FT245 async FIFO mode (baudrate ignored)
    if hasattr(pads, "rd_n") and hasattr(pads, "wr_n"):
        from litex.soc.cores.usb_fifo import FT245PHYAsynchronous
        return FT245PHYAsynchronous(pads, clk_freq)
    # FT245 sync FIFO mode (baudrate ignored)
    if hasattr(pads, "rd_n") and hasattr(pads, "wr_n") and hasattr(pads, "oe_n"):
        from litex.soc.cores.usb_fifo import FT245PHYSynchronous
        return FT245PHYSynchronous(pads, clk_freq)
    # RS232
    else:
        return  RS232PHY(pads, clk_freq, baudrate)

class UART(Module, AutoCSR, UARTInterface):
    def __init__(self, phy=None,
                 tx_fifo_depth = 16,
                 rx_fifo_depth = 16,
                 rx_fifo_rx_we = False,
                 phy_cd        = "sys"):
        self._rxtx    = CSR(8)
        self._txfull  = CSRStatus()
        self._rxempty = CSRStatus()

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourceProcess()
        self.ev.rx = EventSourceProcess()
        self.ev.finalize()

        # # #

        UARTInterface.__init__(self)

        # PHY
        if phy is not None:
            self.comb += [
                phy.source.connect(self.sink),
                self.source.connect(phy.sink)
            ]

        # TX
        tx_fifo = _get_uart_fifo(tx_fifo_depth, source_cd=phy_cd)
        self.submodules += tx_fifo

        self.comb += [
            tx_fifo.sink.valid.eq(self._rxtx.re),
            tx_fifo.sink.data.eq(self._rxtx.r),
            self._txfull.status.eq(~tx_fifo.sink.ready),
            tx_fifo.source.connect(self.source),
            # Generate TX IRQ when tx_fifo becomes non-full
            self.ev.tx.trigger.eq(~tx_fifo.sink.ready)
        ]

        # RX
        rx_fifo = _get_uart_fifo(rx_fifo_depth, sink_cd=phy_cd)
        self.submodules += rx_fifo

        self.comb += [
            self.sink.connect(rx_fifo.sink),
            self._rxempty.status.eq(~rx_fifo.source.valid),
            self._rxtx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ready.eq(self.ev.rx.clear | (rx_fifo_rx_we & self._rxtx.we)),
            # Generate RX IRQ when rx_fifo becomes non-empty
            self.ev.rx.trigger.eq(~rx_fifo.source.valid)
        ]

# UART Bone ----------------------------------------------------------------------------------------

CMD_WRITE = 0x01
CMD_READ  = 0x02

class Stream2Wishbone(Module):
    def __init__(self, phy, clk_freq, data_width=32, address_width=32):
        self.wishbone = wishbone.Interface()
        self.comb += phy.source.ready.eq(1) # Always accept incoming stream.

        # # #

        cmd         = Signal(8,                        reset_less=True)
        length      = Signal(8,                        reset_less=True)
        address     = Signal(address_width,            reset_less=True)
        data        = Signal(data_width,               reset_less=True)
        bytes_count = Signal(int(log2(data_width//8)), reset_less=True)
        words_count = Signal(8,                        reset_less=True)

        bytes_count_done  = (bytes_count == (data_width//8 - 1))
        words_count_done  = (words_count == (length - 1))

        fsm   = ResetInserter()(FSM(reset_state="RECEIVE-CMD"))
        timer = WaitTimer(int(100e-3*clk_freq))
        self.comb += timer.wait.eq(~fsm.ongoing("RECEIVE-CMD"))
        self.submodules += fsm, timer
        self.comb += fsm.reset.eq(timer.done)
        fsm.act("RECEIVE-CMD",
            NextValue(bytes_count, 0),
            NextValue(words_count, 0),
            If(phy.source.valid,
                NextValue(cmd, phy.source.data),
                NextState("RECEIVE-LENGTH")
            )
        )
        fsm.act("RECEIVE-LENGTH",
            If(phy.source.valid,
                NextValue(length, phy.source.data),
                NextState("RECEIVE-ADDRESS")
            )
        )
        fsm.act("RECEIVE-ADDRESS",
            If(phy.source.valid,
                NextValue(address, Cat(phy.source.data, address)),
                NextValue(bytes_count, bytes_count + 1),
                If(bytes_count_done,
                    If(cmd == CMD_WRITE,
                        NextState("RECEIVE-DATA")
                    ).Elif(cmd == CMD_READ,
                        NextState("READ-DATA")
                    ).Else(
                        NextState("RECEIVE-CMD")
                    )
                )
            )
        )
        fsm.act("RECEIVE-DATA",
            If(phy.source.valid,
                NextValue(data, Cat(phy.source.data, data)),
                NextValue(bytes_count, bytes_count + 1),
                If(bytes_count_done,
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
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                NextValue(words_count, words_count + 1),
                NextValue(address, address + 1),
                If(words_count_done,
                    NextState("RECEIVE-CMD")
                ).Else(
                    NextState("RECEIVE-DATA")
                )
            )
        )
        fsm.act("READ-DATA",
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
            cases[i] = phy.sink.data.eq(data[8*n:])
        self.comb += Case(bytes_count, cases)
        fsm.act("SEND-DATA",
            phy.sink.valid.eq(1),
            If(phy.sink.ready,
                NextValue(bytes_count, bytes_count + 1),
                If(bytes_count_done,
                    NextValue(words_count, words_count + 1),
                    NextValue(address, address + 1),
                    If(words_count_done,
                        NextState("RECEIVE-CMD")
                    ).Else(
                        NextState("READ-DATA")
                    )
                )
            )
        )
        self.comb += phy.sink.last.eq(bytes_count_done & words_count_done)
        if hasattr(phy.sink, "length"):
            self.comb += phy.sink.length.eq((data_width//8)*length)


class UARTBone(Stream2Wishbone):
    def __init__(self, pads, clk_freq, baudrate=115200):
        self.submodules.phy = RS232PHY(pads, clk_freq, baudrate)
        Stream2Wishbone.__init__(self, self.phy, clk_freq)

class UARTWishboneBridge(UARTBone): pass

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
        self.submodules.xover = UART(tx_fifo_depth=1, rx_fifo_depth=1, rx_fifo_rx_we=True)
        self.comb += [
            self.source.connect(self.xover.sink),
            self.xover.source.connect(self.sink)
        ]
