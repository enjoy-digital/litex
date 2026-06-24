#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from collections.abc import Mapping

from migen.fhdl.module import Module
from migen.fhdl.structure import Signal
from migen.genlib.record import Record

def allocate_generated_name(obj, used_names):
    """Return a deterministic synthetic instance name for unnamed objects."""
    base = obj.__class__.__name__.lower()
    idx  = 0
    name = f"{base}_{idx}"
    while name in used_names:
        idx += 1
        name = f"{base}_{idx}"
    return name


def get_signals(obj, recurse=False):
    """Return public Signals/Record fields found on obj.

    When recurse is set, registered Migen/LiteX submodules are traversed too.
    The returned list preserves discovery order and removes duplicate Signals.
    """
    signals      = []
    seen_signals = set()
    seen_objects = set()

    def add_signal(signal):
        if signal not in seen_signals:
            signals.append(signal)
            seen_signals.add(signal)

    def collect(value, root=False):
        if isinstance(value, Signal):
            add_signal(value)
            return

        value_id = id(value)
        if value_id in seen_objects:
            return

        if isinstance(value, Record):
            seen_objects.add(value_id)
            for signal in value.flatten():
                collect(signal)
        elif isinstance(value, Mapping):
            seen_objects.add(value_id)
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            seen_objects.add(value_id)
            for item in value:
                collect(item)
        elif isinstance(value, set):
            seen_objects.add(value_id)
            for item in sorted(value, key=lambda item: getattr(item, "duid", id(item))):
                collect(item)
        elif (root or (recurse and isinstance(value, Module))) and hasattr(value, "__dict__"):
            seen_objects.add(value_id)
            for name, attr in vars(value).items():
                if name.startswith("_"):
                    continue
                collect(attr)
            if recurse and isinstance(value, Module):
                for _, submodule in value._submodules:
                    collect(submodule)

    collect(obj, root=True)
    return signals
