#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import sys

from migen import *

from litex.gen import *

# LiteX Hierarchy Explorer -------------------------------------------------------------------------

class LiteXHierarchyExplorer:
    if sys.platform == "win32":
        tree_vert = "|    "
        tree_mid  = "|-- "
        tree_last = "`-- "
    else:
        tree_vert = "│    "
        tree_mid  = "├── "
        tree_last = "└── "

    def __init__(self, top, depth=None, with_colors=True):
        self.top         = top
        self.depth       = depth
        self.with_colors = with_colors

    def _colorer(self, s, color="bright"):
        return colorer(s=s, color=color, enable=self.with_colors)

    def _collect_entries(self, module, with_modules=True, with_instances=True):
        entries = []
        used_names = set([None])

        if with_modules:
            for name, mod in module._submodules:
                gen_name = False
                if name is None:
                    base = mod.__class__.__name__.lower()
                    n = 0
                    candidate = f"{base}_{n}"
                    while candidate in used_names:
                        n += 1
                        candidate = f"{base}_{n}"
                    name = candidate
                    gen_name = True
                used_names.add(name)
                entries.append(("module", name, mod, gen_name))

        if with_instances:
            for s in sorted(module._fragment.specials, key=lambda x: str(x)):
                if isinstance(s, Instance):
                    show = True
                    for _, v in module._submodules:
                        if s in v._fragment.specials:
                            show = False
                            break
                    if show:
                        entries.append(("instance", s, None, False))
        return entries

    def get_tree(self, module, prefix="", ident=0, with_modules=True, with_instances=True):
        r = ""
        if (self.depth is not None) and (ident > self.depth):
            return r

        entries = self._collect_entries(module, with_modules, with_instances)
        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            branch = self.tree_last if is_last else self.tree_mid

            if entry[0] == "module":
                _, name, mod, gen_name = entry
                tag = " [Gen]" if gen_name else ""
                label = f"{self._colorer(name, 'cyan')} ({mod.__class__.__name__}){tag}"
                r += f"{prefix}{branch}{label}\n"
                if (self.depth is None) or (ident < self.depth):
                    child_prefix = prefix + ("     " if is_last else self.tree_vert)
                    r += self.get_tree(mod, prefix=child_prefix, ident=ident + 1)
            else:
                _, inst, _, _ = entry
                label = f"{self._colorer('[BB:' + inst.of + ']', 'yellow')}"
                r += f"{prefix}{branch}{label}\n"

        return r

    def get_hierarchy(self):
        r = ""
        r += f"{self._colorer(self.top.__class__.__name__, 'underline')}\n"
        r += self.get_tree(self.top)
        r += f"{self._colorer('Legend:', 'bright')}\n"
        r += f"{self._colorer('  [Gen]', 'cyan')}: Auto-generated instance name.\n"
        r += f"{self._colorer('  [BB:NAME]', 'yellow')}: Blackbox instance (verilog Instance).\n"
        return r

    def __repr__(self):
        return f"\n{self.get_hierarchy()}"
