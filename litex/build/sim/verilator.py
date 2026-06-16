#
# This file is part of LiteX.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from shutil import which

from migen.fhdl.structure import _Fragment
from litex import get_data_mod
from litex.build import tools
from litex.build.generic_platform import *


sim_directory = os.path.abspath(os.path.dirname(__file__))
core_directory = os.path.join(sim_directory, "core")

_trace_timescale_units = {
    "ps" : 1,
    "ns" : 1_000,
    "us" : 1_000_000,
    "ms" : 1_000_000_000,
    "s"  : 1_000_000_000_000,
}


def _parse_trace_timescale(timescale):
    timescale = timescale.strip().lower()
    match = re.fullmatch(r"(1|10|100)(ps|ns|us|ms|s)", timescale)
    if match is None:
        raise ValueError(
            "Trace timescale must be 1/10/100 followed by ps/ns/us/ms/s "
            "(ex: 1ps, 100ps, 1ns)."
        )
    scale, unit = match.groups()
    return timescale, int(scale) * _trace_timescale_units[unit]


def _trace_timescale_arg(timescale):
    try:
        return _parse_trace_timescale(timescale)[0]
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def _validate_trace_timescale(timescale, timescale_ps, sim_config):
    if sim_config is None:
        return
    timebase_ps = sim_config.get_timebase_ps()
    if timebase_ps % timescale_ps:
        raise ValueError(
            "Trace timescale {} cannot represent simulation timebase {}ps; "
            "use a trace timescale that divides the simulation timebase.".format(
                timescale, timebase_ps)
        )


def _normalize_verilator_extra_sources(verilator_extra_sources):
    if verilator_extra_sources is None:
        return []
    if isinstance(verilator_extra_sources, (str, os.PathLike)):
        verilator_extra_sources = [verilator_extra_sources]
    return [os.path.abspath(os.fspath(filename)) for filename in verilator_extra_sources]


def _generate_sim_h_struct(name, index, siglist):
    content = ""

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
    content = ""

    for i, (signame, sigbits, sigfname) in enumerate(siglist):
        content += '    {}{}[{}].signal = &sim->{};\n'.format(name, index, i, sigfname)

    idx_int = 0 if not index else int(index)
    content += '    litex_sim_register_pads({}{}, (char*)"{}", {});\n\n'.format(name, index, name, idx_int)

    return content


def _generate_sim_cpp(platform, trace=False, trace_start=0, trace_end=-1,
        trace_timescale="1ps", trace_timescale_ps=1, load_start=0, save_start=-1):
    content = """\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "Vsim.h"
#include <verilated.h>
#include "sim_header.h"

extern "C" void litex_sim_init_runtime(long load_start, long save_start);
#if defined(__GNUC__) || defined(__clang__)
extern "C" void litex_sim_user_init(void *vsim) __attribute__((weak));
static void litex_sim_call_user_init(void *vsim)
{
    if (litex_sim_user_init != nullptr)
        litex_sim_user_init(vsim);
}
#else
static void litex_sim_call_user_init(void *vsim)
{
    (void)vsim;
}
#endif
"""
    if trace:
        content += """\
extern "C" void litex_sim_init_tracer(void *vsim, long start, long end,
                                      const char *timescale, uint64_t timescale_ps);
extern "C" void litex_sim_tracer_dump();

"""
    content += """\
extern "C" void litex_sim_dump()
{
"""
    if trace:
        content += """\
    litex_sim_tracer_dump();
"""
    content += """\
}}

extern "C" void litex_sim_init(void **out)
{{
    Vsim *sim;

    sim = new Vsim;

    litex_sim_init_runtime({}, {});
""".format(load_start, save_start)
    if trace:
        content += """\
    litex_sim_init_tracer(sim, {}, {}, "{}", {});

""".format(trace_start, trace_end, trace_timescale, trace_timescale_ps)
    for args in platform.sim_requested:
        content += _generate_sim_cpp_struct(*args)

    content += """\
    litex_sim_call_user_init(sim);

    *out = sim;
}
"""
    tools.write_to_file("sim_init.cpp", content)


def _generate_sim_variables(include_paths, extra_mods, extra_mods_path, video,
        verilator_extra_sources=None):
    tapcfg_dir = get_data_mod("misc", "tapcfg").data_location
    include = ""
    for path in include_paths:
        include += "-I" + path + " "
    verilator_extra_sources = verilator_extra_sources or []
    user_cpp_inc_dirs = []
    for filename in verilator_extra_sources:
        include_dir = os.path.dirname(filename)
        if include_dir and include_dir not in user_cpp_inc_dirs:
            user_cpp_inc_dirs.append(include_dir)
    content = """\
SRC_DIR = {}
INC_DIR = {}
TAPCFG_DIRECTORY = {}
USER_CPP_SRCS = {}
USER_CPP_INC_DIRS = {}
{}
""".format(
    core_directory,
    include,
    tapcfg_dir,
    " ".join(verilator_extra_sources),
    " ".join("-I" + path for path in user_cpp_inc_dirs),
    "VIDEO = 1" if video else "")

    if extra_mods:
        if not extra_mods_path:
            raise ValueError("extra_mods_path must be set when extra_mods is used.")
        modlist = " ".join(extra_mods)
        content += "EXTRA_MOD_LIST = " + modlist + "\n"
        content += "EXTRA_MOD_BASE_DIR = " + extra_mods_path + "\n"
        tools.write_to_file(os.path.join(extra_mods_path, "variables.mak"), content)

    tools.write_to_file("variables.mak", content)


def _generate_sim_config(config):
    content = config.get_json()
    tools.write_to_file("sim_config.js", content)


def _build_sim(build_name, sources, jobs, threads, coverage, opt_level="O3",
        trace=False, trace_fst=False, video=False, savable=False):
    makefile = os.path.join(core_directory, "Makefile")

    cc_srcs = []
    for filename, language, library, *copy in sources:
        if Path(filename).suffix not in [".hex", ".init"]:
            cc_srcs.append("--cc " + filename + " ")

    make_args = [
        'CC_SRCS="{}"'.format("".join(cc_srcs)),
        "JOBS={}".format(jobs) if jobs else "",
        "THREADS={}".format(threads) if int(threads) > 1 else "",
        "COVERAGE=1" if coverage else "",
        "OPT_LEVEL={}".format(opt_level),
        "TRACE=1" if trace else "",
        "TRACE_FST=1" if trace_fst else "",
        "VIDEO=1" if video else "",
        "SAVABLE=1" if savable else "",
    ]

    build_script_contents = """\
rm -rf obj_dir/
make -C . -f {} {}
""".format(makefile, " ".join(arg for arg in make_args if arg))
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
    termios_settings = None
    if sys.platform != "win32" and interactive and sys.stdin.isatty():
        import termios
        termios_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        p = subprocess.Popen(["bash", run_script_file])
        try:
            r = p.wait()
        except KeyboardInterrupt:
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.terminate()
                try:
                    p.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            print()
            raise SystemExit(130)
        if r == -signal.SIGINT:
            print()
            raise SystemExit(130)
        if r != 0:
            raise OSError("Subprocess failed")
    finally:
        if termios_settings is not None:
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
            video            = False,
            trace            = False,
            trace_fst        = False,
            trace_start      = 0,
            trace_end        = -1,
            trace_timescale  = "1ps",
            hierarchical     = False,
            interactive      = True,
            pre_run_callback = None,
            extra_mods       = None,
            extra_mods_path  = "",
            load_start       = 0,
            save_start       = -1,
            verilator_extra_sources = None,
            **kwargs):

        verilator_extra_sources = _normalize_verilator_extra_sources(verilator_extra_sources)

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)
        try:
            if build:
                # Finalize design
                if not isinstance(fragment, _Fragment):
                    fragment = fragment.get_fragment()
                platform.finalize(fragment)

                # Generate verilog
                v_output = platform.get_verilog(fragment,
                    name         = build_name,
                    hierarchical = hierarchical,
                )
                named_sc, named_pc = platform.resolve_signals(v_output.ns)
                v_file = build_name + ".v"
                v_output.write(v_file)
                platform.add_source(v_file)

                # Generate cpp header/main/variables
                _generate_sim_h(platform)
                trace_enabled = trace or trace_fst
                trace_timescale, trace_timescale_ps = _parse_trace_timescale(trace_timescale)
                if trace_enabled:
                    _validate_trace_timescale(trace_timescale, trace_timescale_ps, sim_config)
                _generate_sim_cpp(
                    platform,
                    trace             = trace_enabled,
                    trace_start       = trace_start,
                    trace_end         = trace_end,
                    trace_timescale   = trace_timescale,
                    trace_timescale_ps = trace_timescale_ps,
                    load_start        = load_start,
                    save_start        = save_start,
                )

                _generate_sim_variables(platform.verilog_include_paths,
                                        extra_mods,
                                        extra_mods_path,
                                        video,
                                        verilator_extra_sources)

                # Generate sim config
                if sim_config:
                    _generate_sim_config(sim_config)

                # Build
                # Set SAVABLE=1 if load_start != 0 and save_start != -1
                savable = (load_start != 0 or save_start != -1)
                _build_sim(
                    build_name = build_name,
                    sources    = platform.sources,
                    jobs       = jobs,
                    threads    = threads,
                    coverage   = coverage,
                    opt_level  = opt_level,
                    trace      = trace_enabled,
                    trace_fst  = trace_fst,
                    video      = video,
                    savable    = savable,
                )

            # Run
            if run:
                if pre_run_callback is not None:
                    if not build:
                        raise ValueError("pre_run_callback requires build=True (signal namespace is only available after build).")
                    pre_run_callback(v_output.ns)
                if which("verilator") is None:
                    msg = "Unable to find Verilator toolchain, please either:\n"
                    msg += "- Install Verilator.\n"
                    msg += "- Add Verilator toolchain to your $PATH."
                    raise OSError(msg)
                _compile_sim(build_name, verbose)
                run_as_root = False
                if sim_config is not None and (sim_config.has_module("ethernet")
                   or sim_config.has_module("xgmii_ethernet")
                   or sim_config.has_module("gmii_ethernet")):
                    run_as_root = True
                _run_sim(build_name, as_root=run_as_root, interactive=interactive)
        finally:
            os.chdir(cwd)

        if build:
            return v_output.ns

    def add_period_constraint(self, platform, clk, period, keep=True, name=None):
        pass

    def add_false_path_constraint(self, platform, from_, to):
        pass


def verilator_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Verilator toolchain options")
    toolchain_group.add_argument("--jobs",         default=None,        help="Limit the number of compiler jobs.")
    toolchain_group.add_argument("--threads",      default=1,           help="Set number of simulation threads.")
    toolchain_group.add_argument("--trace",        action="store_true", help="Enable Tracing.")
    toolchain_group.add_argument("--trace-fst",    action="store_true", help="Enable FST tracing.")
    toolchain_group.add_argument("--trace-start",  default="0",         help="Time to start tracing (ps).")
    toolchain_group.add_argument("--trace-end",    default="-1",        help="Time to end tracing (ps).")
    toolchain_group.add_argument("--trace-timescale", default="1ps", type=_trace_timescale_arg,
                                 help="VCD/FST trace timescale (default: 1ps).")
    toolchain_group.add_argument("--opt-level",    default="O3",        help="Compilation optimization level.")
    toolchain_group.add_argument("--load-start",   default="0",         help="Time to restore simulation state (ps).")
    toolchain_group.add_argument("--save-start",   default="-1",        help="Time to save simulation state (ps).")
    toolchain_group.add_argument("--verilator-extra-source", action="append", default=[],
                                 dest="verilator_extra_sources",
                                 help="Add user C++ source to the Verilator simulation executable.")


def verilator_build_argdict(args):
    return {
        "jobs"        : args.jobs,
        "threads"     : args.threads,
        "trace"       : args.trace,
        "trace_fst"   : args.trace_fst,
        "trace_start" : int(float(args.trace_start)),
        "trace_end"   : int(float(args.trace_end)),
        "trace_timescale" : args.trace_timescale,
        "opt_level"   : args.opt_level,
        "load_start"  : int(float(args.load_start)),
        "save_start"  : int(float(args.save_start)),
        "verilator_extra_sources" : args.verilator_extra_sources,
    }
