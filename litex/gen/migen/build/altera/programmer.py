import subprocess

from migen.build.generic_programmer import GenericProgrammer


class USBBlaster(GenericProgrammer):
    needs_bitreverse = False

    def load_bitstream(self, bitstream_file, port=0):
        usb_port = "[USB-{}]".format(port)
        subprocess.call(["quartus_pgm", "-m", "jtag", "-c",
                         "USB-Blaster{}".format(usb_port), "-o",
                         "p;{}".format(bitstream_file)])
