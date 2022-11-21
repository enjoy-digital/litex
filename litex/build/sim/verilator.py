#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess
from pathlib import Path
from shutil import which

from migen.fhdl.structure import _Fragment
from litex import get_data_mod
from litex.build import tools
from litex.build.generic_platform import *


sim_directory = os.path.abspath(os.path.dirname(__file__))
core_directory = os.path.join(sim_directory, 'core')


def _generate_sim_h_struct(name, index, siglist):
    content = ''

    content += 'struct pad_s {}{}[] = {{\n'.format(name, index)
    for signame, sigbits, dummy in siglist:
        content += '    {{ (char*)"{}", {}, NULL }},\n'.format(signame, sigbits)
    content += '    { NULL, 0, NULL }\n'
    content += '};\n\n'

    return content


def _generate_sim_h(platform):
    content = """\
#ifndef __SIM_CORE_H_
#define __SIM_CORE_H_
#include "pads.h"

"""
    for args in platform.sim_requested:
        content += _generate_sim_h_struct(*args)

    content += """\
#ifndef __cplusplus
void litex_sim_init(void **out);
#endif

#endif /* __SIM_CORE_H_ */
"""
    tools.write_to_file("sim_header.h", content)


def _generate_sim_cpp_struct(name, index, siglist):
    content = ''

    for i, (signame, sigbits, sigfname) in enumerate(siglist):
        content += '    {}{}[{}].signal = &sim->{};\n'.format(name, index, i, sigfname)

    idx_int = 0 if not index else int(index)
    content += '    litex_sim_register_pads({}{}, (char*)"{}", {});\n\n'.format(name, index, name, idx_int)

    return content


def _generate_sim_cpp(platform, trace=False, trace_start=0, trace_end=-1):
    content = """\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Vsim.h"
#include <verilated.h>
#include "sim_header.h"

extern "C" void litex_sim_init_tracer(void *vsim, long start, long end);
extern "C" void litex_sim_tracer_dump();

extern "C" void litex_sim_dump()
{
"""
    if trace:
        content += """\
    litex_sim_tracer_dump();
"""
    content  += """\
}}

extern "C" void litex_sim_init(void **out)
{{
    Vsim *sim;

    sim = new Vsim;

    litex_sim_init_tracer(sim, {}, {});

""".format(trace_start, trace_end)
    for args in platform.sim_requested:
        content += _generate_sim_cpp_struct(*args)

    content += """\
    *out=sim;
}
"""
    tools.write_to_file("sim_init.cpp", content)


def _generate_sim_variables(include_paths, extra_mods, extra_mods_path):
    tapcfg_dir = get_data_mod("misc", "tapcfg").data_location
    include = ""
    for path in include_paths:
        include += "-I"+path+" "
    content = """\
SRC_DIR = {}
INC_DIR = {}
TAPCFG_DIRECTORY = {}
""".format(core_directory, include, tapcfg_dir)

    if extra_mods:
        modlist = " ".join(extra_mods)
        content += "EXTRA_MOD_LIST = " + modlist + "\n"
        content += "EXTRA_MOD_BASE_DIR = " + extra_mods_path + "\n"
        tools.write_to_file(extra_mods_path + "/variables.mak", content)

    tools.write_to_file("variables.mak", content)


def _generate_sim_config(config):
    content = config.get_json()
    tools.write_to_file("sim_config.js", content)


def _build_sim(build_name, sources, jobs, threads, coverage, opt_level="O3", trace_fst=False):
    makefile = os.path.join(core_directory, 'Makefile')

    cc_srcs = []
    for filename, language, library, *copy in sources:
        if Path(filename).suffix not in [".hex", ".init"]:
            cc_srcs.append("--cc " + filename + " ")

    build_script_contents = """\
rm -rf obj_dir/
make -C . -f {} {} {} {} {} {} {}
""".format(makefile,
    "CC_SRCS=\"{}\"".format("".join(cc_srcs)),
    "JOBS={}".format(jobs) if jobs else "",
    "THREADS={}".format(threads) if int(threads) > 1 else "",
    "COVERAGE=1" if coverage else "",
    "OPT_LEVEL={}".format(opt_level),
    "TRACE_FST=1" if trace_fst else "",
    )
    build_script_file = "build_" + build_name + ".sh"
    tools.write_to_file(build_script_file, build_script_contents, force_unix=True)

def _compile_sim(build_name, verbose):
    build_script_file = "build_" + build_name + ".sh"
    p = subprocess.Popen(["bash", build_script_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output, _ = p.communicate()
    output = output.decode('utf-8')
    if p.returncode != 0:
        error_messages = []
        for l in output.splitlines():
            if verbose or "error" in l.lower():
                error_messages.append(l)
        raise OSError("Subprocess failed with {}\n{}".format(p.returncode, "\n".join(error_messages)))
    if verbose:
        print(output)

def _run_sim(build_name, as_root=False, interactive=True):
    run_script_contents = "sudo " if as_root else ""
    run_script_contents += "obj_dir/Vsim"
    run_script_file = "run_" + build_name + ".sh"
    tools.write_to_file(run_script_file, run_script_contents, force_unix=True)
    if sys.platform != "win32" and interactive:
        import termios
        termios_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        r = subprocess.call(["bash", run_script_file])
        if r != 0:
            raise OSError("Subprocess failed")
    except:
        pass
    if sys.platform != "win32" and interactive:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, termios_settings)


class SimVerilatorToolchain:
    support_mixed_language = False
    def build(self, platform, fragment,
            build_dir        = "build",
            build_name       = "sim",
            serial           = "console",
            build            = True,
            run              = True,
            build_backend    = None,
            jobs             = None,
            threads          = 1,
            verbose          = True,
            sim_config       = None,
            coverage         = False,
            opt_level        = "O0",
            trace            = False,
            trace_fst        = False,
            trace_start      = 0,
            trace_end        = -1,
            regular_comb     = False,
            interactive      = True,
            pre_run_callback = None,
            extra_mods       = None,
            extra_mods_path  = ""):

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        if build:
            # Finalize design
            if not isinstance(fragment, _Fragment):
                fragment = fragment.get_fragment()
            platform.finalize(fragment)

            # Generate verilog
            v_output = platform.get_verilog(fragment,
                name         = build_name,
                regular_comb = regular_comb
            )
            named_sc, named_pc = platform.resolve_signals(v_output.ns)
            v_file = build_name + ".v"
            v_output.write(v_file)
            platform.add_source(v_file)

            # Generate cpp header/main/variables
            _generate_sim_h(platform)
            _generate_sim_cpp(platform, trace, trace_start, trace_end)

            _generate_sim_variables(platform.verilog_include_paths,
                                    extra_mods,
                                    extra_mods_path)

            # Generate sim config
            if sim_config:
                _generate_sim_config(sim_config)

            # Build
            _build_sim(build_name, platform.sources, jobs, threads, coverage, opt_level, trace_fst)

        # Run
        if run:
            if pre_run_callback is not None:
                pre_run_callback(v_output.ns)
            if which("verilator") is None:
                msg = "Unable to find Verilator toolchain, please either:\n"
                msg += "- Install Verilator.\n"
                msg += "- Add Verilator toolchain to your $PATH."
                raise OSError(msg)
            _compile_sim(build_name, verbose)
            run_as_root = False
            if sim_config.has_module("ethernet") \
               or sim_config.has_module("xgmii_ethernet") \
               or sim_config.has_module("gmii_ethernet"):
                run_as_root = True
            _run_sim(build_name, as_root=run_as_root, interactive=interactive)

        os.chdir(cwd)

        if build:
            return v_output.ns

def verilator_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Verilator toolchain options")
    toolchain_group.add_argument("--jobs",         default=None,        help="Limit the number of compiler jobs.")
    toolchain_group.add_argument("--threads",      default=1,           help="Set number of simulation threads.")
    toolchain_group.add_argument("--trace",        action="store_true", help="Enable Tracing.")
    toolchain_group.add_argument("--trace-fst",    action="store_true", help="Enable FST tracing.")
    toolchain_group.add_argument("--trace-start",  default="0",         help="Time to start tracing (ps).")
    toolchain_group.add_argument("--trace-end",    default="-1",        help="Time to end tracing (ps).")
    toolchain_group.add_argument("--opt-level",    default="O3",        help="Compilation optimization level.")

def verilator_build_argdict(args):
    return {
        "jobs"     :    args.jobs,
        "threads"     : args.threads,
        "trace"       : args.trace,
        "trace_fst"   : args.trace_fst,
        "trace_start" : int(float(args.trace_start)),
        "trace_end"   : int(float(args.trace_end)),
        "opt_level"   : args.opt_level
    }
