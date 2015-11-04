import os


class GenericProgrammer:
    def __init__(self, flash_proxy_basename=None):
        self.flash_proxy_basename = flash_proxy_basename
        self.flash_proxy_dirs = [
            "~/.migen", "/usr/local/share/migen", "/usr/share/migen",
            "~/.mlabs", "/usr/local/share/mlabs", "/usr/share/mlabs"]

    def set_flash_proxy_dir(self, flash_proxy_dir):
        if flash_proxy_dir is not None:
            self.flash_proxy_dirs = [flash_proxy_dir]

    def find_flash_proxy(self):
        for d in self.flash_proxy_dirs:
            fulldir = os.path.abspath(os.path.expanduser(d))
            fullname = os.path.join(fulldir, self.flash_proxy_basename)
            if os.path.exists(fullname):
                return fullname
        raise OSError("Failed to find flash proxy bitstream")

    # must be overloaded by specific programmer
    def load_bitstream(self, bitstream_file):
        raise NotImplementedError

    # must be overloaded by specific programmer
    def flash(self, address, data_file):
        raise NotImplementedError


