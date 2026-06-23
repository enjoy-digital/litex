#
# This file is part of LiteX.
#
# Copyright (c) 2026 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import importlib
import sys

from litex import get_data_mod


# Helpers ------------------------------------------------------------------------------------------

def import_from_pythondata(data_type, data_name, module_name):
    data_mod = get_data_mod(data_type, data_name)
    sdir     = data_mod.data_location

    if sdir not in sys.path:
        sys.path.insert(0, sdir)

    # Avoid collisions with already imported LiteX CPU wrapper modules.
    # This happens for names such as "minerva.core" where a different
    # module can already be present in sys.modules.
    parts = module_name.split(".")
    for i in range(1, len(parts) + 1):
        prefix = ".".join(parts[:i])
        module = sys.modules.get(prefix)
        if module is None:
            continue
        module_file = getattr(module, "__file__", "") or ""
        if not module_file.startswith(sdir):
            del sys.modules[prefix]

    return importlib.import_module(module_name)


def check_required_modules(required_modules):
    missing = []
    for module_name, install_hint in required_modules.items():
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as e:
            if e.name == module_name or module_name.startswith((e.name or "") + "."):
                missing.append((module_name, install_hint))
            else:
                raise
        except ImportError as e:
            if getattr(e, "name", None) == module_name:
                missing.append((module_name, install_hint))
            else:
                raise

    if len(missing):
        lines = ["Missing Python dependencies for Amaranth integration:"]
        for module_name, install_hint in missing:
            lines.append(f"- {module_name}: {install_hint}")
        raise OSError("\n".join(lines))
