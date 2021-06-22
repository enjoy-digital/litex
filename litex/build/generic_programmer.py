#
# This file is part of LiteX.
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause


import os
import sys
import subprocess

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
        self.config_repos = [
            "https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/prog/",
        ]
        self.prog_local = "prog"

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
        fullname = tools.cygpath(os.path.join(self.prog_local, self.flash_proxy_basename))
        if os.path.exists(fullname):
            return fullname
        # Search in repositories and download it
        import requests
        os.makedirs(self.prog_local, exist_ok=True)
        for d in self.flash_proxy_repos:
            fullname = tools.cygpath(os.path.join(self.prog_local, self.flash_proxy_basename))
            try:
                r = requests.get(d + self.flash_proxy_basename)
                if r.status_code != 404:
                    with open(fullname, "wb") as f:
                        f.write(r.content)
                    return fullname
            except:
                pass
        raise OSError("Failed to find flash proxy bitstream")

    def find_config(self):
        # Search in local directory
        fullname = tools.cygpath(self.config)
        if os.path.exists(fullname):
            return self.config
        # Search in local config directory
        fullname = tools.cygpath(os.path.join(self.prog_local, self.config))
        if os.path.exists(fullname):
            return fullname
        # Search in repositories and download it
        import requests
        os.makedirs(self.prog_local, exist_ok=True)
        for d in self.config_repos:
            fullname = tools.cygpath(os.path.join(self.prog_local, self.config))
            try:
                r = requests.get(d + self.config)
                if r.status_code != 404:
                    with open(fullname, "wb") as f:
                        f.write(r.content)
                    return fullname
            except:
                pass
        raise OSError("Failed to find config file")

    # Must be overloaded by specific programmer
    def load_bitstream(self, bitstream_file):
        raise NotImplementedError

    # Must be overloaded by specific programmer
    def flash(self, address, data_file):
        raise NotImplementedError

    def call(self, command, check=True):
        if (subprocess.call(command) != 0) and check:
            msg = f"Error occured during {self.__class__.__name__}'s call, please check:\n"
            msg += f"- {self.__class__.__name__} installation.\n"
            msg += f"- access permissions.\n"
            msg += f"- hardware and cable."
            raise OSError(msg)
