#
# This file is part of LiteX.
#
# Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.build import tools


# Interface Writer Block ---------------------------------------------------------------------------

class IPMWriterBlock(dict):
    def generate(self):
        raise NotImplementedError # Must be overloaded

class IPMWriterXMLBlock(dict):
    def generate(self):
        raise NotImplementedError # Must be overloaded

# Interface Writer  --------------------------------------------------------------------------------

class IPMWriter:
    def __init__(self, efinity_path):
        self.efinity_path = efinity_path
        self.blocks       = []
        self.filename     = ""
        self.platform     = None

    def set_build_params(self, platform, build_name):
        self.filename = build_name
        self.platform = platform



    def header(self, build_name, partnumber, family):
        header = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision()
        header += """
import os
import sys
import pprint
from pathlib import Path

home = "{0}"

sys.path.append(home + "/ipm/bin")

from ipm_api_service.design import IPMDesignAPI
from ipm_api_service.projectxml import ProjectXML

from common.logger import Logger

Logger.setup_logger(log_path_str=Path(".").absolute())

is_verbose = {1}
project_xml_path = Path(".").absolute()/"{2}.xml"

design = IPMDesignAPI(device_name="{3}", family_name="{4}", is_verbose=is_verbose)
projectxml = ProjectXML(project_xml_path=project_xml_path, is_verbose=is_verbose)

# pprint.pprint(design.get_ip_list())


"""
        return header.format(self.efinity_path, "True", build_name, partnumber, family)

    def get_block(self, name):
        for b in self.blocks:
            if b["name"] == name:
                return b
        return None

    def generate_ip_block(self, block, verbose=True):
        name = block["name"]
        cmd = "# ---------- IP {} ---------\n".format(name)
        cmd += f'design.create_ip(module_name="{name}",vendor="{block["vendor"]}",library="{block["library"]}",name="{block["ip_name"]}")\n'
        if "configs" in block:
            cmd += '# Configs\n'
            cmd += f'{name}_configs = {{\n'
            for p, v in block["configs"].items():
                cmd += f'    "{p}":"{v}",\n'
            cmd += f'}}\n\n'
            cmd += f'design.config_ip(module_name="{name}", configs = {name}_configs)\n'
        
        cmd += f'success, validated_param_result, param_template_list = design.validate_ip(module_name="{name}")\n\n'
        
        cmd += f'if success:\n'
        cmd += f'    result = design.generate_ip(module_name="{name}")\n'
        cmd += f'    if not projectxml.is_ip_exists(module_name="{name}"):\n'
        cmd += f'        projectxml.add_ip(module_name="{name}")\n'
        cmd += f'        projectxml.save()\n'

        cmd += "# ---------- END IP {} ---------\n\n".format(name)
        return cmd

    def generate(self, partnumber):
        output = ""
        for block in self.blocks:
            if isinstance(block, IPMWriterBlock):
                output += block.generate()
            else:
                if block["type"] == "IP":
                    output += self.generate_ip_block(block)
        return output
