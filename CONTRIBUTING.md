# Contributing to LiteX

Any contribution is welcome: a design that works, a bug report with enough to reproduce it, an
idea, a pull request, a one-line fix in the documentation. This page is the short version;
[Feedback, contribution, support](https://github.com/enjoy-digital/litex/wiki/Feedback-Contribution-Support)
on the wiki has the details.

## Issues

- **An idea:** open an issue and share it. If you also have an idea of the implementation, try it
  and submit it in the issue or in a pull request: we can give directions.
- **It does not work:** "it does not work" is not enough. Share your environment, the target or
  example you build, the parameters you added, the logs (build, console, toolchain) and the timing
  report. For your own design or a new feature, a minimal reproduction is best. The solution of a
  complex issue is often in a small detail.
- **It works:** let us know, it can be listed as an example on the
  [Projects](https://github.com/enjoy-digital/litex/wiki/Projects) page.

## Pull requests

- One topic per pull request, against the repository it belongs to (LiteX, LiteX-Boards,
  LiteDRAM, LiteEth...). If you doubt it can be merged (too specific, not useful for everyone),
  open an issue first.
- Follow the existing code: [coding style](doc/coding_style.md) and
  [architectural style](doc/architectural_style.md). Commit titles have the form
  `module: Description of the change.`, one change per commit.
- Say what was tested (simulation, which board) and what was not.
- The documentation is in [`doc/wiki`](doc/wiki): wiki fixes are pull requests too, see
  [Contributing to the wiki](doc/wiki/Contributing-to-the-Wiki.md).

## AI-assisted contributions

AI/LLM tools are welcome. Use them as tools: a contribution made with them follows the same rules
as any other.

- You understand the change, have tested it, and can explain and maintain it. Review it yourself
  before asking for a review.
- You are responsible for it: quality, correctness and licensing. It must be compatible with the
  LiteX [BSD-2-Clause license](LICENSE) and must not contain code copied from incompatible sources.
- It fits LiteX: the existing code, its style and its way of doing things.
- If a substantial part was generated, say so in the pull request.

Changes the submitter has not reviewed or cannot explain may be closed without a detailed review.
Agents working on LiteX: see [AGENTS.md](AGENTS.md) and
[LiteX for AI agents](https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#contribute-back).

## Support

The team doing the development and maintenance is small: please understand if we need a few days
to answer. The community helps too, on [Discord](https://discord.gg/PkJwjDbxeG) and on IRC at
[#litex on irc.libera.chat](https://web.libera.chat/#litex). For a product that needs extensive
support or custom developments, get in touch: [florent@enjoy-digital.fr](mailto:florent@enjoy-digital.fr).
