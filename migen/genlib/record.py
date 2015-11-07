from migen.fhdl.structure import *
from migen.fhdl.tracer import get_obj_var_name

from functools import reduce
from operator import or_


(DIR_NONE, DIR_S_TO_M, DIR_M_TO_S) = range(3)

# Possible layout elements:
#   1. (name, size)
#   2. (name, size, direction)
#   3. (name, sublayout)
# size can be an int, or a (int, bool) tuple for signed numbers
# sublayout must be a list


def set_layout_parameters(layout, **layout_dict):
    def resolve(p):
        if isinstance(p, str):
            try:
                return layout_dict[p]
            except KeyError:
                return p
        else:
            return p

    r = []
    for f in layout:
        if isinstance(f[1], (int, tuple, str)):  # cases 1/2
            if len(f) == 3:
                r.append((f[0], resolve(f[1]), f[2]))
            else:
                r.append((f[0], resolve(f[1])))
        elif isinstance(f[1], list):  # case 3
            r.append((f[0], set_layout_parameters(f[1], **layout_dict)))
        else:
            raise TypeError
    return r


def layout_len(layout):
    r = 0
    for f in layout:
        if isinstance(f[1], (int, tuple)):  # cases 1/2
            if len(f) == 3:
                fname, fsize, fdirection = f
            else:
                fname, fsize = f
        elif isinstance(f[1], list):  # case 3
            fname, fsublayout = f
            fsize = layout_len(fsublayout)
        else:
            raise TypeError
        if isinstance(fsize, tuple):
            r += fsize[0]
        else:
            r += fsize
    return r


def layout_get(layout, name):
    for f in layout:
        if f[0] == name:
            return f
    raise KeyError(name)


def layout_partial(layout, *elements):
    r = []
    for path in elements:
        path_s = path.split("/")
        last = path_s.pop()
        copy_ref = layout
        insert_ref = r
        for hop in path_s:
            name, copy_ref = layout_get(copy_ref, hop)
            try:
                name, insert_ref = layout_get(insert_ref, hop)
            except KeyError:
                new_insert_ref = []
                insert_ref.append((hop, new_insert_ref))
                insert_ref = new_insert_ref
        insert_ref.append(layout_get(copy_ref, last))
    return r


class Record:
    def __init__(self, layout, name=None):
        self.name = get_obj_var_name(name, "")
        self.layout = layout

        if self.name:
            prefix = self.name + "_"
        else:
            prefix = ""
        for f in self.layout:
            if isinstance(f[1], (int, tuple)):  # cases 1/2
                if(len(f) == 3):
                    fname, fsize, fdirection = f
                else:
                    fname, fsize = f
                finst = Signal(fsize, name=prefix + fname)
            elif isinstance(f[1], list):  # case 3
                fname, fsublayout = f
                finst = Record(fsublayout, prefix + fname)
            else:
                raise TypeError
            setattr(self, fname, finst)

    def eq(self, other):
        return [getattr(self, f[0]).eq(getattr(other, f[0]))
          for f in self.layout if hasattr(other, f[0])]

    def iter_flat(self):
        for f in self.layout:
            e = getattr(self, f[0])
            if isinstance(e, Signal):
                if len(f) == 3:
                    yield e, f[2]
                else:
                    yield e, DIR_NONE
            elif isinstance(e, Record):
                yield from e.iter_flat()
            else:
                raise TypeError

    def flatten(self):
        return [signal for signal, direction in self.iter_flat()]

    def raw_bits(self):
        return Cat(*self.flatten())

    def connect(self, *slaves, leave_out=set()):
        if isinstance(leave_out, str):
            leave_out = {leave_out}
        r = []
        for f in self.layout:
            field = f[0]
            if field not in leave_out:
                self_e = getattr(self, field)
                if isinstance(self_e, Signal):
                    direction = f[2]
                    if direction == DIR_M_TO_S:
                        r += [getattr(slave, field).eq(self_e) for slave in slaves]
                    elif direction == DIR_S_TO_M:
                        r.append(self_e.eq(reduce(or_, [getattr(slave, field) for slave in slaves])))
                    else:
                        raise TypeError
                else:
                    for slave in slaves:
                        r += self_e.connect(getattr(slave, field), leave_out=leave_out)
        return r

    def connect_flat(self, *slaves):
        r = []
        iter_slaves = [slave.iter_flat() for slave in slaves]
        for m_signal, m_direction in self.iter_flat():
            if m_direction == DIR_M_TO_S:
                for iter_slave in iter_slaves:
                    s_signal, s_direction = next(iter_slave)
                    assert(s_direction == DIR_M_TO_S)
                    r.append(s_signal.eq(m_signal))
            elif m_direction == DIR_S_TO_M:
                s_signals = []
                for iter_slave in iter_slaves:
                    s_signal, s_direction = next(iter_slave)
                    assert(s_direction == DIR_S_TO_M)
                    s_signals.append(s_signal)
                r.append(m_signal.eq(reduce(or_, s_signals)))
            else:
                raise TypeError
        return r

    def __len__(self):
        return layout_len(self.layout)

    def __repr__(self):
        return "<Record " + ":".join(f[0] for f in self.layout) + " at " + hex(id(self)) + ">"
