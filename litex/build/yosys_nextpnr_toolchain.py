#
# This file is part of LiteX.
#
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2017-2018 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import subprocess
from shutil import which

from litex.build import tools
from litex.build.generic_toolchain import GenericToolchain
from litex.build.nextpnr_wrapper import NextPNRWrapper, nextpnr_args, nextpnr_argdict
from litex.build.yosys_wrapper import YosysWrapper, yosys_args, yosys_argdict

# YosysNextPNRToolchain ----------------------------------------------------------------------------

class YosysNextPNRToolchain(GenericToolchain):
    """
    YosysNextPNRToolchain wrapper for toolchain based on yosys + NextPNR
    Attributes
    ==========
    family: str
        target family (ice40, ecp5, nexus, xilinx, ...)
    synth_fmt: str
        synthesys output extension (json, verilog, ...)
    constr_fmt: str
        constraints file extension (pcf, lpf, xdc, ...)
    pnr_fmt: str
        PNR output extension (fasm, asc, ...)
    _synth_opts: str
        Yosys options
    _pnr_opts: str
        nextpnr options
    _pre_packer_cmd: list str
        optional list of command to run after PNR and before packer
    _pre_packer_opts: dict
        optional options to pass to pre_packer command (key refers to
        _pre_packer_cmd)
    packer_cmd: str
        packer command
    _pre_packer_opts: str
        options for packer
    _yosys: YosysWrapper
        Yosys wrapper instance
    _nextpnr: NextPNRWrapper
        nextpnr wrapper instance
    _yosys_template: list
        optional template to use instead of default
    _yosys_cmds: list
        optional list of commands to run before synthesis_xxx
    _architecture: str
        target architecture (optional/target dependant)
    _package: str
        target package  (optional/target dependant)
    _speed_grade: str
        target speed grade (optional/target dependant)
    _support_mixed_language: bool
        informs if toolchain is able to use only verilog or verilog + vhdl
    """
    attr_translate = {
        "keep": ("keep", "true"),
    }
    _support_mixed_language  = False

    family     = ""
    synth_fmt  = ""
    constr_fmt = ""
    pnr_fmt    = ""
    packer_cmd = ""

    def __init__(self):
        super().__init__()
        self._synth_opts      = ""
        self._pnr_opts        = ""
        self._pre_packer_cmd  = []
        self._pre_packer_opts = {}
        self._packer_opts     = ""
        self._yosys           = None
        self._nextpnr         = None
        self._yosys_template  = []
        self._yosys_cmds      = []
        self._architecture    = ""
        self._package         = ""
        self._speed_grade     = ""

    def build(self, platform, fragment,
        nowidelut    = False,
        abc9         = False,
        flow3        = False,
        timingstrict = False,
        ignoreloops  = False,
        seed         = 1,
        **kwargs):
        """
        Parameters
        ==========
        platform : GenericPlatform subclass
            current platform.
        nowidelut : str
            do not use mux resources to implement LUTs larger
            than native for the target (Yosys)
        abc9 : str
            use new ABC9 flow (Yosys)
        flow3 : str
            use ABC9 with flow3 (Yosys)
        timingstrict : list
            check timing failures (nextpnr)
        ignoreloops : str
            ignore combinational loops in timing analysis (nextpnr)
        kwargs: dict
            list of key/value [optional]
        """

        self._nowidelut   = nowidelut
        self._abc9        = abc9 
        if flow3:
            self._abc9 = True
            self._yosys_cmds.append("scratchpad -copy abc9.script.flow3 abc9.script")
        self.timingstrict = timingstrict
        self.ignoreloops  = ignoreloops
        self.seed         = seed

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    def finalize(self):
        """" finalize build: create Yosys and nextpnr wrapper with required
            parameters/options
        """
        self._yosys = YosysWrapper(
            platform     = self.platform,
            build_name   = self._build_name,
            target       = self.family,
            template     = self._yosys_template,
            yosys_cmds   = self._yosys_cmds,
            yosys_opts   = self._synth_opts,
            synth_format = self.synth_fmt,
            nowidelut    = self._nowidelut,
            abc9         = self._abc9,
        )

        # NextPnr options
        self._nextpnr = NextPNRWrapper(
            family            = self.family,
            architecture      = self._architecture,
            package           = self._package,
            speed             = self._speed_grade,
            build_name        = self._build_name,
            in_format         = self.synth_fmt,
            out_format        = self.pnr_fmt,
            constr_format     = self.constr_fmt,
            pnr_opts          = self._pnr_opts,
            timing_allow_fail = not self.timingstrict,
            ignore_loops      = self.ignoreloops,
            seed              = self.seed
        )

    @property
    def pnr_opts(self):
        """return PNR configuration options
        Returns
        =======
        str containing configuration options passed to nextpnr-xxx or None if
            _nextpnr is not already instanciated
        """
        if self._nextpnr is None:
            return None
        else:
            return self._nextpnr.pnr_opts

    def build_project(self):
        """ create project files (mainly Yosys ys file)
        """
        self._yosys.build_script()

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        """ create build_xxx.yy by using Yosys and nextpnr instances, one or
            more cmd between PNR and packer and finaly packer command + options
            provided by subclass
            Return
            ======
                the script name (str)
        """

        if sys.platform in ("win32", "cygwin"):
            script_ext      = ".bat"
            script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
            fail_stmt       = " || exit /b"
        else:
            script_ext      = ".sh"
            script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
            fail_stmt       = ""
        fail_stmt += "\n"

        # yosys call
        script_contents += self._yosys.get_yosys_call("script") + fail_stmt
        # nextpnr call
        script_contents += self._nextpnr.get_call("script") + fail_stmt
        # pre packer (command to use after PNR step and before packer step)
        for pre_packer in self._pre_packer_cmd:
            script_contents += f"{pre_packer} {self._pre_packer_opts[pre_packer]} {fail_stmt}"
        # packer call
        script_contents += f"{self.packer_cmd} {self._packer_opts} {fail_stmt}"

        script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(script_file, script_contents, force_unix=False)

        return script_file

    def run_script(self, script):
        """ run build_xxx.yy script
        Parameters
        ==========
        script: str
            script name to use
        """
        if sys.platform in ("win32", "cygwin"):
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if which("yosys") is None or which(self._nextpnr.name) is None:
            msg = "Unable to find Yosys/Nextpnr toolchain, please:\n"
            msg += "- Add Yosys/Nextpnr toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Error occured during Yosys/Nextpnr's script execution.")

    def build_io_constraints(self):
        raise NotImplementedError("GenericToolchain.build_io_constraints must be overloaded.")

def yosys_nextpnr_args(parser):
    yosys_args(parser)
    nextpnr_args(parser)

def yosys_nextpnr_argdict(args):
    return {
        **yosys_argdict(args),
        **nextpnr_argdict(args),
    }
