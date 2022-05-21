#
# This file is part of LiteX.
#
# Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Yann Sionneau <ys@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import os
import re

from migen.fhdl.structure import Signal, Cat
from migen.genlib.record import Record

from litex.gen.fhdl import verilog

from litex.build.io import CRG
from litex.build import tools

# --------------------------------------------------------------------------------------------------

class ConstraintError(Exception):
    pass


# IOS ----------------------------------------------------------------------------------------------

class Pins:
    def __init__(self, *identifiers):
        self.identifiers = []
        for i in identifiers:
            if isinstance(i, int):
                self.identifiers += ["X"]*i
            else:
                self.identifiers += i.split()

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, " ".join(self.identifiers))


class IOStandard:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.name)


class Drive:
    def __init__(self, strength):
        self.strength = strength

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.strength)


class Misc:
    def __init__(self, misc):
        self.misc = misc

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self.misc))


class Inverted:
    def __repr__(self):
        return "{}()".format(self.__class__.__name__)



class Subsignal:
    def __init__(self, name, *constraints):
        self.name        = name
        self.constraints = list(constraints)

    def __repr__(self):
        return "{}('{}', {})".format(self.__class__.__name__,
            self.name,
            ", ".join([repr(constr) for constr in self.constraints]))

# Platform -----------------------------------------------------------------------------------------

class PlatformInfo:
    def __init__(self, info):
        self.info = info

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self.info))


def _lookup(description, name, number, loose=True):
    for resource in description:
        if resource[0] == name and (number is None or resource[1] == number):
            return resource
    if loose:
        return None
    else:
        raise ConstraintError("Resource not found: {}:{}".format(name, number))


def _resource_type(resource):
    t = None
    i = None
    for element in resource[2:]:
        if isinstance(element, Pins):
            assert(t is None)
            t = len(element.identifiers)
        elif isinstance(element, Subsignal):
            if t is None:
                t = []
            if i is None:
                i = []

            assert(isinstance(t, list))
            n_bits   = None
            inverted = False
            for c in element.constraints:
                if isinstance(c, Pins):
                    assert(n_bits is None)
                    n_bits = len(c.identifiers)
                if isinstance(c, Inverted):
                    inverted = True

            t.append((element.name, n_bits))
            i.append((element.name, inverted))

    return t, i

# Connector Manager --------------------------------------------------------------------------------

class ConnectorManager:
    def __init__(self, connectors):
        self.connector_table = dict()
        for connector in connectors:
            cit       = iter(connector)
            conn_name = next(cit)
            if isinstance(connector[1], str):
                pin_list = []
                for pins in cit:
                    pin_list += pins.split()
                pin_list = [None if pin == "None" else pin for pin in pin_list]
            elif isinstance(connector[1], dict):
                pin_list = connector[1]
            else:
                raise ValueError("Unsupported pin list type {} for connector"
                                 " {}".format(type(connector[1]), conn_name))
            if conn_name in self.connector_table:
                raise ValueError(
                    "Connector specified more than once: {}".format(conn_name))

            self.connector_table[conn_name] = pin_list

    def resolve_identifiers(self, identifiers):
        r = []
        for identifier in identifiers:
            if ":" in identifier:
                try:
                    conn, pn = identifier.split(":")
                except ValueError as err:
                    raise ValueError(f"\"{identifier}\" {err}") from err
                if pn.isdigit():
                    pn = int(pn)

                r.append(self.connector_table[conn][pn])
            else:
                r.append(identifier)

        return r


def _separate_pins(constraints):
    pins   = None
    others = []
    for c in constraints:
        if isinstance(c, Pins):
            assert(pins is None)
            pins = c.identifiers
        else:
            others.append(c)

    return pins, others

# Constraint Manager -------------------------------------------------------------------------------

class ConstraintManager:
    def __init__(self, io, connectors):
        self.available         = list(io)
        self.matched           = []
        self.platform_commands = []
        self.connector_manager = ConnectorManager(connectors)

    def add_extension(self, io):
        self.available.extend(io)

    def request(self, name, number=None, loose=False):
        resource = _lookup(self.available, name, number, loose)
        if resource is None:
            return None
        rt, ri = _resource_type(resource)
        if number is None:
            resource_name = name
        else:
            resource_name = name + str(number)
        if isinstance(rt, int):
            obj = Signal(rt, name_override=resource_name)
        else:
            obj = Record(rt, name=resource_name)
            for name, inverted in ri:
                if inverted:
                    getattr(obj, name).inverted = True

        for element in resource[2:]:
            if isinstance(element, Inverted):
                if isinstance(obj, Signal):
                    obj.inverted = True
            if isinstance(element, PlatformInfo):
                obj.platform_info = element.info
                break

        self.available.remove(resource)
        self.matched.append((resource, obj))
        return obj

    def request_all(self, name):
        r = []
        while True:
            try:
                r.append(self.request(name, len(r)))
            except ConstraintError:
                break
        if not len(r):
            raise ValueError(f"Could not request some pin(s) named '{name}'")
        return Cat(r)

    def request_remaining(self, name):
        r = []
        while True:
            try:
                r.append(self.request(name))
            except ConstraintError:
                break
        if not len(r):
            raise ValueError(f"Could not request any pins named '{name}'")
        return Cat(r)

    def lookup_request(self, name, number=None, loose=False):
        subname = None
        if ":" in name: name, subname = name.split(":")
        for resource, obj in self.matched:
            if resource[0] == name and (number is None or
                                        resource[1] == number):
                if subname is not None:
                    return getattr(obj, subname)
                else:
                    return obj

        if loose:
            return None
        else:
            raise ConstraintError("Resource not found: {}:{}".format(name, number))

    def add_platform_command(self, command, **signals):
        self.platform_commands.append((command, signals))

    def get_io_signals(self):
        r = set()
        for resource, obj in self.matched:
            if isinstance(obj, Signal):
                r.add(obj)
            else:
                r.update(obj.flatten())

        return r

    def get_sig_constraints(self):
        r = []
        for resource, obj in self.matched:
            name            = resource[0]
            number          = resource[1]
            has_subsignals  = False
            top_constraints = []
            for element in resource[2:]:
                if isinstance(element, Subsignal):
                    has_subsignals = True
                else:
                    top_constraints.append(element)

            if has_subsignals:
                for element in resource[2:]:
                    if isinstance(element, Subsignal):
                        # Because we could have removed one Signal From the record
                        if hasattr(obj, element.name):
                            sig = getattr(obj, element.name)
                            pins, others = _separate_pins(top_constraints +
                                                        element.constraints)
                            pins = self.connector_manager.resolve_identifiers(pins)
                            r.append((sig, pins, others,
                                    (name, number, element.name)))
            else:
                pins, others = _separate_pins(top_constraints)
                pins = self.connector_manager.resolve_identifiers(pins)
                r.append((obj, pins, others, (name, number, None)))

        return r

    def get_platform_commands(self):
        return self.platform_commands

# Generic Platform ---------------------------------------------------------------------------------

class GenericPlatform:
    def __init__(self, device, io, connectors=[], name=None):
        self.device             = device
        self.constraint_manager = ConstraintManager(io, connectors)
        if name is None:
            # Get name from Platform file.
            name = self.__module__.split(".")[-1]
        if name == "__main__":
            # If no Platform file, use script filename,
            name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        self.name                  = name
        self.sources               = []
        self.verilog_include_paths = []
        self.output_dir            = None
        self.finalized             = False
        self.use_default_clk       = False

    def request(self, *args, **kwargs):
        return self.constraint_manager.request(*args, **kwargs)

    def request_all(self, *args, **kwargs):
        return self.constraint_manager.request_all(*args, **kwargs)

    def request_remaining(self, *args, **kwargs):
        return self.constraint_manager.request_remaining(*args, **kwargs)

    def lookup_request(self, *args, **kwargs):
        return self.constraint_manager.lookup_request(*args, **kwargs)

    def add_period_constraint(self, clk, period):
        raise NotImplementedError

    def add_false_path_constraint(self, from_, to):
        raise NotImplementedError

    def add_false_path_constraints(self, *clk):
        for a in clk:
            for b in clk:
                if a is not b:
                    self.add_false_path_constraint(a, b)

    def add_platform_command(self, *args, **kwargs):
        return self.constraint_manager.add_platform_command(*args, **kwargs)

    def add_extension(self, *args, **kwargs):
        return self.constraint_manager.add_extension(*args, **kwargs)

    def finalize(self, fragment, *args, **kwargs):
        if self.finalized:
            raise ConstraintError("Already finalized")
        # If none exists, create a default clock domain and drive it.
        if not fragment.clock_domains:
            if not hasattr(self, "default_clk_name"):
                raise NotImplementedError(
                    "No default clock and no clock domain defined")
            crg = CRG(self.request(self.default_clk_name))
            fragment += crg.get_fragment()
            self.use_default_clk = True

        self.do_finalize(fragment, *args, **kwargs)
        self.finalized = True

    def do_finalize(self, fragment, *args, **kwargs):
        # Overload this and e.g. add_platform_command()'s after the modules had their say.
        if self.use_default_clk and hasattr(self, "default_clk_period"):
            try:
                self.add_period_constraint(
                    self.lookup_request(self.default_clk_name),
                    self.default_clk_period)
            except ConstraintError:
                pass

    def add_source(self, filename, language=None, library=None, copy=False):
        filename = os.path.abspath(filename)
        if language is None:
            language = tools.language_by_filename(filename)
        if library is None:
            library = "work"
        for f, *_ in self.sources:
            if f == filename:
                return
        if copy:
            self.sources.append((filename, language, library, True))
        else:
            self.sources.append((filename, language, library))

    def add_sources(self, path, *filenames, language=None, library=None, copy=False):
        for f in filenames:
            self.add_source(os.path.join(path, f), language, library, copy)

    def add_source_dir(self, path, recursive=True, language=None, library=None):
        dir_files = []
        if recursive:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    dir_files.append(os.path.join(root, filename))
        else:
            for item in os.listdir(path):
                if os.path.isfile(os.path.join(path, item)):
                    dir_files.append(os.path.join(path, item))
        for filename in dir_files:
            _language = language
            if _language is None:
                _language = tools.language_by_filename(filename)
            if _language is not None:
                self.add_source(filename, _language, library)

    def add_verilog_include_path(self, path):
        self.verilog_include_paths.append(os.path.abspath(path))

    def resolve_signals(self, vns):
        # Resolve signal names in constraints.
        sc = self.constraint_manager.get_sig_constraints()
        named_sc = [(vns.get_name(sig), pins, others, resource)
                    for sig, pins, others, resource in sc]
        # Resolve signal names in platform commands.
        pc = self.constraint_manager.get_platform_commands()
        named_pc = []
        for template, args in pc:
            name_dict = dict((k, vns.get_name(sig)) for k, sig in args.items())
            named_pc.append(template.format(**name_dict))

        return named_sc, named_pc

    def get_verilog(self, fragment, **kwargs):
        return verilog.convert(fragment, platform=self, **kwargs)

    def get_edif(self, fragment, cell_library, vendor, device, **kwargs):
        return edif.convert(
            fragment,
            self.constraint_manager.get_io_signals(),
            cell_library, vendor, device, **kwargs)

    def build(self, fragment):
        raise NotImplementedError("GenericPlatform.build must be overloaded")

    def create_programmer(self):
        raise NotImplementedError
