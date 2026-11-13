#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import If, Mux, Signal
from migen.genlib.cdc import MultiReg

from litex.gen import LiteXModule

from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import CSRStatus, CSRStorage


class PCM(LiteXModule):
    """CSR and optional DMA access to stereo PCM streams.

    Each frame packs signed left and right samples into the lower and upper
    `sample_width` bits, respectively. The codec consumes `playback` and drives `record`
    in the audio clock domain. A codec with fixed frame timing can request a
    playback frame even when valid is low: the sample will be zero.

    With DMA, supply independent word-addressed Wishbone ports with one frame per word (32 bits
    for sample widths up to 16, or 64 bits for wider samples) and register them as
    SoC bus masters. The high padding bits of DMA words are zero on capture
    and ignored on playback. An enabled DMA owns its direction until disabled.
    Queued PCM frames stay in order across ownership changes. DMA completion
    tracks memory transfers, so playback frames may still be queued at done.
    Set capture before starting a capture transfer.

    In the sys domain, connect a producer to `playback_sink` or consume
    frames from `capture_source` using ready/valid handshakes. Playback
    priority is DMA, then stream, then CSR writes. Capture defaults to
    CSR access. Set capture_stream to select the stream. Capture DMA takes
    priority when enabled. If the stream is presenting a stalled frame,
    it retains ownership until that frame is accepted.

    Parameters
    ----------
    sample_width : int
        Signed PCM bits per channel, from 1 through 32. Defaults to 16.
    clock_domain : str
        Clock domain for the playback and record endpoints. Defaults to
        "audio". Use "sys" to place the endpoints in the CSR clock domain.
    fifo_depth : int
        Playback and capture FIFO depth in stereo frames. Defaults to 256.
    playback_bus : wishbone.Interface or None
        Read-capable Wishbone master port for playback DMA, if enabled.
    capture_bus : wishbone.Interface or None
        Write-capable Wishbone master port for capture DMA, if enabled.
    """

    def __init__(self, *, sample_width=16, clock_domain="audio", fifo_depth=256,
        playback_bus=None, capture_bus=None):
        if not isinstance(sample_width, int) or not 1 <= sample_width <= 32:
            raise ValueError("PCM sample_width must be an integer from 1 to 32.")
        frame_width = 2 * sample_width
        dma_width = 32 if frame_width <= 32 else 64
        layout = [("sample", frame_width)]
        for bus in (playback_bus, capture_bus):
            if bus is not None and bus.data_width != dma_width:
                raise ValueError(f"PCM DMA requires a {dma_width}-bit Wishbone bus for {sample_width}-bit samples.")
            if bus is not None and bus.addressing != "word":
                raise ValueError("PCM DMA requires a word-addressed Wishbone bus.")
        if playback_bus is not None and playback_bus is capture_bus:
            raise ValueError("PCM playback and capture DMA require separate Wishbone masters.")

        self.sample = CSRStorage(frame_width, atomic_write=True, description=f"Write a stereo frame, left in bits {sample_width - 1}:0.")
        self.ready = CSRStatus(description="The playback FIFO can accept a CSR write.")
        self.capture = CSRStorage(description="Enable stereo capture.")
        self.rx_ready = CSRStatus(description="A captured frame is available for CSR access.")
        self.rx_sample = CSRStatus(frame_width, description=f"Oldest captured frame, left in bits {sample_width - 1}:0.")
        self.rx_pop = CSRStorage(description="Write to advance the capture FIFO.")
        self.rx_overflow = CSRStatus(description="Capture FIFO overrun since capture was last disabled.")

        self.word_size = CSRStatus(6, reset=sample_width, description="Bits per PCM channel.")

        self.playback_sink = playback_sink = stream.Endpoint(layout)
        self.capture_source = capture_source = stream.Endpoint(layout)
        self.playback = playback = stream.Endpoint(layout)
        self.record = record = stream.Endpoint(layout)
        if clock_domain == "sys":
            self.tx = tx = stream.SyncFIFO(layout, fifo_depth)
            self.rx = rx = stream.SyncFIFO(layout, fifo_depth, buffered=True)
        else:
            self.tx = tx = stream.ClockDomainCrossing(layout, cd_to=clock_domain, depth=fifo_depth)
            self.rx = rx = stream.ClockDomainCrossing(layout, cd_from=clock_domain, depth=fifo_depth, buffered=True)

        self.comb += [
            playback.valid.eq(tx.source.valid),
            playback.sample.eq(Mux(tx.source.valid, tx.source.sample, 0)),
            tx.source.ready.eq(playback.ready),
        ]

        capture_enabled = Signal()
        overflow = Signal()
        self.specials += [
            MultiReg(self.capture.storage, capture_enabled, odomain=clock_domain),
            MultiReg(overflow, self.rx_overflow.status),
        ]
        self.comb += [
            rx.sink.valid.eq(capture_enabled & record.valid),
            rx.sink.sample.eq(record.sample),
            record.ready.eq(~capture_enabled | rx.sink.ready),
        ]
        capture_sync = getattr(self.sync, clock_domain)
        capture_sync += If(~capture_enabled,
            overflow.eq(0),
        ).Elif(record.valid & ~record.ready,
            overflow.eq(1),
        )

        playback_dma_enabled = 0
        if playback_bus is not None:
            # A one-word prefetch FIFO can be drained while disabled, so an
            # aborted transfer cannot feed stale prefetch into the next one.
            self.playback_dma = dma = WishboneDMAReader(playback_bus, with_byteswap=False,
                fifo_depth=1, with_csr=True)
            playback_dma_enabled = dma.enable
            self.comb += [
                dma.source.ready.eq(~dma.enable | tx.sink.ready),
                If(dma.enable,
                    tx.sink.valid.eq(dma.source.valid),
                    tx.sink.sample.eq(dma.source.data),
                ),
            ]
        self.comb += If(playback_dma_enabled == 0,
            playback_sink.ready.eq(tx.sink.ready),
            tx.sink.valid.eq(playback_sink.valid | self.sample.re),
            tx.sink.sample.eq(Mux(playback_sink.valid, playback_sink.sample, self.sample.storage)),
            self.ready.status.eq(tx.sink.ready & ~playback_sink.valid),
        )

        capture_dma_enabled = 0
        if capture_bus is not None:
            self.capture_dma = dma = WishboneDMAWriter(capture_bus, with_byteswap=False)
            dma.add_ctrl(ready_on_idle=0)
            dma.add_csr()
            capture_dma_enabled = dma.enable

        self.capture_stream = CSRStorage(description="Select capture stream instead of CSR reads.")
        stream_pending = Signal()
        stream_selected = Signal()
        self.comb += stream_selected.eq(stream_pending | (self.capture_stream.storage & ~capture_dma_enabled))
        self.sync += stream_pending.eq(capture_source.valid & ~capture_source.ready)
        self.comb += [
            capture_source.valid.eq(stream_selected & rx.source.valid),
            capture_source.sample.eq(Mux(capture_source.valid, rx.source.sample, 0)),
            If(stream_selected,
                rx.source.ready.eq(capture_source.ready),
            ).Elif(capture_dma_enabled == 0,
                self.rx_ready.status.eq(rx.source.valid),
                self.rx_sample.status.eq(Mux(rx.source.valid, rx.source.sample, 0)),
                rx.source.ready.eq(self.rx_pop.re),
            ),
        ]
        if capture_bus is not None:
            self.comb += [
                dma.sink.valid.eq(dma.enable & ~stream_selected & rx.source.valid),
                dma.sink.data.eq(rx.source.sample),
                If(dma.enable & ~stream_selected,
                    rx.source.ready.eq(~dma.done & dma.sink.ready),
                ),
            ]
