#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import csv
import re
import datetime

from xml.dom import expatbuilder
import xml.etree.ElementTree as et

from litex.build import tools

namespaces = {
    "efxpt" : "http://www.efinixinc.com/peri_design_db",
    "xi"    : "http://www.w3.org/2001/XInclude"
}

# Interface Writer  --------------------------------------------------------------------------------

class InterfaceWriter:
    def __init__(self, efinity_path):
        self.efinity_path = efinity_path
        self.blocks       = []
        self.xml_blocks   = []
        self.filename     = ''
        self.platform     = None

    def set_build_params(self, platform, build_name):
        self.filename = build_name
        self.platform = platform

    def generate_xml_blocks(self):
        et.register_namespace('efxpt', "http://www.efinixinc.com/peri_design_db")
        tree = et.parse(self.filename + '.peri.xml')
        root = tree.getroot()

        for block in self.xml_blocks:
            if block['type'] == 'DDR':
                self.add_ddr_xml(root, block)
            if block['type'] == 'LVDS':
                self.add_ddr_lvds(root, block)

        xml_string = et.tostring(root, 'utf-8')
        reparsed = expatbuilder.parseString(xml_string, False)
        print_string = reparsed.toprettyxml(indent="    ")

        # Remove lines with only whitespaces. Not sure why they are here
        print_string = os.linesep.join([s for s in print_string.splitlines() if s.strip()])

        tools.write_to_file("{}.peri.xml".format(self.filename), print_string)

    def add_ddr_lvds(self, root, params):
        lvds_info = root.find('efxpt:lvds_info', namespaces)
        if params['mode'] == 'OUTPUT':
            dir  = 'tx'
            mode = 'out'
        else:
            dir  = 'rx'
            mode = 'in'

        pad = self.platform.parser.get_gpio_instance_from_pin(params['location'][0])
        pad = pad.replace('TXP', 'TX')
        pad = pad.replace('TXN', 'TX')
        pad = pad.replace('RXP', 'RX')
        pad = pad.replace('RXN', 'RX')
        # Sometimes there is an extra identifier at the end
        # TODO: do a better parser
        if pad.count('_') == 2:
            pad = pad.rsplit('_', 1)[0]

        lvds = et.SubElement(lvds_info, 'efxpt:lvds',
            name     = params['name'],
            lvds_def = pad,
            ops_type = dir
        )

        et.SubElement(lvds, 'efxpt:ltx_info',
            pll_instance    = '',
            fast_clock_name = '{}'.format(params['fast_clk']),
            slow_clock_name = '{}'.format(params['slow_clk']),
            reset_name      = '',
            out_bname       = '{}'.format(params['name']),
            oe_name         = '',
            clock_div       = '1',
            mode            = '{}'.format(mode),
            serialization   = '{}'.format(params['serialisation']),
            reduced_swing   = 'false',
            load            = '3'
        )


    def add_ddr_xml(self, root, params):
        ddr_info = root.find('efxpt:ddr_info', namespaces)

        ddr = et.SubElement(ddr_info, 'efxpt:ddr',
            name            = 'ddr_inst1',
            ddr_def         = 'DDR_0',
            cs_preset_id    = '173',
            cs_mem_type     = 'LPDDR3',
            cs_ctrl_width   = 'x32',
            cs_dram_width   = 'x32',
            cs_dram_density = '8G',
            cs_speedbin     = '800',
            target0_enable  = 'true',
            target1_enable  = 'false',
            ctrl_type       = 'none'
        )

        axi_suffix = ''     # '_1' for second port
        type_suffix = '_0'  # '_1' for second port

        gen_pin_target0 = et.SubElement(ddr, 'efxpt:gen_pin_target0')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_wdata{}'.format(axi_suffix),  type_name='WDATA{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_wready{}'.format(axi_suffix), type_name='WREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_wid{}'.format(axi_suffix),    type_name='WID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_bready{}'.format(axi_suffix), type_name='BREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_rdata{}'.format(axi_suffix),  type_name='RDATA{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_aid{}'.format(axi_suffix),    type_name='AID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_bvalid{}'.format(axi_suffix), type_name='BVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_rlast{}'.format(axi_suffix),  type_name='RLAST{}'.format(type_suffix),  is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_bid{}'.format(axi_suffix),    type_name='BID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_asize{}'.format(axi_suffix),  type_name='ASIZE{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_atype{}'.format(axi_suffix),  type_name='ATYPE{}'.format(type_suffix),  is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_aburst{}'.format(axi_suffix), type_name='ABURST{}'.format(type_suffix), is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_wvalid{}'.format(axi_suffix), type_name='WVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_wlast{}'.format(axi_suffix),  type_name='WLAST{}'.format(type_suffix),  is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_aaddr{}'.format(axi_suffix),  type_name='AADDR{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_rid{}'.format(axi_suffix),    type_name='RID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_avalid{}'.format(axi_suffix), type_name='AVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_rvalid{}'.format(axi_suffix), type_name='RVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_alock{}'.format(axi_suffix),  type_name='ALOCK{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_rready{}'.format(axi_suffix), type_name='RREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_rresp{}'.format(axi_suffix),  type_name='RRESP{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_wstrb{}'.format(axi_suffix),  type_name='WSTRB{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_aready{}'.format(axi_suffix), type_name='AREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_alen{}'.format(axi_suffix),   type_name='ALEN{}'.format(type_suffix),   is_bus = 'true')
        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_clk',                         type_name='ACLK{}'.format(type_suffix),   is_bus = 'false', is_clk = 'true', is_clk_invert = 'false')

        axi_suffix = '_1'     # '_1' for second port
        type_suffix = '_1'  # '_1' for second port

        gen_pin_target1 = et.SubElement(ddr, 'efxpt:gen_pin_target1')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_wdata{}'.format(axi_suffix),  type_name='WDATA{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_wready{}'.format(axi_suffix), type_name='WREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_wid{}'.format(axi_suffix),    type_name='WID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_bready{}'.format(axi_suffix), type_name='BREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_rdata{}'.format(axi_suffix),  type_name='RDATA{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_aid{}'.format(axi_suffix),    type_name='AID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_bvalid{}'.format(axi_suffix), type_name='BVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_rlast{}'.format(axi_suffix),  type_name='RLAST{}'.format(type_suffix),  is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_bid{}'.format(axi_suffix),    type_name='BID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_asize{}'.format(axi_suffix),  type_name='ASIZE{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_atype{}'.format(axi_suffix),  type_name='ATYPE{}'.format(type_suffix),  is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_aburst{}'.format(axi_suffix), type_name='ABURST{}'.format(type_suffix), is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_wvalid{}'.format(axi_suffix), type_name='WVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_wlast{}'.format(axi_suffix),  type_name='WLAST{}'.format(type_suffix),  is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_aaddr{}'.format(axi_suffix),  type_name='AADDR{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_rid{}'.format(axi_suffix),    type_name='RID{}'.format(type_suffix),    is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_avalid{}'.format(axi_suffix), type_name='AVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_rvalid{}'.format(axi_suffix), type_name='RVALID{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_alock{}'.format(axi_suffix),  type_name='ALOCK{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_rready{}'.format(axi_suffix), type_name='RREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_rresp{}'.format(axi_suffix),  type_name='RRESP{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_wstrb{}'.format(axi_suffix),  type_name='WSTRB{}'.format(type_suffix),  is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_aready{}'.format(axi_suffix), type_name='AREADY{}'.format(type_suffix), is_bus = 'false')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_alen{}'.format(axi_suffix),   type_name='ALEN{}'.format(type_suffix),   is_bus = 'true')
        et.SubElement(gen_pin_target1, 'efxpt:pin', name='axi_clk',                         type_name='ACLK{}'.format(type_suffix),   is_bus = 'false', is_clk = 'true', is_clk_invert = 'false')

        gen_pin_config = et.SubElement(ddr, 'efxpt:gen_pin_config')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SEQ_RST',   is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SCL_IN',    is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SEQ_START', is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='RSTN',          is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SDA_IN',    is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SDA_OEN',   is_bus = 'false')

        cs_fpga = et.SubElement(ddr, 'efxpt:cs_fpga')
        et.SubElement(cs_fpga, 'efxpt:param', name='FPGA_ITERM', value='120', value_type = 'str')
        et.SubElement(cs_fpga, 'efxpt:param', name='FPGA_OTERM', value='34',  value_type = 'str')

        cs_memory = et.SubElement(ddr, 'efxpt:cs_memory')
        et.SubElement(cs_memory, 'efxpt:param', name='RTT_NOM',   value='RZQ/2',     value_type = 'str')
        et.SubElement(cs_memory, 'efxpt:param', name='MEM_OTERM', value='40',        value_type = 'str')
        et.SubElement(cs_memory, 'efxpt:param', name='CL',        value='RL=6/WL=3', value_type = 'str')

        timing = et.SubElement(ddr, 'efxpt:cs_memory_timing')
        et.SubElement(timing, 'efxpt:param', name='tRAS',  value= '42.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tRC',   value= '60.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tRP',   value= '18.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tRCD',  value= '18.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tREFI', value= '3.900',   value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tRFC',  value= '210.000', value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tRTP',  value= '10.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tWTR',  value= '10.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tRRD',  value= '10.000',  value_type='float')
        et.SubElement(timing, 'efxpt:param', name='tFAW',  value= '50.000',  value_type='float')

        cs_control = et.SubElement(ddr, 'efxpt:cs_control')
        et.SubElement(cs_control, 'efxpt:param', name='AMAP',             value= 'ROW-COL_HIGH-BANK-COL_LOW', value_type='str')
        et.SubElement(cs_control, 'efxpt:param', name='EN_AUTO_PWR_DN',   value= 'Off',                       value_type='str')
        et.SubElement(cs_control, 'efxpt:param', name='EN_AUTO_SELF_REF', value= 'No',                        value_type='str')

        cs_gate_delay = et.SubElement(ddr, 'efxpt:cs_gate_delay')
        et.SubElement(cs_gate_delay, 'efxpt:param', name='EN_DLY_OVR', value= 'No', value_type='str')
        et.SubElement(cs_gate_delay, 'efxpt:param', name='GATE_C_DLY', value= '3',  value_type='int')
        et.SubElement(cs_gate_delay, 'efxpt:param', name='GATE_F_DLY', value= '0',  value_type='int')

    def header(self, build_name, partnumber):
        header = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision()
        header += """
import os
import sys
import pprint

home = '{0}'

os.environ['EFXPT_HOME']  = home + '/pt'
os.environ['EFXPGM_HOME'] = home + '/pgm'
os.environ['EFXDBG_HOME'] = home + '/debugger'
os.environ['EFXIPM_HOME'] = home + '/ipm'

sys.path.append(home + '/pt/bin')
sys.path.append(home + '/lib/python3.8/site-packages')

from api_service.design import DesignAPI
from api_service.device import DeviceAPI

is_verbose = {1}

design = DesignAPI(is_verbose)
device = DeviceAPI(is_verbose)

design.create('{2}', '{3}', './../gateware', overwrite=True)

"""
        return header.format(self.efinity_path, 'True', build_name, partnumber)

    def get_block(self, name):
        for b in self.blocks:
            if b['name'] == name:
                return b
        return None

    def generate_gpio(self, block, verbose=True):
        name = block['name']
        mode = block['mode']
        cmd = ''

        if mode == 'INOUT':
            if len(block['location']) == 1:
                cmd += 'design.create_inout_gpio("{}")\n'.format(name)
                cmd += 'design.assign_pkg_pin("{}","{}")\n'.format(name, block['location'][0])
            else:
                cmd += 'design.create_inout_gpio("{}",{},0)\n'.format(name, block['size']-1)
                for i, pad in enumerate(block['location']):
                    cmd += 'design.assign_pkg_pin("{}[{}]","{}")\n'.format(name, i, pad)
            cmd += '\n'
            return cmd

        if mode == 'INPUT':
            if len(block['location']) == 1:
                cmd += 'design.create_input_gpio("{}")\n'.format(name)
                cmd += 'design.assign_pkg_pin("{}","{}")\n'.format(name, block['location'][0])
            else:
                cmd += 'design.create_input_gpio("{}",{},0)\n'.format(name, block['size']-1)
                for i, pad in enumerate(block['location']):
                    cmd += 'design.assign_pkg_pin("{}[{}]","{}")\n'.format(name, i, pad)
            if 'in_reg' in block:
                cmd += 'design.set_property("{}","IN_REG","{}")\n'.format(name, block['in_reg'])
                cmd += 'design.set_property("{}","IN_CLK_PIN","{}")\n'.format(name, block['in_clk_pin'])
            return cmd

        if mode == 'OUTPUT':
            if len(block['location']) == 1:
                cmd += 'design.create_output_gpio("{}")\n'.format(name)
                cmd += 'design.assign_pkg_pin("{}","{}")\n'.format(name, block['location'][0])
            else:
                cmd += 'design.create_input_gpio("{}",{},0)\n'.format(name, block['size']-1)
                for i, pad in enumerate(block['location']):
                    cmd += 'design.assign_pkg_pin("{}[{}]","{}")\n'.format(name, i, pad)

            if 'out_reg' in block:
                cmd += 'design.set_property("{}","OUT_REG","{}")\n'.format(name, block['out_reg'])
                cmd += 'design.set_property("{}","OUT_CLK_PIN","{}")\n'.format(name, block['out_clk_pin'])

            if 'drive_strength' in block:
                cmd += 'design.set_property("{}","DRIVE_STRENGTH","4")\n'.format(name, block['drive_strength'])

            cmd += '\n'
            return cmd

        if mode == 'INPUT_CLK':
            cmd += 'design.create_input_clock_gpio("{}")\n'.format(name)
            cmd += 'design.set_property("{}","IN_PIN","{}")\n'.format(name, name)
            cmd += 'design.assign_pkg_pin("{}","{}")\n\n'.format(name, block['location'])
            return cmd

        if mode == 'OUTPUT_CLK':
            cmd += 'design.create_clockout_gpio("{}")\n'.format(name)
            cmd += 'design.set_property("{}","OUT_CLK_PIN","{}")\n'.format(name, name)
            cmd += 'design.assign_pkg_pin("{}","{}")\n\n'.format(name, block['location'])
            return cmd

        cmd = '# TODO: ' + str(block) +'\n'
        return cmd

    def generate_pll(self, block, partnumber, verbose=True):
        name = block['name']
        cmd = '# ---------- PLL {} ---------\n'.format(name)
        cmd += 'design.create_block("{}", block_type="PLL")\n'.format(name)
        cmd += 'pll_config = {{ "REFCLK_FREQ":"{}" }}\n'.format(block['input_freq'] / 1e6)
        cmd += 'design.set_property("{}", pll_config, block_type="PLL")\n\n'.format(name)

        if block['input_clock'] == 'EXTERNAL':
            # PLL V1 has a different configuration
            if partnumber[0:2] in ["T4", "T8"]:
                cmd += 'design.gen_pll_ref_clock("{}", pll_res="{}", refclk_res="{}", refclk_name="{}", ext_refclk_no="{}")\n\n' \
                    .format(name, block['resource'], block['input_clock_pad'], block['input_clock_name'], block['clock_no'])
            else:
                cmd += 'design.gen_pll_ref_clock("{}", pll_res="{}", refclk_src="{}", refclk_name="{}", ext_refclk_no="{}")\n\n' \
                    .format(name, block['resource'], block['input_clock'], block['input_clock_name'], block['clock_no'])
        else:
            cmd += 'design.gen_pll_ref_clock("{}", pll_res="{}", refclk_name="{}", refclk_src="CORE")\n'.format(name, block['resource'], block['input_signal'])
            cmd += 'design.set_property("{}", "CORE_CLK_PIN", "{}", block_type="PLL")\n\n'.format(name, block['input_signal'])

        cmd += 'design.set_property("{}","LOCKED_PIN","{}", block_type="PLL")\n'.format(name, block['locked'])
        if block['reset'] != '':
            cmd += 'design.set_property("{}","RSTN_PIN","{}", block_type="PLL")\n\n'.format(name, block['reset'])

         # Output clock 0 is enabled by default
        for i, clock in enumerate(block['clk_out']):
            if i > 0:
                cmd += 'pll_config = {{ "CLKOUT{}_EN":"1", "CLKOUT{}_PIN":"{}" }}\n'.format(i, i, clock[0])
            else:
                cmd += 'pll_config = {{ "CLKOUT{}_PIN":"{}" }}\n'.format(i, clock[0])

            cmd += 'design.set_property("{}", pll_config, block_type="PLL")\n\n'.format(name)

        for i, clock in enumerate(block['clk_out']):
            cmd += 'design.set_property("{}","CLKOUT{}_PHASE","{}","PLL")\n'.format(name, i, clock[2])

        cmd += 'target_freq = {\n'
        for i, clock in enumerate(block['clk_out']):
            cmd += '    "CLKOUT{}_FREQ": "{}",\n'.format(i, clock[1] / 1e6)
        cmd += '}\n'
        cmd += 'calc_result = design.auto_calc_pll_clock("{}", target_freq)\n'.format(name)

        if 'extra' in block:
            cmd += block['extra']
            cmd += '\n'

        if verbose:
            cmd += 'print("#### {} ####")\n'.format(name)
            cmd += 'clksrc_info = design.trace_ref_clock("{}", block_type="PLL")\n'.format(name)
            cmd += 'pprint.pprint(clksrc_info)\n'
            cmd += 'clock_source_prop = ["REFCLK_SOURCE", "CORE_CLK_PIN", "EXT_CLK", "CLKOUT1_EN", "CLKOUT2_EN","REFCLK_FREQ", "RESOURCE"]\n'
            cmd += 'clock_source_prop += ["CLKOUT0_FREQ", "CLKOUT1_FREQ", "CLKOUT2_FREQ"]\n'
            cmd += 'clock_source_prop += ["CLKOUT0_PHASE", "CLKOUT1_PHASE", "CLKOUT2_PHASE"]\n'
            cmd += 'prop_map = design.get_property("{}", clock_source_prop, block_type="PLL")\n'.format(name)
            cmd += 'pprint.pprint(prop_map)\n'

        cmd += '# ---------- END PLL {} ---------\n\n'.format(name)
        return cmd

    def generate(self, partnumber):
        output = ''
        for b in self.blocks:
            if b['type'] == 'PLL':
                output += self.generate_pll(b, partnumber)
            if b['type'] == 'GPIO':
                output += self.generate_gpio(b)

        return output

    def footer(self):
        return """
# Check design, generate constraints and reports
design.generate(enable_bitstream=True)
# Save the configured periphery design
design.save()"""

