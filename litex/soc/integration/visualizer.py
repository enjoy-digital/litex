# This file is Copyright (c) 2020 Paul Florence <perso@florencepaul.com>
# License: BSD

from graphviz import Digraph


class GraphPrinter:
    def __init__(self, filter=None):
        # This dict is used to generate unique names for modules which share the same name
        self.state = dict()
        self.dot = Digraph(comment='SoC')
        self.filter = filter

    def render(self, root):
        root_name = str(root.__class__.__name__)
        for (name, module) in getattr(root, 'submodules')._fm._submodules:
            self.__visit_node(name, module, root_name)
        self.dot.render('soc.gv', view=True)

    # Insert the given name in the graph, and increase the number of occurrences of this name
    def __insert_node(self, name):
        if self.state.get(name) is None:
            self.state[name] = 0
        else:
            self.state[name] += 1
        self.dot.node(name + str(self.state[name]))

    def __generate_node_name(self, name):
        return name + str(self.state[name])

    def __visit_node(self, name, object, parent_name):
        if self.filter is not None and self.filter(name):
            return
        if len(getattr(object, 'submodules')._fm._submodules) != 0:
            node_name = parent_name
            # Skip nodes with no names
            if name is not None:
                self.__insert_node(name)
                node_name = self.__generate_node_name(name)
                self.dot.edge(parent_name, node_name)
            # Add children
            for (s_name, s_module) in getattr(object, 'submodules')._fm._submodules:
                self.__visit_node(s_name, s_module, node_name)
        # Leaf node: render it if it's name is not None
        else:
            if name is not None:
                self.__insert_node(name)
                node_name = self.__generate_node_name(name)
                self.dot.edge(parent_name, node_name)
