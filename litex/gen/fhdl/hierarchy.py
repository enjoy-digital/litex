#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *


# LiteX Hierarchy Explorer -------------------------------------------------------------------------

class LiteXHierarchyExplorer:
    def __init__(self, top, depth=None):
        self.top            = top
        self.depth          = depth

    def get_tree(self, module, ident=0, with_modules=True, with_instances=True):
        r = ""
        # Modules / SubModules.
        for name, mod in module._submodules:
            if name is None:
                name = "Unnamed"
            if with_modules:
                r += f"{'│     '*ident}├─── {colorer(name, 'cyan')} ({mod.__class__.__name__})\n"
            if (self.depth is None) or (ident < self.depth):
                r += self.get_tree(mod, ident + 1)

        # Instances.
        for s in module._fragment.specials:
            if (self.depth is None) or (ident <= self.depth):
                if isinstance(s, Instance):
                    show = with_instances
                    for k, v in module._submodules:
                        if s in v._fragment.specials:
                            show = False
                    if show:
                        r +=  f"{'│     '*ident}├─── {colorer(s.of, 'bright')}\n"
        return r

    def __repr__(self):
        r = "\n"
        r += f"{colorer(self.top.__class__.__name__, 'green')}\n"
        r += self.get_tree(self.top)
        return r
