# This file is Copyright (c) 2015-2016 Florent Kermarrec <florent@enjoy-digital.fr>
#                            2017 Pierre-Olivier Vauboin <po@lambdaconcept.com>
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


def _generate_sim_cpp(platform):
    content = """\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Vdut.h"
#include <verilated.h>
#include "dut_header.h"

extern "C" void litex_sim_init(void **out)
{
    Vdut *dut;

    dut = new Vdut;

"""
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


def _build_sim(platform, build_name, threads, verbose):
    makefile = os.path.join(core_directory, 'Makefile')
    build_script_contents = """\
rm -rf obj_dir/
make -C . -f {} {}
mkdir -p modules && cp obj_dir/*.so modules
""".format(makefile, "THREADS={}".format(threads) if int(threads) > 1 else "")
    build_script_file = "build_" + build_name + ".sh"
    tools.write_to_file(build_script_file, build_script_contents, force_unix=True)

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
        if sys.platform != "win32":
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, termios_settings)


class SimVerilatorToolchain:
    def build(self, platform, fragment, build_dir="build", build_name="dut",
            toolchain_path=None, serial="console", build=True, run=True, threads=1,
            verbose=True, sim_config=None):

        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        if build:
            if not isinstance(fragment, _Fragment):
                fragment = fragment.get_fragment()
            platform.finalize(fragment)

            v_output = platform.get_verilog(fragment,
                name=build_name, dummy_signal=False, regular_comb=False, blocking_assign=True)
            named_sc, named_pc = platform.resolve_signals(v_output.ns)
            v_output.write(build_name + ".v")

            include_paths = []
            for source in platform.sources:
                path = os.path.dirname(source[0]).replace("\\", "\/")
                if path not in include_paths:
                    include_paths.append(path)
            include_paths += platform.verilog_include_paths
            _generate_sim_h(platform)
            _generate_sim_cpp(platform)
            _generate_sim_variables(include_paths)
            if sim_config:
                _generate_sim_config(sim_config)

            _build_sim(platform, build_name, threads, verbose)

        if run:
            _run_sim(build_name, as_root=sim_config.has_module("ethernet"))

        os.chdir("../../")

        if build:
            return v_output.ns