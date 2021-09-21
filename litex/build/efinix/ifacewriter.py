import os
import csv
import re
import datetime

from xml.dom import expatbuilder
import xml.etree.ElementTree as et

from litex.build import tools

namespaces = { 'efxpt' : 'http://www.efinixinc.com/peri_design_db',
               'xi'    : 'http://www.w3.org/2001/XInclude'
}

class InterfaceWriter():
    def __init__(self, efinity_path):
        self.efinity_path = efinity_path
        self.blocks = []

    def add_ddr_xml(self, filename):
        et.register_namespace('efxpt', "http://www.efinixinc.com/peri_design_db")
        tree = et.parse(filename + '.peri.xml')
        root = tree.getroot()
        ddr_info = root.find('efxpt:ddr_info', namespaces)

        et.SubElement(ddr_info, 'efxpt:ddr',
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
                        ctrl_type       = 'none')

        axi_suffix = ''     # '_1' for second port
        type_suffix = '_0'  # '_1' for second port

        gen_pin_target0 = et.SubElement(ddr_info, 'efxpt:gen_pin_target0')
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

        et.SubElement(gen_pin_target0, 'efxpt:pin', name='axi_clk',  type_name='ACLK_0',   is_bus = 'false', is_clk = 'true', is_clk_invert = 'false')

        gen_pin_config = et.SubElement(ddr_info, 'efxpt:gen_pin_config')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SEQ_RST',   is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SCL_IN',    is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SEQ_START', is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='RSTN',          is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SDA_IN',    is_bus = 'false')
        et.SubElement(gen_pin_config, 'efxpt:pin', name='', type_name='CFG_SDA_OEN',   is_bus = 'false')

        cs_fpga = et.SubElement(ddr_info, 'efxpt:cs_fpga')
        et.SubElement(cs_fpga, 'efxpt:param', name='FPGA_ITERM', value='120', value_type = 'str')
        et.SubElement(cs_fpga, 'efxpt:param', name='FPGA_OTERM', value='34',  value_type = 'str')

        cs_memory = et.SubElement(ddr_info, 'efxpt:cs_memory')
        et.SubElement(cs_memory, 'efxpt:param', name='RTT_NOM',   value='RZQ/2',     value_type = 'str')
        et.SubElement(cs_memory, 'efxpt:param', name='MEM_OTERM', value='40',        value_type = 'str')
        et.SubElement(cs_memory, 'efxpt:param', name='CL',        value='RL=6/WL=3', value_type = 'str')

        timing = et.SubElement(ddr_info, 'efxpt:cs_memory_timing')
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

        cs_control = et.SubElement(ddr_info, 'efxpt:cs_control')
        et.SubElement(cs_control, 'efxpt:param', name='AMAP',             value= 'ROW-COL_HIGH-BANK-COL_LOW', value_type='str')
        et.SubElement(cs_control, 'efxpt:param', name='EN_AUTO_PWR_DN',   value= 'Off',                       value_type='str')
        et.SubElement(cs_control, 'efxpt:param', name='EN_AUTO_SELF_REF', value= 'No',                        value_type='str')

        cs_gate_delay = et.SubElement(ddr_info, 'efxpt:cs_gate_delay')
        et.SubElement(cs_control, 'efxpt:param', name='EN_DLY_OVR', value= 'No', value_type='str')
        et.SubElement(cs_control, 'efxpt:param', name='GATE_C_DLY', value= '3',  value_type='str')
        et.SubElement(cs_control, 'efxpt:param', name='GATE_F_DLY', value= '0',  value_type='str')

        xml_string = et.tostring(root, 'utf-8')
        reparsed = expatbuilder.parseString(xml_string, False)
        print_string = reparsed.toprettyxml(indent="  ")

        # Remove lines with only whitespaces. Not sure why they are here
        print_string = os.linesep.join([s for s in print_string.splitlines() if s.strip()])

        tools.write_to_file("{}.peri.xml".format(filename), print_string)

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

design.create('{2}', '{3}', './../build', overwrite=True)

"""
        return header.format(self.efinity_path, 'True', build_name, partnumber)

    def get_block(self, name):
        for b in self.blocks:
            if b['name'] == name:
                return b
        return None

    def generate_pll(self, block, verbose=True):
        name = block['name']
        cmd = '# ---------- PLL {} ---------\n'.format(name)
        cmd += 'design.create_block("{}", block_type="PLL")\n'.format(name)
        cmd += 'design.gen_pll_ref_clock("{}", pll_res="{}", refclk_src="{}", refclk_name="{}", ext_refclk_no="{}")\n\n' \
               .format(name, block['resource'], block['input_clock'], block['input_clock_name'], block['clock_no'])

        cmd += 'pll_config = {{ "REFCLK_FREQ":"{}" }}\n'.format(block['input_freq'] / 1e6)
        cmd += 'design.set_property("{}", pll_config, block_type="PLL")\n\n'.format(name)

        cmd += 'design.set_property("{}","LOCKED_PIN","{}", block_type="PLL")\n'.format(name, block['locked'])
        if block['reset'] != '':
            cmd += 'design.set_property("{}","RSTN_PIN","{}", block_type="PLL")\n\n'.format(name, block['reset'])

         # Output clock 0 is enabled by default
        for i, clock in enumerate(block['clk_out']):
            if i > 0:
                cmd += 'pll_config = {{ "CLKOUT{}_EN":"1", "CLKOUT{}_PIN":"{}" }}\n'.format(i, i, clock[0])
                cmd += 'design.set_property("{}", pll_config, block_type="PLL")\n\n'.format(name)

        cmd += 'target_freq = {\n'
        for i, clock in enumerate(block['clk_out']):
            cmd += '    "CLKOUT{}_FREQ": "{}",\n'.format(i, clock[1] / 1e6)
            cmd += '    "CLKOUT{}_PHASE": "{}",\n'.format(i, clock[2])
        cmd += '}\n'
        cmd += 'calc_result = design.auto_calc_pll_clock("{}", target_freq)\n\n'.format(name)


        if verbose:
            cmd += 'print("#### {} ####")\n'.format(name)
            cmd += 'clksrc_info = design.trace_ref_clock("{}", block_type="PLL")\n'.format(name)
            cmd += 'pprint.pprint(clksrc_info)\n'
            cmd += 'clock_source_prop = ["REFCLK_SOURCE", "EXT_CLK", "CLKOUT0_EN", "CLKOUT1_EN","REFCLK_FREQ", "RESOURCE"]\n'
            cmd += 'clock_source_prop += ["M", "N", "O", "CLKOUT0_DIV", "CLKOUT2_DIV", "VCO_FREQ", "PLL_FREQ"]\n'
            cmd += 'prop_map = design.get_property("{}", clock_source_prop, block_type="PLL")\n'.format(name)
            cmd += 'pprint.pprint(prop_map)\n'

        cmd += '# ---------- END PLL {} ---------\n\n'.format(name)
        return cmd

    def generate(self):
        output = ''
        for b in self.blocks:
            if b['type'] == 'PLL':
                output += self.generate_pll(b)
        return output

    def footer(self):
        return """
# Check design, generate constraints and reports
#design.generate(enable_bitstream=True)
# Save the configured periphery design
design.save()"""

