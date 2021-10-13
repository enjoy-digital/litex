#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import *
from litex.build.efinix import common, efinity
from litex.build.efinix import EfinixDbParser

# EfinixPlatform -----------------------------------------------------------------------------------

class EfinixPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="efinity", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)

        self.pll_available = ['PLL_TL0', 'PLL_TR0', 'PLL_TR1', 'PLL_TR2', 'PLL_TR3', 'PLL_BR0', 'PLL_BR1', 'PLL_BR2', 'PLL_BL0']
        self.pll_used = []

        if 'LITEX_ENV_EFINITY' in os.environ:
            self.efinity_path = os.environ['LITEX_ENV_EFINITY'].rstrip('/')
            os.environ['EFINITY_HOME'] = self.efinity_path
        else:
            raise OSError('Unable to find Efinity toolchain, please set LITEX_ENV_EFINITY to ${install_dir}')

        if toolchain == "efinity":
            self.toolchain = efinity.EfinityToolchain(self.efinity_path)
        else:
            raise ValueError("Unknown toolchain")

        self.parser = EfinixDbParser(self.efinity_path, self.device)

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.efinix_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
            attr_translate=self.toolchain.attr_translate, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        self.toolchain.add_false_path_constraint(self, from_, to)

    # TODO: fix this when pin is like p = platform.request("sdios")
    # get_pin_location(p[1])
    # not tested with subsignal like get_pin_location(p.clk)
    def get_pin_location(self, sig):
        if sig is None:
            return None
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if (s == sig) and (pins[0] != 'X'):
                    return pins
        return None

    def get_pin_name(self, sig):
        if sig is None:
            return None
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if s == sig:
                if resource[2]:
                    return resource[0] + '_' + resource[2]
                else:
                    return resource[0]
        return None

    def get_sig_constraint(self, sig):
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if s == sig:
                return sc
        return None

    def add_iface_io(self, name, size=1, append=True):
        self.add_extension([(name, 0, Pins(size))])
        tmp = self.request(name)
        # We don't want this IO to be in the interface configuration file as a simple GPIO
        if append:
            self.toolchain.specials_gpios.append(tmp)
        return tmp

    def add_iface_ios(self, io, append=True):
        self.add_extension(io)
        tmp = self.request(io[0][0])
        if append:
            for s in tmp.flatten():
                self.toolchain.specials_gpios.append(s)
        return tmp

    def del_record_signal(self, record, sig):
            for pos, (name, item) in enumerate(vars(record).items()):
                    if isinstance(item, Signal):
                            if item == sig:
                                    # Two first pos are name and layout
                                    del record.layout[pos-2]
                                    delattr(record, name)
                                    break

    def get_pll_resource(self, name):
        self.pll_used.append(name)
        self.pll_available.remove(name)
        print('Pll used         : ' + str(self.pll_used))
        print('Pll pll_available: ' + str(self.pll_available))

    def get_free_pll_resource(self):
        return self.pll_available[0]
