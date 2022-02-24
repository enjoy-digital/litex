#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import csv
import re

import xml.etree.ElementTree as et

# NameSpaces ---------------------------------------------------------------------------------------

namespaces = {
    'efxpt' : "http://www.efinixinc.com/peri_device_db",
    'xi'    : "http://www.w3.org/2001/XInclude"
}

# Efinix Database Parser ---------------------------------------------------------------------------

class EfinixDbParser:
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

    def get_block_instance_names(self, block):
        dmap = self.get_device_map(self.device)
        die = self.get_die_file_name(dmap)
        tree = et.parse(self.efinity_db_path + 'die/' + die)
        root = tree.getroot()

        peri = root.findall('efxpt:periphery_instance', namespaces)
        names = []
        for p in peri:
            if p.get('block') == block:
                names.append(p.get('name'))

        print(f"block {block}: names:{names}")
        return names

    def get_pll_inst_from_gpio_inst(self, dmap, inst):
        die = self.get_die_file_name(dmap)
        tree = et.parse(self.efinity_db_path + 'die/' + die)
        root = tree.getroot()

        peri = root.findall('efxpt:periphery_instance', namespaces)
        for p in peri:
            # T20/T120 have instance attribute in single_conn
            # not true for T4/T8 -> search in dependency subnode
            if p.get('block') == 'pll':
                if self.device[0:2] not in ['T4', 'T8']:
                    conn = p.findall('efxpt:single_conn', namespaces)
                    for c in conn:
                        i = c.get('instance')
                        if i == None:
                            continue
                        if (i == inst) or (inst + '.' in i):
                            refclk_no = 0
                            if c.get('index') == '3':
                                refclk_no = 1
                            return (p.get('name'), refclk_no)
                else:
                    deps = p.findall('efxpt:dependency', namespaces)[0]
                    for c in deps.findall('efxpt:instance_dep', namespaces):
                        if c.get('name') == inst:
                            return (p.get('name'), 3) # always 3 ?

        return None

    def get_gpio_instance_from_pin(self, pin):
        dmap = self.get_device_map(self.device)
        pad = self.get_pad_name_xml(dmap, pin)
        return self.get_instance_name_xml(dmap, pad)

    def get_pll_inst_from_pin(self, pin):
        dmap = self.get_device_map(self.device)
        inst = self.get_gpio_instance_from_pin(pin)

        return self.get_pll_inst_from_gpio_inst(dmap, inst)

    def get_pad_name_from_pin(self, pin):
        dmap = self.get_device_map(self.device)
        return self.get_pad_name_xml(dmap, pin)
