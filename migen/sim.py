import operator

from migen.fhdl.structure import *
from migen.fhdl.structure import (_Operator, _Slice, _ArrayProxy,
                                  _Assign, _Fragment)
from migen.fhdl.bitcontainer import flen
from migen.fhdl.tools import list_targets


__all__ = ["Simulator"]


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

    def eval(self, node, postcommit=False):
        if isinstance(node, Constant):
            return node.value
        elif isinstance(node, Signal):
            if postcommit:
                try:
                    return self.modifications[node]
                except KeyError:
                    pass
            try:
                return self.signal_values[node]
            except KeyError:
                return node.reset.value
        elif isinstance(node, _Operator):
            operands = [self.eval(o, postcommit) for o in node.operands]
            if node.op == "-":
                if len(operands) == 1:
                    return -operands[0]
                else:
                    return operands[0] - operands[1]
            elif node.op == "m":
                return operands[1] if operands[0] else operands[2]
            else:
                return str2op[node.op](*operands)
        elif isinstance(node, _Slice):
            v = self.eval(node.value, postcommit)
            idx = range(node.start, node.stop)
            return sum(((v >> i) & 1) << j for j, i in enumerate(idx))
        elif isinstance(node, Cat):
            shift = 0
            r = 0
            for element in node.l:
                nbits = flen(element)
                # make value always positive
                r |= (self.eval(element, postcommit) & (2**nbits-1)) << shift
                shift += nbits
            return r
        elif isinstance(node, _ArrayProxy):
            return self.eval(node.choices[self.eval(node.key, postcommit)],
                             postcommit)
        else:
            # TODO: ClockSignal, ResetSignal, Memory
            raise NotImplementedError

    def assign(self, node, value):
        if isinstance(node, Signal):
            assert not node.variable
            value = value & (2**node.nbits - 1)
            if node.signed and (value & 2**(node.nbits - 1)):
                value -= 2**node.nbits
            self.modifications[node] = value
        elif isinstance(node, Cat):
            for element in node.l:
                nbits = flen(element)
                self.assign(element, value & (2**nbits-1))
                value >>= nbits
        elif isinstance(node, Slice):
            full_value = self.eval(node, True)
            # clear bits assigned to by the slice
            full_value &= ~((2**node.stop-1) - (2**node.start-1))
            # set them to the new value
            value &= 2**(node.stop - node.start)-1
            full_value |= value << node.start
            self.assign(node, full_value)
        elif isinstance(node, _ArrayProxy):
            self.assign(node.choices[self.eval(node.key)], value)
        else:
            # TODO: ClockSignal, ResetSignal, Memory
            raise NotImplementedError

    def execute(self, statements):
        for s in statements:
            if isinstance(s, _Assign):
                self.assign(s.l, self.eval(s.r))
            elif isinstance(s, If):
                if self.eval(s.cond):
                    self.execute(s.t)
                else:
                    self.execute(s.f)
            elif isinstance(s, Case):
                test = self.eval(s.test)
                for k, v in s.cases.items():
                    if isinstance(k, Constant) and k.value == test:
                        self.execute(v)
                        return
                if "default" in s.cases:
                    self.execute(s.cases["default"])
            else:
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

        # TODO: insert_resets on sync
        # comb signals return to their reset value if nothing assigns them
        self.fragment.comb[0:0] = [s.eq(s.reset)
                                   for s in list_targets(self.fragment.comb)]

        self.time = TimeManager(clocks)
        self.evaluator = Evaluator()

    def _commit_and_comb_propagate(self):
        # TODO: optimize
        modified = self.evaluator.commit()
        while modified:
            self.evaluator.execute(self.fragment.comb)
            modified = self.evaluator.commit()

    def _eval_nested_lists(self, x):
        if isinstance(x, list):
            return [self._eval_nested_lists(e) for e in x]
        elif isinstance(x, Signal):
            return self.evaluator.eval(x)
        else:
            raise ValueError

    def _process_generators(self, cd):
        exhausted = []
        for generator in self.generators[cd]:
            reply = None
            while True:
                try:
                    request = generator.send(reply)
                    if request is None:
                        break  # next cycle
                    elif isinstance(request, tuple):
                        self.evaluator.assign(*request)
                    else:
                        reply = self._eval_nested_lists(request)
                except StopIteration:
                    exhausted.append(generator)
                    break
        for generator in exhausted:
            self.generators[cd].remove(generator)

    def _continue_simulation(self):
        # TODO: passive generators
        return any(self.generators.values())

    def run(self):
        self.evaluator.execute(self.fragment.comb)
        self._commit_and_comb_propagate()

        while True:
            cds = self.time.tick()
            for cd in cds:
                if cd in self.fragment.sync:
                    self.evaluator.execute(self.fragment.sync[cd])
                if cd in self.generators:
                    self._process_generators(cd)
            self._commit_and_comb_propagate()

            if not self._continue_simulation():
                break
