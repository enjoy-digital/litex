#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from itertools import combinations

from migen.fhdl.structure import *

class _Node:
    """A node in a hierarchy tree used for signal name resolution.

    Attributes:
        signal_count (int): The count of signals in this node.
        numbers      (set): A set containing numbers associated with this node.
        use_name    (bool): Flag to determine if the node's name should be used in signal naming.
        use_number  (bool): Flag to determine if the node's number should be used in signal naming.
        children    (dict): A dictionary of child nodes.
    """
    def __init__(self):
        self.signal_count = 0
        self.numbers      = set()
        self.use_name     = False
        self.use_number   = False
        self.children     = {}

def _build_tree(signals, basic_tree=None):
    """Builds a hierarchical tree of nodes based on the provided signals.

    Parameters:
        signals           (iterable): An iterable of signals to be organized into a tree.
        basic_tree (_Node, optional): A basic tree structure that the new tree is based upon.

    Returns:
        _Node: The root node of the constructed hierarchical tree.
    """
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
    """Determines whether names should be used in signal naming by examining child nodes.

    Parameters:
        node    (_Node): The current node in the tree.
        node_name (str): The name of the node, used when the node's name needs to be included.

    Returns:
        set: A set of tuples representing the names that are to be used.
    """
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
    """Generates a hierarchical name for a given signal based on the tree structure.

    Parameters:
        tree (_Node): The root node of the tree used for name resolution.
        signal      : The signal object whose name is to be generated.

    Returns:
        str: The generated hierarchical name for the signal.
    """
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
    """Builds a dictionary mapping signals to their hierarchical names from a tree.

    Parameters:
        tree       (_Node): The tree that contains naming information.
        signals (iterable): An iterable of signals that need to be named.

    Returns:
        dict: A dictionary where keys are signals and values are their hierarchical names.
    """
    return dict((signal, _name_signal(tree, signal)) for signal in signals)


def _invert_pnd(pnd):
    """Inverts a signal-to-name dictionary to a name-to-signals dictionary.

    Parameters:
        pnd (dict): A dictionary mapping signals to names.

    Returns:
        dict: An inverted dictionary where keys are names and values are lists of signals.
    """
    inv_pnd = dict()
    for k, v in pnd.items():
        inv_pnd[v] = inv_pnd.get(v, [])
        inv_pnd[v].append(k)
    return inv_pnd


def _list_conflicting_signals(pnd):
    """Lists signals that have conflicting names in the provided mapping.

    Parameters:
        pnd (dict): A dictionary mapping signals to names.

    Returns:
        set: A set of signals that have name conflicts.
    """
    inv_pnd = _invert_pnd(pnd)
    r = set()
    for k, v in inv_pnd.items():
        if len(v) > 1:
            r.update(v)
    return r


def _set_use_number(tree, signals):
    """Sets nodes in the tree to use numbers based on signal counts to resolve name conflicts.

    Parameters:
        tree       (_Node): The tree that contains naming information.
        signals (iterable): An iterable of signals that may have name conflicts.

    Returns:
        None
    """
    for signal in signals:
        current = tree
        for step_name, step_n in signal.backtrace:
            current = current.children[step_name]
            current.use_number = current.signal_count > len(current.numbers) and len(current.numbers) > 1

def _build_pnd_for_group(group_n, signals):
    """Builds a signal-to-name dictionary for a specific group of signals.

    Parameters:
        group_n      (int): The group number.
        signals (iterable): The signals within the group.

    Returns:
        dict: A dictionary mapping signals to their hierarchical names.
    """
    basic_tree = _build_tree(signals)
    _set_use_name(basic_tree)
    pnd = _build_pnd_from_tree(basic_tree, signals)

    # If there are conflicts, try splitting the tree by numbers on paths taken by conflicting signals.
    conflicting_signals = _list_conflicting_signals(pnd)
    if conflicting_signals:
        _set_use_number(basic_tree, conflicting_signals)
        numbered_tree = _build_tree(signals, basic_tree)
        _set_use_name(numbered_tree)
        pnd = _build_pnd_from_tree(numbered_tree, signals)
    # ...then add number suffixes by DUID.
    inv_pnd       = _invert_pnd(pnd)
    duid_suffixed = False
    for name, signals in inv_pnd.items():
        if len(signals) > 1:
            duid_suffixed = True
            for n, signal in enumerate(sorted(signals, key=lambda x: x.duid)):
                pnd[signal] += str(n)
    return pnd


def _build_signal_groups(signals):
    """Organizes signals into related groups.

    Parameters:
        signals (iterable): An iterable of all signals to be organized.

    Returns:
        list: A list of sets, each containing related signals.
    """
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
    """Builds a complete signal-to-name dictionary using a hierarchical tree.

    Parameters:
        signals (iterable): An iterable of all signals to be named.
        tree       (_Node): The root node of the tree used for name resolution.

    Returns:
        dict: A complete dictionary mapping signals to their hierarchical names.
    """
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
    """Constructs a namespace where each signal is given a unique hierarchical name.

    Parameters:
        signals                (iterable): An iterable of all signals to be named.
        reserved_keywords (set, optional): A set of keywords that cannot be used as signal names.

    Returns:
        Namespace: An object that contains the mapping of signals to unique names and provides methods to access them.
    """
    pnd = _build_pnd(signals)
    ns  = Namespace(pnd, reserved_keywords)
    # Register Signals with name_override.
    swno = {signal for signal in signals if signal.name_override is not None}
    for signal in sorted(swno, key=lambda x: x.duid):
        ns.get_name(signal)
    return ns


class Namespace:
    """
    A Namespace object manages unique naming for signals within a hardware design.

    It ensures that each signal has a unique, conflict-free name within the design's namespace. This
    includes taking into account reserved keywords and handling signals that may share the same name
    by default (due to being instances of the same hardware module or component).

    Attributes:
        counts        (dict): A dictionary to keep track of the number of times a particular name has been used.
        sigs          (dict): A dictionary mapping signals to a unique identifier to avoid name conflicts.
        pnd           (dict): The primary name dictionary that maps signals to their base names.
        clock_domains (dict): A dictionary managing the names of clock signals within various clock domains.

    Methods:
        get_name(sig): Returns a unique name for the given signal. If the signal is associated with a
            clock domain, it handles naming appropriately, considering resets and clock signals. For
            regular signals, it uses overridden names or constructs names based on the signal's
            hierarchical structure.
    """
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
