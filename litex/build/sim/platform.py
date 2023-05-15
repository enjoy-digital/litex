#
# This file is part of LiteX.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.structure import Signal, If, Finish
from migen.fhdl.module import Module
from migen.genlib.record import Record

from litex.build.generic_platform import GenericPlatform, Pins
from litex.build.sim import common, verilator
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStorage


class SimPlatform(GenericPlatform):

    _supported_toolchains = ["verilator"]

    def __init__(self, device, io, name="sim", toolchain="verilator", **kwargs):
        if "sim_trace" not in (iface[0] for iface in io):
            io.append(("sim_trace", 0, Pins(1)))
        GenericPlatform.__init__(self, device, io, name=name, **kwargs)
        self.sim_requested = []
        if toolchain == "verilator":
            self.toolchain = verilator.SimVerilatorToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")
        # we must always request the sim_trace signal
        self.trace = self.request("sim_trace")

    def request(self, name, number=None, loose=False):
        index = ""
        if number is not None:
            index = str(number)
        obj = GenericPlatform.request(self, name, number=number, loose=loose)
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

    def add_debug(self, module, reset=0):
        module.submodules.sim_trace = SimTrace(self.trace, reset=reset)
        module.submodules.sim_marker = SimMarker()
        module.submodules.sim_finish = SimFinish()
        self.trace = None

    @classmethod
    def fill_args(cls, toolchain, parser):
        """
        pass parser to the specific toolchain to
        fill this with toolchain args

        Parameters
        ==========
        toolchain: str
            toolchain name
        parser: argparse.ArgumentParser
            parser to be filled
        """
        verilator.verilator_build_args(parser)

    @classmethod
    def get_argdict(cls, toolchain, args):
        """
        return a dict of args

        Parameters
        ==========
        toolchain: str
            toolchain name

        Return
        ======
        a dict of key/value for each args or an empty dict
        """
        return verilator.verilator_build_argdict(args)

# Sim debug modules --------------------------------------------------------------------------------

class SimTrace(Module, AutoCSR):
    """Start/stop simulation tracing from software/gateware"""
    def __init__(self, pin, reset=0):
        # set from software/gateware
        self.enable = CSRStorage(reset=reset)
        # used by simulator to start/stop dump
        self.comb += pin.eq(self.enable.storage)

class SimMarker(Module, AutoCSR):
    """Set simulation markers from software/gateware

    This is useful when analysing trace dumps. Change the marker value from
    software/gateware, and then check the *_marker_storage signal in GTKWave.
    """
    def __init__(self, size=8):
        # set from software
        self.marker = CSRStorage(size)

class SimFinish(Module, AutoCSR):
    """Finish simulation from software"""
    def __init__(self):
        # set from software
        self.finish = CSR()
        self.sync += If(self.finish.re, Finish())
