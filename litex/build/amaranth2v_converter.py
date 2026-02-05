#
# This file is part of LiteX.
#
# Copyright (c) 2026 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

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

    Main responsibilities:
    - Manage clock domains for the wrapped Amaranth module
    - Convert the Amaranth design to Verilog
    - Map LiteX/Migen signals to Amaranth ports
    - Emit Verilog to the build directory and register it as a source

    The conversion is performed during LiteX finalization, ensuring that
    the generated Verilog reflects the fully elaborated Amaranth design.
    """

    def __init__(self, platform,
        name          = "amaranth2v_converter",
        module        = None,
        conn_list     = None,
        clock_domains = None,
        output_dir    = None
        ):
        """
        Parameters
        ----------
        platform : LiteX platform
            Target LiteX platform (used for output directory and source
            registration).

        name : str
            Name of the generated Verilog module and instance.

        module : amaranth.Module or None
            Optional Amaranth submodule to add to the internal wrapper module.

        conn_list : list of (Signal, Signal)
            List of (Amaranth signal, Migen signal) connections used to
            wire the generated instance.

            Unlike `Instance` or `VHD2VConverter`, a dictionary mapping
            Verilog port names to LiteX/Migen `Signal`s is not used here.
            Instead, this list contains pairs of `Amaranth.Signal` and
            `Migen.Signal`.

            This difference is required because Verilog port names are
            not always fully known before the Amaranth-to-Verilog
            conversion step.

        clock_domains : list of str
            List of clock domain names to create in the Amaranth module.
            The 'sync' domain is always added if missing.

        output_dir : str or None
            Optional override for the Verilog output directory.
        """
        self.platform   = platform
        self.name       = name
        self.output_dir = output_dir

        # Internal Amaranth wrapper module
        self.m           = amaranth.Module()

        # List of LiteX <-> Amaranth signal connections
        self.conn_list   = {True: conn_list, False: list()}[conn_list is not None]

        # List of clock domains
        clock_domains    = {True: clock_domains, False: list()}[clock_domains is not None]

        # Add provided Amaranth module as a submodule
        if module is not None:
            self.m.submodules += module

        # Manage Amaranth ClockDomain creation.
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

        for n, m in self.conn_list:
            name, direction = self.amaranth_name_map[n]
            s = f'{direction}_{name}'

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
        ports = [n for n, _ in self.conn_list]

        fragment = _ir.Fragment.get(self.m, None).prepare(
            ports     = ports,
            hierarchy = (self.name,)
        )

        v, _name_map = verilog.convert_fragment(fragment, name=self.name)
        netlist      = _ir.build_netlist(fragment, name=self.name)

        # Map Amaranth signals to Verilog port names and directions
        self.amaranth_name_map = _ast.SignalDict(
            (sig, (name, 'o' if name in netlist.top.ports_o else 'i'))
            for name, sig, _ in fragment.ports
        )

        # Alias clock and reset signals to their corresponding domain ports
        for name, domain in fragment.fragment.domains.items():
            if domain.clk in self.amaranth_name_map:
                self.amaranth_name_map[amaranth.ClockSignal(name)] = self.amaranth_name_map[domain.clk]
            if domain.rst in self.amaranth_name_map:
                self.amaranth_name_map[amaranth.ResetSignal(name)] = self.amaranth_name_map[domain.rst]

        return v

    def do_finalize(self):
        """
        Finalize the module during the LiteX build process.

        This method:
        - Generates and writes Verilog code produced by Amaranth
        - Registers the Verilog file as a platform source
        - Instantiates the generated module
        """
        output_dir = {True:  self.platform.output_dir, False: self.output_dir}[self.output_dir is None]

        src_dir = os.path.join(output_dir, self.name)
        v_file  = os.path.join(src_dir, f"{self.name}.v")

        # Create output directory if needed
        if not os.path.exists(src_dir):
            os.mkdir(src_dir)

        # Generate and write Verilog
        with open(v_file, "w") as f:
            f.write(self.generate_verilog())

        # Register generated source
        self.platform.add_source(v_file)

        # Add an Instance to map verilog in the LiteX gateware
        self.specials += self.get_instance()
