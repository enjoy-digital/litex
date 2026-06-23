#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from itertools import combinations

from migen.fhdl.structure import *

# Hierarchy Node Class -----------------------------------------------------------------------------

class _HierarchyNode:
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
        self.all_numbers  = []

    def update(self, name, number, use_number, current_base=None):
        """
        Updates or creates a hierarchy node based on the current position, name, and number.
        If numbering is used, sorts and stores all numbers associated with the base node.

        Parameters:
            name                              (str): The name of the current hierarchy level.
            number                            (int): The number associated with the current hierarchy level.
            use_number                       (bool): Flag indicating whether to use the number in the hierarchy.
            current_base (_HierarchyNode, optional): The base node for number usage information.

        Returns:
            _HierarchyNode: The updated or created child node.
        """
        # Create the appropriate key for the node.
        key = (name, number) if use_number else name
        # Use setdefault to either get the existing child node or create a new one.
        child = self.children.setdefault(key, _HierarchyNode())
        # Add the number to the set of numbers associated with this node.
        child.numbers.add(number)
        # Increment the count of signals that have traversed this node.
        child.signal_count += 1
        # If numbering is used, sort and store all numbers associated with the base node.
        if use_number and current_base:
            child.all_numbers = sorted(current_base.numbers)
        return child

# Build Hierarchy Tree Function --------------------------------------------------------------------

def _build_hierarchy_tree(signals, base_tree=None):
    """
    Constructs a hierarchical tree from signals, where each signal's backtrace contributes to the tree structure.

    Parameters:
    - signals                       (list): A list of signals to process.
    - base_tree (_HierarchyNode, optional): A base tree to refine with number usage information.

    Returns:
    - _HierarchyNode: The root node of the constructed tree.
    """
    root = _HierarchyNode()

    # Iterate over each signal to be included in the tree.
    for signal in signals:
        current      = root
        current_base = base_tree

        # Traverse or build the hierarchy of nodes based on the signal's backtrace.
        for name, number in signal.backtrace:
            # Decide whether to use a numbered key based on the base tree.
            use_number = False
            if current_base:
                current_base = current_base.children.get(name)
                use_number = current_base.use_number if current_base else False

            # Update the current node in the hierarchy.
            current = current.update(name, number, use_number, current_base)

    return root

# Determine Name Usage Function --------------------------------------------------------------------

def _determine_name_usage(node, node_name=""):
    """
    Recursively determines if node names should be used to ensure unique signal naming.
    """
    required_names = set()  # This will accumulate all names that ensure unique identification of signals.

    # Recursively collect names from children, identifying if any naming conflicts occur.
    child_name_sets = {
        child_name: _determine_name_usage(child_node, child_name)
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

# Build Signal Name Dict From Tree Function --------------------------------------------------------

def _build_signal_name_dict_from_tree(tree, signals):
    """
    Constructs a mapping of signals to their names derived from a tree structure.

    This mapping is used to identify signals by their unique hierarchical path within the tree. The
    tree structure has 'use_name' flags that influence the naming process.
    """

    # Initialize a dictionary to hold the signal names.
    name_dict = {}

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
            use_number = step_n in treepos.all_numbers

            # If the tree node's name is to be used, add it to the elements.
            if treepos.use_name:
                # Create the name part, including the number if necessary.
                element_name = step_name if not use_number else f"{step_name}{treepos.all_numbers.index(step_n)}"
                elements.append(element_name)

        # Combine the name parts into the signal's full name.
        name_dict[signal] = "_".join(elements)

    # Return the completed name dictionary.
    return name_dict

# Invert Signal Name Dict Function -----------------------------------------------------------------

def _invert_signal_name_dict(name_dict):
    """
    Inverts a signal-to-name dictionary to a name-to-signals dictionary.

    Parameters:
        name_dict (dict): A dictionary mapping signals to names.

    Returns:
        dict: An inverted dictionary where keys are names and values are lists of signals with that name.
    """
    inverted_dict = {}
    for signal, name in name_dict.items():
        # Get the list of signals for the current name, or initialize it if not present.
        signals_with_name = inverted_dict.get(name, [])
        # Add the current signal to the list.
        signals_with_name.append(signal)
        # Place the updated list back in the dictionary.
        inverted_dict[name] = signals_with_name
    return inverted_dict

# List Conflicting Signals Function ----------------------------------------------------------------

def _list_conflicting_signals(name_dict):
    """Lists signals that have conflicting names in the provided mapping.

    Parameters:
        name_dict (dict): A dictionary mapping signals to names.

    Returns:
        set: A set of signals that have name conflicts.
    """
    # Invert the signal-to-name mapping to a name-to-signals mapping.
    inverted_dict = _invert_signal_name_dict(name_dict)

    # Prepare a set to hold signals with conflicting names.
    conflicts = set()

    # Iterate through the inverted dictionary.
    for name, signals in inverted_dict.items():
        # If there is more than one signal for this name, it means there is a conflict.
        if len(signals) > 1:
            # Add all conflicting signals to our set.
            conflicts.update(signals)

    # Return the set of all signals that have name conflicts.
    return conflicts

# Set Number Usage Function ------------------------------------------------------------------------

def _set_number_usage(tree, signals):
    """
    Updates nodes to use number suffixes to resolve naming conflicts when necessary.

    Parameters:
        tree (_HierarchyNode): The root node of the naming tree.
        signals    (iterable): Signals potentially causing naming conflicts.

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

# Build Signal Name Dict For Group Function --------------------------------------------------------

def _build_signal_name_dict_for_group(group_number, signals):
    """Builds a signal-to-name dictionary for a specific group of signals.

    Parameters:
        group_number (int): The group number.
        signals (iterable): The signals within the group.

    Returns:
        dict: A dictionary mapping signals to their hierarchical names.
    """

    def resolve_conflicts_and_rebuild_tree():
        conflicts = _list_conflicting_signals(name_dict)
        if conflicts:
            _set_number_usage(tree, conflicts)
            return _build_hierarchy_tree(signals, tree)
        return tree

    def disambiguate_signals_with_duid():
        inv_name_dict = _invert_signal_name_dict(name_dict)
        for names, sigs in inv_name_dict.items():
            if len(sigs) > 1:
                for idx, sig in enumerate(sorted(sigs, key=lambda s: s.duid)):
                    name_dict[sig] += f"{idx}"

    # Construct initial naming tree and name dictionary.
    tree = _build_hierarchy_tree(signals)
    _determine_name_usage(tree)
    name_dict = _build_signal_name_dict_from_tree(tree, signals)

    # Address naming conflicts by introducing numbers.
    tree = resolve_conflicts_and_rebuild_tree()

    # Re-determine name usage and rebuild the name dictionary.
    _determine_name_usage(tree)
    name_dict = _build_signal_name_dict_from_tree(tree, signals)

    # Disambiguate remaining conflicts using signal's unique identifier (DUID).
    disambiguate_signals_with_duid()

    return name_dict

# Build Signal Groups Function ---------------------------------------------------------------------

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

    return grouped_signals

# Build Hierarchical Name Function -----------------------------------------------------------------

def _build_hierarchical_name(signal, group_number, group_name_dict_mappings):
    """Builds the hierarchical name for a signal.

    Parameters:
        signal                 (Signal): The signal to build the name for.
        group_number              (int): The group number of the signal.
        group_name_dict_mappings (list): The list of all group name dictionaries.

    Returns:
        str: The hierarchical name for the signal.
    """
    hierarchical_name    = group_name_dict_mappings[group_number][signal]
    current_group_number = group_number
    current_signal       = signal

    # Traverse up the signal's group relationships to prepend parent names.
    while current_signal.related is not None:
        current_signal       = current_signal.related
        current_group_number -= 1
        parent_name          = group_name_dict_mappings[current_group_number][current_signal]
        hierarchical_name = f"{parent_name}_{hierarchical_name}"

    return hierarchical_name

# Update Name Dict With Group Function -------------------------------------------------------------

def _update_name_dict_with_group(name_dict, group_number, group_name_dict, group_name_dict_mappings):
    """Updates the name dictionary with hierarchical names for a specific group.

    Parameters:
        name_dict                (dict): The dictionary to update.
        group_number              (int): The current group number.
        group_name_dict          (dict): The name dictionary for the current group.
        group_name_dict_mappings (list): The list of all group name dictionaries.

    Returns:
        None: The name_dict is updated in place.
    """
    for signal, name in group_name_dict.items():
        hierarchical_name = _build_hierarchical_name(
            signal, group_number, group_name_dict_mappings
        )
        name_dict[signal] = hierarchical_name

# Build Signal Name Dict Function ------------------------------------------------------------------

def _build_signal_name_dict(signals):
    """Builds a complete signal-to-name dictionary using a hierarchical tree.

    Parameters:
        signals    (iterable): An iterable of all signals to be named.
        tree (_HierarchyNode): The root node of the tree used for name resolution.

    Returns:
        dict: A complete dictionary mapping signals to their hierarchical names.
    """
    # Group the signals based on their relationships.
    groups = _build_signal_groups(signals)

    # Generate a name mapping for each group.
    group_name_dict_mappings = [
        _build_signal_name_dict_for_group(group_number, group_signals)
        for group_number, group_signals in enumerate(groups)
    ]

    # Create the final signal-to-name mapping.
    name_dict = {}
    for group_number, group_name_dict in enumerate(group_name_dict_mappings):
        _update_name_dict_with_group(name_dict, group_number, group_name_dict, group_name_dict_mappings)

    return name_dict

# Signal Namespace Class ---------------------------------------------------------------------------

class SignalNamespace:
    """
    A _SignalNamespace object manages unique naming for signals within a hardware design.

    It ensures that each signal has a unique, conflict-free name within the design's namespace. This
    includes taking into account reserved keywords and handling signals that may share the same name
    by default (due to being instances of the same hardware module or component).

    Attributes:
        counts        (dict): A dictionary to keep track of the number of times a particular name has been used.
        sigs          (dict): A dictionary mapping signals to a unique identifier to avoid name conflicts.
        name_dict     (dict): The primary name dictionary that maps signals to their base names.
        clock_domains (dict): A dictionary managing the names of clock signals within various clock domains.

    Methods:
        get_name(sig): Returns a unique name for the given signal. If the signal is associated with a
            clock domain, it handles naming appropriately, considering resets and clock signals. For
            regular signals, it uses overridden names or constructs names based on the signal's
            hierarchical structure.
    """
    def __init__(self, name_dict, reserved_keywords=set()):
        self.counts        = {k: 1 for k in reserved_keywords}
        self.sigs          = {}
        self.name_dict     = name_dict
        self.clock_domains = dict()

    def get_name(self, sig):
        # Return None if sig is None.
        # ---------------------------
        if sig is None:
            return None

        # Handle Clock and Reset Signals.
        # -------------------------------
        if isinstance(sig, (ClockSignal, ResetSignal)):
            # Retrieve the clock domain from the dictionary.
            domain = self.clock_domains.get(sig.cd)
            if domain is None:
                raise ValueError(f"Clock Domain '{sig.cd}' not found.")
            # Assign the appropriate signal from the clock domain.
            sig = domain.clk if isinstance(sig, ClockSignal) else domain.rst
            # If the signal is None, the clock domain is missing a clock or reset.
            if sig is None:
                raise ValueError(f"Clock Domain '{sig.cd}' is reset-less, can't obtain name.")

        # Get name of a Regular Signal.
        # -----------------------------
        # Use Name's override when set...
        if sig.name_override is not None:
            sig_name = sig.name_override
        # ... else get Name from name_dict.
        else:
            sig_name = self.name_dict.get(sig)
            # If the signal is not in the name_dict, raise an error.
            if sig_name is None:
                raise ValueError(f"Signal '{sig}' not found in name dictionary.")


        # Check/Add numbering when required.
        # ----------------------------------
        # Retrieve the current count for the signal name, defaulting to 0.
        n = self.sigs.get(sig)
        if n is None:
            n = self.counts.get(sig_name, 0)
            self.sigs[sig] = n
            self.counts[sig_name] = n + 1
        # If the count is greater than 0, append it to the signal name.
        if n > 0:
            sig_name += f"_{n}"

        # Return Name.
        return sig_name

# Build Signal Namespace function ------------------------------------------------------------------

def build_signal_namespace(signals, reserved_keywords=set()):
    """Constructs a namespace where each signal is given a unique hierarchical name.
    Parameters:
        signals                (iterable): An iterable of all signals to be named.
        reserved_keywords (set, optional): A set of keywords that cannot be used as signal names.

    Returns:
        SignalNamespace: An object that contains the mapping of signals to unique names and provides methods to access them.
    """

    # Create the primary signal-to-name dictionary.
    pnd = _build_signal_name_dict(signals)

    # Initialize the namespace with reserved keywords and the primary mapping.
    namespace = SignalNamespace(pnd, reserved_keywords)

    # Handle signals with overridden names, ensuring they are processed in a consistent order.
    signals_with_name_override = filter(lambda s: s.name_override is not None, signals)

    return namespace
