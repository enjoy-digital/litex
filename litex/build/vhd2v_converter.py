#
# This file is part of LiteX.
#
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

# FIXME/CHECKME:
# --------------
# - Ideally, sources should still be added to the platform (and not to VHD2VConverter). The sources
# for the conversion could probably be collected from the LiteX's Module during the finalize.
# - Check parameter names (ex: top_entity->top/top_level?, work_package->work_library?).
# - Check if adding instance will be useful.

# VHD2V Converter ----------------------------------------------------------------------------------

class VHD2VConverter(Module):
    """
    VHD2VConverter simplify use of VHDL code: used to convert with ghdl the code if needed or simply
    pass list of files to platform. May also add an Instance.
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

        self._ghdl_opts     = ["--std=08", "--no-formal"]

        if work_package is not None:
            self._ghdl_opts.append(f"--work={self._work_package}")

    def add_source(self, filename):
        """
        append the source list with the path + name of a file
        Parameters
        ==========
        filename: str
            file name + path
        """
        self._sources.append(filename)

    def add_sources(self, path, *filenames):
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
            for file in self._sources:
                self._platform.add_source(file)
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

            ip_params = dict()
            generics = []
            for k, v in self._params.items():
                if k.startswith("p_"):
                    generics.append("-g" + k[2:] + "=" + str(v))
                else:
                    ip_params[k] = v

            cmd = ["ghdl", "--synth", "--out=verilog"]
            cmd += self._ghdl_opts
            cmd += generics
            cmd += self._sources
            cmd += ["-e", self._top_entity]

            import subprocess
            from litex.build import tools

            with open(verilog_out, 'w') as output:
                s = subprocess.run(cmd, stdout=output)
                if s.returncode:
                    raise OSError(f"Unable to convert {inst_name} to verilog, please check your GHDL install")

            # more than one instance of this core? rename top entity to avoid conflict
            if inst_name != self._top_entity:
                tools.replace_in_file(verilog_out, f"module {self._top_entity}(", f"module {inst_name}(")
            self._platform.add_source(verilog_out)

        if self._add_instance:
            self.specials += Instance(inst_name, **ip_params)
