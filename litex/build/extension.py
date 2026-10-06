#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Composable board extensions.

An Extension describes hardware plugged on one or more connectors ("slots") of a host board: a Pmod
module, a daughterboard, a carrier/baseboard for a SoM, etc. It is described once, independently of
the host, and bound to the host's connector names when instantiated:

    platform.add_extension(PmodSDCard("pmodd"))           # Pmod module on Arty's JD.
    platform.add_extension(PmodDVI(a="PMOD1A", b="PMOD1B")) # Dual-Pmod module.
    platform.add_extension(QMTechDaughterboard())          # Carrier on QMTech core-board J2/J3.

IOs and connectors of an Extension are described by overriding define_io()/define_connectors(), with
the slot names as connector names (for example "pmod:3" or "J2:17"); they are remapped to the bound
host connectors in get_io()/get_connectors().
An Extension can also expose its own connectors (Pmods/FMC of a carrier), on which other Extensions
can then be plugged: LiteX resolves chained connectors at build time.

Vendor-specific IO attributes (IOStandard, pull-up, slew-rate) are obtained from the platform with
GenericPlatform.get_io_attr() so that extensions remain vendor-agnostic.
"""

from litex.build.generic_platform import Pins, Subsignal, IOStandard

# Extension ----------------------------------------------------------------------------------------

class Extension:
    # Slots this extension plugs on: {slot_name: default_host_connector}. A None default means the
    # host connector has to be provided at instantiation.
    slots = {"default": None}

    # Type of connector expected on each slot (informational, for documentation/checks): "pmod",...
    connector_type = None

    def __init__(self, *args, number=None, iostandard=None, **bindings):
        """Bind slots to host connectors.

        Positional arguments are bound to slots in declaration order, keyword arguments by slot name.
        number     : Override resources' number (to plug several identical extensions on a board).
        iostandard : Override default IOStandard (constraint or string), else platform's default.
        """
        slots = list(self.slots.keys())
        if len(args) > len(slots):
            raise ValueError(f"{type(self).__name__}: too many connectors, slots are: {', '.join(slots)}.")
        self.bindings = dict(self.slots)
        for slot, conn in zip(slots, args):
            self.bindings[slot] = conn
        for slot, conn in bindings.items():
            if slot not in self.slots:
                raise ValueError(f"{type(self).__name__}: unknown slot '{slot}', slots are: {', '.join(slots)}.")
            self.bindings[slot] = conn
        for slot, conn in self.bindings.items():
            if conn is None:
                raise ValueError(f"{type(self).__name__}: no connector bound to slot '{slot}'.")
        self.number = number
        if isinstance(iostandard, str):
            iostandard = IOStandard(iostandard)
        self._iostandard = iostandard

    # Helpers for subclasses -----------------------------------------------------------------------

    def iostandard(self, platform):
        """IOStandard constraint(s) to use: user override or platform's 3.3V default."""
        if self._iostandard is not None:
            return [self._iostandard]
        return platform.get_io_attr("iostandard_3v3")

    @staticmethod
    def pullup(platform):
        return platform.get_io_attr("pullup")

    @staticmethod
    def slew_fast(platform):
        return platform.get_io_attr("slew_fast")

    # To be implemented by subclasses --------------------------------------------------------------

    def define_io(self, platform):
        """IOs, written with slot names as connector names."""
        return []

    def define_connectors(self, platform):
        """Connectors exposed by this extension, written with slot names as connector names."""
        return []

    # Public API -----------------------------------------------------------------------------------

    def get_io(self, platform):
        io = []
        for resource in self.define_io(platform):
            name, number, *elements = resource
            if self.number is not None:
                number = self.number
            io.append((name, number, *[self._remap_constraint(e) for e in elements]))
        return io

    def get_connectors(self, platform):
        connectors = []
        for name, *pins in self.define_connectors(platform):
            if len(pins) == 1 and isinstance(pins[0], dict):
                connectors.append((name, {k: self._remap_identifier(v) for k, v in pins[0].items()}))
            else:
                connectors.append((name, *[" ".join(self._remap_identifier(p) for p in s.split()) for s in pins]))
        return connectors

    # Internals ------------------------------------------------------------------------------------

    def _remap_identifier(self, identifier):
        if identifier is None or ":" not in identifier:
            return identifier
        conn, pin = identifier.split(":", 1)
        if conn in self.bindings:
            return f"{self.bindings[conn]}:{pin}"
        return identifier

    def _remap_constraint(self, constraint):
        if isinstance(constraint, Pins):
            return Pins(" ".join(self._remap_identifier(i) for i in constraint.identifiers))
        if isinstance(constraint, Subsignal):
            return Subsignal(constraint.name, *[self._remap_constraint(c) for c in constraint.constraints])
        return constraint

# Extension from IO list ---------------------------------------------------------------------------

class IOExtension(Extension):
    """Extension built from static IO/connector lists (written with slot names as connector names).

    Useful to turn existing IO lists into reusable/rebindable extensions without subclassing:

        my_board = IOExtension(io=_my_io, connectors=_my_connectors, slots={"J2": "J2"})
    """
    def __init__(self, *args, io=[], connectors=[], slots=None, **kwargs):
        if slots is not None:
            self.slots = slots
        self._io         = list(io)
        self._connectors = list(connectors)
        Extension.__init__(self, *args, **kwargs)

    def define_io(self, platform):
        return self._io

    def define_connectors(self, platform):
        return self._connectors
