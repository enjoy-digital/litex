# ice40up5k_toolchain.py
#
# Unified OOP-based IceStorm Toolchain Wrapper for Lattice iCE40UP5K
# -------------------------------------------------------------------
# Author: K.M. Skanda (2025)
# License: BSD-2-Clause (compatible with LiteX)
#
# This module provides:
#  - Platform class (pinout, IOs)
#  - Toolchain class (synth, pnr, pack, bitstream)
#  - Programmer class (flashing)
#
# Works standalone or as part of a LiteX-based SoC.
# -------------------------------------------------------------------

import os
import subprocess
from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import IceStormProgrammer
from litex.build import tools

# -----------------------------------------------------------------------------------------------
# IO Definition for iCE40UP5K
# -----------------------------------------------------------------------------------------------

_io = [
    ("clk12", 0, Pins("20"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("14")),
        Subsignal("rx", Pins("15")),
        IOStandard("LVCMOS33")
    ),

    ("led_red",   0, Pins("39"), IOStandard("LVCMOS33")),
    ("led_green", 0, Pins("40"), IOStandard("LVCMOS33")),
    ("led_blue",  0, Pins("41"), IOStandard("LVCMOS33")),
]

# -----------------------------------------------------------------------------------------------
# Platform Definition
# -----------------------------------------------------------------------------------------------

class Ice40UP5KPlatform(LatticePlatform):
    """Platform class for iCE40UP5K-SG48 FPGA using IceStorm toolchain."""
    default_clk_name   = "clk12"
    default_clk_period = 1e9 / 12e6
    device             = "ice40-up5k-sg48"
    toolchain          = "icestorm"

    def __init__(self):
        super().__init__(self.device, _io, toolchain=self.toolchain)

    def create_programmer(self):
        """Return IceStorm programmer instance."""
        return IceStormProgrammer()

    def do_finalize(self, fragment):
        """Finalize design (add constraints, timing, etc)."""
        super().do_finalize(fragment)

# -----------------------------------------------------------------------------------------------
# Toolchain Definition (Wrapper)
# -----------------------------------------------------------------------------------------------

class IceStormToolchain:
    """Simplified OOP wrapper around Yosys + nextpnr-ice40 + icepack."""
    def __init__(self, top_name="top", build_dir="build", platform=None):
        self.top_name   = top_name
        self.build_dir  = build_dir
        self.json_file  = f"{build_dir}/{top_name}.json"
        self.asc_file   = f"{build_dir}/{top_name}.asc"
        self.bin_file   = f"{build_dir}/{top_name}.bin"
        self.pcf_file   = f"{build_dir}/{top_name}.pcf"
        self.device     = "up5k"
        self.package    = "sg48"
        self.platform   = platform or Ice40UP5KPlatform()

    # ------------------------- PCF Auto-Generation -------------------------
    def generate_pcf(self):
        """Auto-generate .pcf constraints file from platform IOs."""
        print(f"[GEN-PCF] Generating {self.pcf_file} from platform IOs...")
        lines = []
        for name, index, pins, *rest in _io:
            # Handle clock
            if name.startswith("clk"):
                lines.append(f"set_io {name} {pins.identifiers[0]}")
            # Handle LEDs
            elif name.startswith("led"):
                lines.append(f"set_io {name} {pins.identifiers[0]}")
            # Handle serial TX/RX
            elif name == "serial":
                tx_pin = rest[0].subsigs["tx"].pins.identifiers[0]
                rx_pin = rest[0].subsigs["rx"].pins.identifiers[0]
                lines.append(f"set_io serial_tx {tx_pin}")
                lines.append(f"set_io serial_rx {rx_pin}")
        tools.write_to_file(self.pcf_file, "\n".join(lines) + "\n")
        print(f"[GEN-PCF] Done. ({len(lines)} pins written)")

    # ------------------------- Yosys Synthesis -------------------------
    def synthesize(self, verilog_file):
        """Run Yosys synthesis for Ice40."""
        cmd = [
            "yosys",
            "-p", f"synth_ice40 -top {self.top_name} -json {self.json_file} -dsp",
            verilog_file
        ]
        print(f"[SYNTH] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    # ------------------------- nextpnr Place & Route -------------------------
    def place_and_route(self):
        """Run nextpnr for Ice40 UP5K."""
        cmd = [
            "nextpnr-ice40",
            "--up5k",
            f"--package={self.package}",
            f"--json={self.json_file}",
            f"--pcf={self.pcf_file}",
            f"--asc={self.asc_file}",
        ]
        print(f"[PNR] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    # ------------------------- Bitstream Packing -------------------------
    def pack(self):
        """Convert .asc to .bin bitstream."""
        cmd = ["icepack", self.asc_file, self.bin_file]
        print(f"[PACK] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    # ------------------------- Full Build -------------------------
    def build(self, verilog_file):
        """Run full build flow."""
        os.makedirs(self.build_dir, exist_ok=True)
        print(f"\n  Starting IceStorm build for {self.top_name}\n")
        self.generate_pcf()
        self.synthesize(verilog_file)
        self.place_and_route()
        self.pack()
        print(f"\n Build complete! Bitstream: {self.bin_file}\n")

    # ------------------------- Flashing -------------------------
    def flash(self):
        """Flash the generated bitstream using iceprog."""
        cmd = ["iceprog", self.bin_file]
        print(f"[FLASH] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
