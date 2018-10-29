#!/usr/bin/env python3

from migen import *

from litex.boards.platforms import versaecp55g

from litex.soc.integration.builder import *


class BaseSoC(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()

        # crg
        self.comb += self.cd_sys.clk.eq(platform.request("clk100"))

        # led0 (blink)
        counter = Signal(32)
        self.sync += counter.eq(counter + 1)
        self.comb += platform.request("user_led", 0).eq(counter[26])

        # led1 (btn)
        self.comb += platform.request("user_led", 1).eq(platform.request("user_dip_btn", 0))

def main():
    platform = versaecp55g.Platform(toolchain="prjtrellis")
    soc = BaseSoC(platform)
    platform.build(soc, toolchain_path="/home/florent/dev/symbiflow/prjtrellis") # FIXME


if __name__ == "__main__":
    main()
