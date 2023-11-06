#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from itertools import combinations

from migen.fhdl.structure import *

# Private Classes/Helpers --------------------------------------------------------------------------

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

def _build_tree(signals, base_tree=None):
    """
    Constructs a hierarchical tree from signals, where each signal's backtrace contributes to the tree structure.

    Parameters:
    - signals (list): A list of signals to process.
    - base_tree (Node, optional): A base tree to refine with number usage information.

    Returns:
    - Node: The root node of the constructed tree.
    """
    root = _Node()

    # Iterate over each signal to be included in the tree.
    for signal in signals:
        current = root
        current.signal_count += 1
        current_base = base_tree

        # Traverse or build the hierarchy of nodes based on the signal's backtrace.
        for name, number in signal.backtrace:
            # Decide whether to use a numbered key based on the base tree.
            use_number = False
            if current_base:
                current_base = current_base.children.get(name)
                use_number   = current_base.use_number if current_base else False

            # Create the appropriate key for the node.
            key = (name, number) if use_number else name
            # Use setdefault to either get the existing child node or create a new one.
            current = current.children.setdefault(key, _Node())
            # Add the number to the set of numbers associated with this node.
            current.numbers.add(number)
            # Increment the count of signals that have traversed this node.
            current.signal_count += 1
            # If numbering is used, sort and store all numbers associated with the base node.
            if use_number:
                current.all_numbers = sorted(current_base.numbers)

    return root

def _set_use_name(node, node_name=""):
    """
    Recursively determines if node names should be used to ensure unique signal naming.
    """
    required_names = set()  # This will accumulate all names that ensure unique identification of signals.

    # Recursively collect names from children, identifying if any naming conflicts occur.
    child_name_sets = {
        child_name: _set_use_name(child_node, child_name)
        for child_name, child_node in node.children.items()
    }

    # Check for naming conflicts between all pairs of children.
    for (child1_name, names1), (child2_name, names2) in combinations(child_name_sets.items(), 2):
        if names1 & names2:  # If there's an intersection, we have a naming conflict.
            node.children[child1_name].use_name = node.children[child2_name].use_name = True

    # Collect names, prepending child's name if necessary.
    for child_name, child_names in child_name_sets.items():
        if node.children[child_name].use_name:
            # Prepend the child's name to ensure uniqueness.
            required_names.update((child_name,) + name for name in child_names)
        else:
            required_names.update(child_names)

    # If this node has its own signals, ensure its name is used.
    if node.signal_count > sum(child.signal_count for child in node.children.values()):
        node.use_name = True
        required_names.add((node_name,))  # Add this node's name only if it has additional signals.

    return required_names

def _build_pnd_from_tree(tree, signals):
    """
    Constructs a mapping of signals to their names derived from a tree structure.

    This mapping is used to identify signals by their unique hierarchical path within the tree. The
    tree structure has 'use_name' flags that influence the naming process.
    """

    # Initialize a dictionary to hold the signal names.
    pnd = {}

    # Process each signal to build its hierarchical name.
    for signal in signals:
        # Collect name parts for the hierarchical name.
        elements = []
        # Start traversing the tree from the root.
        treepos = tree

        # Walk through the signal's history to assemble its name.
        for step_name, step_n in signal.backtrace:
            # Navigate the tree according to the signal's path.
            treepos = treepos.children.get((step_name, step_n)) or treepos.children.get(step_name)
            # Check if the number is part of the name based on the tree node.
            use_number = step_n in treepos.all_numbers if hasattr(treepos, 'all_numbers') else False

            # If the tree node's name is to be used, add it to the elements.
            if treepos.use_name:
                # Create the name part, including the number if necessary.
                element_name = step_name if not use_number else f"{step_name}{treepos.all_numbers.index(step_n)}"
                elements.append(element_name)

        # Combine the name parts into the signal's full name.
        pnd[signal] = "_".join(elements)

    # Return the completed name dictionary.
    return pnd

def _invert_pnd(pnd):
    """
    Inverts a signal-to-name dictionary to a name-to-signals dictionary.

    Parameters:
        pnd (dict): A dictionary mapping signals to names.

    Returns:
        dict: An inverted dictionary where keys are names and values are lists of signals with that name.
    """
    inv_pnd = {}
    for signal, name in pnd.items():
        # Get the list of signals for the current name, or initialize it if not present.
        signals_with_name = inv_pnd.get(name, [])
        # Add the current signal to the list.
        signals_with_name.append(signal)
        # Place the updated list back in the dictionary.
        inv_pnd[name] = signals_with_name
    return inv_pnd

def _list_conflicting_signals(pnd):
    """Lists signals that have conflicting names in the provided mapping.

    Parameters:
        pnd (dict): A dictionary mapping signals to names.

    Returns:
        set: A set of signals that have name conflicts.
    """
    # Invert the signal-to-name mapping to a name-to-signals mapping.
    inv_pnd = _invert_pnd(pnd)

    # Prepare a set to hold signals with conflicting names.
    conflicts = set()

    # Iterate through the inverted dictionary.
    for name, signals in inv_pnd.items():
        # If there is more than one signal for this name, it means there is a conflict.
        if len(signals) > 1:
            # Add all conflicting signals to our set.
            conflicts.update(signals)

    # Return the set of all signals that have name conflicts.
    return conflicts

def _set_use_number(tree, signals):
    """
    Updates nodes to use number suffixes to resolve naming conflicts when necessary.

    Parameters:
        tree    (_Node): The root node of the naming tree.
        signals (iterable): Signals potentially causing naming conflicts.

    Returns:
        None: Tree is modified in place.
    """
    for signal in signals:
        node = tree  # Start traversal from the root node.

        # Traverse the signal's path and decide if numbering is needed.
        for step_name, _ in signal.backtrace:
            node = node.children[step_name]  # Proceed to the next node.
            # Set use_number if signal count exceeds unique identifiers.
            if not node.use_number:
                node.use_number = node.signal_count > len(node.numbers) > 1
            # Once use_number is True, it stays True.

def _build_pnd_for_group(group_n, signals):
    """Builds a signal-to-name dictionary for a specific group of signals.

    Parameters:
        group_n      (int): The group number.
        signals (iterable): The signals within the group.

    Returns:
        dict: A dictionary mapping signals to their hierarchical names.
    """

    # Construct initial naming tree and name dictionary.
    tree = _build_tree(signals)
    _set_use_name(tree)
    name_dict = _build_pnd_from_tree(tree, signals)

    # Address naming conflicts by introducing numbers.
    conflicts = _list_conflicting_signals(name_dict)
    if conflicts:
        _set_use_number(tree, conflicts)
        # Rebuild tree and name dictionary if there were conflicts.
        tree = _build_tree(signals, tree)
        _set_use_name(tree)
        name_dict = _build_pnd_from_tree(tree, signals)

    # Disambiguate remaining conflicts using signal's unique identifier (DUID).
    inv_name_dict = _invert_pnd(name_dict)
    for names, sigs in inv_name_dict.items():
        if len(sigs) > 1:
            for idx, sig in enumerate(sorted(sigs, key=lambda s: s.duid)):
                name_dict[sig] += f"{idx}"

    return name_dict


def _build_signal_groups(signals):
    """Organizes signals into related groups.

    Parameters:
        signals (iterable): An iterable of all signals to be organized.

    Returns:
        list: A list of sets, each containing related signals.
    """
    grouped_signals = []

    # Create groups of related signals.
    for signal in signals:
        chain = []
        # Trace back the chain of related signals.
        while signal is not None:
            chain.insert(0, signal)
            signal = signal.related

        # Ensure there's a set for each level of relation.
        while len(grouped_signals) < len(chain):
            grouped_signals.append(set())

        # Assign signals to their respective group.
        for group, sig in zip(grouped_signals, chain):
            group.add(sig)

    # Ensure signals only appear in their most specific group.
    for i in range(len(grouped_signals) - 1):
        grouped_signals[i] -= grouped_signals[i + 1]

    return grouped_signals


def _build_pnd(signals):
    """Builds a complete signal-to-name dictionary using a hierarchical tree.

    Parameters:
        signals (iterable): An iterable of all signals to be named.
        tree       (_Node): The root node of the tree used for name resolution.

    Returns:
        dict: A complete dictionary mapping signals to their hierarchical names.
    """
    # Group the signals based on their relationships.
    groups = _build_signal_groups(signals)

    # Generate a name mapping for each group.
    group_pnd_mappings = [_build_pnd_for_group(group_number, group_signals)
                          for group_number, group_signals in enumerate(groups)]

    # Create the final signal-to-name mapping.
    pnd = {}
    for group_number, group_pnd in enumerate(group_pnd_mappings):
        for signal, name in group_pnd.items():
            # Build the full hierarchical name for each signal.
            hierarchical_name = name
            current_group_number = group_number
            current_signal = signal

            # Traverse up the signal's group relationships to prepend parent names.
            while current_signal.related is not None:
                current_signal = current_signal.related
                current_group_number -= 1
                hierarchical_name = f"{group_pnd_mappings[current_group_number][current_signal]}_{hierarchical_name}"

            # Map the signal to its full hierarchical name.
            pnd[signal] = hierarchical_name

    return pnd

# Public Classes/Helpers ---------------------------------------------------------------------------

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

def build_namespace(signals, reserved_keywords=set()):
    """Constructs a namespace where each signal is given a unique hierarchical name.

    Parameters:
        signals                (iterable): An iterable of all signals to be named.
        reserved_keywords (set, optional): A set of keywords that cannot be used as signal names.

    Returns:
        Namespace: An object that contains the mapping of signals to unique names and provides methods to access them.
    """

    # Create the primary signal-to-name dictionary.
    pnd = _build_pnd(signals)

    # Initialize the namespace with reserved keywords and the primary mapping.
    namespace = Namespace(pnd, reserved_keywords)

    # Handle signals with overridden names, ensuring they are processed in a consistent order.
    signals_with_name_override = filter(lambda s: s.name_override is not None, signals)
    for signal in sorted(signals_with_name_override, key=lambda s: s.duid):
        namespace.get_name(signal)

    return namespace