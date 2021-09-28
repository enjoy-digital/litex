import os
import csv
import re

import xml.etree.ElementTree as et

namespaces = { 'efxpt' : 'http://www.efinixinc.com/peri_device_db',
               'xi'    : 'http://www.w3.org/2001/XInclude'
}

class EfinixDbParser():
    def __init__(self, efinity_path, device):
        self.efinity_db_path = efinity_path + '/pt/db/'
        self.device = device

    def get_device_map(self, device):
        with open(self.efinity_db_path + 'devicemap.csv') as f:
            reader = csv.reader(f)
            data = list(reader)

        for d in data:
            if d[0] == device:
                return d

        return None

    def get_package_file_name(self, dmap):
        tree = et.parse(self.efinity_db_path + dmap[2])
        root = tree.getroot()
        inc = root.findall('xi:include', namespaces)
        for i in inc:
            if 'package' in i.get('href'):
                return i.get('href').split('/')[1]

        return None

    def get_die_file_name(self, dmap):
        tree = et.parse(self.efinity_db_path + dmap[2])
        root = tree.getroot()
        inc = root.findall('xi:include', namespaces)
        for i in inc:
            if 'die' in i.get('href'):
                return i.get('href').split('/')[1]

        return None

    def get_pad_name_xml(self, dmap, pin):
        package_file = self.get_package_file_name(dmap)
        tree = et.parse(self.efinity_db_path + 'package/' + package_file)
        root = tree.getroot()

        pm = root.findall('efxpt:package_map', namespaces)
        for p in pm:
            if p.get('package_pin') == pin:
                return (p.get('pad_name'))

        return None

    def get_instance_name_xml(self, dmap, pad):
        die = self.get_die_file_name(dmap)
        tree = et.parse(self.efinity_db_path + 'die/' + die)
        root = tree.getroot()

        ipd = root.find('efxpt:io_pad_definition', namespaces)
        ios = ipd.findall('efxpt:io_pad_map', namespaces)
        for io in ios:
            if io.get('pad_name') == pad:
                    return (io.get('instance'))

        return None

    def get_pll_inst_from_gpio_inst(self, dmap, inst):
        die = self.get_die_file_name(dmap)
        tree = et.parse(self.efinity_db_path + 'die/' + die)
        root = tree.getroot()

        peri = root.findall('efxpt:periphery_instance', namespaces)
        for p in peri:
            if p.get('block') == 'pll':
                conn = p.findall('efxpt:single_conn', namespaces)
                for c in conn:
                    if c.get('instance') == inst:
                        refclk_no = 0
                        if c.get('index') == '3':
                            refclk_no = 1
                        return (p.get('name'), refclk_no)

        return None

    def get_pll_inst_from_pin(self, pin):
        dmap = self.get_device_map(self.device)
        pad = self.get_pad_name_xml(dmap, pin)
        inst = self.get_instance_name_xml(dmap, pad)

        return self.get_pll_inst_from_gpio_inst(dmap, inst)

    def get_gpio_instance_from_pin(self, pin):
        dmap = self.get_device_map(self.device)
        return self.get_pad_name_xml(dmap, pin)
