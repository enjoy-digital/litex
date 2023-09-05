#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.module import _ModuleProxy
from migen.fhdl.specials import Special

from litex.soc.interconnect.csr import _CSRBase, AutoCSR
from litex.soc.integration.doc import AutoDoc

# LiteX Module -------------------------------------------------------------------------------------

class LiteXModule(Module, AutoCSR, AutoDoc):
    """
    LiteXModule is an enhancement of the Migen Module, offering additional features and simplifications
    for users to handle submodules, specials, and clock domains. It is integrated with AutoCSR and
    AutoDoc for CSR and documentation automation, respectively.
    """

    def __setattr__(m, name, value):
        """
        Overrides the default behavior of attribute assignment in Python. This method simplifies the
        process of adding submodules, specials, and clock domains in LiteX compared to Migen.
        """

        # Migen behavior:
        if name in ["comb", "sync", "specials", "submodules", "clock_domains"]:
            if not isinstance(value, _ModuleProxy):
                raise AttributeError("Attempted to assign special Module property - use += instead")
        # Automatic handling for adding submodules, specials, and clock domains in LiteX.
        # - m.module_x  = .. equivalent of Migen's m.submodules.module_x = ..
        # Note: Do an exception for CSRs that have a specific collection mechanism.
        elif (isinstance(value, Module)      and ((name, value) not in m._submodules) and (not isinstance(value, _CSRBase))):
            setattr(m.submodules, name, value)
        # - m.special_x = .. equivalent of Migen's m.specials.special_x  = ..
        elif isinstance(value, Special)     and (value not in m._fragment.specials):
            setattr(m.specials, name, value)
        # - m.cd_x      = .. equivalent of Migen's m.clock_domains.cd_x  = ..
        elif isinstance(value, ClockDomain) and (value not in m._fragment.clock_domains):
            setattr(m.clock_domains, name, value)
        # Else use default __setattr__.
        else:
            object.__setattr__(m, name, value)

    def __iadd__(m, other):
        """
        Overrides the default behavior of "+=" in Python. Simplifies addition of submodules, specials,
        and clock domains.
        """

        # - m += module_x  equivalent of Migen's m.submodules += module_x.
        if isinstance(other, Module):
            print(other)
            m.submodules += other
        # - m += special_x  equivalent of Migen's m.specials += special_x.
        elif isinstance(other, Special):
            m.specials += other
        # - m += cd_x  equivalent of Migen's m.clock_domains += cd_x.
        elif isinstance(other, ClockDomain):
            m.clock_domains += other
        # Else use default __iadd__.
        else:
            object.__iadd__(m, other)
        return m

    def add_module(self, name, module):
        """
        Add a submodule to the current module.

        Args:
            name (str): Name to assign to the submodule.
            module (Module): Submodule to be added.

        Raises:
            AssertionError: If provided object is not a Module or module name already exists.
        """
        assert isinstance(module, Module)
        assert not hasattr(self, name)
        setattr(self, name, module)

    def get_module(self, name):
        """
        Retrieve a submodule by its name.

        Args:
            name (str): Name of the submodule to retrieve.

        Returns:
            module (Module or None): Returns the module if found, otherwise None.

        Raises:
            AssertionError: If found object is not of type Module.
        """
        module = getattr(self, name, None)
        if module is not None:
            assert isinstance(module, Module)
        return module
