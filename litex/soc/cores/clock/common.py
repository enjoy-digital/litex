#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import logging
import math

from migen import Record
from migen.fhdl.structure import ClockDomain

from litex.soc.integration.soc import colorer

logging.basicConfig(level=logging.INFO)

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

def clkdiv_range(start, stop, step=1):
    start   = float(start)
    stop    = float(stop)
    step    = float(step)
    current = start
    while current < stop:
        yield int(current) if math.floor(current) == current else current
        current += step

def ClockFrequency(cd_or_signal="sys", set_freq=None):
    CF = ClockFrequency
    CF.freqs = getattr(CF, 'freqs', {})
    if set_freq is not None:
        if isinstance(cd_or_signal, ClockDomain):
            CF.freqs[cd_or_signal.name] = set_freq
        else:
            CF.freqs[cd_or_signal] = set_freq
    else:
        try:
            return CF.freqs[cd_or_signal]
        except KeyError:
            raise KeyError(f"ClockFrequency has not yet been set for domain/signal '{cd_or_signal}'")
