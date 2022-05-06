# This file is part of LiteX.
#
# Copyright (c) 2021 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause
#

import os
import re

from typing import Optional, Sequence, Any, Callable, Generator, Dict, Tuple

from migen import *

from litex.gen.fhdl.namer import Namespace

from litex.soc.interconnect import stream


class SigTrace:
    """Trace configuration for a single signal"""
    def __init__(self,
            name: str,
            signal: Signal,
            alias: str = None,
            color: str = None,
            filter_file: str = None):
        self.name = name
        self.signal = signal
        self.alias = alias
        self.color = color
        self.filter_file = filter_file


# Type aliases
Regex = str
SigMapper = Callable[[Sequence[SigTrace]], Sequence[SigTrace]]


class GTKWSave:
    """Generator of pretty GTKWave savefiles from SoC signals

    Usage example:
    ```
    builder = Builder(soc, **builder_kwargs)
    vns = builder.build(run=False, **build_kwargs)

    with GTKWSave(vns, savefile=savefile, dumpfile=dumpfile) as gtkw:
        gtkw.clocks()
        gtkw.fsm_states(soc)
        gtkw.add(soc.bus.slaves["main_ram"])
    ```
    """

    def __init__(self,
            vns: Namespace,
            savefile: str,
            dumpfile: str,
            filtersdir: str = None,
            treeopen: bool = True,
            prefix: str = "TOP.sim."):
        """Crate savefile generator for the namespace.

        `prefix` is prepended to all signal names and defaults to the one used by Litex simulator.
        """
        self.vns = vns   # Namespace output of Builder.build, required to resolve signal names
        self.prefix = prefix
        self.savefile = savefile
        self.dumpfile = dumpfile
        self.filtersdir = filtersdir
        self.treeopen = treeopen
        if self.filtersdir is None:
            self.filtersdir = os.path.dirname(self.savefile)

    def __enter__(self):
        # pyvcd: https://pyvcd.readthedocs.io/en/latest/vcd.gtkw.html
        from vcd.gtkw import GTKWSave
        self.file = open(self.savefile, "w")
        self.gtkw = GTKWSave(self.file)
        self.gtkw.dumpfile(self.dumpfile)
        if self.treeopen:
            modules = self.prefix.rstrip(".").split(".")
            for i in range(len(modules)):
                if modules[i]:
                    self.gtkw.treeopen(".".join(modules[:i + 1]))
        self.gtkw.sst_expanded(True)
        return self

    def __exit__(self, type, value, traceback):
        self.file.close()
        print("\nGenerated GTKWave save file at: {}\n".format(self.savefile))

    def name(self, sig: Signal) -> str:
        bits = ""
        if len(sig) > 1:
            bits = "[{}:0]".format(len(sig) - 1)
        return self.vns.get_name(sig) + bits

    def signal(self, signal: Signal):
        self.gtkw.trace(self.prefix + self.name(signal))

    def common_prefix(self, names: Sequence[str]) -> str:
        prefix = os.path.commonprefix(names)
        last_underscore = prefix.rfind("_")
        return prefix[:last_underscore + 1]

    def group(self,
            signals: Sequence[Signal],
            group_name: str = None,
            alias: bool = True,
            closed: bool = True,
            mappers: Optional[Sequence[SigMapper]] = None,
            translation_files: Optional[Sequence[str]] = None,
            **kwargs):
        mappers = mappers or []
        translation_files = translation_files or {}
        if len(signals) == 1:
            return self.signal(signals[0])

        names = [self.name(s) for s in signals]
        common = self.common_prefix(names)

        make_alias = (lambda n: n[len(common):]) if alias else (lambda n: n)
        sigs = [
            SigTrace(name=n, signal=s, alias=make_alias(n))
            for i, (s, n) in enumerate(zip(signals, names))
        ]

        for sig, file in zip(sigs, translation_files):
            sig.filter_file = file

        for mapper in mappers:
            sigs = list(mapper(sigs))

        with self.gtkw.group(group_name or common.strip("_"), closed=closed):
            for s in sigs:
                self.gtkw.trace(self.prefix + s.name, alias=s.alias, color=s.color,
                    translate_filter_file=s.filter_file, **kwargs)

    def by_regex(self, regex: Regex, **kwargs):
        pattern = re.compile(regex)
        signals = list(filter(
            lambda sig: pattern.search(self.vns.pnd[sig]),
            self.vns.pnd.keys()))
        assert len(signals) > 0, "No match found for {}".format(regex)
        return self.group(signals, **kwargs)

    def clocks(self, **kwargs):
        clks = [cd.clk for cd in self.vns.clock_domains]
        self.group(clks, group_name="clocks", alias=False, closed=False, **kwargs)

    def add(self, obj: Any, no_defaults=False, **kwargs):
        # TODO: add automatic default handlers for Litex types (e.g. WishBone, AXI, ...)

        def default_mappers(types, mappers):
            if not no_defaults and isinstance(obj, types):
                kwargs["mappers"] = DEFAULT_ENDPOINT_MAPPERS + kwargs.get("mappers", [])

        if isinstance(obj, Record):
            # automatic settings for supported Record types
            default_mappers(stream.Endpoint, DEFAULT_ENDPOINT_MAPPERS)
            self.group([s for s, _ in obj.iter_flat()], **kwargs)
        elif isinstance(obj, Signal):
            self.signal(obj)
        elif self._is_module_with_attrs(obj, ["sink", "source"], types=stream.Endpoint, required=any):
            self._add_groupped_attrs(obj, ["sink", "source"], **kwargs)  # recurse to Record->Endpoint handler
        else:
            raise NotImplementedError(type(obj), obj)

    def _add_groupped_attrs(self, obj, attrs, **kwargs):
        # add given attributes of an object in an encapsulating group, with attribute names as subgroup names
        with self.gtkw.group(kwargs["group_name"], closed=kwargs.get("closed", True)):
            for attr in attrs:
                if hasattr(obj, attr):
                    new_kwargs = kwargs.copy()
                    new_kwargs["group_name"] = attr
                    self.add(getattr(obj, attr), **new_kwargs)

    def make_fsm_state_translation(self, fsm: FSM) -> str:
        # generate filter file
        from vcd.gtkw import make_translation_filter
        translations = list(fsm.decoding.items())
        filename = "filter__{}.txt".format(self._strip_bits(self.name(fsm.state)))
        filepath = os.path.join(self.filtersdir, filename)
        with open(filepath, 'w') as f:
            f.write(make_translation_filter(translations, size=len(fsm.state)))
        return filepath

    def iter_submodules(self, parent: Module) -> Generator[Module, None, None]:
        for name, module in getattr(parent, "_submodules", []):
            yield module
            yield from self.iter_submodules(module)

    def make_fsm_state_alias(self, state: Signal):
        # Try to improve state name, as the defaults are usually hard to decipher.
        # This will make sure to include the name of the module that has the FSM,
        # but still there are some issues, e.g. we always add number to all names.
        alias = ""
        for name, num in reversed(state.backtrace):
            if alias.startswith(name):
                continue
            if name == "subfragments":
                break
            alias = "{}{}_{}".format(name, num, alias)
        return alias.strip("_")

    def fsm_states(self, soc: Module, alias: bool = True, **kwargs):
        fsms = list(filter(lambda module: isinstance(module, FSM), self.iter_submodules(soc)))
        states = [fsm.state for fsm in fsms]
        files = [self.make_fsm_state_translation(fsm) for fsm in fsms]

        if alias:
            aliases = {state: self.make_fsm_state_alias(state) for state in states}

            def add_alias(sig):
                sig.alias = aliases.get(sig.signal, None)
                return sig

            kwargs["mappers"] = [lambda sigs: map(add_alias, sigs)] + kwargs.get("mappers", [])

        self.group(states, group_name="FSM states", translation_files=files, **kwargs)

    @staticmethod
    def _strip_bits(name: str) -> str:
        if name.endswith("]") and "[" in name:
            name = name[:name.rfind("[")]
        return name

    @staticmethod
    def _is_module_with_attrs(obj, attrs, types, required) -> bool:
        if not isinstance(obj, Module):
            return False
        available = map(lambda a: hasattr(obj, a) and isinstance(getattr(obj, a), types), attrs)
        return required(available)

# Generic mappers ----------------------------------------------------------------------------------

def _regex_map(
        sig: SigTrace,
        patterns: Sequence[Regex],
        on_match: Callable[[SigTrace, Regex], Optional[SigTrace]],
        on_no_match: Callable[[SigTrace], Optional[SigTrace]],
        remove_bits: bool = True) -> Optional[SigTrace]:
    # Given `patterns` return `on_match(sig, pattern)` if any pattern matches or else `on_no_match(sig)`
    alias = sig.alias
    if remove_bits:  # get rid of signal bits (e.g. wb_adr[29:0])
        alias = GTKWSave._strip_bits(alias)
    for pattern in patterns:
        if pattern.search(alias):
            return on_match(sig, pattern)
    return on_no_match(sig)

def suffixes2re(strings: Sequence[str]) -> Sequence[Regex]:
    return ["{}$".format(s) for s in strings]

def prefixes2re(strings: Sequence[str]) -> Sequence[Regex]:
    return ["^{}".format(s) for s in strings]

def strings2re(strings: Sequence[str]) -> Sequence[Regex]:
    return suffixes2re(prefixes2re(strings))

def regex_filter(patterns: Sequence[Regex], negate: bool = False, **kwargs) -> SigMapper:
    """Filter out the signals that do not match regex patterns (or do match if negate=True)."""
    patterns = list(map(re.compile, patterns))
    def filt(sigs):
        def map_sig(sig):
            return _regex_map(sig, patterns,
                on_match = lambda s, p: (s if not negate else None),
                on_no_match = lambda s: (None if not negate else s),
                **kwargs)
        return list(filter(None, map(map_sig, sigs)))
    return filt

def regex_sorter(patterns: Sequence[Regex], unmatched_last: bool = True, **kwargs) -> SigMapper:
    """Sort signals accorting to the order of patterns. Unmatched are placed last/first."""
    def sort(sigs):
        order = {re.compile(pattern): i for i, pattern in enumerate(patterns)}
        return sorted(sigs, key=lambda sig: _regex_map(sig, order.keys(),
            on_match    = lambda s, p: order[p],
            on_no_match = lambda s: len(order) if unmatched_last else -1,
            **kwargs))
    return sort

def regex_colorer(
        color_patterns: Dict[str, Sequence[Regex]],
        default: Optional[str] = None,
        **kwargs) -> SigMapper:
    """Apply colors to signals based on per-color patterns with an optional default on no match."""
    colors = {}
    for color, patterns in color_patterns.items():
        for pattern in patterns:
            colors[re.compile(pattern)] = color

    def add_color(sig, color):
        sig.color = color

    def add_colors(sigs):
        for sig in sigs:
            _regex_map(sig, colors.keys(),
                on_match = lambda s, p: add_color(s, colors[p]),
                on_no_match = lambda s: add_color(s, default),
                **kwargs)
        return sigs

    return add_colors

# Mappers ------------------------------------------------------------------------------------------

def wishbone_sorter(**kwargs) -> SigMapper:
    suffixes = ["cyc", "stb", "ack", "adr", "we", "sel", "dat_w", "dat_r"]
    return regex_sorter(suffixes2re(suffixes), **kwargs)

def wishbone_colorer(**kwargs) -> SigMapper:
    return regex_colorer({
        "normal": suffixes2re(["cyc", "stb", "ack"]),
        "yellow": suffixes2re(["adr", "we", "sel"]),
        "orange": suffixes2re(["dat_w"]),
        "red":    suffixes2re(["dat_r"]),
    }, default="indigo", **kwargs)

def dfi_sorter(phases: bool = True, nphases_max: int = 8, **kwargs) -> SigMapper:
    suffixes = [
        "cas_n", "ras_n", "we_n",
        "address", "bank",
        "wrdata_en", "wrdata", "wrdata_mask",
        "rddata_en", "rddata", "rddata_valid",
    ]
    if phases:
        patterns = []
        for phase in range(nphases_max):
            patterns.extend(["p{}_{}".format(phase, suffix) for suffix in suffixes])
    else:
        patterns = suffixes
    return regex_sorter(suffixes2re(patterns), **kwargs)

def dfi_per_phase_colorer(nphases_max: int = 8, **kwargs) -> SigMapper:
    colors = ["normal", "yellow", "orange", "red"]
    color_patterns = {}
    for p in range(nphases_max):
        color = colors[p % len(colors)]
        patterns = color_patterns.get(color, [])
        patterns.append("p{}_".format(p))
        color_patterns[color] = patterns
    return regex_colorer(color_patterns, default="indigo", **kwargs)

def dfi_in_phase_colorer(**kwargs) -> SigMapper:
    return regex_colorer({
        "normal": suffixes2re(["cas_n", "ras_n", "we_n"]),
        "yellow": suffixes2re(["address", "bank"]),
        "orange": suffixes2re(["wrdata_en", "wrdata", "wrdata_mask"]),
        "red":    suffixes2re(["rddata_en", "rddata", "rddata_valid"]),
    }, default="indigo", **kwargs)

def endpoint_filter(firstlast=False, payload=True, param=True, **kwargs) -> SigMapper:
    patterns = suffixes2re(["valid", "ready"])
    if firstlast: patterns += suffixes2re(["first", "last"])
    if payload:   patterns += ["payload_"]
    if param:     patterns += ["param_"]
    return regex_filter(patterns, **kwargs)

def endpoint_sorter(**kwargs) -> SigMapper:
    return regex_sorter(suffixes2re(["valid", "ready", "first", "last"]), **kwargs)

def endpoint_colorer(**kwargs) -> SigMapper:
    return regex_colorer({
        "yellow": suffixes2re(["valid"]),
        "orange": suffixes2re(["ready"]),
        "indigo": suffixes2re(["first", "last"]),
    }, default="normal", **kwargs)

DEFAULT_ENDPOINT_MAPPERS = [endpoint_sorter(), endpoint_colorer()]
