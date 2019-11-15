# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# License: BSD

import os
import sys
import subprocess

from migen.fhdl.structure import _Fragment

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
    tools.write_to_file("dut_header.h", content)


def _generate_sim_cpp_struct(name, index, siglist):
    content = ''

    for i, (signame, sigbits, sigfname) in enumerate(siglist):
        content += '    {}{}[{}].signal = &dut->{};\n'.format(name, index, i, sigfname)

    idx_int = 0 if not index else int(index)
    content += '    litex_sim_register_pads({}{}, (char*)"{}", {});\n\n'.format(name, index, name, idx_int)

    return content


def _generate_sim_cpp(platform, trace=False, trace_start=0, trace_end=-1):
    content = """\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Vdut.h"
#include <verilated.h>
#include "dut_header.h"

extern "C" void litex_sim_init_tracer(void *vdut, long start, long end);
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
    Vdut *dut;

    dut = new Vdut;

    litex_sim_init_tracer(dut, {},{});

""".format(trace_start, trace_end)
    for args in platform.sim_requested:
        content += _generate_sim_cpp_struct(*args)

    content += """\
    *out=dut;
}
"""
    tools.write_to_file("dut_init.cpp", content)


def _generate_sim_variables(include_paths):
    include = ""
    for path in include_paths:
        include += "-I"+path+" "
    content = """\
SRC_DIR = {}
INC_DIR = {}
""".format(core_directory, include)
    tools.write_to_file("variables.mak", content)


def _generate_sim_config(config):
    content = config.get_json()
    tools.write_to_file("sim_config.js", content)


def _build_sim(build_name, sources, threads, coverage, opt_level="O3"):
    makefile = os.path.join(core_directory, 'Makefile')
    cc_srcs = []
    for filename, language, library in sources:
        cc_srcs.append("--cc " + filename + " ")
    build_script_contents = """\
rm -rf obj_dir/
make -C . -f {} {} {} {} {}
mkdir -p modules && cp obj_dir/*.so modules
""".format(makefile,
    "CC_SRCS=\"{}\"".format("".join(cc_srcs)),
    "THREADS={}".format(threads) if int(threads) > 1 else "",
    "COVERAGE=1" if coverage else "",
    "OPT_LEVEL={}".format(opt_level),
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

def _run_sim(build_name, as_root=False):
    run_script_contents = "sudo " if as_root else ""
    run_script_contents += "obj_dir/Vdut"
    run_script_file = "run_" + build_name + ".sh"
    tools.write_to_file(run_script_file, run_script_contents, force_unix=True)
    if sys.platform != "win32":
        import termios
        termios_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        r = subprocess.call(["bash", run_script_file])
        if r != 0:
            raise OSError("Subprocess failed")
    except:
        pass
    if sys.platform != "win32":
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, termios_settings)


class SimVerilatorToolchain:
    def build(self, platform, fragment, build_dir="build", build_name="dut",
            toolchain_path=None, serial="console", build=True, run=True, threads=1,
            verbose=True, sim_config=None, coverage=False, opt_level="O0",
            trace=False, trace_start=0, trace_end=-1):

        # create build directory
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        if build:
            # finalize design
            if not isinstance(fragment, _Fragment):
                fragment = fragment.get_fragment()
            platform.finalize(fragment)

            # generate top module
            top_output = platform.get_verilog(fragment,
                name=build_name, dummy_signal=False, regular_comb=False, blocking_assign=True)
            named_sc, named_pc = platform.resolve_signals(top_output.ns)
            top_file = build_name + ".v"
            top_output.write(top_file)
            platform.add_source(top_file)

            # generate cpp header/main/variables
            _generate_sim_h(platform)
            _generate_sim_cpp(platform, trace, trace_start, trace_end)
            _generate_sim_variables(platform.verilog_include_paths)

            # generate sim config
            if sim_config:
                _generate_sim_config(sim_config)

            # build
            _build_sim(build_name, platform.sources, threads, coverage, opt_level)

        # run
        if run:
            _compile_sim(build_name, verbose)
            run_as_root = False
            if sim_config.has_module("ethernet"):
                run_as_root = True
            if sim_config.has_module("xgmii_ethernet"):
                run_as_root = True
            _run_sim(build_name, as_root=run_as_root)

        os.chdir("../../")

        if build:
            return top_output.ns