#
# This file is part of LiteX.
#
# Copyright (c) 2022 Sebastien BOUCHE <sebastien.bouche@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

# python3 -m unittest test.test_packaging

import unittest

from migen import *


from litex.build import tools
from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform

from litex.soc.interconnect import stream
from litex.soc.interconnect.axi import *
from litex.soc.interconnect import csr_eventmanager as ev
from litex.soc.interconnect import wishbone

# GUI Interfaces -----------------------------------------------------------------------------------

def get_gui_interface():
    return {
        'AXI Lite' : 
            {
            'order': 0,
            'vars' : 
                {
                'address_width' : 
                    {
                    'order' : 0,
                    },
                },
            },
        'AXI Stream' :
            {
            'order': 1,
            'vars' : 
                {
                'input_width' : 
                    {
                    'order' : 0,
                    },
                'output_width' : 
                    {
                    'order' : 1,
                    },
                'user_width' : 
                    {
                    'order' : 2,
                    },
                },
            },
        'Misc' :
            {
            'order': 2,
            'vars' : 
                {
                'reverse' : 
                    {
                    'order' : 0,
                    },
                },
            },
    }

# Custom Interfaces -------------------------------------------------------------------------------

def get_custom_interface():
    return {
        'wishbone' : 
            {
            'name': 'wishbone_in',
            'type': 'slave',
            'signals' : 
                {
                    'wishbone_in_adr'   : 'wishbone_adr',
                    'wishbone_in_dat_w' : 'wishbone_dat_w',
                    'wishbone_in_dat_r' : 'wishbone_dat_r',
                    'wishbone_in_sel'   : 'wishbone_sel',
                    'wishbone_in_cyc'   : 'wishbone_cyc',
                    'wishbone_in_stb'   : 'wishbone_stb',
                    'wishbone_in_ack'   : 'wishbone_ack',
                    'wishbone_in_we'    : 'wishbone_we',
                    'wishbone_in_cti'   : 'wishbone_cti',
                    'wishbone_in_bte'   : 'wishbone_bte',
                    'wishbone_in_err'   : 'wishbone_err',
                },
            },
    }


def declare_custom_interface():
    return {
        'wishbone' : 
            {
            'signals' : 
                [
                    ("wishbone_adr","30","input"),
                    ("wishbone_dat_w","16","input"),
                    ("wishbone_dat_r","16","output"),
                    ("wishbone_sel","2","input"),
                    ("wishbone_cyc","1","input"),
                    ("wishbone_stb","1","input"),
                    ("wishbone_ack","1","output"),
                    ("wishbone_we","1","input"),
                    ("wishbone_cti","3","input"),
                    ("wishbone_bte","2","input"),
                    ("wishbone_err","1","output"),
                ],
            },
    }

# Interfaces Clock & resets ------------------------------------------------------------------------

def get_interface_clocks():
    return {
        'Wishbone' :
           {
            'clock_domain': 'axilite_clk',
            'reset': 'axilite_rst',
            'interfaces': 'wishbone_in',
            },
        'AXI Stream' :
            {
            'clock_domain': 'axis_clk',
            'reset': 'axis_rst',
            'interfaces': 'axis_in:axis_out',
            },
        'AXI Lite' : 
            {
            'clock_domain': 'axilite_clk',
            'reset': 'axilite_rst',
            'interfaces': 'axilite_in',
            },
    }

# IOs/Interfaces -----------------------------------------------------------------------------------

def get_clkin_ios():
    return [
        ("axis_clk",  0, Pins(1)),
        ("axis_rst",  0, Pins(1)),
        ("axilite_clk",  0, Pins(1)),
        ("axilite_rst",  0, Pins(1)),
        ("irq"    ,  0, Pins(1)),
    ]

# TestPackaging -------------------------------------------------------------------------------------

class TestPackaging(unittest.TestCase):
    def test_packaging(self):
        
        class AXIConverter(Module):
            def __init__(self, platform, address_width=64, input_width=64, output_width=64, user_width=0, reverse=False):
                # SAve input parameter as generic for later use.
                self.address_width = address_width
                self.input_width   = input_width
                self.output_width  = output_width
                self.user_width    = user_width
                self.reverse       = reverse
                # Clocking ---------------------------------------------------------------------------------
                platform.add_extension(get_clkin_ios())
                self.clock_domains.cd_sys  = ClockDomain()
                self.comb += self.cd_sys.clk.eq(platform.request("axis_clk"))
                self.comb += self.cd_sys.rst.eq(platform.request("axis_rst"))

                self.clock_domains.cd_syslite  = ClockDomain()
                self.comb += self.cd_syslite.clk.eq(platform.request("axilite_clk"))
                self.comb += self.cd_syslite.rst.eq(platform.request("axilite_rst"))

                # Input AXI Lite ---------------------------------------------------------------------------
                axilite_in = AXILiteInterface(data_width=32, address_width=address_width, clock_domain="cd_syslite")
                platform.add_extension(axilite_in.get_ios("axilite_in"))
                self.comb += axilite_in.connect_to_pads(platform.request("axilite_in"), mode="slave")

                # Input AXI --------------------------------------------------------------------------------
                axis_in = AXIStreamInterface(data_width=input_width, user_width=user_width)
                platform.add_extension(axis_in.get_ios("axis_in"))
                self.comb += axis_in.connect_to_pads(platform.request("axis_in"), mode="slave")

                # Output AXI -------------------------------------------------------------------------------
                axis_out = AXIStreamInterface(data_width=output_width, user_width=user_width)
                platform.add_extension(axis_out.get_ios("axis_out"))
                self.comb += axis_out.connect_to_pads(platform.request("axis_out"), mode="master")

                # Custom interface -----------------------------------------------------------------------
                wishbone_in = wishbone.Interface(data_width=16)
                platform.add_extension(wishbone_in.get_ios("wishbone_in"))
                self.comb += wishbone_in.connect_to_pads(platform.request("wishbone_in"), mode="slave")

                self.submodules.ev = ev.EventManager()
                self.ev.my_int1 = ev.EventSourceProcess()
                self.ev.my_int2 = ev.EventSourceProcess()
                self.ev.finalize()

                self.comb += self.ev.my_int1.trigger.eq(0)
                self.comb += self.ev.my_int2.trigger.eq(1)

                self.comb += platform.request("irq").eq(self.ev.irq)

                # Converter --------------------------------------------------------------------------------
                converter = stream.StrideConverter(axis_in.description, axis_out.description, reverse=reverse)
                self.submodules += converter
                self.comb += axis_in.connect(converter.sink)
                self.comb += converter.source.connect(axis_out)


        get_generic_parameters = [
            ("address_width",  64),
            ("input_width"  ,  128),
            ("output_width" , 64),
            ("user_width"   , 0),
            ("reverse"      ,  True),
        ]

        input_width  = 128
        output_width = 64
        user_width   = 0
        build_name   = "axi_converter_{}b_to_{}b".format(input_width, output_width)
        platform     = XilinxPlatform("", io=[], toolchain="vivado")
        module       = AXIConverter(platform,
            input_width  = input_width,
            output_width = output_width,
            user_width   = user_width,
            reverse      = True)
        
        platform.build(module, build_name=build_name, run=False)
        
        file_list = ["../build/"+build_name+".xdc", "../build/"+build_name+".v"]
        platform.packaging.version_number = "1.3"
        # exit()
        platform.package(build_name=build_name, file_list=file_list, 
            clock_domain=get_interface_clocks(),
            generic_parameters=get_generic_parameters,
            gui_description=get_gui_interface(),
            custom_interface=get_custom_interface(),
            declare_interface=declare_custom_interface(),
            interrupt = "irq",
            run=True)
 