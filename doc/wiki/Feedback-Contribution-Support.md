Feedback and contributions are what make an open-source project better, and any contribution
to LiteX is welcome: a design that works, a bug report with enough to reproduce it, an idea, a
pull request, a one-line fix in this wiki. This page says how to make each one useful, where
to ask for help, and how to get support when LiteX is part of your product.

- You created a design with LiteX, **it works** and you are happy with it? Please **let us
  know**: we could list it as a [resource](Tutorials-Resources.md#examples-to-read) or a
  [project](Projects.md), as an example for others.
- You try to use LiteX and it **does not work**? We can certainly help if you create an
  **issue**, with the [things we will need to know](#how-to-create-an-issue-when-it-does-not-work).
- You have seen things that could be **improved**, or have **ideas**? **Please share them.**
  If you do not feel confident enough to modify the code yourself, create an issue describing
  the idea and how it would improve the project; if you think you can do it, **try and open a
  pull request**. Even if it is not perfect, it will be welcome and we will help you improve
  it, or do the modification for you.
- The documentation is wrong, outdated or missing something? This wiki is generated from the
  `doc/wiki` directory of the LiteX repository: [send a pull request](Contributing-to-the-Wiki.md),
  even for a one-line fix.

You may well think of things we would never have figured out ourselves, or be an expert in
something we would implement less well: that is what makes open source so rewarding,
**everyone learns from each other**!

We think LiteX can be useful and bring innovative solutions to some projects, but we also know
it is not perfect and will not be the solution for everyone or every project. If you are
interested and **want to contribute, please do**; if the only thing LiteX does for you is make
you angry, this is probably not the right project for you :) (constructive criticism is
welcome, though).

## How to create an issue when you just have an idea

**Just create an issue and share the idea with us.** If you also have ideas on the
implementation, we encourage you to try it (that is how you will learn and progress!) and
submit it in the issue or even in a pull request. The LiteX community is **very welcoming**,
and we can give directions or do the implementation ourselves when it is interesting for the
whole project.

## How to create an issue when it does not work

LiteX provides [tutorials](Tutorials-Resources.md), [projects](Projects.md) to read, and
platforms and targets for a lot of FPGA boards in [LiteX-Boards](https://github.com/litex-hub/litex-boards),
tested and validated, most of them covered by our CI.

Since LiteX **possibilities are infinite**, we cannot support or test every combination: the
code base has wanted limitations (no need for this yet) and issues that are not wanted; FPGAs
are also constrained in size and speed. We are happy to hear about the issues and limitations
you find, but analyzing, fixing or adding support takes a minimum of information and time, so
if you want us to take time to look at the issue, please **take a bit of your time to prepare
it**: "**it does not work**" is **not enough** :) The solution to a complex issue is often in
a small detail, and enough information from the start saves days of back and forth.

If you are testing an example with specific parameters you think should be supported, share:

- Your test environment.
- The target or example you are building.
- The parameters you added.
- The logs LiteX generates (during the build, on the console, from the toolchains).
- The timing report of your design.

If you are testing a design of your own or developing a new feature, the best is a minimal
reproduction of the issue, so that we can reproduce it and investigate without asking you at
each step.

**Reading this is the first thing we will ask if your issue does not provide enough
information, so please anticipate :)**

## How to create a pull request

If you **have an idea** and think you can **implement it**, go ahead, **that is how you will
learn and progress!** We **always welcome contributions** and will help make yours mergeable
when it is useful for the whole project. If, before the hard work, you doubt it can be merged
(too specific, or not useful for everyone), open an issue first to discuss it.

Use a coding style close to the existing files: the
[coding style](https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md) and
[architectural style](https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md)
documents describe it (file layout, HDL conventions, where a device-specific piece of code
belongs), with commit messages of the form `module: Description of the change.`. Say in the
pull request what was tested (simulation, which board) and what was not.

## Support

LiteX is an open-source project we really enjoy working on, but the team doing the development
and maintenance is small and has other obligations, since the initial goal of LiteX was to
build custom FPGA systems with it: please understand if we need a few days to respond. The
community is growing and helping too: join us on [Discord](https://discord.gg/PkJwjDbxeG) or on
IRC at [#litex on irc.libera.chat](https://web.libera.chat/#litex).

We are lucky to have clients trusting us and funding systems built with LiteX and new
developments, but most of us can only answer on working days, and need weekends and holidays
with family and friends to come back with fresh minds and ideas!

We are happy to provide basic support to everyone. If you are developing a product, want to
reuse LiteX or part of it (the cores, the infrastructure) and need extensive support, or want
us to customize things for you, please get in touch: seeing our work used in real products is
what motivates us, and we will see together what we and our partners can do.

## Community

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex-hub.png" width="400"></p>

Over the years a friendly community has grown around LiteX and the ecosystem of cores.
Feedback and contributions have already greatly improved the project; Enjoy-Digital still
leads the development, but it is now a community project, and the collaborative projects
created around and with LiteX live at [github.com/litex-hub](https://github.com/litex-hub).

Contact: [florent@enjoy-digital.fr](mailto:florent@enjoy-digital.fr)

## Next

- [Contributing to the wiki](Contributing-to-the-Wiki.md): the pages are pull requests too.
- [Projects](Projects.md): what the community and the clients built, and the custom support we offer.
- [Tutorials and resources](Tutorials-Resources.md): where to learn before asking.
- [LiteX for AI agents](LiteX-for-AI-Agents.md): the conventions a contribution follows, in short.
