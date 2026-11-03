#!/usr/bin/env python3
#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
"""Colorbars plus transceiver diagnostics for Decklink Mini 4K and ModRetro M64.

Default: generate RTL/CSR files only. --build runs the normal software/Vivado build.
Add --load to load the resulting bitstream through the board's normal programmer.
M64 requires an already configured external clock, with its actual frequency supplied.
"""
import argparse
from migen import Cat, ClockSignal, Signal
from migen.genlib.cdc import MultiReg
from litex.gen import LiteXModule
from litex.soc.cores.freqmeter import FreqMeter
from litex.soc.integration.builder import Builder
from litex.soc.interconnect.csr import CSRStatus, CSRStorage


class VideoDiagnostics(LiteXModule):
    def __init__(self, soc, family):
        phy = soc.videophy
        names = ['r', 'g', 'b'] if family == 'gtp' else ['clk', 'r', 'g', 'b']
        self.restart = CSRStorage(name='restart', description='Hold all TX initialization FSMs in reset when 1; write 0 to restart.')
        self.status = CSRStatus(1 + 3*len(names), name='status', description=(
            'Bit 0: PLL lock. Then 3 bits per lane (' + ','.join(names) +
            '): TX ready, raw TXRESETDONE, TX buffer error. Status bits are synchronized individually.'))
        raw = [phy.pll.lock]
        self.pixel = FreqMeter(int(soc.sys_clk_freq), clk=ClockSignal('hdmi'))
        tx = phy.gtpb if family == 'gtp' else phy.gthclk
        # Fabric-derived GTP references do not give Vivado an automatic TX clock.
        # Constrain the real shared clock, not meter aliases that synthesis removes.
        if family == 'gtp':
            soc.platform.add_period_constraint(tx.cd_tx.clk, 1e9/tx.tx_clk_freq)
        soc.platform.add_false_path_constraints(soc.crg.cd_sys.clk, tx.cd_tx.clk)
        soc.platform.add_false_path_constraints(soc.crg.cd_hdmi.clk, tx.cd_tx.clk)
        for name in names:
            gt = getattr(phy, family + name)
            params = getattr(gt, family + '_params')
            buffer_status = Signal(2)
            params['o_TXBUFSTATUS'] = buffer_status
            raw.extend([gt.tx_ready, params['o_TXRESETDONE'], buffer_status[1]])
            self.comb += gt.tx_enable.eq(~self.restart.storage)
            meter = FreqMeter(int(soc.sys_clk_freq), clk=gt.cd_tx.clk)
            setattr(self, 'tx_' + name, meter)
        self.specials += MultiReg(Cat(*raw), self.status.status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', choices=['decklink', 'm64'])
    parser.add_argument('--video-refclk-freq', type=float)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--load', action='store_true')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    if args.board == 'decklink':
        from litex_boards.targets.decklink_mini_4k import BaseSoC
        class ColorbarSoC(BaseSoC):
            # Reuse the target's video clock/PHY setup, with a hardware-only pattern source.
            def add_video_terminal(self, **kwargs):
                self.add_video_colorbars(**kwargs)
        soc = ColorbarSoC(with_video_terminal=True,
            integrated_rom_size=0x10000, integrated_main_ram_size=0x20000)
        # The board's 100MHz input is not clock-capable. The smaller BRAM-only design
        # can introduce an input BUFG; cover that route as well as the auxiliary PLL.
        # Use plain XDC commands (the target's conditional Tcl is not supported in XDC).
        soc.platform.add_platform_command(
            'set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets clk100_IBUF]')
        soc.platform.add_platform_command(
            'set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {{{clkin}}}]',
            clkin=soc.crg.aux_pll.clkin)
        family = 'gtp'
    else:
        from litex_boards.targets.modretro_m64 import BaseSoC
        soc = BaseSoC(with_video_colorbars=True, video_refclk_freq=args.video_refclk_freq)
        family = 'gth'
    soc.video_diag = VideoDiagnostics(soc, family)
    builder = Builder(soc, output_dir=args.output_dir,
        compile_software=args.build, compile_gateware=args.build,
        csr_csv=args.output_dir + '/csr.csv')
    builder.build(run=args.build)
    if args.load:
        soc.platform.create_programmer().load_bitstream(builder.get_bitstream_filename(mode='sram'))


if __name__ == '__main__':
    main()
