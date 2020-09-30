#
# This file is part of LiteX.
#
# Copyright (c) 2020 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import DUID
from migen.util.misc import xdir

from litex.soc.interconnect.csr_eventmanager import EventManager
from litex.soc.integration.doc import ModuleDoc

import textwrap

from .rst import print_table, print_rst

def gather_submodules_inner(module, depth, seen_modules, submodules):
    if module is None:
        return submodules
    if depth == 0:
        if isinstance(module, ModuleDoc):
            # print("{} is an instance of ModuleDoc".format(module))
            submodules["module_doc"].append(module)
    for k,v in module._submodules:
        # print("{}Submodule {} {}".format(" "*(depth*4), k, v))
        if v not in seen_modules:
            seen_modules.add(v)
            if isinstance(v, EventManager):
                # print("{}{} appears to be an EventManager".format(" "*(depth*4), k))
                submodules["event_managers"].append(v)

            if isinstance(v, ModuleDoc):
                submodules["module_doc"].append(v)

            gather_submodules_inner(v, depth + 1, seen_modules, submodules)
    return submodules

def gather_submodules(module):
    depth        = 0
    seen_modules = set()
    submodules   = {
        "event_managers": [],
        "module_doc": [],
    }

    return gather_submodules_inner(module, depth, seen_modules, submodules)

class ModuleNotDocumented(Exception):
    """Indicates a Module has no documentation or sub-documentation"""
    pass

class DocumentedModule:
    """Multi-section Documentation of a Module"""

    def __init__(self, name, module, has_documentation=False):
        self.name     = name
        self.sections = []

        if isinstance(module, ModuleDoc):
            has_documentation = True
            self.sections.append(module)

        if hasattr(module, "get_module_documentation"):
            for doc in module.get_module_documentation():
                has_documentation = True
                self.sections.append(doc)

        if not has_documentation:
            raise ModuleNotDocumented()

    def print_region(self, stream, base_dir, note_pulses=False):
        title = "{}".format(self.name.upper())
        print(title, file=stream)
        print("=" * len(title), file=stream)
        print("", file=stream)

        for section in self.sections:
            title = textwrap.dedent(section.title())
            body = textwrap.dedent(section.body())
            print("{}".format(title), file=stream)
            print("-" * len(title), file=stream)
            print(textwrap.dedent(body), file=stream)
            print("", file=stream)

class DocumentedInterrupts(DocumentedModule):
    """A :obj:`DocumentedModule` that automatically documents interrupts in an SoC

    This creates a :obj:`DocumentedModule` object that prints out the contents
    of the interrupt map of an SoC.
    """
    def __init__(self, interrupts):
        DocumentedModule.__init__(self, "interrupts", None, has_documentation=True)

        self.irq_table = [["Interrupt", "Module"]]
        for module_name, irq_no in interrupts.items():
            self.irq_table.append([str(irq_no), ":doc:`{} <{}>`".format(module_name.upper(), module_name)])

    def print_region(self, stream, base_dir, note_pulses=False):
        title = "Interrupt Controller"
        print(title, file=stream)
        print("=" * len(title), file=stream)
        print("", file=stream)

        print_rst(stream,
        """
        This device has an ``EventManager``-based interrupt
        system.  Individual modules generate `events` which are wired
        into a central interrupt controller.

        When an interrupt occurs, you should look the interrupt number up
        in the CPU-specific interrupt table and then call the relevant
        module.
        """)

        section_title = "Assigned Interrupts"
        print("{}".format(section_title), file=stream)
        print("-" * len(section_title), file=stream)
        print("", file=stream)

        print("The following interrupts are assigned on this system:", file=stream)
        print_table(self.irq_table, stream)


