from copy import copy

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _ArrayProxy, _Fragment

class NodeVisitor:
    def visit(self, node):
        if isinstance(node, (int, bool)):
            self.visit_constant(node)
        elif isinstance(node, Signal):
            self.visit_Signal(node)
        elif isinstance(node, ClockSignal):
            self.visit_ClockSignal(node)
        elif isinstance(node, ResetSignal):
            self.visit_ResetSignal(node)
        elif isinstance(node, _Operator):
            self.visit_Operator(node)
        elif isinstance(node, _Slice):
            self.visit_Slice(node)
        elif isinstance(node, Cat):
            self.visit_Cat(node)
        elif isinstance(node, Replicate):
            self.visit_Replicate(node)
        elif isinstance(node, _Assign):
            self.visit_Assign(node)
        elif isinstance(node, If):
            self.visit_If(node)
        elif isinstance(node, Case):
            self.visit_Case(node)
        elif isinstance(node, _Fragment):
            self.visit_Fragment(node)
        elif isinstance(node, (list, tuple)):
            self.visit_statements(node)
        elif isinstance(node, dict):
            self.visit_clock_domains(node)
        elif isinstance(node, _ArrayProxy):
            self.visit_ArrayProxy(node)
        elif node is not None:
            self.visit_unknown(node)

    def visit_constant(self, node):
        pass

    def visit_Signal(self, node):
        pass

    def visit_ClockSignal(self, node):
        pass

    def visit_ResetSignal(self, node):
        pass

    def visit_Operator(self, node):
        for o in node.operands:
            self.visit(o)

    def visit_Slice(self, node):
        self.visit(node.value)

    def visit_Cat(self, node):
        for e in node.l:
            self.visit(e)

    def visit_Replicate(self, node):
        self.visit(node.v)

    def visit_Assign(self, node):
        self.visit(node.l)
        self.visit(node.r)

    def visit_If(self, node):
        self.visit(node.cond)
        self.visit(node.t)
        self.visit(node.f)

    def visit_Case(self, node):
        self.visit(node.test)
        for v, statements in node.cases.items():
            self.visit(statements)

    def visit_Fragment(self, node):
        self.visit(node.comb)
        self.visit(node.sync)

    def visit_statements(self, node):
        for statement in node:
            self.visit(statement)

    def visit_clock_domains(self, node):
        for clockname, statements in node.items():
            self.visit(statements)

    def visit_ArrayProxy(self, node):
        for choice in node.choices:
            self.visit(choice)
        self.visit(node.key)

    def visit_unknown(self, node):
        pass

# Default methods always copy the node, except for:
# - Signals, ClockSignals and ResetSignals
# - Unknown objects
# - All fragment fields except comb and sync
# In those cases, the original node is returned unchanged.
class NodeTransformer:
    def visit(self, node):
        if isinstance(node, (int, bool)):
            return self.visit_constant(node)
        elif isinstance(node, Signal):
            return self.visit_Signal(node)
        elif isinstance(node, ClockSignal):
            return self.visit_ClockSignal(node)
        elif isinstance(node, ResetSignal):
            return self.visit_ResetSignal(node)
        elif isinstance(node, _Operator):
            return self.visit_Operator(node)
        elif isinstance(node, _Slice):
            return self.visit_Slice(node)
        elif isinstance(node, Cat):
            return self.visit_Cat(node)
        elif isinstance(node, Replicate):
            return self.visit_Replicate(node)
        elif isinstance(node, _Assign):
            return self.visit_Assign(node)
        elif isinstance(node, If):
            return self.visit_If(node)
        elif isinstance(node, Case):
            return self.visit_Case(node)
        elif isinstance(node, _Fragment):
            return self.visit_Fragment(node)
        elif isinstance(node, (list, tuple)):
            return self.visit_statements(node)
        elif isinstance(node, dict):
            return self.visit_clock_domains(node)
        elif isinstance(node, _ArrayProxy):
            return self.visit_ArrayProxy(node)
        elif node is not None:
            return self.visit_unknown(node)
        else:
            return None

    def visit_constant(self, node):
        return node

    def visit_Signal(self, node):
        return node

    def visit_ClockSignal(self, node):
        return node

    def visit_ResetSignal(self, node):
        return node

    def visit_Operator(self, node):
        return _Operator(node.op, [self.visit(o) for o in node.operands])

    def visit_Slice(self, node):
        return _Slice(self.visit(node.value), node.start, node.stop)

    def visit_Cat(self, node):
        return Cat(*[self.visit(e) for e in node.l])

    def visit_Replicate(self, node):
        return Replicate(self.visit(node.v), node.n)

    def visit_Assign(self, node):
        return _Assign(self.visit(node.l), self.visit(node.r))

    def visit_If(self, node):
        r = If(self.visit(node.cond))
        r.t = self.visit(node.t)
        r.f = self.visit(node.f)
        return r

    def visit_Case(self, node):
        cases = dict((v, self.visit(statements)) for v, statements in node.cases.items())
        r = Case(self.visit(node.test), cases)
        return r

    def visit_Fragment(self, node):
        r = copy(node)
        r.comb = self.visit(node.comb)
        r.sync = self.visit(node.sync)
        return r

    # NOTE: this will always return a list, even if node is a tuple
    def visit_statements(self, node):
        return [self.visit(statement) for statement in node]

    def visit_clock_domains(self, node):
        return dict((clockname, self.visit(statements)) for clockname, statements in node.items())

    def visit_ArrayProxy(self, node):
        return _ArrayProxy([self.visit(choice) for choice in node.choices],
            self.visit(node.key))

    def visit_unknown(self, node):
        return node
