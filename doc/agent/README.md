# LiteX agent skills

Procedures for AI agents working with LiteX, in the [Agent Skills](https://agentskills.io) format:
one directory per skill, a `SKILL.md` with a `name` and a `description` that says when to use it.
They use the real LiteX tools (`litex_server`, `litex_cli --json`, `litescope_cli --json`,
`litex.build.report`) and the [`litex_mcp`](https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#drive-a-soc-through-mcp)
tools, and point to the wiki pages behind them.

| Skill | Use it to |
| --- | --- |
| [litex-build-and-load](skills/litex-build-and-load/SKILL.md) | find the command line, elaborate, build, read the result, load |
| [litex-bringup](skills/litex-bringup/SKILL.md) | bring a board up one layer at a time (UART, bridge, DRAM, Ethernet...) |
| [litex-csr-debug](skills/litex-csr-debug/SKILL.md) | check the host link, read/write CSRs, add the register that answers |
| [litescope-capture](skills/litescope-capture/SKILL.md) | add a narrow LiteScope probe, trigger, read the capture as data |
| [litex-timing-triage](skills/litex-timing-triage/SKILL.md) | read the parsed timing reports, classify failing paths, fix the design |
| [litex-upstream-a-fix](skills/litex-upstream-a-fix/SKILL.md) | turn a project's patch of LiteX into a clean pull request |

## Install

Claude Code (this directory is a plugin, listed by the marketplace at the repository root):

```
/plugin marketplace add enjoy-digital/litex
/plugin install litex@litex
```

The skills are then available as `/litex:<skill>` and are picked up automatically when a task
matches their description. To try a local checkout: `claude --plugin-dir doc/agent`.

Other agents: point them at `doc/agent/skills/*/SKILL.md` (or copy the directories into their
skills folder); the files are plain Markdown with a YAML header.

The skills stay generic: project-specific procedures belong in the project's own
`doc/debugging-guide.md` (template on the [wiki](https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents)).
