---
name: litex-upstream-a-fix
description: Turn a fix or an addition made for a project (a patched LiteX file, a copied core, a board target change, a workaround subclass) into a clean pull request against the LiteX repository it belongs to, with a test and a verification report. Use when a project needed to change LiteX, LiteX-Boards or a Lite* core, when asked to "upstream", "send back" or "contribute" a change, or before ending a task that left a local patch of the framework.
---

# Upstream a fix to LiteX

A fix kept in a project tree serves that project only; merged upstream, it is tested by the CI
and found by the next person (or agent). One topic per pull request, verified, in the style of
the files around it.

## 1. Find where it belongs

| The change | Repository |
| --- | --- |
| SoC builder, interconnect, in-tree cores, CPUs, build backends, BIOS, host tools | `enjoy-digital/litex` |
| A board's platform or target | `litex-hub/litex-boards` |
| DRAM, Ethernet, PCIe, SATA, SD card, transceivers, JESD204, LiteScope... | the core's repository (`enjoy-digital/lite*`, `litex-hub/litespi`, `litex-hub/litei2c`) |

Read that repository's `AGENTS.md` and `doc/coding_style.md` (or the closest equivalent) first.
Keep what helps one design only (a copy tuned for one traffic pattern) in the project; when
unsure, open an issue with the diff and ask.

## 2. Reduce the change to its cause

- Diff the project's copy against upstream `master` (`git diff`, or `diff -u` against a fresh
  clone): keep the lines that fix the cause, drop the project's names, paths and tuning.
- A subclass or monkey-patch that works around a limitation becomes a fix of the limitation, or
  an option of the core with the old behavior as default.
- Keep public names, constructor arguments, CSR layouts, clock domain names and command-line
  options (or give a compatibility path); no reformatting of unrelated code, no dependency bumps.

## 3. Branch, test, verify

```sh
git fetch origin && git switch -c <topic> origin/master
python3 -m pytest test/<area>/test_<thing>.py                       # the closest tests, plus a new one
python3 -m litex_boards.targets.<board> --build --no-compile          # a target that uses the code
litex_sim --cpu-type=vexriscv [--with-sdram ...]                      # when the BIOS exercises it
python3 doc/wiki_sync.py check --strict                               # when doc/wiki/ changed (LiteX)
```

Add the test that would have caught the bug, in the layer that failed (an address computation,
a CSR map, a generated constant, a simulation of the core). Hardware results: say which board,
which toolchain version, what ran and what did not.

## 4. Commit and open the pull request

- Commit titles `module: Description of the change.` (`litex/soc/cores/uart: Fix RX FIFO overflow.`),
  one change per commit, the exploratory instrumentation left out.
- Pull request against `master` (or the repository's default branch): what it fixes, how it was
  checked (the commands and their result), what changes for other users.
- Say that an agent wrote it and who supervised. Never merge it yourself; answer review comments
  with evidence.

## Pitfalls

- No client, product or person names, internal paths or IP addresses in the diff, commits or
  pull request text.
- Generated files (`build/`, `csr.h`, `csr.csv`, Verilog) are never edited: change the Python.
- A test that only imports the module proves nothing; elaborate or simulate.
- Several unrelated fixes in one pull request get stuck behind the most debatable one: split them.
- The direction stays with the maintainers: a "no" with a reason is a normal answer.

## See also

- https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#contribute-back
- https://github.com/enjoy-digital/litex/wiki/Feedback-Contribution-Support#how-to-create-a-pull-request
- https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md
- https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md
