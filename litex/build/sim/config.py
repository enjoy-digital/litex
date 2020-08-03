# This file is Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# This file is Copyright (c) 2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import json
import math

class SimConfig():
    def __init__(self, timebase_ps=None):
        self.modules = []
        self.timebase_ps = timebase_ps

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

    def _format_timebase(self):
        timebase_ps = self.timebase_ps
        if timebase_ps is None:
            timebase_ps = self._get_timebase_ps()
        return {"timebase": int(timebase_ps)}

    def _get_timebase_ps(self):
        clockers = [m for m in self.modules if m["module"] == "clocker"]
        periods_ps = [1e12 / m["args"]["freq_hz"] for m in clockers]
        # timebase is half of the shortest period
        for p in periods_ps:
            assert round(p/2) == int(p//2), "Period cannot be represented: {}".format(p)
        half_period = [int(p//2) for p in periods_ps]
        # find greatest common denominator
        gcd = half_period[0]
        for p in half_period[1:]:
            gcd = math.gcd(gcd, p)
        assert gcd >= 1
        return gcd

    def add_clocker(self, clk, freq_hz, phase_deg=0):
        args = {"freq_hz": freq_hz, "phase_deg": phase_deg}
        self.add_module("clocker", [], clocks=clk, tickfirst=True, args=args)

    def add_module(self, name, interfaces, clocks="sys_clk", args=None, tickfirst=False):
        interfaces = self._format_interfaces(interfaces)
        interfaces += self._format_interfaces(clocks)
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
        assert "clocker" in (m["module"] for m in self.modules), \
            "No simulation clocker found! Use sim_config.add_clocker() to define one or more clockers."
        config = self.modules + [self._format_timebase()]
        return json.dumps(config, indent=4)
