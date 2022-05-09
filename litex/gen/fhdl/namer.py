#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from collections import OrderedDict
from itertools import combinations

from migen.fhdl.structure import *


class _Node:
    def __init__(self):
        self.signal_count = 0
        self.numbers      = set()
        self.use_name     = False
        self.use_number   = False
        self.children     = OrderedDict()


def _display_tree(filename, tree):
    from migen.util.treeviz import RenderNode

    def _to_render_node(name, node):
        children = [_to_render_node(k, v) for k, v in node.children.items()]
        if node.use_name:
            if node.use_number:
                color = (0.5, 0.9, 0.8)
            else:
                color = (0.8, 0.5, 0.9)
        else:
            if node.use_number:
                color = (0.9, 0.8, 0.5)
            else:
                color = (0.8, 0.8, 0.8)
        label = "{0}\n{1} signals\n{2}".format(name, node.signal_count, node.numbers)
        return RenderNode(label, children, color=color)

    top = _to_render_node("top", tree)
    top.to_svg(filename)


def _build_tree(signals, basic_tree=None):
    root = _Node()
    for signal in signals:
        current_b = basic_tree
        current   = root
        current.signal_count += 1
        for name, number in signal.backtrace:
            if basic_tree is None:
                use_number = False
            else:
                current_b  = current_b.children[name]
                use_number = current_b.use_number
            if use_number:
                key = (name, number)
            else:
                key = name
            try:
                current = current.children[key]
            except KeyError:
                new = _Node()
                current.children[key] = new
                current = new
            current.numbers.add(number)
            if use_number:
                current.all_numbers = sorted(current_b.numbers)
            current.signal_count += 1
    return root


def _set_use_name(node, node_name=""):
    cnames = [(k, _set_use_name(v, k)) for k, v in node.children.items()]
    for (c1_prefix, c1_names), (c2_prefix, c2_names) in combinations(cnames, 2):
        if not c1_names.isdisjoint(c2_names):
            node.children[c1_prefix].use_name = True
            node.children[c2_prefix].use_name = True
    r = set()
    for c_prefix, c_names in cnames:
        if node.children[c_prefix].use_name:
            for c_name in c_names:
                r.add((c_prefix, ) + c_name)
        else:
            r |= c_names

    if node.signal_count > sum(c.signal_count for c in node.children.values()):
        node.use_name = True
        r.add((node_name, ))

    return r


def _name_signal(tree, signal):
    elements = []
    treepos  = tree
    for step_name, step_n in signal.backtrace:
        try:
            treepos    = treepos.children[(step_name, step_n)]
            use_number = True
        except KeyError:
            treepos    = treepos.children[step_name]
            use_number = False
        if treepos.use_name:
            elname = step_name
            if use_number:
                elname += str(treepos.all_numbers.index(step_n))
            elements.append(elname)
    return "_".join(elements)


def _build_pnd_from_tree(tree, signals):
    return dict((signal, _name_signal(tree, signal)) for signal in signals)


def _invert_pnd(pnd):
    inv_pnd = dict()
    for k, v in pnd.items():
        inv_pnd[v] = inv_pnd.get(v, [])
        inv_pnd[v].append(k)
    return inv_pnd


def _list_conflicting_signals(pnd):
    inv_pnd = _invert_pnd(pnd)
    r = set()
    for k, v in inv_pnd.items():
        if len(v) > 1:
            r.update(v)
    return r


def _set_use_number(tree, signals):
    for signal in signals:
        current = tree
        for step_name, step_n in signal.backtrace:
            current = current.children[step_name]
            current.use_number = current.signal_count > len(current.numbers) and len(current.numbers) > 1

_debug = False


def _build_pnd_for_group(group_n, signals):
    basic_tree = _build_tree(signals)
    _set_use_name(basic_tree)
    if _debug:
        _display_tree("tree{0}_basic.svg".format(group_n), basic_tree)
    pnd = _build_pnd_from_tree(basic_tree, signals)

    # If there are conflicts, try splitting the tree by numbers on paths taken by conflicting signals.
    conflicting_signals = _list_conflicting_signals(pnd)
    if conflicting_signals:
        _set_use_number(basic_tree, conflicting_signals)
        if _debug:
            print("namer: using split-by-number strategy (group {0})".format(group_n))
            _display_tree("tree{0}_marked.svg".format(group_n), basic_tree)
        numbered_tree = _build_tree(signals, basic_tree)
        _set_use_name(numbered_tree)
        if _debug:
            _display_tree("tree{0}_numbered.svg".format(group_n), numbered_tree)
        pnd = _build_pnd_from_tree(numbered_tree, signals)
    else:
        if _debug:
            print("namer: using basic strategy (group {0})".format(group_n))

    # ...then add number suffixes by DUID.
    inv_pnd       = _invert_pnd(pnd)
    duid_suffixed = False
    for name, signals in inv_pnd.items():
        if len(signals) > 1:
            duid_suffixed = True
            for n, signal in enumerate(sorted(signals, key=lambda x: x.duid)):
                pnd[signal] += str(n)
    if _debug and duid_suffixed:
        print("namer: using DUID suffixes (group {0})".format(group_n))

    return pnd


def _build_signal_groups(signals):
    r = []
    for signal in signals:
        # Build chain of related signals.
        related_list = []
        cur_signal   = signal
        while cur_signal is not None:
            related_list.insert(0, cur_signal)
            cur_signal = cur_signal.related
        # Add to groups.
        for _ in range(len(related_list) - len(r)):
            r.append(set())
        for target_set, source_signal in zip(r, related_list):
            target_set.add(source_signal)
    # With the algorithm above and a list of all signals, a signal appears in all groups of a lower
    # number than its. Make signals appear only in their group of highest number.
    for s1, s2 in zip(r, r[1:]):
        s1 -= s2
    return r


def _build_pnd(signals):
    groups = _build_signal_groups(signals)
    gpnds  = [_build_pnd_for_group(n, gsignals) for n, gsignals in enumerate(groups)]
    pnd    = dict()
    for gn, gpnd in enumerate(gpnds):
        for signal, name in gpnd.items():
            result     = name
            cur_gn     = gn
            cur_signal = signal
            while cur_signal.related is not None:
                cur_signal = cur_signal.related
                cur_gn     -= 1
                result     = gpnds[cur_gn][cur_signal] + "_" + result
            pnd[signal] = result
    return pnd


def build_namespace(signals, reserved_keywords=set()):
    pnd = _build_pnd(signals)
    ns  = Namespace(pnd, reserved_keywords)
    # Register Signals with name_override.
    swno = {signal for signal in signals if signal.name_override is not None}
    for signal in sorted(swno, key=lambda x: x.duid):
        ns.get_name(signal)
    return ns


class Namespace:
    def __init__(self, pnd, reserved_keywords=set()):
        self.counts = {k: 1 for k in reserved_keywords}
        self.sigs   = {}
        self.pnd    = pnd
        self.clock_domains = dict()

    def get_name(self, sig):
        # Get name of a Clock Signal.
        # ---------------------------
        if isinstance(sig, ClockSignal):
            sig = self.clock_domains[sig.cd].clk

        # Get name of a Reset Signal.
        # ---------------------------
        if isinstance(sig, ResetSignal):
            sig = self.clock_domains[sig.cd].rst
            if sig is None:
                msg = f"Clock Domain {sig.cd} is reset-less, can't obtain name"
                raise ValueError(msg)

        # Get name of a Regular Signal.
        # -----------------------------
        # Use Name's override when set...
        if sig.name_override is not None:
            sig_name = sig.name_override
        # ... else get Name from pnd.
        else:
            sig_name = self.pnd[sig]

        # Check/Add numbering suffix when required.
        # -----------------------------------------
        try:
            n = self.sigs[sig]
        except KeyError:
            try:
                n = self.counts[sig_name]
            except KeyError:
                n = 0
            self.sigs[sig]        = n
            self.counts[sig_name] = n + 1
        suffix = "" if n == 0 else f"_{n}"

        # Return Name.
        return sig_name + suffix
