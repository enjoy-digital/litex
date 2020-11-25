#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import csv

# CSR Elements -------------------------------------------------------------------------------------

class CSRElements:
    def __init__(self, d):
        self.__dict__.update(d)

    @property
    def d(self):
        return self.__dict__

    def __getattr__(self, attr):
        try:
            return self.__dict__[attr]
        except KeyError:
            pass
        raise AttributeError("No such element " + attr)

class CSRRegister:
    def __init__(self, readfn, writefn, name, addr, length, data_width, mode):
        self.readfn     = readfn
        self.writefn    = writefn
        self.name       = name
        self.addr       = addr
        self.length     = length
        self.data_width = data_width
        self.mode       = mode

    def read(self):
        if self.mode not in ["rw", "ro"]:
            raise KeyError(self.name + "register not readable")
        datas = self.readfn(self.addr, length=self.length)
        if isinstance(datas, int):
            return datas
        else:
            data = 0
            for i in range(self.length):
                data = data << self.data_width
                data |= datas[i]
            return data

    def write(self, value):
        if self.mode not in ["rw", "wo"]:
            raise KeyError(self.name + "register not writable")
        datas = []
        for i in range(self.length):
            datas.append((value >> ((self.length-1-i)*self.data_width)) & (2**self.data_width-1))
        self.writefn(self.addr, datas)

class CSRMemoryRegion:
    def __init__(self, base, size, type):
        self.base = base
        self.size = size
        self.type = type

# CSR Builder --------------------------------------------------------------------------------------

class CSRBuilder:
    def __init__(self, comm, csr_csv, csr_data_width=None):
        if csr_csv is not None:
            self.items     = self.get_csr_items(csr_csv)
            self.constants = self.build_constants()

            # Load csr_data_width from the constants, otherwise it must be provided
            constant_csr_data_width = self.constants.d.get("config_csr_data_width", None)
            if csr_data_width is None:
                csr_data_width = constant_csr_data_width
            if csr_data_width is None:
                raise KeyError("csr_data_width not found in constants, please provide!")
            if csr_data_width != constant_csr_data_width:
                raise KeyError("csr_data_width of {} provided but {} found in constants".format(
                    csr_data_width, constant_csr_data_width))

            self.csr_data_width = csr_data_width
            self.bases = self.build_bases()
            self.regs  = self.build_registers(comm.read, comm.write)
            self.mems  = self.build_memories()

    @staticmethod
    def get_csr_items(csr_csv):
        return list(csv.reader(filter(lambda row: row[0] != "#", open(csr_csv))))

    def build_bases(self):
        d = {}
        for item in self.items:
            group, name, addr, dummy0, dummy1 = item
            if group == "csr_base":
                d[name] = int(addr.replace("0x", ""), 16)
        return CSRElements(d)

    def build_registers(self, readfn, writefn):
        d = {}
        for item in self.items:
            group, name, addr, length, mode = item
            if group == "csr_register":
                addr = int(addr.replace("0x", ""), 16)
                length = int(length)
                d[name] = CSRRegister(readfn, writefn, name, addr, length, self.csr_data_width, mode)
        return CSRElements(d)

    def build_constants(self):
        d = {}
        for item in self.items:
            group, name, value, dummy0, dummy1 = item
            if group == "constant":
                try:
                    d[name] = int(value)
                except:
                    d[name] = value
        return CSRElements(d)

    def build_memories(self):
        d = {}
        for item in self.items:
            group, name, base, size, type = item
            if group == "memory_region":
                d[name] = CSRMemoryRegion(int(base, 16), int(size), type)
        return CSRElements(d)
