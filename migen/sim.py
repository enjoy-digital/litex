import operator
from collections import defaultdict

from migen.fhdl.std import *
from migen.fhdl.structure import _Operator, _Assign, _Fragment
from migen.fhdl.tools import list_inputs


class ClockState:
    def __init__(self, period, times_before_tick):
        self.period = period
        self.times_before_tick = times_before_tick


class TimeManager:
    def __init__(self, description):
        self.clocks = dict()

        for k, v in description.items():
            if not isinstance(v, tuple):
                v = v, 0
            self.clocks[k] = ClockState(v[0], v[0] - v[1])
    
    def tick(self):
        r = set()
        dt = min(cs.times_before_tick for cs in self.clocks.values())
        for k, cs in self.clocks.items():
            if cs.times_before_tick == dt:
                r.add(k)
            cs.times_before_tick -= dt
            if not cs.times_before_tick:
                cs.times_before_tick += cs.period
        return r


str2op = {
    "~": operator.invert,
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    
    ">>>": operator.rshift,
    "<<<": operator.lshift,
    
    "&": operator.and_,
    "^": operator.xor,
    "|": operator.or_,
    
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
}


class Evaluator:
    def __init__(self):
        self.signal_values = dict()
        self.modifications = dict()

    def commit(self):
        r = set()
        for k, v in self.modifications.items():
            if k not in self.signal_values or self.signal_values[k] != v:
                self.signal_values[k] = v
                r.add(k)
        self.modifications.clear()
        return r

    def _eval(self, node):
        if isinstance(node, (int, bool)):
            return node
        elif isinstance(node, Signal):
            try:
                return self.signal_values[node]
            except KeyError:
                return node.reset
        elif isinstance(node, _Operator):
            operands = [self._eval(o) for o in node.operands]
            if node.op == "-":
                if len(operands) == 1:
                    return -operands[0]
                else:
                    return operands[0] - operands[1]
            else:
                return str2op[node.op](*operands)
        else:
            # TODO: Cat, Slice, Array, ClockSignal, ResetSignal, Memory
            raise NotImplementedError

    def execute(self, statements):
        for s in statements:
            if isinstance(s, _Assign):
                value = self._eval(s.r)
                if isinstance(s.l, Signal):
                    value = value & (2**s.l.nbits - 1)
                    if s.l.signed and (value & 2**(s.l.nbits - 1)):
                        value -= 2**s.l.nbits
                    self.modifications[s.l] = value
                else:
                    # TODO: Cat, Slice, Array, ClockSignal, ResetSignal, Memory
                    raise NotImplementedError
            elif isinstance(s, If):
                if self._eval(s.cond):
                    self.execute(s.t)
                else:
                    self.execute(s.f)
            else:
                # TODO: Case
                raise NotImplementedError


# TODO: instances via Iverilog/VPI
# TODO: VCD output
class Simulator:
    def __init__(self, fragment_or_module, generators, clocks={"sys": 100}):
        if isinstance(fragment_or_module, _Fragment):
            self.fragment = fragment_or_module
        else:
            self.fragment = fragment_or_module.get_fragment()
        if not isinstance(generators, dict):
            generators = {"sys": generators}
        self.generators = dict()
        for k, v in generators.items():
            if isinstance(v, list):
                self.generators[k] = v
            else:
                self.generators[k] = [v]

        # TODO: insert_resets
        self.time = TimeManager(clocks)
        self.evaluator = Evaluator()

        self.comb_dependent_statements = defaultdict(list)
        for statement in self.fragment.comb:
            for signal in list_inputs(statement):
                self.comb_dependent_statements[signal].append(statement)

    def _comb_propagate(self, modified):
        while modified:
            for signal in modified:
                self.evaluator.execute(self.comb_dependent_statements[signal])
            modified = self.evaluator.commit()

    def _continue_simulation(self):
        # TODO: passive generators
        return any(self.generators.values())

    def run(self):
        self.evaluator.execute(self.fragment.comb)
        self._comb_propagate(self.evaluator.commit())

        while True:
            print(self.evaluator.signal_values)
            cds = self.time.tick()
            for cd in cds:
                self.evaluator.execute(self.fragment.sync[cd])
            self._comb_propagate(self.evaluator.commit())            
            if not self._continue_simulation():
                break
