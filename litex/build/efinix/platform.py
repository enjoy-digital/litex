#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen.fhdl.structure import _Slice

from litex.build.generic_platform import *
from litex.build.efinix import common, efinity
from litex.build.efinix import EfinixDbParser

# EfinixPlatform -----------------------------------------------------------------------------------

class EfinixPlatform(GenericPlatform):
    _bitstream_ext = {
        "sram"  : ".bit",
        "flash" : ".hex"
    }

    _supported_toolchains = ["efinity"]

    def __init__(self, *args, iobank_info=None, toolchain="efinity", spi_mode="active", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)

        self.timing_model = self.device[-2:]
        self.device       = self.device[:-2]
        self.iobank_info  = iobank_info
        self.spi_mode     = spi_mode
        if self.device[:2] == "Ti":
            self.family = "Titanium"
        else:
            self.family = "Trion"

        if os.getenv("LITEX_ENV_EFINITY", False) == False:
            msg = "Unable to find or source Efinity toolchain, please either:\n"
            msg += "- Set LITEX_ENV_EFINITY environment variant to Efinity path.\n"
            msg += "- Or add Efinity toolchain to your $PATH."
            raise OSError(msg)

        self.efinity_path = os.environ["LITEX_ENV_EFINITY"].rstrip('/')
        os.environ["EFINITY_HOME"] = self.efinity_path

        if toolchain == "efinity":
            self.toolchain = efinity.EfinityToolchain(self.efinity_path)
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

        self.parser = EfinixDbParser(self.efinity_path, self.device)
        self.pll_available = self.parser.get_block_instance_names('pll')
        self.pll_used = []

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.efinix_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
            attr_translate=self.toolchain.attr_translate, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

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
        assert len(sig) == 1
        idx = 0
        while isinstance(sig, _Slice) and hasattr(sig, "value"):
            idx = sig.start
            sig = sig.value
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if (s == sig) and (pins[0] != 'X'):
                    return [pins[idx]]
        return None

    def get_pin_properties(self, sig):
        ret = []
        if sig is None:
            return None
        assert len(sig) == 1

        while isinstance(sig, _Slice) and hasattr(sig, "value"):
            sig = sig.value
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if (s == sig) and (pins[0] != 'X'):
                    for o in others:
                        if isinstance(o, IOStandard):
                            ret.append(('IO_STANDARD', o.name))
                        if isinstance(o, Misc):
                            if o.misc in ["WEAK_PULLUP", "WEAK_PULLDOWN"]:
                                prop = "PULL_OPTION"
                                val = o.misc
                                ret.append((prop, val))
                            if "DRIVE_STRENGTH" in o.misc:
                                prop = "DRIVE_STRENGTH"
                                val = o.misc.split("=")[1]
                                ret.append((prop, val))
                            if "SLEWRATE" in o.misc:
                                prop = "SLEW_RATE"
                                val = "1"
                                ret.append((prop, val))
                    return ret
        return None

    def get_pin(self, sig):
        while isinstance(sig, _Slice) and hasattr(sig, "value"):
            sig = sig.value
        return sig

    def get_pin_name(self, sig, without_index=False):
        if sig is None:
            return None
        assert len(sig) == 1
        idx = 0
        slc = False
        while isinstance(sig, _Slice) and hasattr(sig, "value"):
            slc = True
            idx = sig.start
            sig = sig.value
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if s == sig:
                if resource[2]:
                    name = resource[0] + "_" + resource[2]
                    if without_index is False:
                        name = name + (f"{idx}" if slc else "")
                    return name
                else:
                    return resource[0] + (f"{idx}" if slc else "")
        return None

    def get_sig_constraint(self, sig):
        sc = self.constraint_manager.get_sig_constraints()
        for s, pins, others, resource in sc:
            if s == sig:
                return sc
        return None

    def add_iface_io(self, name, size=1):
        self.add_extension([(name, 0, Pins(size))])
        self.toolchain.excluded_ios.append(name)
        return self.request(name)

    def add_iface_ios(self, io):
        self.add_extension(io)
        tmp = self.request(io[0][0])
        for s in tmp.flatten():
            self.toolchain.excluded_ios.append(s)
        return tmp

    def get_pll_resource(self, name):
        self.pll_used.append(name)
        self.pll_available.remove(name)

    def get_free_pll_resource(self):
        pll = self.pll_available[0]
        self.get_pll_resource(pll)
        return pll
