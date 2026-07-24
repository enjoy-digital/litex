#
# This file is part of LiteX.
#
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build import tools

# YosysWrapper -------------------------------------------------------------------------------------

class YosysWrapper():
    """
    YosysWrapper synthesis wrapper
    """

    def __init__(self, platform, build_name,
        target       = "",
        output_name  = "",
        template     = [],
        yosys_opts   = "",
        yosys_cmds   = [],
        use_slang    = False,
        slang_plugin = False,
        slang_opts   = "",
        synth_format = "json",
        **kwargs)    :
        """
        Parameters
        ==========
        platform : GenericPlatform subclass
            current platform.
        build_name : str
            gateware name.
        target: str
            target model (ice40, ecp5, nexus, ...).
        output_name: str
            output name if different to build_name [optional]
        template: str
            yosys template to use instead of default.
        yosys_opts : str
            Yosys options to use for synth_xxx
        yosys_cmds : list
            optionals commands called before synth_xxx
        use_slang : bool
            use Yosys's slang frontend for SystemVerilog sources.
        slang_plugin : bool
            load the legacy external slang plugin before using read_slang.
        slang_opts : str
            options to pass to read_slang.
        synth_format : str
            Yosys ouptput format
        kwargs: dict
            list of key/value for yosys_opts [optional]
        """

        assert platform     != ""
        assert build_name   != ""
        assert target       != ""
        assert synth_format != ""

        self._template    = self._default_template if template == [] else template
        self._output_name = build_name if output_name == "" else output_name

        self._platform     = platform
        self._build_name   = build_name
        self._synth_format = synth_format
        self._yosys_opts   = yosys_opts
        self._yosys_cmds   = yosys_cmds
        self._quiet        = "" if not kwargs.pop("quiet", False) else '-Qq'
        self._slang_plugin = slang_plugin or getattr(platform, "yosys_slang_plugin", False)
        self._use_slang    = use_slang or self._slang_plugin or getattr(platform, "yosys_use_slang", False)
        self._slang_opts   = slang_opts or getattr(platform, "yosys_slang_opts", "")

        self._target = target

        for key,value in kwargs.items():
            key = key.replace("_","-")
            if isinstance(value, bool):
                self._yosys_opts += f"-{key} " if value else ""
            else:
                self._yosys_opts += f"-{key} {value} "

    def _import_sources(self):
        """built a list of sources to read
        Return
        ======
            a string containing all read_xxx lines
        """
        includes = ""
        reads = []
        slang_files = []
        for path in self._platform.verilog_include_paths:
            includes += " -I" + path
        for filename, language, library, *copy in self._platform.sources:
            # yosys has no such function read_systemverilog
            if language == "systemverilog":
                if self._use_slang:
                    slang_files.append(filename)
                    continue
                language = "verilog -sv"
            if language is None:
                continue
            reads.append(f'read_{language}{includes} "{filename}"')
        if slang_files:
            opts  = f" {self._slang_opts}" if self._slang_opts else ""
            files = " ".join(slang_files)
            if self._slang_plugin:
                reads.insert(0, "plugin -i slang")
            reads.append(f"read_slang{opts}{includes} {files}")
        return "\n".join(reads)

    _default_template = [
        "verilog_defaults -push",
        "verilog_defaults -add -defer",
        "{read_files}",
        "verilog_defaults -pop",
        "attrmap -tocase keep -imap keep=\"true\" keep=1 -imap keep=\"false\" keep=0 -remove keep=0",
        "{yosys_cmds}",
        "synth_{target} {synth_opts} -top {build_name}",
        "write_{write_fmt} {write_opts} {output_name}.{synth_fmt}",
    ]

    def build_script(self):
        """fill and write ys script.
        """
        read_files = self._import_sources()

        format_dict = {
            "build_name"  : self._build_name,
            "read_files"  : read_files,
            "synth_opts"  : self._yosys_opts,
            "target"      : self._target,
            "synth_fmt"   : self._synth_format,
            "write_fmt"   : "verilog" if self._synth_format[0] == "v" else self._synth_format,
            "write_opts"  : "-pvector bra -attrprop" if self._synth_format == "edif" else "",
            "output_name" : self._output_name,
        }

        yosys_cmds = [l.format(**format_dict) for l in self._yosys_cmds]
        format_dict["yosys_cmds"] = "\n".join(yosys_cmds)

        ys = [l.format(**format_dict) for l in self._template]

        tools.write_to_file(self._build_name + ".ys", "\n".join(ys))

    def get_yosys_call(self, target="script"):
        """built the script command or Makefile rule + command

        Parameters
        ==========
        target : str
            selects if it's a script command or a Makefile rule to be returned

        Returns
        =======
        str containing instruction and/or rule
        """
        base_cmd = f"yosys {self._quiet} -l {self._build_name}.rpt {self._build_name}.ys"
        if target == "makefile":
            return f"{self._build_name}.{self._synth_format}:\n\t" + base_cmd + "\n"
        elif target == "script":
            return base_cmd
        else:
            raise ValueError("Invalid script type")

def yosys_args(parser):
    parser.add_argument("--yosys-nowidelut", action="store_true", help="Use Yosys's nowidelut mode.")
    parser.add_argument("--yosys-abc9",      action="store_true", help="Use Yosys's abc9 mode.")
    parser.add_argument("--yosys-flow3",     action="store_true", help="Use Yosys's abc9 mode with the flow3 script.")
    parser.add_argument("--yosys-slang",     action="store_true", help="Use Yosys's slang SystemVerilog frontend.")
    parser.add_argument("--yosys-slang-plugin", action="store_true", help="Load the legacy external slang plugin (for Yosys < 0.67).")
    parser.add_argument("--yosys-quiet",     action="store_true", help="Use Yosys's '-Qq' to be quiet")

def yosys_argdict(args):
    return {
        "nowidelut": args.yosys_nowidelut,
        "abc9":      args.yosys_abc9,
        "flow3":     args.yosys_flow3,
        "use_slang":    args.yosys_slang or args.yosys_slang_plugin,
        "slang_plugin": args.yosys_slang_plugin,
        "quiet":        args.yosys_quiet,
    }
