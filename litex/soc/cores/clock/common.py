#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import logging
import math

from migen import Record

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

def period_ns(freq):
    return 1e9/freq

def check_freq_range(freq, freq_range, name="frequency"):
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

def check_clkin_registered(clkin_registered):
    if not clkin_registered:
        raise ValueError("Input clock has not been registered.")

def check_clkout_count(nclkouts, nclkouts_max):
    if nclkouts >= nclkouts_max:
        raise ValueError("Cannot add more than {} output clocks.".format(nclkouts_max))

def check_clkouts(nclkouts):
    if nclkouts == 0:
        raise ValueError("At least one output clock must be registered.")

def clkdiv_range(start, stop, step=1):
    start   = float(start)
    stop    = float(stop)
    step    = float(step)
    current = start
    while current < stop:
        yield int(current) if math.floor(current) == current else current
        current += step
