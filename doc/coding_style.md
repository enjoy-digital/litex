# LiteX Coding Style

LiteX style is mostly local and practical: first match the surrounding file,
then follow normal Python readability rules. Do not reformat whole files only
to satisfy an external formatter. Keep diffs focused, preserve established
names and command-line interfaces, and use existing LiteX helpers before adding
new abstractions.

LiteX contains two main kinds of Python code with different conventions:
regular Python scripts/utilities and LiteX/Migen modules that describe hardware.

## Common Structure

Most project-owned source files use the standard LiteX header:

```python
#
# This file is part of LiteX.
#
# Copyright (c) <years> <author>
# SPDX-License-Identifier: BSD-2-Clause
```

Small definition files, generated files or files that already intentionally
omit this header can stay minimal. Do not add copyright headers as unrelated
cleanup.

Use the long section separators that are common in LiteX:

```python
# Helpers ------------------------------------------------------------------------------------------
# Git repositories ---------------------------------------------------------------------------------
# Run ----------------------------------------------------------------------------------------------
```

Keep imports grouped by origin and type. For regular Python modules, order
imports by progressively increasing module/import length, with alphabetical
order only used to break ties:

```python
import os
import sys
import time
import shutil
import argparse
import subprocess
```

Keep third-party imports separate from LiteX imports. For Migen/LiteX modules,
group imports by domain: Migen first, then `litex.gen`, then `litex.build`,
then interconnect/CSR/bus helpers, then SoC cores/integration/tooling. Preserve
local grouping when a file already has a clear domain order. Avoid import churn
unless the file is already being touched.

LiteX commonly aligns related assignments, dictionaries and keyword arguments
when this makes repeated structure easier to scan:

```python
self.output_dir    = output_dir
self.gateware_dir  = gateware_dir
self.software_dir  = software_dir

register_value = {
    True  : f"0b{value:032b}",
    False : f"0x{value:08x}",
}[binary]
```

Line length is guided by readability, not a rigid formatter. Tables, register
maps and `argparse` declarations can stay compact when that helps scanning;
split lines when dense expressions hide structure or make diffs hard to review.

## Regular Python Scripts

Regular scripts include setup, release, build, conversion, programmer and debug
utilities. They should be explicit, command-oriented and easy to run directly.

Prefer explicit imports in scripts. Use lists of arguments for subprocess
commands, and keep command construction readable:

```python
pull_cmd = ["git", "-c", f"color.ui={color}", "pull", "--ff-only", "--stat"]
output   = subprocess_check_output(pull_cmd, cwd=repo_path).strip()
```

Use context managers for file I/O. Specify `encoding="utf-8"` for text files
when reasonable. Avoid bare `except`; catch the specific failure when possible,
or `Exception` only for deliberate best-effort paths such as auto-update.

Use small helpers when a command pattern or parsing rule is repeated. Private
helpers can use a leading underscore; public helpers should use the naming style
already used by the script. Avoid clever one-liners when a small helper makes
the behavior easier to inspect.

For `argparse` tools, keep options grouped by purpose with short section
comments. Print a concrete error before raising the local tool exception when
one exists, and keep useful subprocess output visible for Git/build/install
failures.

## LiteX/Migen Modules (HDL)

LiteX hardware modules are Python code that describes hardware. They have
different conventions from regular scripts.

It is normal for HDL modules to use:

```python
from migen import *
from litex.gen import *
from litex.soc.interconnect.csr import *
```

Use `LiteXModule` for new LiteX modules when appropriate. Keep module
construction readable: group parameters, CSRs, events, signals, combinatorial
logic, synchronous logic and specials by function.

Use the `# # #` separator before the hardware implementation after CSRs,
submodules or configuration have been declared:

```python
self._enable = CSRStorage()
self._status = CSRStatus()

# # #

counter = Signal(32)
self.sync += If(self._enable.storage, counter.eq(counter + 1))
self.comb += self._status.status.eq(counter != 0)
```

Expose software-visible state with LiteX CSR helpers (`CSRStorage`,
`CSRStatus`, `CSRField`, `EventManager`, `EventSource*`) rather than open-coded
register behavior. Use LiteX bus, clock-domain and integration helpers instead
of parallel local mechanisms.

For CSRs, prefer named `CSRField`s with descriptions when a register contains
control/status bits or packed fields. This documents the software interface and
lets hardware use `csr.fields.<name>` instead of numeric bit slices. Use
`offset`, `size`, `reset`, `pulse` and `values` explicitly when they clarify
the register layout or behavior. Simple full-width data registers can remain
plain `CSRStorage(width, description=...)` / `CSRStatus(width, description=...)`.

The HyperBus core is a good reference for CSR style: group related registers,
describe each field, use `values` for enumerations and connect fields by name.
When adding new CSRs, prefer a field description even when `values` documents
the possible encodings:

```python
self.config = CSRStorage(fields=[
    CSRField("rst",     offset=0, size=1, pulse=True, description="HyperRAM Rst."),
    CSRField("latency", offset=8, size=8,             description="HyperRAM Latency (X1).", reset=default_latency),
])
self.comb += [
    self.core.rst.eq(    self.config.fields.rst),
    self.core.latency.eq(self.config.fields.latency),
]

self.status = CSRStatus(fields=[
    CSRField("latency_mode", offset=0, size=1, description="HyperRAM latency mode.", values=[
        ("``0b0``", "Fixed Latency."),
        ("``0b1``", "Variable Latency."),
    ]),
])
```

Keep hardware behavior explicit. Prefer simple `Signal`, `Record`, `FSM`,
`If/Elif/Else`, `Case`, `self.comb`, `self.sync` and `self.specials` blocks over
abstractions that hide timing or reset behavior. Use `reset_less=True`
deliberately and keep clock-domain crossings explicit with the existing CDC
helpers.

Avoid software side effects in module construction. A module `__init__` should
describe hardware and attach submodules/specials; command execution, file I/O
and board policy belong in build scripts, targets, platforms or integration
code.

When adding platform or core support, keep board-specific policy in targets or
platform files, and keep reusable behavior in the relevant core or integration
module.

## Comments And Names

Use comments to explain intent, hardware behavior, compatibility constraints or
non-obvious ordering. Avoid comments that only restate the code. Keep comments
short and use the same capitalization/punctuation as nearby code.

Prefer names that match LiteX terminology: `soc`, `csr`, `bus`, `clk_freq`,
`data_width`, `with_<feature>`, `add_<thing>()`. Preserve public names and
command-line options unless there is a compatibility plan.

## Documentation

Documentation should be concise and command-oriented. Prefer examples that
users can run. When documenting maintenance procedures, list preflight checks
and recovery/resume steps explicitly.

## Guidance For AI Agents

Before editing, inspect the local file and a few neighboring LiteX files of the
same kind. Do not apply regular-script style to HDL modules, and do not apply
HDL star-import conventions to regular scripts.

Keep edits scoped to the requested behavior, preserve aligned blocks, and avoid
unrelated renames or cleanup. After editing, run the smallest useful syntax or
behavior checks and report any checks that could not be run.
