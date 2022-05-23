#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.record import Record
from migen.fhdl.module import Module
from migen.fhdl.structure import Signal

def get_signals(obj, recurse=False):
    signals = set()
    for attr_name in dir(obj):
        if attr_name[:2] == "__" and attr_name[-2:] == "__":
            continue
        attr = getattr(obj, attr_name)
        if isinstance(attr, Signal):
            signals.add(attr)
        elif isinstance(attr, Record):
            for robj in attr.flatten():
                if isinstance(robj, Signal):
                    signals.add(robj)
        elif recurse and isinstance(attr, Module):
            signals |= get_signals(attr, recurse=True)

    return signals
