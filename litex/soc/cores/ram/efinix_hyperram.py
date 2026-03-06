#
# This file is part of LiteHyperBus
#
# Copyright (c) 2023 Gwenhael Goavec-Merou <gwenhael@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.build.generic_platform import *

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.build.io import DifferentialOutput

from litex.soc.interconnect import wishbone

from litex.soc.cores.clock.efinix import TITANIUMPLL

from litex.soc.cores.hyperbus import HyperRAM

# HyperRAM (efinix F100) ---------------------------------------------------------------------------

class EfinixHyperRAM(HyperRAM):
    """ HyperRAM wrapper for efinix F100 (internal)
    """
    def __init__(self, platform, latency=6, latency_mode="fixed", clock_domain="sys", sys_clk_freq=None, with_bursting=True, with_csr=True):

        # # #

        assert sys_clk_freq is not None and sys_clk_freq * 4 < 250e6

        _io = [
            ("hyperram", 0,
                Subsignal("clkp_h",   0, Pins(1)),
                Subsignal("clkp_l",   0, Pins(1)),
                Subsignal("clkn_h",   0, Pins(1)),
                Subsignal("clkn_l",   0, Pins(1)),
                Subsignal("dq_o_h",   0, Pins(16)),
                Subsignal("dq_o_l",   0, Pins(16)),
                Subsignal("dq_i_h",   0, Pins(16)),
                Subsignal("dq_i_l",   0, Pins(16)),
                Subsignal("dq_oe",    0, Pins(16)),
                Subsignal("rwds_o_h", 0, Pins(2)),
                Subsignal("rwds_o_l", 0, Pins(2)),
                Subsignal("rwds_i_h", 0, Pins(2)),
                Subsignal("rwds_i_l", 0, Pins(2)),
                Subsignal("rwds_oe",  0, Pins(2)),
                Subsignal("csn",      0, Pins(1)),
                Subsignal("rstn",     0, Pins(1)),
        )]

        # PLL dyn phase shift

        platform.add_extension([
            ("shift_ena", 0, Pins(1)),
            ("shift_sel", 0, Pins(1)),
            ("shift",     0, Pins(1)),
        ])

        _dps_pads = {
            "shift_ena" : platform.request("shift_ena"),
            "shift_sel" : platform.request("shift_sel"),
            "shift"     : platform.request("shift"),
        }
        platform.toolchain.excluded_ios.append(_dps_pads["shift_ena"])
        platform.toolchain.excluded_ios.append(_dps_pads["shift_sel"])
        platform.toolchain.excluded_ios.append(_dps_pads["shift"])

        # PLL.
        self.cd_hp = ClockDomain()
        self.cd_hp90 = ClockDomain()
        self.cd_hpcal = ClockDomain()
        self.pll = pll = TITANIUMPLL(platform, dyn_phase_shift_pads=_dps_pads)
        pll.register_clkin(None, sys_clk_freq, name=f"{clock_domain}_pll0_clk") # FIXME: fix clkin name
        pll.create_clkout(None,              sys_clk_freq)
        pll.create_clkout(self.cd_hp,    4 * sys_clk_freq,           with_reset=True)
        pll.create_clkout(self.cd_hp90,  4 * sys_clk_freq, phase=90, with_reset=True)
        pll.create_clkout(self.cd_hpcal, 4 * sys_clk_freq,           with_reset=True, dyn_phase=True)


        # connect HyperRAM to interface designer block
        class HPPads:
            def __init__(self):
                self.dq    = TSTriple(16)
                self.rwds  = TSTriple(2)
                self.cs_n  = Signal(1)
                self.rst_n = Signal(1)
                self.clk   = Signal(1)

        _hp_pads = HPPads()
        platform.add_extension(_io)
        self.io_pads = _io_pads = platform.request("hyperram")

        self.comb += [
            _io_pads.clkp_l.eq(_hp_pads.clk),
            _io_pads.clkp_h.eq(_hp_pads.clk),
            _io_pads.clkn_l.eq(~_hp_pads.clk),
            _io_pads.clkn_h.eq(~_hp_pads.clk),
            _io_pads.dq_o_h.eq(_hp_pads.dq.o),
            _io_pads.dq_o_l.eq(_hp_pads.dq.o),
            _hp_pads.dq.i.eq(_io_pads.dq_i_h | _io_pads.dq_i_l),
            _io_pads.dq_oe.eq(Replicate(_hp_pads.dq.oe[0], 16)),
            _io_pads.rwds_o_h.eq(_hp_pads.rwds.o),
            _io_pads.rwds_o_l.eq(_hp_pads.rwds.o),
            _hp_pads.rwds.i.eq(_io_pads.rwds_i_h | _io_pads.rwds_i_l),
            _io_pads.rwds_oe.eq(Replicate(_hp_pads.rwds.oe[0], 2)),
            _io_pads.csn.eq(_hp_pads.cs_n),
            _io_pads.rstn.eq(_hp_pads.rst_n),
        ]

        block = {
            "type"      : "HYPERRAM",
            "name"      : "hp_inst",
            "location"  : "HYPER_RAM0",
            "pads"      : _io_pads,
            "ctl_clk"   : self.cd_hp.clk,
            "cal_clk"   : self.cd_hpcal.clk,
            "clk90_clk" : self.cd_hp90.clk,
        }

        platform.toolchain.ifacewriter.blocks.append(block)

        platform.toolchain.excluded_ios.append(_io_pads.clkp_h)
        platform.toolchain.excluded_ios.append(_io_pads.clkp_l)
        platform.toolchain.excluded_ios.append(_io_pads.clkn_h)
        platform.toolchain.excluded_ios.append(_io_pads.clkn_l)
        platform.toolchain.excluded_ios.append(_io_pads.dq_o_h)
        platform.toolchain.excluded_ios.append(_io_pads.dq_o_l)
        platform.toolchain.excluded_ios.append(_io_pads.dq_i_h)
        platform.toolchain.excluded_ios.append(_io_pads.dq_i_l)
        platform.toolchain.excluded_ios.append(_io_pads.dq_oe)
        platform.toolchain.excluded_ios.append(_io_pads.rwds_o_h)
        platform.toolchain.excluded_ios.append(_io_pads.rwds_o_l)
        platform.toolchain.excluded_ios.append(_io_pads.rwds_i_l)
        platform.toolchain.excluded_ios.append(_io_pads.rwds_i_h)
        platform.toolchain.excluded_ios.append(_io_pads.rwds_oe)
        platform.toolchain.excluded_ios.append(_io_pads.csn)
        platform.toolchain.excluded_ios.append(_io_pads.rstn)
        platform.toolchain.excluded_ios.append(self.cd_hp.clk)
        platform.toolchain.excluded_ios.append(self.cd_hp90.clk)

        HyperRAM.__init__(self,
            pads          = _hp_pads,
            latency       = latency,
            latency_mode  = latency_mode,
            sys_clk_freq  = sys_clk_freq,
            clk_ratio     = "4:1",
            with_bursting = with_bursting,
            with_csr      = with_csr,
            dq_i_cd       = None,
        )
