#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import LiteXModule

from litex.soc.interconnect.csr import *

# Generic Temperature Monitor ----------------------------------------------------------------------

class LiteXTemperatureMonitor(LiteXModule):
    def __init__(self,
        bits,
        temp_scale,
        temp_divisor,
        temp_offset,
        temp_signed_bits = 0,
        description      = None,
    ):
        self.temperature = CSRStatus(bits, name="temperature", description=description)
        self.ready       = CSRStatus(1,    name="ready",       description="Temperature sample valid.")

        self.hwmon_temp_scale       = CSRConstant(temp_scale,       name="hwmon_temp_scale")
        self.hwmon_temp_divisor     = CSRConstant(temp_divisor,     name="hwmon_temp_divisor")
        self.hwmon_temp_offset      = CSRConstant(temp_offset,      name="hwmon_temp_offset")
        self.hwmon_temp_signed_bits = CSRConstant(temp_signed_bits, name="hwmon_temp_signed_bits")

# Gowin Temperature Monitor ------------------------------------------------------------------------

class GowinAroraVTemperatureSensor(LiteXTemperatureMonitor):
    def __init__(self,
        clock_domain  = "sys",
        primitive     = "Gowin_ADC",
        sample_cycles = 2**16,
    ):
        LiteXTemperatureMonitor.__init__(self,
            bits             = 14,
            temp_scale       = 250,
            temp_divisor     = 1,
            temp_offset      = 0,
            temp_signed_bits = 14,
            description      = "Raw signed temperature value from Gowin Arora V ADC. "
                               "Temperature (deg C) = ``Value`` / 4.",
        )

        # # #

        # Initial support, following Gowin UG299E temperature mode. This wrapper has
        # not yet been validated on hardware and is intentionally not auto-enabled.
        sample_cycles = max(2, int(sample_cycles))
        counter       = Signal(max=sample_cycles, reset=sample_cycles - 1)
        adcreqi       = Signal()
        adcrdy        = Signal()
        adcvalue      = Signal(14)

        self.sync += [
            adcreqi.eq(0),
            If(counter == 0,
                counter.eq(sample_cycles - 1),
                adcreqi.eq(1),
            ).Else(
                counter.eq(counter - 1),
            ),
            If(adcrdy,
                self.temperature.status.eq(adcvalue),
                self.ready.status.eq(1),
            ),
        ]

        self.specials += Instance(primitive,
            i_clk          = ClockSignal(clock_domain),
            i_drstn        = ~ResetSignal(clock_domain),
            i_adcmode      = 0, # Temperature mode.
            i_vsenctl      = 0,
            i_adcen        = 1,
            i_adcreqi      = adcreqi,
            o_adcrdy       = adcrdy,
            o_adcvalue     = adcvalue,
            i_mdrp_clk     = ClockSignal(clock_domain),
            i_mdrp_wdata   = 0,
            i_mdrp_a_inc   = 0,
            i_mdrp_opcode  = 0,
        )

# Intel Temperature Monitors -----------------------------------------------------------------------

class IntelA10C10GXTemperatureSensor(LiteXTemperatureMonitor):
    def __init__(self,
        clock_domain = "sys",
        primitive    = "alttemp_sense",
    ):
        LiteXTemperatureMonitor.__init__(self,
            bits             = 10,
            temp_scale       = 693000,
            temp_divisor     = 1024,
            temp_offset      = 265000,
            temp_signed_bits = 0,
            description      = "Raw temperature value from Intel Arria 10/Cyclone 10 GX Temperature Sensor IP. "
                               "Temperature (deg C) = ``Value`` x 693 / 1024 - 265.",
        )

        # # #

        # Initial support, following Intel Temperature Sensor IP core ports for
        # Arria 10/Cyclone 10 GX. This wrapper has not yet been validated on hardware.
        tempout     = Signal(10)
        tempout_sys = Signal(10)
        eoc         = Signal()
        eoc_sys     = Signal()
        eoc_sys_d   = Signal()

        self.specials += [
            Instance(primitive,
                i_corectl = 1,
                i_reset   = ResetSignal(clock_domain),
                o_tempout = tempout,
                o_eoc     = eoc,
            ),
            MultiReg(tempout, tempout_sys, odomain=clock_domain),
            MultiReg(eoc,     eoc_sys,     odomain=clock_domain),
        ]

        self.sync += [
            eoc_sys_d.eq(eoc_sys),
            If(eoc_sys & ~eoc_sys_d,
                self.temperature.status.eq(tempout_sys),
                self.ready.status.eq(1),
            ),
        ]

class IntelTemperatureSensor(IntelA10C10GXTemperatureSensor): pass # For compat.

class IntelLegacyTemperatureSensor(LiteXTemperatureMonitor):
    def __init__(self,
        clock_domain  = "sys",
        primitive     = "alttemp_sense",
        sample_cycles = 2**20,
        clear_cycles  = 80,
    ):
        LiteXTemperatureMonitor.__init__(self,
            bits             = 8,
            temp_scale       = 1000,
            temp_divisor     = 1,
            temp_offset      = 128000,
            temp_signed_bits = 0,
            description      = "Raw temperature value from legacy Intel Temperature Sensor IP. "
                               "Temperature (deg C) = ``Value`` - 128.",
        )

        # # #

        # Initial support, following Intel Temperature Sensor IP core ports for
        # Arria V/Stratix V/Stratix IV. This wrapper has not yet been validated on hardware.
        sample_cycles = max(2, int(sample_cycles))
        clear_cycles  = max(1, int(clear_cycles))
        counter       = Signal(max=sample_cycles,    reset=sample_cycles - 1)
        clear_counter = Signal(max=clear_cycles + 1, reset=clear_cycles)
        clr           = Signal(reset=1)
        tsdcalo       = Signal(8)
        tsdcaldone    = Signal()

        self.sync += [
            clr.eq(clear_counter != 0),
            If(clear_counter != 0,
                clear_counter.eq(clear_counter - 1),
            ).Elif(counter == 0,
                clear_counter.eq(clear_cycles),
                counter.eq(sample_cycles - 1),
            ).Else(
                counter.eq(counter - 1),
            ),
            If(tsdcaldone,
                self.temperature.status.eq(tsdcalo),
                self.ready.status.eq(1),
            ),
        ]

        self.specials += Instance(primitive,
            i_clk        = ClockSignal(clock_domain),
            i_ce         = 1,
            i_clr        = clr,
            o_tsdcalo    = tsdcalo,
            o_tsdcaldone = tsdcaldone,
        )
