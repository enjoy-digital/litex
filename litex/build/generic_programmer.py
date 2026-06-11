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

# Generic Programmer -------------------------------------------------------------------------------

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

    def _find_or_download(self, basename, dirs, repos, description):
        # Search in local directory.
        fullname = tools.cygpath(basename)
        if os.path.exists(fullname):
            return fullname
        # Search in user directories.
        for d in dirs:
            fulldir  = os.path.abspath(os.path.expanduser(d))
            fullname = tools.cygpath(os.path.join(fulldir, basename))
            if os.path.exists(fullname):
                return fullname
        # Search in local prog directory.
        fullname = tools.cygpath(os.path.join(self.prog_local, basename))
        if os.path.exists(fullname):
            return fullname
        # Search in repositories and download it.
        import requests
        os.makedirs(self.prog_local, exist_ok=True)
        for repo in repos:
            try:
                r = requests.get(repo + basename, timeout=30)
                if r.ok:
                    # Write atomically to avoid caching truncated files on interruption.
                    tmpname = fullname + ".tmp"
                    with open(tmpname, "wb") as f:
                        f.write(r.content)
                    os.replace(tmpname, fullname)
                    return fullname
            except requests.RequestException:
                pass
        raise OSError(f"Failed to find {description}")

    def find_flash_proxy(self):
        return self._find_or_download(
            basename    = self.flash_proxy_basename,
            dirs        = self.flash_proxy_dirs,
            repos       = self.flash_proxy_repos,
            description = "flash proxy bitstream",
        )

    def find_config(self):
        return self._find_or_download(
            basename    = self.config,
            dirs        = [],
            repos       = self.config_repos,
            description = "config file",
        )

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
            msg += f"- Access permissions.\n"
            msg += f"- Hardware and cable.\n"
            msg += f"- Bitstream presence."
            raise OSError(msg)
