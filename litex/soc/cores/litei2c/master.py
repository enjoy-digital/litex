#
# This file is part of LiteI2C
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litex.soc.cores.litei2c.common import *


class LiteI2CMaster(Module, AutoCSR):
    """Generic LiteI2C Master

    The ``LiteI2CMaster`` class provides a generic I2C master that can be controlled using CSRs.

    Parameters
    ----------
    fifo_depth : int
        Depth of the internal TX/RX FIFO.

    Attributes
    ----------
    source : Endpoint(i2c_phy2core_layout), out
        Data stream.

    sink : Endpoint(i2c_core2phy_layout), in
        Control stream.

    enable : Signal(), out
        Enable signal.

    """
    def __init__(self, tx_fifo_depth=1, rx_fifo_depth=1):
        self.sink   = stream.Endpoint(i2c_phy2core_layout)
        self.source = stream.Endpoint(i2c_core2phy_layout)
        self.enable = Signal()

        self._enable = CSRStorage()
        self._settings = CSRStorage(fields=[
            CSRField("len_tx",   size=3, offset=0,  description="I2C tx Xfer length (in bytes). Set to a value greater then 4 to anounce more data has to be transmitted."),
            CSRField("len_rx",   size=3, offset=8,  description="I2C rx Xfer length (in bytes). Set to a value greater then 4 to anounce more data has to be received."),
            CSRField("recover",  size=1, offset=16, description="I2C recover bus. If set, the I2C bus will be recovered."),
        ], description="I2C transfer settings")
        self._addr = CSRStorage(self.source.addr.nbits)
        self._rxtx = CSR(self.source.data.nbits)
        self._status = CSRStatus(fields=[
            CSRField("tx_ready", size=1, offset=0, description="TX FIFO is not full."),
            CSRField("rx_ready", size=1, offset=1, description="RX FIFO is not empty."),
            CSRField("nack", size=1, offset=8, description="Error on transfer." ),
            CSRField("tx_unfinished", size=1, offset=16, description="Another tx transfer is expected."),
            CSRField("rx_unfinished", size=1, offset=17, description="Another rx transfer is expected.")
        ])

        # FIFOs.
        tx_fifo = stream.SyncFIFO(i2c_core2phy_layout, depth=tx_fifo_depth)
        rx_fifo = stream.SyncFIFO(i2c_phy2core_layout, depth=rx_fifo_depth)
        self.submodules += tx_fifo, rx_fifo
        self.comb += self.sink.connect(rx_fifo.sink)
        self.comb += tx_fifo.source.connect(self.source)

        # I2C Enable.
        self.comb += self.enable.eq(self._enable.storage)

        # I2C TX.
        self.comb += [
            tx_fifo.sink.valid.eq(self._rxtx.re),
            self._status.fields.tx_ready.eq(tx_fifo.sink.ready),
            tx_fifo.sink.data.eq(self._rxtx.r),
            tx_fifo.sink.addr.eq(self._addr.storage),
            tx_fifo.sink.len_tx.eq(self._settings.fields.len_tx),
            tx_fifo.sink.len_rx.eq(self._settings.fields.len_rx),
            tx_fifo.sink.recover.eq(self._settings.fields.recover),
            tx_fifo.sink.last.eq(1),
        ]

        # I2C RX.
        self.comb += [
            rx_fifo.source.ready.eq(self._rxtx.we),
            self._status.fields.rx_ready.eq(rx_fifo.source.valid),
            self._status.fields.nack.eq(rx_fifo.source.nack),
            self._status.fields.tx_unfinished.eq(rx_fifo.source.unfinished_tx),
            self._status.fields.rx_unfinished.eq(rx_fifo.source.unfinished_rx),
            self._rxtx.w.eq(rx_fifo.source.data),
        ]
