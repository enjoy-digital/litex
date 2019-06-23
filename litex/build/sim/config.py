# This file is Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# This file is Copyright (c) 2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import json

class SimConfig():
    def __init__(self, default_clk=None):
        self.modules = []
        self.default_clk = default_clk
        if default_clk:
            self.add_clocker(default_clk)

    def _format_interfaces(self, interfaces):
        if not isinstance(interfaces, list):
            interfaces = [interfaces]
        new = []
        for it in interfaces:
            obj = it
            if isinstance(it, tuple):
                name, index = it
                obj = {"name": name, "index": index}
            new.append(obj)
        return new

    def add_clocker(self, clk):
        self.add_module("clocker", [], clocks=clk, tickfirst=True)

    def add_module(self, name, interfaces, clocks=None, args=None, tickfirst=False):
        interfaces = self._format_interfaces(interfaces)
        if clocks:
            interfaces += self._format_interfaces(clocks)
        else:
            interfaces += [self.default_clk]
        newmod = {
            "module": name,
            "interface": interfaces,
        }
        if args:
            newmod.update({"args": args})
        if tickfirst:
            newmod.update({"tickfirst": tickfirst})
        self.modules.append(newmod)

    def has_module(self, name):
        for module in self.modules:
            if module["module"] == name:
                return True
        return False

    def get_json(self):
        return json.dumps(self.modules, indent=4)
