#
# This file is part of Migen and has been adapted/modified for LiteX.
#
# This file is Copyright (c) 2015-2016 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2018 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2016-2018 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2018-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 N. Engelhardt <nakengelhardt@gmail.com>
# This file is Copyright (c) 2018 Robin Ole Heinemann <robin.ole.heinemann@t-online.de>
# SPDX-License-Identifier: BSD-2-Clause

import os
import operator
import collections
import collections.abc
import inspect
from functools import wraps

from migen.fhdl.structure import *
from migen.fhdl.structure import (_Value, _Statement,
                                  _Operator, _Slice, _Part, _ArrayProxy,
                                  _Assign, _Fragment)
from migen.fhdl.bitcontainer import value_bits_sign
from migen.fhdl.tools import (list_targets, list_signals, group_by_targets, flat_iteration,
                              insert_resets, lower_specials)
from migen.fhdl.simplify import MemoryToArray
from migen.fhdl.specials import _MemoryLocation
from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen.sim.vcd import VCDWriter, DummyVCDWriter


def _get_fragment(fragment_or_module):
    return fragment_or_module if isinstance(fragment_or_module, _Fragment) else fragment_or_module.get_fragment()


def generate_gtkw_savefile(fragment_or_module, vns, savefile, dumpfile,
    clocks     = True,
    fsm_states = True,
    signals    = None,
    prefix     = ""):
    """Generate a GTKWave savefile for a litex.gen.sim VCD/FST dump.

    This helper is intentionally small and generic for unit simulations. The
    richer SoC helper in litex_sim can still add SoC-specific groups.
    """
    from litex.build.sim import gtkwave as gtkw

    if vns is None:
        raise ValueError("A signal namespace is required to generate a GTKWave savefile.")

    with gtkw.GTKWSave(vns, savefile=savefile, dumpfile=dumpfile, prefix=prefix) as save:
        if clocks:
            save.clocks()
        if fsm_states and isinstance(fragment_or_module, Module):
            save.fsm_states(fragment_or_module)
        for signal in signals or []:
            save.add(signal)


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


# Evaluator ----------------------------------------------------------------------------------------

class Evaluator:
    """Signal values and statements interpreter.

    The values are stored by Signal slot (an index allocated at the first access of the Signal), in
    the lists/dicts the compiled statements (Compiler) access directly: values (committed) and
    modifications (the assignments of the current delta cycle, applied by commit). eval/assign/
    execute interpret expressions/statements (generator requests, statements not compiled).
    """
    def __init__(self, clock_domains, replaced_memories):
        self.clock_domains     = clock_domains
        self.replaced_memories = replaced_memories
        self.slots             = dict() # Signal -> slot.
        self.signals           = []     # Slot   -> Signal.
        self.values            = []     # Slot   -> value.
        self.modifications     = dict() # Slot   -> value.

    def slot(self, signal):
        try:
            return self.slots[signal]
        except KeyError:
            slot = self.slots[signal] = len(self.values)
            self.signals.append(signal)
            self.values.append(signal.reset.value)
            return slot

    def value(self, signal):
        return self.values[self.slot(signal)]

    def commit(self):
        """Apply the modifications, return the slots of the Signals whose value changed."""
        values  = self.values
        changed = []
        for slot, value in self.modifications.items():
            if values[slot] != value:
                values[slot] = value
                changed.append(slot)
        self.modifications.clear()
        return changed

    def eval(self, node, postcommit=False):
        if isinstance(node, Constant):
            return node.value
        elif isinstance(node, Signal):
            slot = self.slot(node)
            if postcommit:
                try:
                    return self.modifications[slot]
                except KeyError:
                    pass
            return self.values[slot]
        elif isinstance(node, _Operator):
            operands = [self.eval(o, postcommit) for o in node.operands]
            if node.op == "-":
                if len(operands) == 1:
                    return -operands[0]
                else:
                    return operands[0] - operands[1]
            elif node.op == "m":
                return operands[1] if operands[0] else operands[2]
            elif node.op == "~":
                # Inversion of an unsigned value: width of its operand (not an infinite number of
                # ones, ex: ~ of a 1-bit Signal at 1 is 0).
                nbits, signed = value_bits_sign(node.operands[0])
                return ~operands[0] if signed else (~operands[0]) & (2**nbits - 1)
            else:
                return str2op[node.op](*operands)
        elif isinstance(node, _Slice):
            v = self.eval(node.value, postcommit)
            idx = range(node.start, node.stop)
            return sum(((v >> i) & 1) << j for j, i in enumerate(idx))
        elif isinstance(node, _Part):
            v = self.eval(node.value, postcommit)
            offset = self.eval(node.offset, postcommit)
            idx = range(offset, offset + node.width)
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
            self.modifications[self.slot(node)] = _truncate(value, node.nbits, node.signed)
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
        elif isinstance(node, _Part):
            full_value = self.eval(node.value, True)
            offset = self.eval(node.offset, True)
            start = offset
            stop = offset + node.width
            full_value &= ~((2**stop-1) - (2**start-1))
            value &= 2**(stop - start)-1
            full_value |= value << start
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
                    args.append(self.value(arg))
                print(s.s %(*args,))
            else:
                raise NotImplementedError


# Compiler -----------------------------------------------------------------------------------------

class Compiler:
    """Statements compiled to Python functions f(v, m) on the Evaluator slots.

    v is the committed values list and m the modifications dict of the Evaluator. The generated code
    has the Evaluator semantics: expressions on Python integers, truncated to the target width on
    assignment, ~ of an unsigned value masked to its width, reads of the committed values except for
    the partial assignments of a Signal (slices/parts: the previous assignments of the same
    statements are seen). A statement that can't be compiled is executed by the Evaluator.
    """
    _binary_ops = {"+", "-", "*", "&", "^", "|", "<", "<=", "==", "!=", ">", ">="}
    _shift_ops  = {">>>": ">>", "<<<": "<<"}

    class Unsupported(Exception):
        pass

    def __init__(self, evaluator):
        self.evaluator = evaluator
        self.namespace = {"_evaluator": evaluator}
        self.constants = 0
        self.temps     = 0
        self.reads     = set()

    # Expressions ----------------------------------------------------------------------------------

    def read(self, signal, postcommit=False):
        slot = self.evaluator.slot(signal)
        self.reads.add(slot)
        if postcommit:
            return f"m.get({slot}, v[{slot}])"
        return f"v[{slot}]"

    def constant(self, name, value):
        self.constants += 1
        name = f"_{name}{self.constants}"
        self.namespace[name] = value
        return name

    def expr(self, node, postcommit=False):
        if isinstance(node, Constant):
            return f"({node.value})"
        elif isinstance(node, Signal):
            return self.read(node, postcommit)
        elif isinstance(node, _Operator):
            operands = [self.expr(o, postcommit) for o in node.operands]
            if node.op == "m":
                return f"({operands[1]} if {operands[0]} else {operands[2]})"
            elif node.op == "~":
                nbits, signed = value_bits_sign(node.operands[0])
                if signed:
                    return f"(~{operands[0]})"
                return f"((~{operands[0]}) & {2**nbits - 1})"
            elif node.op == "-" and len(operands) == 1:
                return f"(-{operands[0]})"
            elif node.op in self._shift_ops:
                return f"({operands[0]} {self._shift_ops[node.op]} {operands[1]})"
            elif node.op in self._binary_ops and len(operands) == 2:
                return f"({operands[0]} {node.op} {operands[1]})"
            raise self.Unsupported(node.op)
        elif isinstance(node, _Slice):
            value = self.expr(node.value, postcommit)
            mask  = 2**(node.stop - node.start) - 1
            if node.start:
                return f"(({value} >> {node.start}) & {mask})"
            return f"({value} & {mask})"
        elif isinstance(node, _Part):
            value  = self.expr(node.value, postcommit)
            offset = self.expr(node.offset, postcommit)
            return f"(({value} >> {offset}) & {2**node.width - 1})"
        elif isinstance(node, Cat):
            elements = []
            shift    = 0
            for element in node.l:
                nbits = len(element)
                value = f"({self.expr(element, postcommit)} & {2**nbits - 1})"
                elements.append(f"({value} << {shift})" if shift else value)
                shift += nbits
            if not elements:
                return "(0)"
            return "(" + " | ".join(elements) + ")"
        elif isinstance(node, Replicate):
            nbits  = len(node.v)
            factor = sum(2**(i*nbits) for i in range(node.n))
            return f"(({self.expr(node.v, postcommit)} & {2**nbits - 1}) * {factor})"
        elif isinstance(node, _ArrayProxy):
            key  = f"min({len(node.choices) - 1}, {self.expr(node.key, postcommit)})"
            if all(isinstance(choice, Signal) for choice in node.choices):
                slots = tuple(self.evaluator.slot(choice) for choice in node.choices)
                self.reads.update(slots)
                slots = self.constant("a", slots)
                if postcommit:
                    return f"m.get({slots}[{key}], v[{slots}[{key}]])"
                return f"v[{slots}[{key}]]"
            choices = ", ".join(self.expr(choice, postcommit) for choice in node.choices)
            return f"({choices},)[{key}]"
        elif isinstance(node, ClockSignal):
            return self.read(self.evaluator.clock_domains[node.cd].clk, postcommit)
        elif isinstance(node, ResetSignal):
            rst = self.evaluator.clock_domains[node.cd].rst
            if rst is None:
                if node.allow_reset_less:
                    return "(0)"
                raise self.Unsupported(node)
            return self.read(rst, postcommit)
        raise self.Unsupported(node)

    # Assignments ----------------------------------------------------------------------------------

    def temp(self):
        self.temps += 1
        return f"_t{self.temps}"

    def truncate(self, value, nbits, signed):
        mask = 2**nbits - 1
        if signed and nbits:
            half = 2**(nbits - 1)
            return f"((({value}) + {half}) & {mask}) - {half}"
        return f"({value}) & {mask}"

    def assign(self, node, value, indent, lines):
        pad = "    "*indent
        if isinstance(node, Signal):
            if node.variable:
                raise self.Unsupported(node)
            lines.append(f"{pad}m[{self.evaluator.slot(node)}] = {self.truncate(value, node.nbits, node.signed)}")
        elif isinstance(node, Cat):
            temp = self.temp()
            lines.append(f"{pad}{temp} = {value}")
            for element in node.l:
                nbits = len(element)
                self.assign(element, f"{temp} & {2**nbits - 1}", indent, lines)
                lines.append(f"{pad}{temp} >>= {nbits}")
        elif isinstance(node, (_Slice, _Part)):
            if isinstance(node, _Slice):
                start = str(node.start)
                width = node.stop - node.start
            else:
                start = self.temp()
                width = node.width
                lines.append(f"{pad}{start} = {self.expr(node.offset, postcommit=True)}")
            full = self.temp()
            mask = 2**width - 1
            lines.append(f"{pad}{full} = ({self.expr(node.value, postcommit=True)} & ~({mask} << {start})) "
                         f"| ((({value}) & {mask}) << {start})")
            self.assign(node.value, full, indent, lines)
        elif isinstance(node, _ArrayProxy):
            choices = node.choices
            widths  = {(choice.nbits, choice.signed) for choice in choices if isinstance(choice, Signal)}
            if (len(widths) != 1) or any(not isinstance(choice, Signal) or choice.variable for choice in choices):
                raise self.Unsupported(node)
            slots = self.constant("a", tuple(self.evaluator.slot(choice) for choice in choices))
            key   = f"min({len(choices) - 1}, {self.expr(node.key)})"
            nbits, signed = widths.pop()
            lines.append(f"{pad}m[{slots}[{key}]] = {self.truncate(value, nbits, signed)}")
        else:
            raise self.Unsupported(node)

    # Statements -----------------------------------------------------------------------------------

    def statements(self, statements, indent, lines):
        pad   = "    "*indent
        empty = len(lines)
        for s in statements:
            if isinstance(s, _Assign):
                self.assign(s.l, self.expr(s.r), indent, lines)
            elif isinstance(s, If):
                lines.append(f"{pad}if {self.expr(s.cond)} & {2**len(s.cond) - 1}:")
                self.statements(s.t, indent + 1, lines)
                if s.f:
                    lines.append(f"{pad}else:")
                    self.statements(s.f, indent + 1, lines)
            elif isinstance(s, Case):
                nbits, signed = value_bits_sign(s.test)
                test = self.temp()
                lines.append(f"{pad}{test} = {self.truncate(self.expr(s.test), nbits, signed)}")
                keyword = "if"
                for k, v in s.cases.items():
                    if isinstance(k, Constant):
                        lines.append(f"{pad}{keyword} {test} == ({k.value}):")
                        self.statements(v, indent + 1, lines)
                        keyword = "elif"
                if "default" in s.cases:
                    if keyword == "if":
                        self.statements(s.cases["default"], indent, lines)
                    else:
                        lines.append(f"{pad}else:")
                        self.statements(s.cases["default"], indent + 1, lines)
            elif isinstance(s, collections.abc.Iterable):
                self.statements(s, indent, lines)
            else:
                raise self.Unsupported(s)
        if len(lines) == empty:
            lines.append(f"{pad}pass")

    # Functions ------------------------------------------------------------------------------------

    def function(self, statements):
        """Function f(v, m) executing the statements and the slots it reads (None when a statement
        is executed by the Evaluator: reads unknown)."""
        self.reads  = set()
        lines       = []
        reads_known = True
        for statement in flat_iteration(statements):
            try:
                statement_lines = []
                self.statements([statement], 1, statement_lines)
                lines += statement_lines
            except (self.Unsupported, RecursionError):
                lines.append(f"    _evaluator.execute([{self.constant('s', statement)}])")
                reads_known = False
        if not lines:
            lines.append("    pass")
        source = "def _f(v, m):\n" + "\n".join(lines)
        try:
            exec(compile(source, "<litex.gen.sim>", "exec"), self.namespace)
        except (SyntaxError, RecursionError, MemoryError):
            # Ex: too many levels of indentation.
            evaluator = self.evaluator
            return (lambda v, m: evaluator.execute(statements)), None
        return self.namespace.pop("_f"), (set(self.reads) if reads_known else None)


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


# Simulator ----------------------------------------------------------------------------------------

# TODO: instances via Iverilog/VPI
class Simulator:
    """Event-driven simulation of a fragment with its statements compiled to Python (Compiler).

    On each clock edge, the sync statements of the clock domain then its generators are executed,
    the modifications are committed and the comb statements are propagated: a comb group (statements
    sharing targets) is executed again on the next delta cycle only when a Signal it reads (or one of
    its targets, assigned from elsewhere) changed, until the values are stable. The generators see
    the committed values (their assignments are visible on the next cycle).
    """
    def __init__(self, fragment_or_module, generators, clocks={"sys": 10}, vcd_name=None,
                 gtkw_name=None, special_overrides={}):
        self.fragment_or_module = fragment_or_module
        self.gtkw_name          = gtkw_name
        self.gtkw_generated     = False

        if gtkw_name is not None and vcd_name is None:
            vcd_name = os.path.splitext(gtkw_name)[0] + ".vcd"

        self.fragment = _get_fragment(fragment_or_module)

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

        # Statements compiled to Python functions.
        compiler = Compiler(self.evaluator)
        # Sync statements: executed on the rising edge of their clock domain.
        self._sync = {cd: compiler.function(statements)[0]
            for cd, statements in self.fragment.sync.items()}
        # Comb statements: groups of statements sharing targets (the targets of the groups are
        # disjoint: their order in a delta cycle is free), executed again in the next delta cycle
        # when a Signal they read (or one of their targets) changed. The groups with statements
        # executed by the Evaluator (reads unknown) are executed on every delta cycle.
        self._comb_groups = []
        self._comb_always = []
        self._comb_deps   = dict() # Slot -> groups.
        for targets, statements in group_by_targets(self.fragment.comb):
            function, reads = compiler.function(statements)
            group = len(self._comb_groups)
            self._comb_groups.append(function)
            if reads is None:
                self._comb_always.append(group)
                continue
            for slot in reads | {self.evaluator.slot(target) for target in targets}:
                self._comb_deps.setdefault(slot, []).append(group)
        self._clk_slots = {cd.name: self.evaluator.slot(cd.clk) for cd in self.fragment.clock_domains}

        self._vcd_enabled = vcd_name is not None
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
            self.vcd.init(signals, clock_domains=self.fragment.clock_domains)
            for signal in sorted(signals, key=lambda x: x.duid):
                self.vcd.set(signal, signal.reset.value)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        if self.gtkw_name is not None and not self.gtkw_generated:
            self.generate_gtkw_savefile(self.gtkw_name)
        self.vcd.close()

    def generate_gtkw_savefile(self, savefile=None, **kwargs):
        if self.vcd.vns is None:
            raise ValueError("GTKWave savefile generation requires VCD generation.")
        if savefile is None:
            savefile = self.gtkw_name
        if savefile is None:
            savefile = os.path.splitext(self.vcd.filename)[0] + ".gtkw"
        generate_gtkw_savefile(
            fragment_or_module = self.fragment_or_module,
            vns                = self.vcd.vns,
            savefile           = savefile,
            dumpfile           = self.vcd.filename,
            **kwargs)
        self.gtkw_generated = True

    def _commit_and_comb_propagate(self):
        evaluator = self.evaluator
        v, m      = evaluator.values, evaluator.modifications
        groups    = self._comb_groups
        deps      = self._comb_deps
        always    = self._comb_always
        vcd       = self._vcd_enabled
        modified     = evaluator.commit()
        all_modified = set(modified)
        while modified:
            dirty = set(always)
            for slot in modified:
                slot_groups = deps.get(slot)
                if slot_groups is not None:
                    dirty.update(slot_groups)
            for group in sorted(dirty):
                groups[group](v, m)
            modified = evaluator.commit()
            if vcd:
                all_modified.update(modified)
        if vcd:
            for slot in all_modified:
                self.vcd.set(evaluator.signals[slot], v[slot])

    def _evalexec_nested_lists(self, x):
        if isinstance(x, list):
            return [self._evalexec_nested_lists(e) for e in x]
        elif isinstance(x, _Value):
            return self.evaluator.eval(x)
        elif isinstance(x, _Statement):
            self.evaluator.execute([x])
            return None
        else:
            raise ValueError("Invalid simulator exec/eval request", x)

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
                        try:
                            reply = self._evalexec_nested_lists(request)
                        except Exception as e:
                            tb = inspect.getframeinfo(generator.gi_frame)
                            print("While evaluating the following generator, an error occurred:")
                            print("  File {}, line {}, in {}".format(tb.filename, tb.lineno, tb.function))
                            for c in tb.code_context or []:
                                print("    ", c.lstrip())
                            raise
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
        evaluator = self.evaluator
        v, m      = evaluator.values, evaluator.modifications
        for group in self._comb_groups:
            group(v, m)
        self._commit_and_comb_propagate()

        while True:
            dt, rising, falling = self.time.tick()
            self.vcd.delay(dt)
            for cd in rising:
                m[self._clk_slots[cd]] = 1
                sync = self._sync.get(cd)
                if sync is not None:
                    sync(v, m)
                if cd in self.generators:
                    self._process_generators(cd)
            for cd in falling:
                m[self._clk_slots[cd]] = 0
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
