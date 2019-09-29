# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD

from migen import *
from migen.genlib.record import Record
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.interconnect import stream
from litex.soc.interconnect.wishbonebridge import WishboneStreamingBridge

# RS232 PHY ----------------------------------------------------------------------------------------

class RS232PHYInterface:
    def __init__(self):
        self.sink = stream.Endpoint([("data", 8)])
        self.source = stream.Endpoint([("data", 8)])


class RS232PHYRX(Module):
    def __init__(self, pads, tuning_word):
        self.source = stream.Endpoint([("data", 8)])

        # # #

        uart_clk_rxen = Signal()
        phase_accumulator_rx = Signal(32)

        rx = Signal()
        self.specials += MultiReg(pads.rx, rx)
        rx_r = Signal()
        rx_reg = Signal(8)
        rx_bitcount = Signal(4)
        rx_busy = Signal()
        rx_done = self.source.valid
        rx_data = self.source.data
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

        uart_clk_txen = Signal()
        phase_accumulator_tx = Signal(32)

        pads.tx.reset = 1

        tx_reg = Signal(8)
        tx_bitcount = Signal(4)
        tx_busy = Signal()
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
                    Cat(phase_accumulator_tx, uart_clk_txen).eq(0)
                )
        ]


class RS232PHY(Module, AutoCSR):
    def __init__(self, pads, clk_freq, baudrate=115200):
        self._tuning_word = CSRStorage(32, reset=int((baudrate/clk_freq)*2**32))
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
        self.sink = stream.Endpoint([("data", 8)])
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

class UART(Module, AutoCSR):
    def __init__(self, phy,
                 tx_fifo_depth=16,
                 rx_fifo_depth=16,
                 phy_cd="sys"):
        self._rxtx = CSR(8)
        self._txfull = CSRStatus()
        self._rxempty = CSRStatus()

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourceProcess()
        self.ev.rx = EventSourceProcess()
        self.ev.finalize()

        # # #

        # TX
        tx_fifo = _get_uart_fifo(tx_fifo_depth, source_cd=phy_cd)
        self.submodules += tx_fifo

        self.comb += [
            tx_fifo.sink.valid.eq(self._rxtx.re),
            tx_fifo.sink.data.eq(self._rxtx.r),
            self._txfull.status.eq(~tx_fifo.sink.ready),
            tx_fifo.source.connect(phy.sink),
            # Generate TX IRQ when tx_fifo becomes non-full
            self.ev.tx.trigger.eq(~tx_fifo.sink.ready)
        ]

        # RX
        rx_fifo = _get_uart_fifo(rx_fifo_depth, sink_cd=phy_cd)
        self.submodules += rx_fifo

        self.comb += [
            phy.source.connect(rx_fifo.sink),
            self._rxempty.status.eq(~rx_fifo.source.valid),
            self._rxtx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ready.eq(self.ev.rx.clear),
            # Generate RX IRQ when tx_fifo becomes non-empty
            self.ev.rx.trigger.eq(~rx_fifo.source.valid)
        ]


class UARTStub(Module, AutoCSR):
    def __init__(self):
        self._rxtx = CSR(8)
        self._txfull = CSRStatus()
        self._rxempty = CSRStatus()

        self.submodules.ev = EventManager()
        self.ev.tx = EventSourceProcess()
        self.ev.rx = EventSourceProcess()
        self.ev.finalize()

        # # #

        self.comb += [
            self._txfull.status.eq(0),
            self.ev.tx.trigger.eq(~(self._rxtx.re & self._rxtx.r)),
            self._rxempty.status.eq(1)
        ]


class UARTWishboneBridge(WishboneStreamingBridge):
    def __init__(self, pads, clk_freq, baudrate=115200):
        self.submodules.phy = RS232PHY(pads, clk_freq, baudrate)
        WishboneStreamingBridge.__init__(self, self.phy, clk_freq)

# UART Mutltiplexer --------------------------------------------------------------------------------

def UARTPads():
    return Record([("tx", 1), ("rx", 1)])


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
