#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

"""Streaming between clock domains, with optional data-width conversion.

Streaming from one clock domain to another, often with a width converter on one side, is a common
pattern (video framebuffer, PCIe PHYs, ...). ClockDomainCrossingConverter builds that chain once:
it picks which side the converter goes on, sizes the AsyncFIFO for full rate, and warns when a
configuration can't keep up (bubbles).
"""

import logging

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.stream import async_fifo_full_rate_depth, async_fifo_depth_ok

# Helpers ------------------------------------------------------------------------------------------

def _layout_width(layout):
    return len(stream.Endpoint(layout).payload.raw_bits())

def _default_converter(layout_from, layout_to):
    # Single "data" field on both sides: Converter; else StrideConverter (ex PCIe PHY layouts).
    if [f[0] for f in layout_from] == ["data"] and [f[0] for f in layout_to] == ["data"]:
        return stream.Converter(_layout_width(layout_from), _layout_width(layout_to))
    return stream.StrideConverter(layout_from, layout_to)

# ClockDomainCrossingConverter ---------------------------------------------------------------------

class ClockDomainCrossingConverter(LiteXModule):
    """Stream from `cd_from` to `cd_to`, with optional data-width conversion.

    Builds [PipeValid] -> [Converter] -> ClockDomainCrossing -> [Converter] -> [PipeReady].

    Parameters
    ----------
    layout_from, layout_to : stream layouts on the sink (cd_from) and source (cd_to) sides.
    converter   : factory(layout_from, layout_to) -> module with sink/source. Default: Converter for
                  single-"data" layouts, StrideConverter otherwise.
    convert_in  : "from"  convert in cd_from, cross at layout_to's width.
                  "to"    cross at layout_from's width, convert in cd_to.
                  "auto"  with clk_freq_from/clk_freq_to: convert in the wide side's domain
                          (cross at the narrow width, smaller FIFO) when its clock can carry one
                          narrow word per narrow-side cycle; else, or without frequencies, convert
                          in the narrow side's domain (always full rate).
    clk_freq_from, clk_freq_to : clock frequencies in Hz (optional; enable "auto" and warnings).
    rate_margin : how much faster the wide side's clock must be to convert there (>1 leaves room for
                  upstream gaps, ex DMA bubbles). Default 1.0.
    depth       : AsyncFIFO depth. None: full-rate depth (see stream.async_fifo_full_rate_depth).
    buffered, with_common_rst, with_rst_gating : passed to stream.ClockDomainCrossing.
    pipe_valid_in  : add a PipeValid on the sink side (timing).
    pipe_ready_out : add a PipeReady on the source side (timing).

    Attributes
    ----------
    cdc        : the stream.ClockDomainCrossing.
    convert_in : resolved side ("from", "to", or None without conversion).
    depth      : resolved AsyncFIFO depth.
    """
    def __init__(self, layout_from, layout_to, cd_from="sys", cd_to="sys",
        converter       = None,
        convert_in      = "auto",
        clk_freq_from   = None,
        clk_freq_to     = None,
        rate_margin     = 1.0,
        depth           = None,
        buffered        = False,
        with_common_rst = False,
        with_rst_gating = False,
        pipe_valid_in   = False,
        pipe_ready_out  = False):
        assert convert_in in ["auto", "from", "to"]
        self.logger = logging.getLogger("ClockDomainCrossingConverter")
        self.sink   = sink   = stream.Endpoint(layout_from)
        self.source = source = stream.Endpoint(layout_to)

        # # #

        converter  = _default_converter if converter is None else converter
        width_from = _layout_width(layout_from)
        width_to   = _layout_width(layout_to)
        freqs      = (clk_freq_from is not None) and (clk_freq_to is not None)
        name       = f"{cd_from}->{cd_to}"

        # Converter side.
        if width_from == width_to:
            convert_in = None
        else:
            # Narrow side: the one carrying more, smaller words.
            narrow_cd = cd_to   if width_from > width_to else cd_from
            wide_cd   = cd_from if narrow_cd == cd_to    else cd_to
            freq      = {cd_from: clk_freq_from, cd_to: clk_freq_to}
            def wide_side_can_convert():
                return freq[wide_cd] >= rate_margin*freq[narrow_cd]

            if convert_in == "auto":
                if freqs and wide_side_can_convert():
                    convert_in = "from" if wide_cd == cd_from else "to"
                else:
                    convert_in = "from" if narrow_cd == cd_from else "to"
                    if not freqs:
                        self.logger.info(f"{name}: no clock frequencies given, converting in "
                            f"{narrow_cd} (always full rate, crossing at the wide width).")
            elif freqs:
                converting_cd = cd_from if convert_in == "from" else cd_to
                if (converting_cd == wide_cd) and not wide_side_can_convert():
                    other = "to" if convert_in == "from" else "from"
                    self.logger.warning(f"{name}: converting in {wide_cd} "
                        f"({freq[wide_cd]/1e6:.2f}MHz) can't sustain {narrow_cd} "
                        f"({freq[narrow_cd]/1e6:.2f}MHz, margin {rate_margin}): expect bubbles. "
                        f"Use convert_in=\"{other}\" or \"auto\".")
        self.convert_in = convert_in
        cdc_layout = layout_to if convert_in == "from" else layout_from

        # AsyncFIFO depth.
        if depth is None:
            depth = async_fifo_full_rate_depth(buffered=buffered)
        elif freqs and (cd_from != cd_to):
            f_slow = min(clk_freq_from, clk_freq_to)
            ratio  = f_slow/max(clk_freq_from, clk_freq_to)
            # Words crossing per second: the narrow side takes one narrow word per cycle; crossing
            # at the wide width carries k of them per FIFO word.
            if convert_in is None:
                word_rate = f_slow
            else:
                k          = max(width_from, width_to)//min(width_from, width_to)
                f_narrow   = clk_freq_to if width_from > width_to else clk_freq_from
                cross_wide = _layout_width(cdc_layout) == max(width_from, width_to)
                word_rate  = f_narrow/(k if cross_wide else 1)
            utilization = min(1.0, word_rate/f_slow)
            if not async_fifo_depth_ok(depth, ratio, utilization):
                self.logger.warning(f"{name}: AsyncFIFO depth {depth} at a {ratio:.2f} clock "
                    f"ratio loses throughput (bubbles); full rate needs depth "
                    f"{async_fifo_full_rate_depth(buffered=buffered)}.")
        self.depth = depth

        # Chain.
        chain = []
        if pipe_valid_in:
            self.pipe_valid = ClockDomainsRenamer(cd_from)(stream.PipeValid(layout_from))
            chain.append(self.pipe_valid)
        if convert_in == "from":
            self.converter = ClockDomainsRenamer(cd_from)(converter(layout_from, layout_to))
            chain.append(self.converter)
        self.cdc = stream.ClockDomainCrossing(cdc_layout, cd_from=cd_from, cd_to=cd_to,
            depth           = depth,
            buffered        = buffered,
            with_common_rst = with_common_rst,
            with_rst_gating = with_rst_gating,
        )
        chain.append(self.cdc)
        if convert_in == "to":
            self.converter = ClockDomainsRenamer(cd_to)(converter(layout_from, layout_to))
            chain.append(self.converter)
        if pipe_ready_out:
            self.pipe_ready = ClockDomainsRenamer(cd_to)(stream.PipeReady(layout_to))
            chain.append(self.pipe_ready)
        self.comb += sink.connect(chain[0].sink)
        for a, b in zip(chain, chain[1:]):
            self.comb += a.source.connect(b.sink)
        self.comb += chain[-1].source.connect(source)
