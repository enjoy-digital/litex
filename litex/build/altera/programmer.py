import subprocess

from litex.build.generic_programmer import GenericProgrammer


class USBBlaster(GenericProgrammer):
    needs_bitreverse = False

    def load_bitstream(self, bitstream_file, cable_suffix=""):
        subprocess.call(["quartus_pgm", "-m", "jtag", "-c",
                         "USB-Blaster{}".format(cable_suffix), "-o",
                         "p;{}".format(bitstream_file)])
