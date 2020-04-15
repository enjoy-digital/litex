# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD


import os
import sys
import requests
from litex.build import tools


class GenericProgrammer:
    def __init__(self, flash_proxy_basename=None):
        self.flash_proxy_basename = flash_proxy_basename
        self.flash_proxy_dirs = [
            "~/.migen", "/usr/local/share/migen", "/usr/share/migen",
            "~/.mlabs", "/usr/local/share/mlabs", "/usr/share/mlabs",
            "~/.litex", "/usr/local/share/litex", "/usr/share/litex"
        ]
        self.flash_proxy_repos = [
            "https://github.com/quartiq/bscan_spi_bitstreams/raw/master/",
        ]
        self.flash_proxy_local = "flash_proxies"

    def set_flash_proxy_dir(self, flash_proxy_dir):
        if flash_proxy_dir is not None:
            self.flash_proxy_dirs = [flash_proxy_dir]

    def find_flash_proxy(self):
        # Search in installed flash_proxy_directories
        for d in self.flash_proxy_dirs:
            fulldir  = os.path.abspath(os.path.expanduser(d))
            fullname = tools.cygpath(os.path.join(fulldir, self.flash_proxy_basename))
            if os.path.exists(fullname):
                return fullname
        # Search in local flash_proxy directory
        fullname = tools.cygpath(os.path.join(self.flash_proxy_local, self.flash_proxy_basename))
        if os.path.exists(fullname):
            return fullname
        # Search in repositories and download it
        os.makedirs(self.flash_proxy_local, exist_ok=True)
        for d in self.flash_proxy_repos:
            fullname = tools.cygpath(os.path.join(self.flash_proxy_local, self.flash_proxy_basename))
            try:
                r = requests.get(d + self.flash_proxy_basename)
                with open(fullname, "wb") as f:
                    f.write(r.content)
                return fullname
            except:
                pass
        raise OSError("Failed to find flash proxy bitstream")

    # Must be overloaded by specific programmer
    def load_bitstream(self, bitstream_file):
        raise NotImplementedError

    # Must be overloaded by specific programmer
    def flash(self, address, data_file):
        raise NotImplementedError


