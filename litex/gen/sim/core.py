#
# This file is part of Migen and has been adapted/modified for LiteX.
#
# This file is Copyright (c) 2015-2016 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2018 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2016-2018 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 N. Engelhardt <nakengelhardt@gmail.com>
# This file is Copyright (c) 2018 Robin Ole Heinemann <robin.ole.heinemann@t-online.de>
# SPDX-License-Identifier: BSD-2-Clause

import operator
import collections
import inspect
from functools import wraps

from migen.fhdl.structure import *
from migen.fhdl.structure import (_Value, _Statement,
                                  _Operator, _Slice, _ArrayProxy,
                                  _Assign, _Fragment)
from migen.fhdl.bitcontainer import value_bits_sign
from migen.fhdl.tools import (list_targets, list_signals,
                              insert_resets, lower_specials)
from migen.fhdl.simplify import MemoryToArray
from migen.fhdl.specials import _MemoryLocation
from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen.sim.vcd import VCDWriter, DummyVCDWriter


class ClockState:
    def __init__(self, high, half_period, time_before_trans):
        self.high = high
        self.half_period = half_period
        self.time_before_trans = time_before_trans


class TimeManager:
    def __init__(self, description):
        self.clocks = collections.OrderedDict()

        for k, period_phase in description.items():
            if isinstance(period_phase, tuple):
                period, phase = period_phase
            else:
                period = period_phase
                phase = 0
            half_period = period//2
            if phase >= half_period:
                phase -= half_period
                high = True
            else:
                high = False
            self.clocks[k] = ClockState(high, half_period, half_period - phase)

    def tick(self):
        rising = set()
        falling = set()
        dt = min(cs.time_before_trans for cs in self.clocks.values())
        for k, cs in self.clocks.items():
            if cs.time_before_trans == dt:
                cs.high = not cs.high
                if cs.high:
                    rising.add(k)
                else:
                    falling.add(k)
            cs.time_before_trans -= dt
            if not cs.time_before_trans:
                cs.time_before_trans += cs.half_period
        return dt, rising, falling


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


def _truncate(value, nbits, signed):
    value = value & (2**nbits - 1)
    if signed and (value & 2**(nbits - 1)):
        value -= 2**nbits
    return value


class Evaluator:
    def __init__(self, clock_domains, replaced_memories):
        self.clock_domains = clock_domains
        self.replaced_memories = replaced_memories
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
                nbits = len(element)
                # make value always positive
                r |= (self.eval(element, postcommit) & (2**nbits-1)) << shift
                shift += nbits
            return r
        elif isinstance(node, Replicate):
            nbits = len(node.v)
            v = self.eval(node.v, postcommit) & (2**nbits - 1)
            return sum(v << i*nbits for i in range(node.n))
        elif isinstance(node, _ArrayProxy):
            idx = min(len(node.choices) - 1, self.eval(node.key, postcommit))
            return self.eval(node.choices[idx], postcommit)
        elif isinstance(node, _MemoryLocation):
            array = self.replaced_memories[node.memory]
            return self.eval(array[self.eval(node.index, postcommit)], postcommit)
        elif isinstance(node, ClockSignal):
            return self.eval(self.clock_domains[node.cd].clk, postcommit)
        elif isinstance(node, ResetSignal):
            rst = self.clock_domains[node.cd].rst
            if rst is None:
                if node.allow_reset_less:
                    return 0
                else:
                    raise ValueError("Attempted to get reset signal of resetless"
                                     " domain '{}'".format(node.cd))
            else:
                return self.eval(rst, postcommit)
        else:
            raise NotImplementedError(node)

    def assign(self, node, value):
        if isinstance(node, Signal):
            assert not node.variable
            self.modifications[node] = _truncate(value,
                                                 node.nbits, node.signed)
        elif isinstance(node, Cat):
            for element in node.l:
                nbits = len(element)
                self.assign(element, value & (2**nbits-1))
                value >>= nbits
        elif isinstance(node, _Slice):
            full_value = self.eval(node.value, True)
            # clear bits assigned to by the slice
            full_value &= ~((2**node.stop-1) - (2**node.start-1))
            # set them to the new value
            value &= 2**(node.stop - node.start)-1
            full_value |= value << node.start
            self.assign(node.value, full_value)
        elif isinstance(node, _ArrayProxy):
            idx = min(len(node.choices) - 1, self.eval(node.key))
            self.assign(node.choices[idx], value)
        elif isinstance(node, _MemoryLocation):
            array = self.replaced_memories[node.memory]
            self.assign(array[self.eval(node.index)], value)
        else:
            raise NotImplementedError(node)

    def execute(self, statements):
        for s in statements:
            if isinstance(s, _Assign):
                self.assign(s.l, self.eval(s.r))
            elif isinstance(s, If):
                if self.eval(s.cond) & (2**len(s.cond) - 1):
                    self.execute(s.t)
                else:
                    self.execute(s.f)
            elif isinstance(s, Case):
                nbits, signed = value_bits_sign(s.test)
                test = _truncate(self.eval(s.test), nbits, signed)
                found = False
                for k, v in s.cases.items():
                    if isinstance(k, Constant) and k.value == test:
                        self.execute(v)
                        found = True
                        break
                if not found and "default" in s.cases:
                    self.execute(s.cases["default"])
            elif isinstance(s, collections.abc.Iterable):
                self.execute(s)
            elif isinstance(s, Display):
                args = []
                for arg in s.args:
                    assert isinstance(arg, _Value)
                    try:
                        args.append(self.signal_values[arg])
                    except: # not yet evaluated
                        args.append(arg.reset.value)
                print(s.s %(*args,))
            else:
                raise NotImplementedError


class DummyAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        # TODO: asynchronous set
        # This naive implementation has a minimum reset pulse
        # width requirement of one clock period in cd.
        self.comb += cd.rst.eq(async_reset)


class DummyAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return DummyAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


# TODO: instances via Iverilog/VPI
class Simulator:
    def __init__(self, fragment_or_module, generators, clocks={"sys": 10}, vcd_name=None,
                 special_overrides={}):
        if isinstance(fragment_or_module, _Fragment):
            self.fragment = fragment_or_module
        else:
            self.fragment = fragment_or_module.get_fragment()

        mta = MemoryToArray()
        mta.transform_fragment(None, self.fragment)

        overrides = {AsyncResetSynchronizer: DummyAsyncResetSynchronizer}
        overrides.update(special_overrides)
        f, lowered = lower_specials(overrides, self.fragment)
        if self.fragment.specials:
            raise ValueError("Could not lower all specials", self.fragment.specials)

        if not isinstance(generators, dict):
            generators = {"sys": generators}
        self.generators = dict()
        self.passive_generators = set()
        for k, v in generators.items():
            if (isinstance(v, collections.abc.Iterable)
                    and not inspect.isgenerator(v)):
                self.generators[k] = list(v)
            else:
                self.generators[k] = [v]

        clocks = collections.OrderedDict(sorted(clocks.items(),
                                                key=operator.itemgetter(0)))
        self.time = TimeManager(clocks)
        for clock in clocks.keys():
            if clock not in self.fragment.clock_domains:
                cd = ClockDomain(name=clock, reset_less=True)
                cd.clk.reset = C(self.time.clocks[clock].high)
                self.fragment.clock_domains.append(cd)

        insert_resets(self.fragment)
        # comb signals return to their reset value if nothing assigns them
        self.fragment.comb[0:0] = [s.eq(s.reset)
                                   for s in list_targets(self.fragment.comb)]
        self.evaluator = Evaluator(self.fragment.clock_domains,
                                   mta.replacements)

        if vcd_name is None:
            self.vcd = DummyVCDWriter()
        else:
            self.vcd = VCDWriter(vcd_name)

            signals = list_signals(self.fragment)
            for cd in self.fragment.clock_domains:
                signals.add(cd.clk)
                if cd.rst is not None:
                    signals.add(cd.rst)
            for memory_array in mta.replacements.values():
                signals |= set(memory_array)
            self.vcd.init(signals)
            for signal in sorted(signals, key=lambda x: x.duid):
                self.vcd.set(signal, signal.reset.value)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self.vcd.close()

    def _commit_and_comb_propagate(self):
        # TODO: optimize
        all_modified = set()
        modified = self.evaluator.commit()
        all_modified |= modified
        while modified:
            self.evaluator.execute(self.fragment.comb)
            modified = self.evaluator.commit()
            all_modified |= modified
        for signal in all_modified:
            self.vcd.set(signal, self.evaluator.signal_values[signal])

    def _evalexec_nested_lists(self, x):
        if isinstance(x, list):
            return [self._evalexec_nested_lists(e) for e in x]
        elif isinstance(x, _Value):
            return self.evaluator.eval(x)
        elif isinstance(x, _Statement):
            self.evaluator.execute([x])
            return None
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
                    elif isinstance(request, str):
                        if request == "passive":
                            self.passive_generators.add(generator)
                        elif request == "active":
                            self.passive_generators.discard(generator)
                        else:
                            raise ValueError("Unknown simulator command: '{}'"
                                             .format(request))
                    else:
                        reply = self._evalexec_nested_lists(request)
                except StopIteration:
                    exhausted.append(generator)
                    break
        for generator in exhausted:
            self.generators[cd].remove(generator)

    def _continue_simulation(self):
        for cd_generators in self.generators.values():
            if set(cd_generators) - self.passive_generators:
                return True
        return False

    def run(self):
        self.evaluator.execute(self.fragment.comb)
        self._commit_and_comb_propagate()

        while True:
            dt, rising, falling = self.time.tick()
            self.vcd.delay(dt)
            for cd in rising:
                self.evaluator.assign(self.fragment.clock_domains[cd].clk, 1)
                if cd in self.fragment.sync:
                    self.evaluator.execute(self.fragment.sync[cd])
                if cd in self.generators:
                    self._process_generators(cd)
            for cd in falling:
                self.evaluator.assign(self.fragment.clock_domains[cd].clk, 0)
            self._commit_and_comb_propagate()

            if not self._continue_simulation():
                break


def run_simulation(*args, **kwargs):
    with Simulator(*args, **kwargs) as s:
        s.run()


def passive(generator):
    @wraps(generator)
    def wrapper(*args, **kwargs):
        yield "passive"
        yield from generator(*args, **kwargs)
    return wrapper
