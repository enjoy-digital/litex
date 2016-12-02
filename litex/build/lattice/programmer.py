import os
import subprocess

from litex.build.generic_programmer import GenericProgrammer
from litex.build import tools


class LatticeProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, xcf_template):
        self.xcf_template = xcf_template

    def load_bitstream(self, bitstream_file):
        xcf_file = bitstream_file.replace(".bit", ".xcf")
        xcf_content = self.xcf_template.format(bitstream_file=bitstream_file)
        tools.write_to_file(xcf_file, xcf_content)
        subprocess.call(["pgrcmd", "-infile", xcf_file])
