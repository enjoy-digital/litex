# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# License: BSD

from migen.fhdl.structure import Signal
from migen.genlib.record import Record

from litex.build.generic_platform import GenericPlatform
from litex.build.sim import common, verilator


class SimPlatform(GenericPlatform):
    def __init__(self, *args, name="sim", toolchain="verilator", **kwargs):
        GenericPlatform.__init__(self, *args, name=name, **kwargs)
        self.sim_requested = []
        if toolchain == "verilator":
            self.toolchain = verilator.SimVerilatorToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def request(self, name, number=None):
        index = ""
        if number is not None:
            index = str(number)
        obj = GenericPlatform.request(self, name, number=number)
        siglist = []
        if isinstance(obj, Signal):
            siglist.append((name, obj.nbits, name))
        elif isinstance(obj, Record):
            for subsignal, dummy in obj.iter_flat():
                subfname = subsignal.backtrace[-1][0]
                prefix = "{}{}_".format(name, index)
                subname = subfname.split(prefix)[1]
                siglist.append((subname, subsignal.nbits, subfname))
        self.sim_requested.append((name, index, siglist))
        return obj

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.sim_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

