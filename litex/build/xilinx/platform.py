# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# License: BSD

import os

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import GenericPlatform
from litex.build.xilinx import common, vivado, ise, symbiflow
try:
    from litex.build import edalize
except:
    pass

# XilinxPlatform -----------------------------------------------------------------------------------

class XilinxPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    attr_translations = {
        "ise": {
            "keep":             ("keep", "true"),
            "no_retiming":      ("register_balancing", "no"),
            "async_reg":        None,
            "mr_ff":            None,
            "ars_ff1":          None,
            "ars_ff2":          None,
            "no_shreg_extract": ("shreg_extract", "no")
        },
        "vivado": {
            "keep":            ("dont_touch", "true"),
            "no_retiming":     ("dont_touch", "true"),
            "async_reg":       ("async_reg",  "true"),
            "mr_ff":           ("mr_ff",      "true"), # user-defined attribute
            "ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
            "ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
            "no_shreg_extract": None
        },
        "symbiflow": {
            "keep":            ("dont_touch", "true"),
            "no_retiming":     ("dont_touch", "true"),
            "async_reg":       ("async_reg",  "true"),
            "mr_ff":           ("mr_ff",      "true"), # user-defined attribute
            "ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
            "ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
            "no_shreg_extract": None
        }
    }

    def __init__(self, *args, toolchain="ise", use_edalize=False, **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        self.edifs = set()
        self.ips   = {}

        self.toolchain_name = toolchain

        if use_edalize:
            self.toolchain = edalize.EdalizeToolchain(toolchain=toolchain)
        else:
            if toolchain == "ise":
                self.toolchain = ise.XilinxISEToolchain()
            elif toolchain == "vivado":
                self.toolchain = vivado.XilinxVivadoToolchain()
            elif toolchain == "symbiflow":
                self.toolchain = symbiflow.SymbiflowToolchain()
            else:
                raise ValueError("Unknown toolchain")

    def add_edif(self, filename):
        self.edifs.add((os.path.abspath(filename)))

    def add_ip(self, filename, disable_constraints=False):
        self.ips.update({os.path.abspath(filename): disable_constraints})

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.xilinx_special_overrides)
        if self.device[:3] == "xc6":
            so.update(common.xilinx_s6_special_overrides)
        if self.device[:3] == "xc7":
            so.update(common.xilinx_s7_special_overrides)
        if self.device[:4] == "xcku":
            so.update(common.xilinx_us_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
            attr_translate=self.attr_translations[self.toolchain_name], **kwargs)

    def get_edif(self, fragment, **kwargs):
        return GenericPlatform.get_edif(self, fragment, "UNISIMS", "Xilinx", self.device, **kwargs)

    def build(self, fragment, build_dir="build", build_name="top", run=True, verilog_args={}, **kwargs):
        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        self.finalize(fragment)

        tool_args = kwargs
        # FIXME: This is used for backward compatibility and can be removed in the future
        if len(verilog_args) == 0:
            verilog_args = {}
            tool_args = {}
            # Keyword arguments accepted by self.get_verilog()
            get_verilog_allowed_keys = [
                "special_overrides",
                "name",
                "special_overrides",
                "attr_translate",
                "create_clock_domains",
                "display_run",
                "reg_initialization",
                "dummy_signal",
                "blocking_assign",
                "regular_comb"
            ]
            for k,v in kwargs.items():
                if k in get_verilog_allowed_keys:
                    # raise TypeError(f"Argument {k} must be passed through verilog_args dictionary")
                    verilog_args[k] = v
                else:
                    tool_args[k] = v

        # Run toolchain
        vns = None
        try:
            vns = self.toolchain.build(self, fragment, build_dir, build_name, run, verilog_args=verilog_args, **tool_args)
        finally:
            os.chdir(cwd)

        return vns

    def add_period_constraint(self, clk, period):
        if clk is None: return
        if hasattr(clk, "p"):
            clk = clk.p
        clk.attr.add("keep")
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        from_.attr.add("keep")
        to.attr.add("keep")
        self.toolchain.add_false_path_constraint(self, from_, to)


# XilinxPlatform arguments --------------------------------------------------------------------------

def xilinx_platform_args(parser):
    if "edalize" in globals():
        parser.add_argument("--use-edalize", action="store_true", help="Use Edalize toolchain backend")

def xilinx_platform_argdict(args):
    r = {}
    r.update({
        "use_edalize": args.use_edalize
    })
    return r

def xilinx_platform_build_argdict(args):
    r = {}
    return r
