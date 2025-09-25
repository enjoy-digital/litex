#
# This file is part of LiteX.
#
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from shutil import which

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
    _instance: class Instance
        Another instance to convert
    _add_instance: bool
        add if True an Instance()
    _force_convert: bool
        force use of GHDL even if the platform supports VHDL
    _flatten_source: bool
        flatten source with yosys after GHDL's convert (Only used when GHDL is used and yosys present).
    _ghdl_opts: str
        options to pass to ghdl
    _libraries: list of str or tuple
        list of libraries (library_name, library_path) to compile before conversion.
    """
    def __init__(self, platform, top_entity=None, build_dir=None,
        work_package   = None,
        force_convert  = False,
        flatten_source = True,
        add_instance   = False,
        params         = None,
        instance       = None,
        files          = None,
        libraries      = None):
        """
        constructor (see class attributes)
        """
        if files is None:
            files = []
        if libraries is None:
            libraries = []
        self._top_entity     = top_entity
        self._build_dir      = build_dir
        self._work_package   = work_package
        self._platform       = platform
        self._sources        = files
        self._params         = params
        self._instance       = instance
        self._force_convert  = force_convert
        self._flatten_source = flatten_source
        self._add_instance   = add_instance
        self._work_package   = work_package
        self._libraries      = list()

        # Params and instance can't be provided at the same time.
        assert not ((self._params is not None) and (self._instance is not None))
        # When add_instance params or instance must be set.
        assert not (self._add_instance and ((self._params is None) and (self._instance is None)))

        if self._instance is not None and self._top_entity is None:
            self._top_entity = self._instance.name_override

        self._ghdl_opts     = ["--std=08", "--no-formal"]

        if work_package is not None:
            self._ghdl_opts.append(f"--work={self._work_package}")

        self.add_libraries(libraries)

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

    def add_libraries(self, libraries=[]):
        """
        append the library list with a list of tuple (work, file).
        Parameters
        ==========
        libraries: list of str or tuple
            when str a vhdl library full path, when tuple the work package name
            and the vhdl libary path
        """
        for lib in libraries:
            # when lib is a str -> convert to a tupple based on lib name
            if type(lib) == str:
                work_pkg = os.path.splitext(os.path.basename(lib))[0]
                lib      = (work_pkg, lib)
            elif type(lib) != tuple:
                raise OSError(f"{lib} must a string or a set")
            self._libraries.append(lib)

    def do_finalize(self):
        """
        - convert vhdl to verilog when toolchain can't deal with VHDL or
          when force_convert is set to true
        - appends platform file's list with the list of VHDL sources or
          with resulting verilog
        - add an Instance for this core
        """
        inst_name = self._top_entity

        if self._build_dir is None:
            self._build_dir = os.path.join(os.path.abspath(self._platform.output_dir), "vhd2v")

        # platform able to synthesis verilog and vhdl -> no conversion
        if self._platform.support_mixed_language and not self._force_convert:
            if self._params:
                ip_params = self._params
            elif self._instance:
                ip_params = self._instance.items
            for file in self._sources:
                self._platform.add_source(file, library=self._work_package)
        else: # platform is only able to synthesis verilog -> convert vhdl to verilog
            import subprocess
            from litex.build import tools

            # First: compile external libraries (if requested)
            for lib in self._libraries:
                (work_pkg, filename) = lib
                cmd = ["ghdl", "-a", "--std=08", f"--work={work_pkg}", filename]
                print(cmd)
                s   = subprocess.run(cmd)
                if s.returncode:
                    raise OSError(f"Unable to compile {filename}, please check your GHDL install.")

            # check if more than one core is instanciated
            # if so -> append with _X
            # FIXME: better solution ?
            v_list = []
            for file, _, _ in self._platform.sources:
                if self._top_entity in file:
                    v_list.append(file)
            if len(v_list) != 0:
                inst_name += f"_{len(v_list)}"


            # Create build_dir if not existing.
            if not os.path.exists(self._build_dir):
                os.makedirs(self._build_dir)

            verilog_out = os.path.join(self._build_dir, f"{inst_name}.v")

            generics = []
            if self._params:
                ip_params = dict()
                for k, v in self._params.items():
                    if k.startswith("p_"):
                        generics.append("-g" + k[2:] + "=" + str(v))
                    else:
                        ip_params[k] = v
            elif self._instance:
                ip_params = list()
                for item in self._instance.items:
                    if isinstance(item, Instance.Parameter):
                        generics.append("-g" + item.name + "=" + str(item.value.value))
                    else:
                        ip_params.append(item)

            cmd = ["ghdl", "--synth", "--out=verilog"]
            cmd += self._ghdl_opts
            cmd += generics
            cmd += self._sources
            cmd += ["-e", self._top_entity]
            print(cmd)

            with open(verilog_out, 'w') as output:
                s = subprocess.run(cmd, stdout=output)
                if s.returncode:
                    raise OSError(f"Unable to convert {inst_name} to verilog, please check your GHDL install")

            # Prepend `default_nettype wire`
            with open(verilog_out, 'r') as f:
                content = f.read()
            with open(verilog_out, 'w') as f:
                f.write("`default_nettype wire\n" + content)

            flatten_source = False
            if which("yosys") is not None and self._flatten_source:
                s = subprocess.run(["yosys", "-V"], capture_output=True)
                if not s.returncode:
                    # yosys version is the second word in the answer
                    ret = str(s.stdout).split(" ")[1]
                    # case a -yy is added too (ubuntu sub-version)
                    version = float(ret.split("+")[0].split("-")[0])
                    # yosys 0.9 is too old and can't support following command
                    if version != 0.9:
                        flatten_source = True

            # Flatten and rename verilog entity to avoid conflicts
            if flatten_source:
                yscmd = ["yosys", "-p",
                    f"read_verilog {verilog_out}; hierarchy -top {self._top_entity}; flatten; proc; rename {self._top_entity} {inst_name}; write_verilog {verilog_out};"]

                s = subprocess.run(yscmd)
                if s.returncode:
                    raise OSError(f"Unable to flatten {inst_name}, please check your yosys install")
            else:
                # more than one instance of this core? rename top entity to avoid conflict
                if inst_name != self._top_entity:
                    tools.replace_in_file(verilog_out, f"module {self._top_entity}", f"module {inst_name}")
                tools.replace_in_file(verilog_out, f"\\", f"ghdl_") # FIXME: GHDL synth workaround, improve.

            self._platform.add_source(verilog_out)

        if self._add_instance:
            if self._instance:
                # remove current instance to avoid multiple definition
                delattr(self, "_instance")
                self.specials += Instance(inst_name, *ip_params)
            else:
                self.specials += Instance(inst_name, **ip_params)
