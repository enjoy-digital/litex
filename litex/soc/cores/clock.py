# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
# License: BSD

"""Clock Abstraction Modules"""

from migen import *
from migen.genlib.io import DifferentialInput
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.interconnect.csr import *


def period_ns(freq):
    return 1e9/freq

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

    def create_clkout(self, cd, freq, phase=0, buf="bufg", margin=1e-2, with_reset=True):
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        self.nclkouts += 1
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
            else:
                raise ValueError

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
                        for d in range(*self.clkout_divide_range):
                            clk_freq = vco_freq/d
                            if abs(clk_freq - f) < f*m:
                                config["clkout{}_freq".format(n)]   = clk_freq
                                config["clkout{}_divide".format(n)] = d
                                config["clkout{}_phase".format(n)]  = p
                                valid = True
                                break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["clkfbout_mult"] = clkfbout_mult
                    return config
        raise ValueError("No PLL config found")

    def expose_drp(self):
        self.drp_reset = CSR()
        self.drp_read  = CSR()
        self.drp_write = CSR()
        self.drp_drdy  = CSRStatus()
        self.drp_adr   = CSRStorage(7)
        self.drp_dat_w = CSRStorage(16)
        self.drp_dat_r = CSRStatus(16)

        # # #

        drp_drdy = Signal()
        self.params.update(
            i_DCLK  = ClockSignal(),
            i_DWE   = self.drp_write.re,
            i_DEN   = self.drp_read.re | self.drp_write.re,
            o_DRDY  = drp_drdy,
            i_DADDR = self.drp_adr.storage,
            i_DI    = self.drp_dat_w.storage,
            o_DO    = self.drp_dat_r.status
        )
        self.sync += [
            If(self.drp_read.re | self.drp_write.re,
                self.drp_drdy.status.eq(0)
            ).Elif(drp_drdy,
                self.drp_drdy.status.eq(1)
            )
        ]

    def do_finalize(self):
        assert hasattr(self, "clkin")

# Xilinx / Spartan6 --------------------------------------------------------------------------------

class S6PLL(XilinxClocking):
    nclkouts_max = 6
    clkin_freq_range = (19e6, 540e6)

    def __init__(self, speedgrade=-1):
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
        XilinxClocking.__init__(self)
        self.divclk_divide_range = (1, 1) # FIXME
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

# Xilinx / 7-Series --------------------------------------------------------------------------------

class S7PLL(XilinxClocking):
    nclkouts_max = 6
    clkin_freq_range = (19e6, 800e6)

    def __init__(self, speedgrade=-1):
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
            p_STARTUP_WAIT="FALSE", o_LOCKED=self.locked,

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
    nclkouts_max = 7

    def __init__(self, speedgrade=-1):
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
            p_BANDWIDTH="OPTIMIZED", o_LOCKED=self.locked,

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
    def __init__(self, cd):
        reset_counter = Signal(4, reset=15)
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
            p_STARTUP_WAIT="FALSE", o_LOCKED=self.locked,

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
            p_BANDWIDTH="OPTIMIZED", o_LOCKED=self.locked,

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
    def __init__(self, cd):
        reset_counter = Signal(6, reset=63)
        ic_reset = Signal(reset=1)
        sync = getattr(self.sync, cd.name)
        sync += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL",
            p_SIM_DEVICE = "ULTRASCALE",
            i_REFCLK     = cd.clk,
            i_RST        = ic_reset
        )

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

    def __init__(self):
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

    def create_clkout(self, cd, freq, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, 0, margin)
        self.nclkouts += 1
        self.comb += cd.clk.eq(clkout)

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
                            if abs(clk_freq - f) < f*m:
                                config["divq"] = divq
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
            i_REFERENCECLK  = self.clkin,
            o_LOCK          = self.locked,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            self.params["p_DIVR"]         = config["divr"]
            self.params["p_DIVF"]         = config["divf"]
            self.params["p_DIVQ"]         = config["divq"]
            self.params["o_PLLOUTGLOBAL"] = clk
        self.specials += Instance("SB_PLL40_CORE", **self.params)

# Lattice / ECP5 -----------------------------------------------------------------------------------

# TODO:
# - add proper phase support.

class ECP5PLL(Module):
    nclkouts_max    = 3
    clkfb_div_range = (1, 128+1)
    clko_div_range  = (1, 128+1)
    clki_freq_range = (    8e6,  400e6)
    clko_freq_range = (3.125e6,  400e6)
    vco_freq_range  = (  550e6, 1250e6)

    def __init__(self):
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

    def create_clkout(self, cd, freq, phase=0, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        clkout = Signal()
        self.clkouts[self.nclkouts] = (clkout, freq, phase, margin)
        self.nclkouts += 1
        self.comb += cd.clk.eq(clkout)

    def compute_config(self):
        config = {}
        config["clki_div"] = 1
        for clkfb_div in range(*self.clkfb_div_range):
            all_valid = True
            vco_freq = self.clkin_freq*clkfb_div*1 # clkos3_div=1
            (vco_freq_min, vco_freq_max) = self.vco_freq_range
            if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                    valid = False
                    for d in range(*self.clko_div_range):
                        clk_freq = vco_freq/d
                        if abs(clk_freq - f) < f*m:
                            config["clko{}_freq".format(n)] = clk_freq
                            config["clko{}_div".format(n)] = d
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
                return config
        raise ValueError("No PLL config found")

    def do_finalize(self):
        config = self.compute_config()
        clkfb = Signal()
        self.params.update(
            attr=[
                ("ICP_CURRENT",            "6"),
                ("LPF_RESISTOR",          "16"),
                ("MFG_ENABLE_FILTEROPAMP", "1"),
                ("MFG_GMCREF_SEL",         "2")],
            i_RST=self.reset,

            i_CLKI = self.clkin,
            o_LOCK = self.locked,

            p_FEEDBK_PATH   = "INT_OS3",   # CLKOS3 reserved for
            p_CLKOS3_ENABLE = "ENABLED", # feedback with div=1.
            p_CLKOS3_DIV    = 1,

            p_CLKFB_DIV=config["clkfb_div"],
            p_CLKI_DIV=1,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            n_to_l = {0: "P", 1: "S", 2: "S2"}
            self.params["p_CLKO{}_ENABLE".format(n_to_l[n])] = "ENABLED"
            self.params["p_CLKO{}_DIV".format(n_to_l[n])]    = config["clko{}_div".format(n)]
            self.params["p_CLKO{}_FPHASE".format(n_to_l[n])] = 0
            self.params["p_CLKO{}_CPHASE".format(n_to_l[n])] = p
            self.params["o_CLKO{}".format(n_to_l[n])]        = clk
        self.specials += Instance("EHXPLLL", **self.params)
