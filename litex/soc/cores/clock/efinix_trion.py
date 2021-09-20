#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import *
from litex.soc.cores.clock.common import *

from litex.build.efinix import EfinixDbParser

class Open(Signal): pass

#TODO: do somthing else
count = 0

# Efinix / TRIONPLL ----------------------------------------------------------------------------------

class TRIONPLL(Module):
    nclkouts_max = 4
    def __init__(self, platform, with_reset=False):
        global count
        self.logger = logging.getLogger("TRIONPLL")
        self.logger.info("Creating TRIONPLL.".format())
        self.platform   = platform
        self.nclkouts   = 0
        self.pll_name   = "pll{}".format(count)
        self.reset      = Signal()
        self.locked     = Signal()

        block = {}
        count += 1

        block['type'] = 'PLL'
        block['name'] = self.pll_name
        block['clk_out'] = []

        pll_locked_name = self.pll_name + '_locked'
        block['locked'] = pll_locked_name
        io = self.platform.add_iface_io(pll_locked_name)
        self.comb += self.locked.eq(io)

        block['reset'] = ''
        if with_reset:
            pll_reset_name = self.pll_name + '_reset'
            block['reset'] = pll_reset_name
            io = self.platform.add_iface_io(pll_reset_name)
            self.comb += io.eq(self.reset)

        self.platform.toolchain.ifacewriter.blocks.append(block)

    def register_clkin(self, clkin, freq):
        block = self.platform.toolchain.ifacewriter.get_block(self.pll_name)

        # If clkin has resource, PLL clock input is EXTERNAL
        # When PLL clock is external, it must not be present in the top file
        # Add a test on clkin resource here
        block['input_clock_name'] = self.platform.get_pin_name(clkin)
        pin_name = self.platform.get_pin_location(clkin)

        self.platform.delete(clkin)

        #tpl = "create_clock -name {clk} -period {period} [get_ports {{{clk}}}]"
        #sdc = self.platform.toolchain.additional_sdc_commands
        #sdc.append(tpl.format(clk=block['input_clock_name'], period=1/freq))

        parser = EfinixDbParser(self.platform.efinity_path, self.platform.device)
        (pll_res, clock_no) = parser.get_pll_inst_from_pin(pin_name)

        block['input_clock'] = 'EXTERNAL'
        block['input_freq'] = freq
        block['resource'] = pll_res
        block['clock_no'] = clock_no

        self.logger.info("Using {}".format(pll_res))
        self.logger.info("Clock source: {}, using EXT_CLK{}".format(block['input_clock'], clock_no))

    def create_clkout(self, cd, freq, phase=0, margin=1e-2, with_reset=True):
        assert self.nclkouts < self.nclkouts_max

        clk_out_name = '{}_CLKOUT{}'.format(self.pll_name, self.nclkouts)

        self.platform.add_extension([(clk_out_name, 0, Pins(1))])
        tmp = self.platform.request(clk_out_name)

        if with_reset:
            self.specials += AsyncResetSynchronizer(cd, ~self.locked)

        # We don't want this IO to be in the interface configuration file as a simple GPIO
        self.platform.toolchain.specials_gpios.append(tmp)
        self.comb += cd.clk.eq(tmp)
        create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        self.nclkouts += 1

        block = self.platform.toolchain.ifacewriter.get_block(self.pll_name)
        block['clk_out'].append([clk_out_name, freq, phase, margin])

    def compute_config(self):
        pass

    def set_configuration(self):
        pass

    def do_finalize(self):
        pass