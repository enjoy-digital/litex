#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

"""Clock Abstraction Modules"""

import math
import logging

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import DifferentialInput

from litex.soc.integration.soc import colorer
from litex.soc.interconnect.csr import *

logging.basicConfig(level=logging.INFO)

def period_ns(freq):
    return 1e9/freq

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

def clkdiv_range(start, stop, step=1):
    start   = float(start)
    stop    = float(stop)
    step    = float(step)
    current = start
    while current < stop:
        yield int(current) if math.floor(current) == current else current
        current += step

# Xilinx / Generic ---------------------------------------------------------------------------------

class XilinxClocking(Module, AutoCSR):
    clkfbout_mult_frange = (2,  64+1)
    clkout_divide_range  = (1, 128+1)

    def __init__(self, vco_margin=0):
        self.vco_margin = vco_margin
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        elif isinstance(clkin, Record):
            self.specials += DifferentialInput(clkin.p, clkin.n, self.clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, buf="bufg", margin=1e-2, with_reset=True, ce=None):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked | self.reset)
        if buf is None:
            self.comb += cd.clk.eq(clkout)
        else:
            clkout_buf = Signal()
            self.comb += cd.clk.eq(clkout_buf)
            if buf == "bufg":
                self.specials += Instance("BUFG", i_I=clkout, o_O=clkout_buf)
            elif buf == "bufr":
                self.specials += Instance("BUFR", i_I=clkout, o_O=clkout_buf)
            elif buf == "bufgce":
                if ce is None:
                    raise ValueError("BUFGCE requires user to provide a clock enable ce Signal")
                self.specials += Instance("BUFGCE", i_I=clkout, o_O=clkout_buf, i_CE=ce)
            elif buf == "bufio":
                self.specials += Instance("BUFIO", i_I=clkout, o_O=clkout_buf)
            else:
                raise ValueError("Unsupported clock buffer: {}".format(buf))
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for divclk_divide in range(*self.divclk_divide_range):
            config["divclk_divide"] = divclk_divide
            for clkfbout_mult in reversed(range(*self.clkfbout_mult_frange)):
                all_valid = True
                vco_freq = self.clkin_freq*clkfbout_mult/divclk_divide
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        d_ranges = [self.clkout_divide_range]
                        if getattr(self, "clkout{}_divide_range".format(n), None) is not None:
                            d_ranges += [getattr(self, "clkout{}_divide_range".format(n))]
                        for d_range in d_ranges:
                            for d in clkdiv_range(*d_range):
                                clk_freq = vco_freq/d
                                if abs(clk_freq - f) <= f*m:
                                    config["clkout{}_freq".format(n)]   = clk_freq
                                    config["clkout{}_divide".format(n)] = d
                                    config["clkout{}_phase".format(n)]  = p
                                    valid = True
                                    break
                                if valid:
                                    break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"]           = vco_freq
                    config["clkfbout_mult"] = clkfbout_mult
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def expose_drp(self):
        self.drp_reset  = CSR()
        self.drp_locked = CSRStatus()
        self.drp_read   = CSR()
        self.drp_write  = CSR()
        self.drp_drdy   = CSRStatus()
        self.drp_adr    = CSRStorage(7,  reset_less=True)
        self.drp_dat_w  = CSRStorage(16, reset_less=True)
        self.drp_dat_r  = CSRStatus(16)

        # # #

        den_pipe = Signal()
        dwe_pipe = Signal()

        drp_drdy = Signal()
        self.params.update(
            i_DCLK  = ClockSignal(),
            i_DWE   = dwe_pipe,
            i_DEN   = den_pipe,
            o_DRDY  = drp_drdy,
            i_DADDR = self.drp_adr.storage,
            i_DI    = self.drp_dat_w.storage,
            o_DO    = self.drp_dat_r.status
        )
        self.sync += [
            den_pipe.eq(self.drp_read.re | self.drp_write.re),
            dwe_pipe.eq(self.drp_write.re),
            If(self.drp_read.re | self.drp_write.re,
                self.drp_drdy.status.eq(0)
            ).Elif(drp_drdy,
                self.drp_drdy.status.eq(1)
            )
        ]
        self.comb += self.drp_locked.status.eq(self.locked)
        self.logger.info("Exposing DRP interface.")

    def do_finalize(self):
        assert hasattr(self, "clkin")

# Xilinx / Spartan6 --------------------------------------------------------------------------------

class S6PLL(XilinxClocking):
    nclkouts_max = 6
    clkin_freq_range = (19e6, 540e6)

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("S6PLL")
        self.logger.info("Creating S6PLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 52 + 1)
        self.vco_freq_range      = {
            -1: (400e6, 1000e6),
            -2: (400e6, 1000e6),
            -3: (400e6, 1080e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        self.params.update(
            p_SIM_DEVICE     = "SPARTAN6",
            p_BANDWIDTH      = "OPTIMIZED",
            p_COMPENSATION   = "INTERNAL",
            p_REF_JITTER     = .01, p_CLK_FEEDBACK="CLKFBOUT",
            p_CLKIN1_PERIOD  = 1e9/self.clkin_freq,
            p_CLKIN2_PERIOD  = 0.,
            p_CLKFBOUT_MULT  = config["clkfbout_mult"],
            p_CLKFBOUT_PHASE = 0.,
            p_DIVCLK_DIVIDE  = config["divclk_divide"],
            i_CLKINSEL       = 1,
            i_RST            = self.reset,
            i_CLKIN1         = self.clkin,
            i_CLKFBIN        = pll_fb,
            o_CLKFBOUT       = pll_fb,
            o_LOCKED         = self.locked,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_CLKOUT{}_DIVIDE".format(n)]     = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)]      = float(config["clkout{}_phase".format(n)])
            self.params["p_CLKOUT{}_DUTY_CYCLE".format(n)] = 0.5
            self.params["o_CLKOUT{}".format(n)]            = clk
        self.specials += Instance("PLL_ADV", **self.params)


class S6DCM(XilinxClocking):
    """ single output with f_out = f_in * {2 .. 256} / {1 .. 256} """
    nclkouts_max = 1
    clkfbout_mult_frange = (2, 256 + 1)
    clkout_divide_range  = (1, 256 + 1)

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("S6DCM")
        self.logger.info("Creating S6DCM, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 2) # FIXME
        self.clkin_freq_range = {
            -1: (0.5e6, 200e6),
            -2: (0.5e6, 333e6),
            -3: (0.5e6, 375e6),
        }[speedgrade]

        self.vco_freq_range = {
            -1: (5e6, 1e16),
            -2: (5e6, 1e16),
            -3: (5e6, 1e16),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        clk, f, p, m = sorted(self.clkouts.items())[0][1]
        self.params.update(
            p_CLKFX_MULTIPLY  = config["clkfbout_mult"],
            p_CLKFX_DIVIDE    = config["clkout0_divide"] * config["divclk_divide"],
            p_SPREAD_SPECTRUM = "NONE",
            p_CLKIN_PERIOD    = 1e9/self.clkin_freq,
            i_CLKIN           = self.clkin,
            i_RST             = self.reset,
            i_FREEZEDCM       = 0,
            o_CLKFX           = clk,
            o_LOCKED          = self.locked,
        )
        self.specials += Instance("DCM_CLKGEN", **self.params)

    def expose_drp(self):
        self._cmd_data      = CSRStorage(10)
        self._send_cmd_data = CSR()
        self._send_go       = CSR()
        self._status        = CSRStatus(4)

        progdata = Signal()
        progen   = Signal()
        progdone = Signal()
        locked   = Signal()

        self.params.update(
            i_PROGCLK         = ClockSignal(),
            i_PROGDATA        = progdata,
            i_PROGEN          = progen,
            o_PROGDONE        = progdone
        )

        remaining_bits = Signal(max=11)
        transmitting   = Signal()
        self.comb += transmitting.eq(remaining_bits != 0)
        sr = Signal(10)
        self.sync += [
            If(self._send_cmd_data.re,
                remaining_bits.eq(10),
                sr.eq(self._cmd_data.storage)
            ).Elif(transmitting,
                remaining_bits.eq(remaining_bits - 1),
                sr.eq(sr[1:])
            )
        ]
        self.comb += [
            progdata.eq(transmitting & sr[0]),
            progen.eq(transmitting | self._send_go.re)
        ]

        # Enforce gap between commands
        busy_counter = Signal(max=14)
        busy         = Signal()
        self.comb += busy.eq(busy_counter != 0)
        self.sync += If(self._send_cmd_data.re,
                busy_counter.eq(13)
            ).Elif(busy,
                busy_counter.eq(busy_counter - 1)
            )

        self.comb += self._status.status.eq(Cat(busy, progdone, self.locked))

        self.logger.info("Exposing DRP interface.")

# Xilinx / 7-Series --------------------------------------------------------------------------------

class S7PLL(XilinxClocking):
    nclkouts_max = 6
    clkin_freq_range = (19e6, 800e6)

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("S7PLL")
        self.logger.info("Creating S7PLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 56+1)
        self.vco_freq_range = {
            -1: (800e6, 1600e6),
            -2: (800e6, 1866e6),
            -3: (800e6, 2133e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        self.params.update(
            p_STARTUP_WAIT="FALSE", o_LOCKED=self.locked, i_RST=self.reset,

            # VCO
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=1e9/self.clkin_freq,
            p_CLKFBOUT_MULT=config["clkfbout_mult"], p_DIVCLK_DIVIDE=config["divclk_divide"],
            i_CLKIN1=self.clkin, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)] = clk
        self.specials += Instance("PLLE2_ADV", **self.params)


class S7MMCM(XilinxClocking):
    nclkouts_max         = 7
    clkout0_divide_range = (1, (128 + 1/8), 1/8) # Fractional Divide available on CLKOUT0

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("S7MMCM")
        self.logger.info("Creating S7MMCM, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 106+1)
        self.clkin_freq_range = {
            -1: (10e6,  800e6),
            -2: (10e6,  933e6),
            -3: (10e6, 1066e6),
        }[speedgrade]

        self.vco_freq_range = {
            -1: (600e6, 1200e6),
            -2: (600e6, 1440e6),
            -3: (600e6, 1600e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        mmcm_fb = Signal()
        self.params.update(
            p_BANDWIDTH="OPTIMIZED", o_LOCKED=self.locked, i_RST=self.reset,

            # VCO
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=1e9/self.clkin_freq,
            p_CLKFBOUT_MULT_F=config["clkfbout_mult"], p_DIVCLK_DIVIDE=config["divclk_divide"],
            i_CLKIN1=self.clkin, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            if n == 0:
                self.params["p_CLKOUT{}_DIVIDE_F".format(n)] = config["clkout{}_divide".format(n)]
            else:
                self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)]       = clk
        self.specials += Instance("MMCME2_ADV", **self.params)


class S7IDELAYCTRL(Module):
    def __init__(self, cd, reset_cycles=16):
        reset_counter = Signal(log2_int(reset_cycles), reset=reset_cycles - 1)
        ic_reset      = Signal(reset=1)
        sync = getattr(self.sync, cd.name)
        sync += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=cd.clk, i_RST=ic_reset)

# Xilinx / Ultrascale ------------------------------------------------------------------------------

# TODO:
# - use Ultrascale primitives instead of 7-Series' ones. (Vivado recognize and convert them).

class USPLL(XilinxClocking):
    nclkouts_max = 6

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("USPLL")
        self.logger.info("Creating USPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 56+1)
        self.clkin_freq_range = {
            -1: (70e6,  800e6),
            -2: (70e6,  933e6),
            -3: (70e6, 1066e6),
        }[speedgrade]
        self.vco_freq_range = {
            -1: (600e6, 1200e6),
            -2: (600e6, 1335e6),
            -3: (600e6, 1335e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        pll_fb = Signal()
        self.params.update(
            p_STARTUP_WAIT="FALSE", o_LOCKED=self.locked, i_RST=self.reset,

            # VCO
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=1e9/self.clkin_freq,
            p_CLKFBOUT_MULT=config["clkfbout_mult"], p_DIVCLK_DIVIDE=config["divclk_divide"],
            i_CLKIN1=self.clkin, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)]  = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)]        = clk
        self.specials += Instance("PLLE2_ADV", **self.params)


class USMMCM(XilinxClocking):
    nclkouts_max = 7

    def __init__(self, speedgrade=-1):
        self.logger = logging.getLogger("USMMCM")
        self.logger.info("Creating UMMCM, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 106+1)
        self.clkin_freq_range = {
            -1: (10e6,  800e6),
            -2: (10e6,  933e6),
            -3: (10e6, 1066e6),
        }[speedgrade]
        self.vco_freq_range = {
            -1: (600e6, 1200e6),
            -2: (600e6, 1440e6),
            -3: (600e6, 1600e6),
        }[speedgrade]

    def do_finalize(self):
        XilinxClocking.do_finalize(self)
        config = self.compute_config()
        mmcm_fb = Signal()
        self.params.update(
            p_BANDWIDTH="OPTIMIZED", o_LOCKED=self.locked, i_RST=self.reset,

            # VCO
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=1e9/self.clkin_freq,
            p_CLKFBOUT_MULT_F=config["clkfbout_mult"], p_DIVCLK_DIVIDE=config["divclk_divide"],
            i_CLKIN1=self.clkin, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            if n == 0:
                self.params["p_CLKOUT{}_DIVIDE_F".format(n)] = config["clkout{}_divide".format(n)]
            else:
                self.params["p_CLKOUT{}_DIVIDE".format(n)] = config["clkout{}_divide".format(n)]
            self.params["p_CLKOUT{}_PHASE".format(n)] = config["clkout{}_phase".format(n)]
            self.params["o_CLKOUT{}".format(n)]       = clk
        self.specials += Instance("MMCME2_ADV", **self.params)


class USIDELAYCTRL(Module):
    def __init__(self, cd_ref, cd_sys, reset_cycles=64, ready_cycles=64):
        cd_sys.rst.reset = 1
        self.clock_domains.cd_ic = ClockDomain()
        ic_reset_counter = Signal(max=reset_cycles, reset=reset_cycles-1)
        ic_reset         = Signal(reset=1)
        cd_ref_sync      = getattr(self.sync, cd_ref.name)
        cd_ref_sync += [
            If(ic_reset_counter != 0,
                ic_reset_counter.eq(ic_reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        ]
        ic_ready_counter = Signal(max=ready_cycles, reset=ready_cycles-1)
        ic_ready         = Signal()
        self.comb += self.cd_ic.clk.eq(cd_sys.clk)
        self.sync.ic += [
            If(ic_ready,
                If(ic_ready_counter != 0,
                    ic_ready_counter.eq(ic_ready_counter - 1)
                ).Else(
                    cd_sys.rst.eq(0)
                )
            )
        ]
        self.specials += [
            Instance("IDELAYCTRL",
                p_SIM_DEVICE = "ULTRASCALE",
                i_REFCLK     = cd_ref.clk,
                i_RST        = ic_reset,
                o_RDY        = ic_ready),
            AsyncResetSynchronizer(self.cd_ic, ic_reset)
        ]

# Lattice / iCE40 ----------------------------------------------------------------------------------

# TODO:
# - add phase support.
# - add support for GENCLK_HALF to be able to generate clock down to 8MHz.

class iCE40PLL(Module):
    nclkouts_max = 1
    divr_range = (0,  16)
    divf_range = (0, 128)
    divq_range = (0,   7)
    clki_freq_range = ( 10e6,  133e9)
    clko_freq_range = ( 16e6,  275e9)
    vco_freq_range  = (533e6, 1066e6)

    def __init__(self, primitive="SB_PLL40_CORE"):
        assert primitive in ["SB_PLL40_CORE", "SB_PLL40_PAD"]
        self.logger = logging.getLogger("iCE40PLL")
        self.logger.info("Creating iCE40PLL, {} primitive.".format(colorer(primitive)))
        self.primitive  = primitive
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        (clki_freq_min, clki_freq_max) = self.clki_freq_range
        assert freq >= clki_freq_min
        assert freq <= clki_freq_max
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, 0, margin)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for divr in range(*self.divr_range):
            for divf in range(*self.divf_range):
                all_valid = True
                vco_freq = self.clkin_freq/(divr + 1)*(divf +  1)
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        for divq in range(*self.divq_range):
                            clk_freq = vco_freq/(2**divq)
                            if abs(clk_freq - f) <= f*m:
                                config["clkout_freq"] = clk_freq
                                config["divq"]        = divq
                                valid = True
                                break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["divr"] = divr
                    config["divf"] = divf
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        config = self.compute_config()
        clkfb = Signal()
        for f, v in [(17e6, 1), (26e6, 2), (44e6, 3), (66e6, 4), (101e6, 5), (133e6, 6)]:
            pfd_freq = self.clkin_freq/(config["divr"] + 1)
            if pfd_freq < f:
                filter_range = v
                break
        self.params.update(
            p_FEEDBACK_PATH = "SIMPLE",
            p_FILTER_RANGE  = filter_range,
            i_RESETB        = ~self.reset,
            o_LOCK          = self.locked,
        )
        if self.primitive == "SB_PLL40_CORE":
            self.params.update(i_REFERENCECLK=self.clkin)
        if self.primitive == "SB_PLL40_PAD":
            self.params.update(i_PACKAGEPIN=self.clkin)
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_DIVR"]         = config["divr"]
            self.params["p_DIVF"]         = config["divf"]
            self.params["p_DIVQ"]         = config["divq"]
            self.params["o_PLLOUTGLOBAL"] = clk
        self.specials += Instance(self.primitive, **self.params)

# Lattice / ECP5 -----------------------------------------------------------------------------------

class ECP5PLL(Module):
    nclkouts_max    = 3
    clki_div_range  = (1, 128+1)
    clkfb_div_range = (1, 128+1)
    clko_div_range  = (1, 128+1)
    clki_freq_range = (    8e6,  400e6)
    clko_freq_range = (3.125e6,  400e6)
    vco_freq_range  = (  400e6,  800e6)

    def __init__(self):
        self.logger = logging.getLogger("ECP5PLL")
        self.logger.info("Creating ECP5PLL.")
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        (clki_freq_min, clki_freq_max) = self.clki_freq_range
        assert freq >= clki_freq_min
        assert freq <= clki_freq_max
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for clki_div in range(*self.clki_div_range):
            config["clki_div"] = clki_div
            for clkfb_div in range(*self.clkfb_div_range):
                all_valid = True
                vco_freq = self.clkin_freq/clki_div*clkfb_div*1 # clkos3_div=1
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        for d in range(*self.clko_div_range):
                            clk_freq = vco_freq/d
                            if abs(clk_freq - f) <= f*m:
                                config["clko{}_freq".format(n)]  = clk_freq
                                config["clko{}_div".format(n)]   = d
                                config["clko{}_phase".format(n)] = p
                                valid = True
                                break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["clkfb_div"] = clkfb_div
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        config = self.compute_config()
        clkfb  = Signal()
        self.params.update(
            attr=[
                ("FREQUENCY_PIN_CLKI",     str(self.clkin_freq/1e6)),
                ("ICP_CURRENT",            "6"),
                ("LPF_RESISTOR",          "16"),
                ("MFG_ENABLE_FILTEROPAMP", "1"),
                ("MFG_GMCREF_SEL",         "2")],
            i_RST           = self.reset,
            i_CLKI          = self.clkin,
            o_LOCK          = self.locked,
            p_FEEDBK_PATH   = "INT_OS3", # CLKOS3 reserved for feedback with div=1.
            p_CLKOS3_ENABLE = "ENABLED",
            p_CLKOS3_DIV    = 1,
            p_CLKFB_DIV     = config["clkfb_div"],
            p_CLKI_DIV      = config["clki_div"],
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            n_to_l = {0: "P", 1: "S", 2: "S2"}
            div    = config["clko{}_div".format(n)]
            cphase = int(p*(div + 1)/360 + div)
            self.params["p_CLKO{}_ENABLE".format(n_to_l[n])] = "ENABLED"
            self.params["p_CLKO{}_DIV".format(n_to_l[n])]    = div
            self.params["p_CLKO{}_FPHASE".format(n_to_l[n])] = 0
            self.params["p_CLKO{}_CPHASE".format(n_to_l[n])] = cphase
            self.params["o_CLKO{}".format(n_to_l[n])]        = clk
        self.specials += Instance("EHXPLLL", **self.params)

# Intel / Generic ---------------------------------------------------------------------------------

class IntelClocking(Module, AutoCSR):
    def __init__(self, vco_margin=0):
        self.vco_margin = vco_margin
        self.reset      = Signal()
        self.locked     = Signal()
        self.clkin_freq = None
        self.vcxo_freq  = None
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def register_clkin(self, clkin, freq):
        self.clkin = Signal()
        if isinstance(clkin, (Signal, ClockSignal)):
            self.comb += self.clkin.eq(clkin)
        elif isinstance(clkin, Record):
            self.specials += DifferentialInput(clkin.p, clkin.n, self.clkin)
        else:
            raise ValueError
        self.clkin_freq = freq
        register_clkin_log(self.logger, clkin, freq)

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked | self.reset)
        self.comb += cd.clk.eq(clkout)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for n in range(*self.n_div_range):
            config["n"] = n
            for m in reversed(range(*self.m_div_range)):
                all_valid = True
                vco_freq = self.clkin_freq*m/n
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if (vco_freq >= vco_freq_min*(1 + self.vco_margin) and
                    vco_freq <= vco_freq_max*(1 - self.vco_margin)):
                    for _n, (clk, f, p, _m) in sorted(self.clkouts.items()):
                        valid = False
                        for c in clkdiv_range(*self.c_div_range):
                            clk_freq = vco_freq/c
                            if abs(clk_freq - f) <= f*_m:
                                config["clk{}_freq".format(_n)]   = clk_freq
                                config["clk{}_divide".format(_n)] = c
                                config["clk{}_phase".format(_n)]  = p
                                valid = True
                                break
                            if valid:
                                break
                    if not valid:
                        all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["m"]   = m
                    compute_config_log(self.logger, config)
                    return config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        assert hasattr(self, "clkin")
        config = self.compute_config()
        clks = Signal(self.nclkouts)
        self.params.update(
            p_BANDWIDTH_TYPE         = "AUTO",
            p_COMPENSATE_CLOCK       = "CLK0",
            p_INCLK0_INPUT_FREQUENCY = int(1e12/self.clkin_freq),
            p_OPERATION_MODE         = "NORMAL",
            i_INCLK                  = self.clkin,
            o_CLK                    = clks,
            i_ARESET                 = 0,
            i_CLKENA                 = 2**self.nclkouts_max - 1,
            i_EXTCLKENA              = 0xf,
            i_FBIN                   = 1,
            i_PFDENA                 = 1,
            i_PLLENA                 = 1,
            o_LOCKED                 = self.locked,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            clk_phase_ps = int((1e12/config["clk{}_freq".format(n)])*config["clk{}_phase".format(n)]/360)
            self.params["p_CLK{}_DIVIDE_BY".format(n)]   = config["clk{}_divide".format(n)]
            self.params["p_CLK{}_DUTY_CYCLE".format(n)]  = 50
            self.params["p_CLK{}_MULTIPLY_BY".format(n)] = config["m"]
            self.params["p_CLK{}_PHASE_SHIFT".format(n)] = clk_phase_ps
            self.comb += clk.eq(clks[n])
        self.specials += Instance("ALTPLL", **self.params)

# Intel / CycloneIV -------------------------------------------------------------------------------

class CycloneIVPLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    vco_freq_range = (600e6, 1300e6)
    def __init__(self, speedgrade="-6"):
        self.logger = logging.getLogger("CycloneIVPLL")
        self.logger.info("Creating CycloneIVPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clkin_freq_range = {
            "-6" : (5e6, 472.5e6),
            "-7" : (5e6, 472.5e6),
            "-8" : (5e6, 472.5e6),
            "-8L": (5e6, 362e6),
            "-9L": (5e6, 256e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-6" : (0e6, 472.5e6),
            "-7" : (0e6, 450e6),
            "-8" : (0e6, 402.5e6),
            "-8L": (0e6, 362e6),
            "-9L": (0e6, 265e6),
        }[speedgrade]

# Intel / CycloneV --------------------------------------------------------------------------------

class CycloneVPLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range  = (5e6, 325e6)  # FIXME: use
    clkfin_pfd_freq_range = (50e6, 160e6) # FIXME: use
    def __init__(self, speedgrade="-C6"):
        self.logger = logging.getLogger("CycloneVPLL")
        self.logger.info("Creating CycloneVPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clkin_freq_range = {
            "-C6" : (5e6, 670e6),
            "-C7" : (5e6, 622e6),
            "-I7" : (5e6, 622e6),
            "-C8" : (5e6, 622e6),
            "-A7" : (5e6, 500e6),
        }[speedgrade]
        self.vco_freq_range = {
            "-C6" : (600e6, 1600e6),
            "-C7" : (600e6, 1600e6),
            "-I7" : (600e6, 1600e6),
            "-C8" : (600e6, 1300e6),
            "-A7" : (600e6, 1300e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-C6" : (0e6, 550e6),
            "-C7" : (0e6, 550e6),
            "-I7" : (0e6, 550e6),
            "-C8" : (0e6, 460e6),
            "-A7" : (0e6, 460e6),
        }[speedgrade]

# Intel / Cyclone10LP ------------------------------------------------------------------------------

class Cyclone10LPPLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range  = (5e6, 325e6)  # FIXME: use
    vco_freq_range        = (600e6, 1300e6)
    def __init__(self, speedgrade="-C6"):
        self.logger = logging.getLogger("Cyclone10LPPLL")
        self.logger.info("Creating Cyclone10LPPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clkin_freq_range = {
            "-C6" : (5e6, 472.5e6),
            "-C8" : (5e6, 472.5e6),
            "-I7" : (5e6, 472.5e6),
            "-A7" : (5e6, 472.5e6),
            "-I8" : (5e6, 362e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-C6" : (0e6, 472.5e6),
            "-C8" : (0e6, 402.5e6),
            "-I7" : (0e6, 450e6),
            "-A7" : (0e6, 450e6),
            "-I8" : (0e6, 362e6),
        }[speedgrade]

# Intel / Max10 ------------------------------------------------------------------------------------

class Max10PLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_freq_range     = (5e6, 472.5e6)
    clkin_pfd_freq_range = (5e6, 325e6)  # FIXME: use
    vco_freq_range       = (600e6, 1300e6)
    def __init__(self, speedgrade="-6"):
        self.logger = logging.getLogger("Max10PLL")
        self.logger.info("Creating Max10PLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clko_freq_range = {
            "-6" : (0e6, 472.5e6),
            "-7" : (0e6, 450e6),
            "-8" : (0e6, 402.5e6),
        }[speedgrade]
