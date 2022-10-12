#
# This file is part of LiteX.
#
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

# VHD2V Converter ----------------------------------------------------------------------------------

class VHD2VConverter(Module):
    """
    VHD2VConverter simplify use of VHDL code: used to convert with ghdl the code if
    needed or simply pass list of files to platform. May also add an Instance.
    Attributes
    ==========
    _top_entity: str
        name of the core highest level entity
    _build_dir: str
        directory where .ys and .v must be written and where to build 
    _work_package: str
        when package is not default one, used to provides its name
    _platform: subclass of GenericPlatform
        current platform
    _sources: list
        list of files contained into the core (relative or absolute path)
    _params: dict
        Instance like params (p_ generics, o_ output, ...) when add_instance,
        generics without prefix otherwise
    _add_instance: bool
        add if True an Instance()
    _force_convert: bool
        force use of GHDL even if the platform supports VHDL
    _ghdl_opts: str
        options to pass to ghdl
    """
    def __init__(self, platform, top_entity, build_dir,
        work_package  = None,
        force_convert = False,
        add_instance  = False,
        params        = dict(),
        files         = list()):
        """
        constructor (see class attributes)
        """
        self._top_entity    = top_entity
        self._build_dir     = build_dir
        self._work_package  = work_package 
        self._platform      = platform
        self._sources       = files
        self._params        = params
        self._force_convert = force_convert
        self._add_instance  = add_instance

        self._ghdl_opts    = "--ieee=synopsys -fexplicit -frelaxed-rules --std=08 "
        if work_package is not None:
            self._ghdl_opts += f"--work={self._work_package} "
        self._ghdl_opts += "\\"

    def add_source(self, filename):
        """
        append the source list with the path + name of a file
        Parameters
        ==========
        filename: str
            file name + path
        """
        self._sources.append(filename)

    def add_sources(self, path, filenames):
        """
        append the source list with a list of file after adding path
        Parameters
        ==========
        path: str
            absolute or relative path for all files
        filenames: list
            list of file to add
        """
        self._sources += [os.path.join(path, f) for f in filenames]

    def do_finalize(self):
        """
        - convert vhdl to verilog when toolchain can't deal with VHDL or
          when force_convert is set to true
        - appends platform file's list with the list of VHDL sources or
          with resulting verilog
        - add an Instance for this core
        """
        inst_name = self._top_entity

        # platform able to synthesis verilog and vhdl -> no conversion
        if self._platform.support_mixed_language and not self._force_convert:
            ip_params = self._params
            for file in self._files:
                platform.add_source(file)
        else: # platform is only able to synthesis verilog -> convert vhdl to verilog
            # check if more than one core is instanciated
            # if so -> append with _X
            # FIXME: better solution ?
            v_list = []
            for file, _, _ in self._platform.sources:
                if self._top_entity in file:
                    v_list.append(file)
            if len(v_list) != 0:
                inst_name += f"_{len(v_list)}"

            verilog_out = os.path.join(self._build_dir, f"{inst_name}.v")
            script = os.path.join(self._build_dir, f"{inst_name}.ys")
            ys = []
            ys.append("ghdl " + self._ghdl_opts)

            ip_params = dict()
            generics = []
            if self._add_instance:
                for k, v in self._params.items():
                    if k.startswith("p_"):
                        ys.append("-g" + k[2:] + "=" + str(v) + " \\")
                    else:
                        ip_params[k] = v
            else:
                ip_params = self._params

            from litex.build import tools
            import subprocess
            for source in self._sources:
                ys.append(source + " \\")
            ys.append(f"-e {self._top_entity}")
            ys.append("chformal -assert -remove")
            ys.append("write_verilog {}".format(verilog_out))
            tools.write_to_file(script, "\n".join(ys))
            if subprocess.call(["yosys", "-q", "-m", "ghdl", script]):
                raise OSError(f"Unable to convert {inst_name} to verilog, please check your GHDL-Yosys-plugin install")

            # more than one instance of this core? rename top entity to avoid conflict
            if inst_name != self._top_entity:
                tools.replace_in_file(verilog_out, f"module {self._top_entity}(", f"module {inst_name}(")
            self._platform.add_source(verilog_out)

        if self._add_instance:
            self.specials += Instance(inst_name, **ip_params)
