#
# This file is part of LiteX.
#
# This file is Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

def allocate_generated_name(obj, used_names):
    """Return a deterministic synthetic instance name for unnamed objects."""
    base = obj.__class__.__name__.lower()
    idx  = 0
    name = f"{base}_{idx}"
    while name in used_names:
        idx += 1
        name = f"{base}_{idx}"
    return name
