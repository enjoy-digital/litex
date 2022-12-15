#
# This file is part of LiteX.
#
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build import tools

# NextPNR Wrapper ----------------------------------------------------------------------------------

class NextPNRWrapper():
    """
    NextPNRWrapper NexPNR wrapper
    """

    def __init__(self,
        family        = "",
        architecture  = "",
        package       = "",
        build_name    = "",
        in_format     = "",
        out_format    = "",
        constr_format = "",
        pnr_opts      = "",
        **kwargs)     :
        """
        Parameters
        ==========
        family: str
            device family (ice40, ecp5, nexus).
        architecture: str
            device architecture.
        package: str
            device package.
        build_name: str
            gateware name.
        in_format: str
            NextPNR input file format.
        out_format: str
            NextPNR output file format.
        constr_format: str
            gateware constraints format.
        pnr_opts: str
            options to pass to nextpnr-xxx
        kwargs: dict
            alternate options key/value
        """
        self.name           = f"nextpnr-{family}"
        self._target        = family
        self._build_name    = build_name
        self._in_format     = in_format
        self._out_format    = out_format
        self._constr_format = constr_format
        self._pnr_opts      = pnr_opts + " "
        self._pnr_opts     += f"--{architecture} " if architecture != "" else ""
        self._pnr_opts     += f"--package {package} " if package != "" else ""
        for key,value in kwargs.items():
            key = key.replace("_","-")
            if isinstance(value, bool):
                self._pnr_opts += f"--{key} " if value else ""
            else:
                if value != "":
                    self._pnr_opts += f"--{key} {value} "

    @property
    def pnr_opts(self):
        """return PNR configuration options
        Returns
        =======
        str containing configuration options passed to nextpnr-xxx
        """
        return self._pnr_opts

    def get_call(self, target="script"):
        """built a script command or a Makefile rule + command

        Parameters
        ==========
        target : str
            selects if it's a script command or a Makefile rule to be returned

        Returns
        =======
        str containing instruction and/or rule
        """
        cmd = "{pnr_name} --{in_fmt} {build_name}.{in_fmt} --{constr_fmt}" + \
            " {build_name}.{constr_fmt}" + \
            " --{out_fmt} {build_name}.{out_ext} {pnr_opts}"
        base_cmd = cmd.format(
            pnr_name   = self.name,
            build_name = self._build_name,
            in_fmt     = self._in_format,
            out_fmt    = "textcfg" if self._out_format == "config" else self._out_format,
            out_ext    = self._out_format,
            constr_fmt = self._constr_format,
            pnr_opts   = self._pnr_opts
        )
        if target == "makefile":
            return f"{self._build_name}.{self._out_format}:\n\t" + base_cmd + "\n"
        elif target == "script":
            return base_cmd
        else:
            raise ValueError("Invalid target type")

def nextpnr_args(parser):
    parser.add_argument("--nextpnr-timingstrict", action="store_true", help="Use strict Timing mode (Build will fail when Timings are not met).")
    parser.add_argument("--nextpnr-ignoreloops",  action="store_true", help="Ignore combinatorial loops in Timing Analysis.")
    parser.add_argument("--nextpnr-seed",         default=1, type=int, help="Set Nextpnr's seed.")

def nextpnr_argdict(args):
    return {
        "timingstrict": args.nextpnr_timingstrict,
        "ignoreloops":  args.nextpnr_ignoreloops,
        "seed":         args.nextpnr_seed,
    }
