import subprocess

from mibuild.generic_programmer import GenericProgrammer


class OpenOCD(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, config, flash_proxy_basename=None):
        GenericProgrammer.__init__(self, flash_proxy_basename)
        self.config = config

    def load_bitstream(self, bitstream):
        script = "; ".join([
            "init",
            "pld load 0 {}".format(bitstream),
            "exit",
        ])
        subprocess.call(["openocd", "-f", self.config, "-c", script])

    def flash(self, address, data):
        flash_proxy = self.find_flash_proxy()
        script = "; ".join([
            "init",
            "jtagspi_init 0 {}".format(flash_proxy),
            "jtagspi_program {} 0x{:x}".format(data, address),
            "fpga_program",
            "exit"
        ])
        subprocess.call(["openocd", "-f", self.config, "-c", script])
