#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import importlib
import sys

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

# Litex Argument Parser ----------------------------------------------------------------------------

class LiteXArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass used to intercept parse_args call and to simplify
    common arguments addition
    Attributes
    ==========
    _platform: GenericPlatform subclass
        target platform
    _device: str
        target device family
    _args: argparse.Namespace
        list of args after parse_args call
    _toolchain: str
        toolchain used at build time
    _default_toolchain: str
        toolchain to use by default or when no selection is done  by the user
    """
    def __init__(self, platform=None, **kwargs):
        """
        CTOR: create a Target options group, adds toolchain, build and load
        arguments. Call builder_args and soc_core_args for fill parser with
        corresponding options

        Parameters
        ==========
        platform: GenericPlatform subclass
            targeted platform
        kwargs: dict
            all arguments passed to argparse.ArgumentParser CTOR
        """
        argparse.ArgumentParser.__init__(self, kwargs)
        self._platform = platform
        if platform is not None:
            self._device            = platform.device_family
            toolchains              = platform.toolchains(self._device)
            self._default_toolchain = toolchains[0]
        else:
            self._device            = None
            toolchains              = None
            self._default_toolchain = None
        self._args              = None
        self._toolchain         = None

        self._target_group = self.add_argument_group(title="Target options")
        if toolchains is not None:
            self.add_target_argument("--toolchain",
                default = self._default_toolchain,
                choices = toolchains,
                help    = "FPGA toolchain ({}).".format(" or ".join(toolchains)))
        else:
            self.add_target_argument("-toolchain", help="FPGA toolchain")
        self.add_target_argument("--build", action="store_true", help="Build design.")
        self.add_target_argument("--load",  action="store_true", help="Load bitstream.")
        builder_args(self)
        soc_core_args(self)

    def set_platform(self, platform):
        """ set platform. Check first if not already set

        Parameter
        =========
        platform: GenericPlatform subclass
            the platform
        """
        assert self._platform is None
        self._platform          = platform
        self._device            = platform.device_family
        toolchains              = platform.toolchains(self._device)
        self._default_toolchain = toolchains[0]
    # add a setter (LitexArgumentParserInstance.platform = myPlatform)
    platform = property(None, set_platform)

    @property
    def target_group(self):
        """ return target_group
        """
        return self._target_group

    def add_target_argument(self, *args, **kwargs):
        """ wrapper to add argument to "Target options group" from outer of this
        class
        """
        self._target_group.add_argument(*args, **kwargs)

    @property
    def builder_argdict(self):
        """
        access to builder_argdict

        Return
        ======
        builder arguments dict
        """
        return builder_argdict(self._args)

    @property
    def soc_argdict(self):
        """
        access to soc_argdict

        Return
        ======
        soc_core arguments dict
        """
        return soc_core_argdict(self._args) # FIXME: Rename to soc_argdict in the future.

    @property
    def toolchain_argdict(self):
        """
        access to target toolchain argdict

        Return
        ======
        toolchain arguments dict
        """
        if self._platform is None:
            return dict()
        else:
            return self._platform.get_argdict(self._toolchain, self._args)

    def parse_args(self, args=None, namespace=None):
        """
        override argparse.ArgumentParser.parse_args to inject toolchain
        and soc_core args.
        Checks first is platform is set: when platform is none: try to
        search for a platform argument
        """
        # When platform is None try to search for a user input
        if self._platform is None:
            platform = self.get_value_from_key("--platform", None)
            if platform is not None:
                self.set_platform(importlib.import_module(platform).Platform)

        # Intercept selected toolchain to fill arguments.
        if self._platform is not None:
            self._toolchain = self.get_value_from_key("--toolchain", self._default_toolchain)
            if self._toolchain is not None:
                self._platform.fill_args(self._toolchain, self)

        # Intercept selected CPU to fill arguments.
        cpu_cls  = None
        cpu_name = self.get_value_from_key("--cpu-type")
        if cpu_name is not None:
            cpu_cls = cpu.CPUS[cpu_name]
            if cpu_cls is not None and hasattr(cpu_cls, "args_fill"):
                cpu_cls.args_fill(self)
        self._args = argparse.ArgumentParser.parse_args(self, args, namespace)

        # Re-inject CPU read arguments.
        if cpu_cls is not None and hasattr(cpu_cls, "args_read"):
            cpu_cls.args_read(self._args)

        return self._args

    def get_value_from_key(self, key, default=None):
        """
        search key into sys.argv

        Parameters
        ==========
        key: str
            key to search
        default: str
            default value when key is not in sys.argv

        Return
        ======
            sys.argv corresponding value or default
        """
        value = None
        try:
            index = [i for i, item in enumerate(sys.argv) if key in item][0]
            if '=' in sys.argv[index]:
                value = sys.argv[index].split('=')[1]
            else:
                value = sys.argv[index+1]
        except IndexError:
            value = default
        return value
