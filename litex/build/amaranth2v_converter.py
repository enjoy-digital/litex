#
# This file is part of LiteX.
#
# Copyright (c) 2026 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

import amaranth
from amaranth.back import verilog

import migen
from litex.gen.fhdl.module import LiteXModule
from litex.build.converter_common import (
    apply_aliases_with_conflict_checks,
    format_unresolved_port_error,
    parse_port_keyword,
    resolve_output_paths,
    write_text_if_different,
)

# Amaranth Compatibility ---------------------------------------------------------------------------

try:
    from amaranth.hdl import _ast as _am_ast
except ImportError:
    _am_ast = None

try:
    from amaranth.hdl import _ir as _am_ir
except ImportError:
    _am_ir = None


class _CompatSignalDict:
    """Identity-keyed dictionary fallback when Amaranth SignalDict is unavailable."""
    def __init__(self):
        self._data = {}

    def __setitem__(self, key, value):
        self._data[id(key)] = (key, value)

    def __getitem__(self, key):
        return self._data[id(key)][1]

    def get(self, key, default=None):
        item = self._data.get(id(key), None)
        return default if item is None else item[1]

    def __contains__(self, key):
        return id(key) in self._data


def _new_signal_dict(items=None):
    signal_dict_cls = getattr(_am_ast, "SignalDict", None) if _am_ast is not None else None
    if signal_dict_cls is not None:
        return signal_dict_cls(items or [])

    d = _CompatSignalDict()
    for k, v in (items or []):
        d[k] = v
    return d


def _prepare_fragment(module, ports, hierarchy):
    fragment_cls = getattr(_am_ir, "Fragment", None) if _am_ir is not None else None
    if fragment_cls is None or not hasattr(fragment_cls, "get"):
        raise RuntimeError("Amaranth Fragment API is unavailable in this version.")

    return fragment_cls.get(module, None).prepare(
        ports     = ports,
        hierarchy = hierarchy,
    )


def _build_netlist(fragment, name):
    builder = getattr(_am_ir, "build_netlist", None) if _am_ir is not None else None
    if builder is None:
        raise RuntimeError("Amaranth netlist builder API is unavailable in this version.")
    return builder(fragment, name=name)


def _convert_fragment(fragment, name):
    converter = getattr(verilog, "convert_fragment", None)
    if converter is None:
        raise RuntimeError("Amaranth Verilog convert_fragment API is unavailable in this version.")
    return converter(fragment, name=name)


_SIGNAL_TYPE = getattr(_am_ast, "Signal", None) if _am_ast is not None else None

# Amaranth2VConverter ------------------------------------------------------------------------------

class Amaranth2VConverter(LiteXModule):
    """
    Bridge module between Amaranth and LiteX/Migen.

    This class wraps an Amaranth `Module`, converts it to Verilog, and
    instantiates it as a Migen/LiteX `Instance`. It allows Amaranth-based
    designs to be integrated into LiteX-based SoCs.

    The converter allows Amaranth-based IP to be integrated into
    LiteX-based SoCs without modifying either design flow.

    Main responsibilities
    ---------------------
    - Manage clock domains for the wrapped Amaranth module
    - Convert the Amaranth design to Verilog
    - Resolve and map LiteX/Migen signals to Amaranth signals
    - Emit Verilog to the build directory and register it as a source

    Signal connections are declared using string keys in `core_params`
    and resolved recursively at finalization time.
    """

    def __init__(self, platform,
        name          = "amaranth2v_converter",
        module        = None,
        ports         = None,
        domains       = None,
        core_params   = None,
        clock_domains = None,
        output_dir    = None,
        ):
        """
        Parameters
        ----------
        platform : LiteX platform
            Target LiteX platform (used for output directory and source
            registration).

        name : str
            Name of the generated Verilog module and instantiated Instance.

        module : amaranth.Module or None
            Optional Amaranth module to be added as a submodule of the
            internal wrapper module.

        ports : dict[str, migen.Signal]
            Mapping between string-encoded port names and LiteX/Migen signals.

            Format: <dir>_<path>

            Where:
                <dir>  ::= i | o | io
                <path> ::= name { "_" name }*

            Form may be:
            - i_rx_data to connect migen Signal to wrapper module.rx.data
            - o__bus_pullup_o where _bus is an internal object (Record for example)
              with a pullup sub Record containing only a sub sub Record o
            - Clock And Reset signals must be <dir>_cdname_[clk|rst]

        domains : list[str] or None
            List of clock domain names to create in the Amaranth wrapper.
            The 'sync' domain is always added if missing.

        core_params : dict[str, migen.Signal] or None
            Deprecated alias for `ports`.

        clock_domains : list[str] or None
            Deprecated alias for `domains`.

        output_dir : str or None
            Optional override for the Verilog output directory.
        """
        self.platform    = platform
        self.name        = name
        self.output_dir  = output_dir

        normalized = apply_aliases_with_conflict_checks(
            {
                "ports"        : ports,
                "core_params": core_params,
                "domains"      : domains,
                "clock_domains": clock_domains,
            },
            alias_map={
                "ports"  : ("ports", "core_params"),
                "domains": ("domains", "clock_domains"),
            },
        )

        # Internal Amaranth wrapper module
        self.m           = amaranth.Module()

        # List of LiteX <-> Amaranth signal connections (direction, amaranth_signal, migen_signal)
        self.conn_list   = []

        # Port aliases.
        ports = normalized["ports"]
        self.ports = ports or dict()
        # Backward-compatible public attribute.
        self.core_params = self.ports

        # Domain aliases.
        domains = normalized["domains"]
        domains = domains or list()

        # Add provided Amaranth module as submodules
        if module is not None:
            self.m.submodules += module
            self._module = module

        # Ensure sync domain exists
        if "sync" not in domains:
            domains.append("sync")

        for cd in domains:
            self.add_clock_domain(cd)

    def add_clock_domain(self, name):
        """
        Add a clock domain to the internal Amaranth module.

        Parameters
        ----------
        name : str
            Name of the clock domain.
        """
        setattr(self.m.domains, name, amaranth.ClockDomain(name))

    def get_instance(self):
        """
        Create a Migen `Instance` of the generated Verilog module.

        Returns
        -------
        migen.Instance
            Instance with ports connected according to `conn_list`.

        Notes
        -----
        Port names and directions are inferred during Verilog generation
        and stored in `self.amaranth_name_map`.
        """
        connections = {}

        for d, n, m in self.conn_list:
            name, direction = self.amaranth_name_map[n]
            s = f"{direction}_{name}"

            assert d == direction, f'Mismatch direction for signal {name}: expected {d} seen {direction}.'
            assert s not in connections, f'Signal {s} connected multiple times.'

            connections[s] = m

        return migen.Instance(self.name, **connections)

    def generate_verilog(self):
        """
        Convert the internal Amaranth module to Verilog.

        Returns
        -------
        str
            Generated Verilog source code.

        Side Effects
        ------------
        - Builds a mapping between Amaranth signals and generated Verilog
          port names and directions (`self.amaranth_name_map`)
        - Resolves clock and reset signals for all declared clock domains
        """
        ports = [n for _, n, _ in self.conn_list]

        fragment = _prepare_fragment(self.m, ports=ports, hierarchy=(self.name,))

        v, _name_map = _convert_fragment(fragment, name=self.name)
        netlist      = _build_netlist(fragment, name=self.name)

        ports_i  = set(getattr(netlist.top, "ports_i", ()))
        ports_o  = set(getattr(netlist.top, "ports_o", ()))
        ports_io = set(getattr(netlist.top, "ports_io", ()))

        def get_direction(name):
            if name in ports_o:
                return "o"
            if name in ports_i:
                return "i"
            if name in ports_io:
                return "io"
            raise ValueError(f"Unable to infer direction for generated port '{name}'")

        # Map Amaranth signals to Verilog port names and directions
        self.amaranth_name_map = _new_signal_dict(
            (sig, (name, get_direction(name)))
            for name, sig, _ in fragment.ports
        )

        # Alias clock and reset signals to their corresponding domain ports
        for name, domain in fragment.fragment.domains.items():
            if domain.clk in self.amaranth_name_map:
                self.amaranth_name_map[amaranth.ClockSignal(name)] = self.amaranth_name_map[domain.clk]
            if domain.rst in self.amaranth_name_map:
                self.amaranth_name_map[amaranth.ResetSignal(name)] = self.amaranth_name_map[domain.rst]

        return v

    def _iter_signals(self, obj, rem_lst):
        """
        Recursively resolve a signal by progressively grouping path elements.

        This method performs a depth-first search and backtracks over
        all possible underscore groupings.

        Parameters
        ----------
        obj : object
            Current object being inspected.

        name : str or None
            Unused legacy parameter (kept for compatibility).

        rem_lst : list[str]
            Remaining path components.

        Returns
        -------
        amaranth.Signal or None
        """
        if obj is None:
            return None
        # it's a Signal -> it's the solution
        if _SIGNAL_TYPE is not None and isinstance(obj, _SIGNAL_TYPE):
            return obj

        sig = None

        for i in range(1, len(rem_lst) + 1):
            # Extract name from remaining list
            name = "_".join(rem_lst[:i])

            if type(obj) is amaranth.Record:
                subobj = getattr(obj, "fields", None)
                if subobj is not None:
                    subobj = subobj.get(name, None)
            else:
                subobj = getattr(obj, name, None)
            # Search for the next level.
            sig = self._iter_signals(subobj, rem_lst[i:])
            # found -> stop
            if sig is not None:
                break

        return sig

    def connect_wrapper(self):
        """
        Resolve and register all LiteX ↔ Amaranth signal connections.

        Resolution order:
        1. Wrapper module
        2. Provided submodule (recursive)
        3. Clock domain signals (cdname_clk / cdname_rst)

        Raises
        ------
        ValueError
            If a signal cannot be resolved.
        """
        resolved = _new_signal_dict()

        for kw, v in self.ports.items():
            d, parts = self._parse_port_keyword(kw)

            # Wrapper-level resolution.
            wrapper_head = parts[0]
            am_sig       = getattr(self.m, wrapper_head, None)

            # Recursive submodule resolution
            if am_sig is None and hasattr(self, "_module"):
                am_sig = self._iter_signals(self._module, parts)

            # Wrapper clock domain (cdname_clk or cdname_rst).
            if am_sig is None and len(parts) >= 2:
                # join kw with last word
                cd_name = "_".join(parts[:-1])
                candr   = parts[-1]
                cd      = self.m._domains.get(cd_name, None)
                if cd is not None:
                    am_sig = getattr(cd, candr, None)

            if am_sig is None:
                raise ValueError(format_unresolved_port_error(
                    kw            = kw,
                    d             = d,
                    parts         = parts,
                    wrapper_head  = wrapper_head,
                    has_submodule = hasattr(self, "_module"),
                    domains       = self.m._domains.keys(),
                    target        = "Amaranth module",
                ))

            previous_kw = resolved.get(am_sig, None)
            if previous_kw is not None:
                raise ValueError(
                    f"Ambiguous ports: both '{previous_kw}' and '{kw}' resolve to the same Amaranth signal.")
            resolved[am_sig] = kw

            self.conn_list.append((d, am_sig, v))

    def do_finalize(self):
        """
        Finalize the module during the LiteX build process.

        This method:
        - Resolves all signal connections
        - Generates and writes Verilog code produced by Amaranth
        - Registers the Verilog file as a platform source
        - Instantiates the generated module
        """
        src_dir, v_file = resolve_output_paths(
            platform   = self.platform,
            output_dir = self.output_dir,
            name       = self.name)

        # Resolve connections
        self.connect_wrapper()

        # Generate and write Verilog
        write_text_if_different(v_file, self.generate_verilog())

        # Register generated source
        self.platform.add_source(v_file)

        # Add an Instance to map verilog in the LiteX gateware
        self.specials += self.get_instance()

    @staticmethod
    def _parse_port_keyword(kw):
        return parse_port_keyword(kw)
