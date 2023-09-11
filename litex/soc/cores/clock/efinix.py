#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.build.generic_platform import *
from litex.soc.cores.clock.common import *

# Efinix / TRIONPLL ----------------------------------------------------------------------------------

class EFINIXPLL(LiteXModule):
    n            = 0
    nclkouts_max = 3
    def __init__(self, platform,version="V1_V2"):
        self.logger = logging.getLogger("EFINIXPLL")

        if version == "V1_V2":
            self.type = "TRIONPLL"
        elif version == "V3":
            self.type = "TITANIUMPLL"
        else:
            self.logger.error("PLL version {} not supported".format(version))
            quit()

        self.logger.info("Creating {}".format(colorer(self.type, color="green")))
        self.platform   = platform
        self.nclkouts   = 0
        self.reset      = Signal()
        self.locked     = Signal()
        self.name       = f"pll{self.n}"
        EFINIXPLL.n += 1 # FIXME: Improve.

        # Create PLL block.
        block = {}
        block["type"]    = "PLL"
        block["name"]    = self.name
        block["clk_out"] = []
        block["locked"]  = self.name + "_locked"
        block["rstn"]    = self.name + "_rstn"
        block["version"] = version
        self.platform.toolchain.ifacewriter.blocks.append(block)

        # Connect PLL's rstn/locked.
        self.comb += self.platform.add_iface_io(self.name + "_rstn").eq(~self.reset)
        self.comb += self.locked.eq(self.platform.add_iface_io(self.name + "_locked"))

    def register_clkin(self, clkin, freq, name=""):
        block = self.platform.toolchain.ifacewriter.get_block(self.name)

        block["input_clock_name"] = self.platform.get_pin_name(clkin)

        # If clkin has a pin number, PLL clock input is EXTERNAL
        if self.platform.get_pin_location(clkin):
            pad_name = self.platform.get_pin_location(clkin)[0]
            # PLL v1 needs pin name
            pin_name = self.platform.parser.get_pad_name_from_pin(pad_name)
            if pin_name.count("_") == 2:
                pin_name = pin_name.rsplit("_", 1)[0]
            self.platform.toolchain.excluded_ios.append(clkin)

            #tpl = "create_clock -name {clk} -period {period} [get_ports {{{clk}}}]"
            #sdc = self.platform.toolchain.additional_sdc_commands
            #sdc.append(tpl.format(clk=block["input_clock_name"], period=1/freq))

            try:
                (pll_res, clock_no) = self.platform.parser.get_pll_inst_from_pin(pad_name)
            except:
                self.logger.error("Cannot find a pll with {} as input".format(pad_name))
                quit()

            block["input_clock"]     = "EXTERNAL"
            block["input_clock_pad"] = pin_name
            block["resource"]        = pll_res
            block["clock_no"]        = clock_no
            self.logger.info("Clock source: {}, using EXT_CLK{}".format(block["input_clock"], clock_no))
            self.platform.get_pll_resource(pll_res)
        else:
            block["input_clock"]  = "INTERNAL"
            block["resource"]     = self.platform.get_free_pll_resource()
            block["input_signal"] = name
            self.logger.info("Clock source: {}".format(block["input_clock"]))

        self.logger.info("PLL used     : " + colorer(str(self.platform.pll_used), "cyan"))
        self.logger.info("PLL available: " + colorer(str(self.platform.pll_available), "cyan"))

        block["input_freq"] = freq

        self.logger.info("Use {}".format(colorer(block["resource"], "green")))

    def create_clkout(self, cd, freq, phase=0, margin=0, name="", with_reset=True):
        assert self.nclkouts < self.nclkouts_max

        clk_out_name = f"{self.name}_clkout{self.nclkouts}" if name == "" else name

        if cd is not None:
            self.platform.add_extension([(clk_out_name, 0, Pins(1))])
            clk_name = f"{cd.name}_clk"
            clk_out = self.platform.request(clk_out_name)
            self.comb += cd.clk.eq(clk_out)
            self.platform.add_period_constraint(clk=clk_out, period=1e9/freq, name=clk_name)
            if with_reset:
                self.specials += AsyncResetSynchronizer(cd, ~self.locked)
            self.platform.toolchain.excluded_ios.append(clk_out_name)

        create_clkout_log(self.logger, clk_out_name, freq, margin, self.nclkouts)

        self.nclkouts += 1

        block = self.platform.toolchain.ifacewriter.get_block(self.name)
        block["clk_out"].append([clk_out_name, freq, phase, margin])

    def extra(self, extra):
        block = self.platform.toolchain.ifacewriter.get_block(self.name)
        block["extra"] = extra

    def compute_config(self):
        pass

    def set_configuration(self):
        pass

    def do_finalize(self):
        pass

# Efinix / TITANIUMPLL -----------------------------------------------------------------------------

class TITANIUMPLL(EFINIXPLL):
    nclkouts_max = 5
    def __init__(self, platform):
        EFINIXPLL.__init__(self, platform, version="V3")

# Efinix / TRION ----------------------------------------------------------------------------------

class TRIONPLL(EFINIXPLL):
    nclkouts_max = 3
    def __init__(self, platform):
        EFINIXPLL.__init__(self, platform, version="V1_V2")
