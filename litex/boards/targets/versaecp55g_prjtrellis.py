#!/usr/bin/env python3

from migen import *

from litex.boards.platforms import versaecp55g

from litex.soc.integration.builder import *


class BaseSoC(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()

        sys_clk_pads = platform.request("clk100")
        btn_pads = platform.request("user_dip_btn")
        led0_pads = platform.request("user_led", 0)
        led1_pads = platform.request("user_led", 1)

        # FIXME: no constraint file for now with prjtrellis
        platform.lookup_request("clk100").attr.add(("LOC", "P3"))
        platform.lookup_request("clk100").attr.add(("IO_TYPE", "LVDS"))
        platform.lookup_request("user_dip_btn").attr.add(("LOC", "H2"))
        platform.lookup_request("user_dip_btn").attr.add(("IO_TYPE", "LVCMOS15"))
        platform.lookup_request("user_led", 0).attr.add(("LOC", "E16"))
        platform.lookup_request("user_led", 0).attr.add(("IO_TYPE", "LVCMOS25"))
        platform.lookup_request("user_led", 1).attr.add(("LOC", "D17"))
        platform.lookup_request("user_led", 1).attr.add(("IO_TYPE", "LVCMOS25"))

        # FIXME: add TRELLIS_IO instance on all inputs/outputs
        sys_clk_pads_i = Signal()
        btn_pads_i = Signal()
        led0_pads_i = Signal()
        led1_pads_i = Signal()
        self.specials += [
            Instance("TRELLIS_IO", p_DIR="INPUT", io_B=sys_clk_pads, o_O=sys_clk_pads_i),
            Instance("TRELLIS_IO", p_DIR="INPUT", io_B=btn_pads, o_O=btn_pads_i),
            Instance("TRELLIS_IO", p_DIR="OUTPUT", io_B=led0_pads, i_I=led0_pads_i),
            Instance("TRELLIS_IO", p_DIR="OUTPUT", io_B=led1_pads, i_I=led1_pads_i),
        ]

        # crg
        self.comb += self.cd_sys.clk.eq(sys_clk_pads_i)

        # led0 (blink)
        counter = Signal(32)
        self.sync += counter.eq(counter + 1)
        self.comb += led0_pads_i.eq(counter[26])

        # led1 (btn)
        self.comb += led1_pads_i.eq(btn_pads_i)


def main():
    platform = versaecp55g.Platform(toolchain="prjtrellis")
    soc = BaseSoC(platform)
    platform.build(soc, toolchain_path="/home/florent/dev/symbiflow/prjtrellis") # FIXME


if __name__ == "__main__":
    main()
