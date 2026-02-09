#
# This file is part of LiteX.
#
# Copyright (c) 2026 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

import amaranth
from amaranth.hdl import _ast, _ir
from amaranth.back import verilog

import migen
from litex.gen.fhdl.module import LiteXModule

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

        core_params : dict[str, migen.Signal]
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

        clock_domains : list[str] or None
            List of clock domain names to create in the Amaranth wrapper.
            The 'sync' domain is always added if missing.

        output_dir : str or None
            Optional override for the Verilog output directory.
        """
        self.platform    = platform
        self.name        = name
        self.output_dir  = output_dir

        # Internal Amaranth wrapper module
        self.m           = amaranth.Module()

        # List of LiteX <-> Amaranth signal connections (direction, amaranth_signal, migen_signal)
        self.conn_list   = []

        # Core parameters
        self.core_params = {True: core_params, False: dict()}[core_params is not None]

        # Clock domains
        clock_domains    = {True: clock_domains, False: list()}[clock_domains is not None]

        # Add provided Amaranth module as submodules
        if module is not None:
            self.m.submodules += module
            self._module = module

        # Ensure sync domain exists
        if "sync" not in clock_domains:
            clock_domains.append("sync")

        for cd in clock_domains:
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

        fragment = _ir.Fragment.get(self.m, None).prepare(
            ports     = ports,
            hierarchy = (self.name,)
        )

        v, _name_map = verilog.convert_fragment(fragment, name=self.name)
        netlist      = _ir.build_netlist(fragment, name=self.name)

        # Map Amaranth signals to Verilog port names and directions
        self.amaranth_name_map = _ast.SignalDict(
            (sig, (name, "o" if name in netlist.top.ports_o else "i"))
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
        if type(obj) is amaranth.Signal:
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
        for kw, v in self.core_params.items():
            # Direction prefix.
            # Extract direction and signals hierarchy.
            parts = re.findall(r'(?:^|_)(_[a-z]+|[a-z]+)', kw)
            if len(parts) == 0:
                raise ValueError(f"Cannot parse port name {kw}")

            d     = parts[0]
            parts = parts[1:]

            if d not in ("i", "o", "io"):
                raise ValueError(f"Invalid port '{kw}': must start with i_, o_ or io_")

            # Wrapper-level resolution.
            am_sig = getattr(self.m, parts[0], None)

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
                raise ValueError(f"Cannot resolve '{kw}' on Amaranth module.")

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
        output_dir = {True:  self.platform.output_dir, False: self.output_dir}[self.output_dir is None]

        src_dir = os.path.join(output_dir, self.name)
        v_file  = os.path.join(src_dir, f"{self.name}.v")

        os.makedirs(src_dir, exist_ok=True)

        # Resolve connections
        self.connect_wrapper()

        # Generate and write Verilog
        with open(v_file, "w") as f:
            f.write(self.generate_verilog())

        # Register generated source
        self.platform.add_source(v_file)

        # Add an Instance to map verilog in the LiteX gateware
        self.specials += self.get_instance()
