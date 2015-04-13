import subprocess

from mibuild.generic_programmer import GenericProgrammer


class USBBlaster(GenericProgrammer):
    needs_bitreverse = False

    def load_bitstream(self, bitstream_file, port=0):
        usb_port = "[USB-"+str(port)+"]"
        subprocess.call(["quartus_pgm", "-m", "jtag", "-c", "USB-Blaster"+usb_port, "-o", "p;"+bitstream_file])
