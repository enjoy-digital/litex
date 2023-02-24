#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# This file is Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import logging
import argparse
import importlib

from litex.soc.cores import cpu
from litex.soc.integration import soc_core
from litex.soc.integration import builder

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
    _args_default: dict
        couple argument name / default value to apply just before to call
        parse_args()
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
        self._platform          = None
        self._device            = None
        self.toolchains         = None
        self._default_toolchain = None
        self._args              = None
        self._toolchain         = None
        self._target_group      = None
        self._logging_group     = None
        self._args_default      = {}
        if platform is not None:
            self.set_platform(platform)
            self.add_target_group()
        self.add_logging_group()

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
        self.toolchains         = platform.toolchains(self._device)
        self._default_toolchain = self.toolchains[0]

    # add a setter (LitexArgumentParserInstance.platform = myPlatform)
    platform = property(None, set_platform)

    @property
    def target_group(self):
        """ return target_group
        """
        return self._target_group

    def add_target_group(self):
        """ create target group and add --toolchain/build/load args.
        """
        if self.toolchains is not None:
            self.add_target_argument("--toolchain",
                default = self._default_toolchain,
                choices = self.toolchains,
                help    = "FPGA toolchain ({}).".format(" or ".join(self.toolchains)))
        else:
            self.add_target_argument("-toolchain", help="FPGA toolchain")
        self.add_target_argument("--build", action="store_true", help="Build design.")
        self.add_target_argument("--load",  action="store_true", help="Load bitstream.")

    def add_target_argument(self, *args, **kwargs):
        """ wrapper to add argument to "Target options group" from outer of this
        class
        """
        if self._target_group is None:
            self._target_group = self.add_argument_group(title="Target options")
        self._target_group.add_argument(*args, **kwargs)

    def add_logging_group(self):
        """ create logging group and add --log-filename/log-level args.
        """
        self._logging_group = self.add_argument_group(title="Logging options")
        self._logging_group.add_argument("--log-filename", default=None,   help="Logging filename.")
        self._logging_group.add_argument("--log-level",    default="info", help="Logging level: debug, info (default), warning error or critical.")

    def set_defaults(self, **kwargs):
        """
        Overrides argparse.ArgumentParser.set_defaults. Used to delay default
        values application

        Parameters
        ==========
        kwargs: dict
            couple argument name / default value
        """
        self._args_default.update(kwargs)

    @property
    def builder_argdict(self):
        """
        access to builder_argdict

        Return
        ======
        builder arguments dict
        """
        return builder.builder_argdict(self._args)

    @property
    def soc_argdict(self):
        """
        access to soc_argdict

        Return
        ======
        soc_core arguments dict
        """
        return soc_core.soc_core_argdict(self._args) # FIXME: Rename to soc_argdict in the future.

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
            if platform is None: # no user selection: try default
                platform = self.get_default_value_from_actions("platform", None)
            if platform is not None:
                try:
                    platform_cls = importlib.import_module(platform).Platform
                except ModuleNotFoundError as e:
                    # platform not found: try litex-boards package
                    platform = "litex_boards.platforms." + platform
                    platform_cls = importlib.import_module(platform).Platform
                self.set_platform(platform_cls)

                self.add_target_group()

        # When platform provided/set, set builder/soc_core args.
        if self._platform is not None:
            builder.builder_args(self)
            soc_core.soc_core_args(self)

        # Intercept selected toolchain to fill arguments.
        if self._platform is not None:
            self._toolchain = self.get_value_from_key("--toolchain", self._default_toolchain)
            if self._toolchain is not None:
                self._platform.fill_args(self._toolchain, self)

        # Intercept selected CPU to fill arguments.
        cpu_cls = cpu.CPUS.get(self.get_value_from_key("--cpu-type"), None)
        if cpu_cls is not None and hasattr(cpu_cls, "args_fill"):
            cpu_cls.args_fill(self)

        # Injects arguments default values
        if len(self._args_default):
            argparse.ArgumentParser.set_defaults(self, **self._args_default)

        # Parse args.
        self._args = argparse.ArgumentParser.parse_args(self, args, namespace)

        # Re-inject CPU read arguments.
        if cpu_cls is not None and hasattr(cpu_cls, "args_read"):
            cpu_cls.args_read(self._args)

        # Configure logging.
        logging.basicConfig(
            filename = self._args.log_filename,
            level    = {
                "debug"    : logging.DEBUG,
                "info"     : logging.INFO,
                "warning"  : logging.WARNING,
                "error"    : logging.ERROR,
                "critical" : logging.CRITICAL,
            }[self._args.log_level]
        )

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

    def get_default_value_from_actions(self, key, default=None):
        """
        search key into ArgumentParser _actions list

        Parameters
        ==========
        key: str
            key to search
        default: str
            default value when key is not in _actions list

        Return
        ======
            default value or default when key is not present
        """
        for act in self._actions:
            if act.dest == key:
                return act.default
        return default
