#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import logging
import math
from collections import namedtuple

from migen import ClockSignal, Record, Signal
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import DifferentialInput
from litex.gen import colorer

# Logging ------------------------------------------------------------------------------------------

def register_clkin_log(logger, clkin, freq):
    logger.info("Registering {} {} of {}.".format(
        colorer("Differential") if isinstance(clkin, Record) else colorer("Single Ended"),
        colorer("ClkIn"),
        colorer("{:3.2f}MHz".format(freq/1e6))
    ))

def create_clkout_log(logger, name, freq, margin, nclkouts):
    logger.info("Creating {} of {} {}.".format(
        colorer("ClkOut{} {}".format(nclkouts, name)),
        colorer("{:3.2f}MHz".format(freq/1e6)),
        "(+-{:3.2f}ppm)".format(margin*1e6),
    ))

def compute_config_log(logger, config):
    log    = "Config:\n"
    length = 0
    for name in config.keys():
        if len(name) > length: length = len(name)
    for name, value in config.items():
        if "freq" in name or "vco" in name:
            value = "{:3.2f}MHz".format(value/1e6)
        if "phase" in name:
            value = "{:3.2f}°".format(value)
        log += "{}{}: {}\n".format(name, " "*(length-len(name)), value)
    log = log[:-1]
    logger.info(log)

# Helpers ------------------------------------------------------------------------------------------

ClkOut      = namedtuple("ClkOut",      "clk freq phase margin")
ClkOutDPA   = namedtuple("ClkOutDPA",   "clk freq phase margin uses_dpa")
ClkOutNamed = namedtuple("ClkOutNamed", "clk freq phase margin name")

def period_ns(freq):
    check_freq_positive(freq)
    return 1e9/freq

def check_freq_positive(freq, name="frequency"):
    if freq <= 0:
        raise ValueError("{} must be positive.".format(name))

def check_freq_range(freq, freq_range, name="frequency"):
    check_freq_positive(freq, name)
    freq_min, freq_max = freq_range
    if freq < freq_min or freq > freq_max:
        raise ValueError(
            "{} ({:3.2f}MHz) is outside supported range [{:3.2f}MHz, {:3.2f}MHz].".format(
                name,
                freq/1e6,
                freq_min/1e6,
                freq_max/1e6,
            )
        )

def check_margin(margin, name="clock margin"):
    if margin < 0:
        raise ValueError("{} must be non-negative.".format(name))

def check_phase_allowed(phase, allowed_phases, name="Output clock phase"):
    if phase not in allowed_phases:
        allowed = ", ".join(str(phase) for phase in allowed_phases)
        raise ValueError("{} must be one of {} degrees.".format(name, allowed))

def check_clkin_registered(clkin_registered):
    if not clkin_registered:
        raise ValueError("Input clock has not been registered.")

def check_clkout_count(nclkouts, nclkouts_max):
    if nclkouts >= nclkouts_max:
        raise ValueError("Cannot add more than {} output clocks.".format(nclkouts_max))

def check_clkouts(nclkouts):
    if nclkouts == 0:
        raise ValueError("At least one output clock must be registered.")

def _clkout_cd_name(cd):
    return getattr(cd, "name", None) or getattr(getattr(cd, "clk", None), "name_override", None)

def check_clkout_cd_unused(module, cd):
    if cd is None:
        return
    clk  = getattr(cd, "clk", None)
    name = _clkout_cd_name(cd)
    for other_cd, other_clk, other_name in getattr(module, "_clkout_cds", []):
        if other_cd is cd or (clk is not None and other_clk is clk) or (name is not None and name == other_name):
            raise ValueError("Clock domain {} is already driven by this clocking instance.".format(name or "<unnamed>"))

def register_clkout_cd(module, cd):
    check_clkout_cd_unused(module, cd)
    if cd is None:
        return
    if not hasattr(module, "_clkout_cds"):
        module._clkout_cds = []
    module._clkout_cds.append((cd, getattr(cd, "clk", None), _clkout_cd_name(cd)))

def format_freq(freq):
    return "{:3.2f}MHz".format(freq/1e6)

def format_clkout_freqs(clkouts):
    if clkouts is None:
        return []
    clkout_items = clkouts.items() if hasattr(clkouts, "items") else enumerate(clkouts)
    freqs = []
    for n, clkout in clkout_items:
        if clkout is None:
            continue
        freq = clkout.freq if hasattr(clkout, "freq") else clkout[1]
        freqs.append("ClkOut{}={}".format(n, format_freq(freq)))
    return freqs

def pll_config_error(clkin_freq=None, clkouts=None, msg="No PLL config found"):
    details = []
    if clkin_freq is not None:
        details.append("ClkIn={}".format(format_freq(clkin_freq)))
    details += format_clkout_freqs(clkouts)
    if details:
        return ValueError("{} ({}).".format(msg, ", ".join(details)))
    return ValueError(msg)

def connect_clkin(module, clkin, differential=False):
    clkin_signal = Signal()
    if isinstance(clkin, (Signal, ClockSignal)):
        module.comb += clkin_signal.eq(clkin)
    elif differential and isinstance(clkin, Record):
        module.specials += DifferentialInput(clkin.p, clkin.n, clkin_signal)
    else:
        raise ValueError("Unsupported input clock.")
    return clkin_signal

def connect_clkout(module, cd, clkout, reset=None, with_reset=True):
    register_clkout_cd(module, cd)
    if with_reset and reset is not None:
        module.specials += AsyncResetSynchronizer(cd, reset)
    module.comb += cd.clk.eq(clkout)

def clkout_freq_error(clk_freq, freq):
    check_freq_positive(freq, "Output clock frequency")
    return abs(clk_freq - freq)/freq

def clkout_config_score(errors, vco_freq=0):
    return (max(errors), sum(errors), -vco_freq)

def update_best_config(best_config, best_score, config, errors, vco_freq=0):
    score = clkout_config_score(errors, vco_freq)
    if best_score is None or score < best_score:
        return config, score
    return best_config, best_score

def clkout_best_divider(freq, margin, dividers, clk_freq):
    check_margin(margin)
    best = None
    for divider in dividers:
        clkout_freq = clk_freq(divider)
        error       = clkout_freq_error(clkout_freq, freq)
        if error <= margin and (best is None or error < best[0]):
            best = (error, clkout_freq, divider)
    return best

def clkdiv_range(start, stop, step=1):
    start   = float(start)
    stop    = float(stop)
    step    = float(step)
    current = start
    while current < stop:
        yield int(current) if math.floor(current) == current else current
        current += step

def clkdiv_nearest(start, stop, step=1, ideal=None):
    if ideal is None:
        yield from clkdiv_range(start, stop, step)
        return

    start = float(start)
    stop  = float(stop)
    step  = float(step)
    last  = int(math.floor((stop - start)/step - 1e-12))
    if last < 0:
        return

    center = int(round((ideal - start)/step))
    seen   = set()
    for index in range(center - 2, center + 3):
        index = min(max(index, 0), last)
        if index in seen:
            continue
        seen.add(index)
        current = start + index*step
        yield int(current) if math.floor(current) == current else current

def clkdiv_candidates(div_ranges, ideal=None):
    for div_range in div_ranges:
        yield from clkdiv_nearest(*div_range, ideal=ideal)
