
# Why is LiteX Migen based and hasn't switched to Amaranth?

To give a bit of context/history, Migen DSL has been around since 2012 and we have been involved in its development since then while also working on LiteX and creating the ecosystem of cores.

Since 2012, LiteX has been used to create very various FPGA based systems for [open-source and commercial projects](Projects.md) and most of the codebase is currently tightly linked to Migen since written with its DSL. Most of these projects are still maintained and can't for now justify a complete rewrite.

Amaranth has been developed since 2018, several years after the initial LiteX development, and is revisiting/improving some of the concepts introduced by Migen. Switching the DSL used by LiteX needs to be prepared and will require hard work, time (and/or money :))... and we are still evaluating if it's worth switching to Amaranth or have our own DSL.

# Why isn't LiteX using Amaranth's Migen compat mode?

Amaranth has a Migen compatibility layer that works great for small/medium size projects, but:
 - This is not a long term solution.
 - This still requires changes to the codebase.
 - This does not mix well with LiteX relying on some Migen internals for simulation, build, logic analyzer, etc...

At some point, using  Amaranth compat mode was envisaged but for the foregoing reasons this does not seem practical.

# Is it already possible to use Amaranth modules/cores with LiteX?

LiteX is a very permissive SoC builder and the fact that the main modules/cores are still written with Migen DSL does not prevent integrating Amaranth modules in a LiteX SoC by elaborating the Amaranth module to verilog and integrating it in the design. A good example for this is the [Minerva CPU](https://github.com/lambdaconcept/minerva) integration in LiteX: the CPU is elaborated at build-time from Amaranth sources with appropriate parameters, exported to verilog and integrated in the LiteX design as any other CPU. LiteX provides this as a generic converter: `litex/build/amaranth2v_converter.py` elaborates an Amaranth `Elaboratable` to Verilog during the LiteX build (see [Reuse a core](Reuse-a-SystemVerilog-VHDL-Amaranth-Spinal-HDL-Chisel-core.md)).

Even if new DSLs allow developers to avoid VHDL/Verilog with FOSS toolchains, VHDL/Verilog will probably remain interchange formats for quite some time and developers will probably create standalone verilog core generator to facilitate reuse from other flows, similarly to what we are already doing with [LiteDRAM](https://github.com/enjoy-digital/litedram), [LitePCIe](https://github.com/enjoy-digital/litepcie), [LiteEth](https://github.com/enjoy-digital/liteeth), etc...

Reusing Amaranth modules with LiteX can already be done in two different ways:
- Reusing a pre-generated verilog provided by developers.
- Elaborating the verilog from the Amaranth during the LiteX build (as done with Minerva CPU).

The latter is more flexible/powerful since allows elaborating the Amaranth module with appropriate parameters.

# Will I be limited by this?

Not really: Amaranth has some advantages over Migen, and LiteX has features and a rich ecosystem of cores not available in other projects, so while waiting for the planets to be aligned, the best is probably to take the best of both worlds:

 - Develop in the language you find the most appropriate for you (VHDL/Verilog/Amaranth/Migen, etc....)
 - Reuse other open-source cores when you don't have the time or don't want to develop it yourself. (Amaranth core exported to verilog and integrated in a LiteX design, LiteX core exported to verilog and integrated in a Amaranth design, Amaranth/LiteX core exported to verilog and integrated in a traditional VHDL/Verilog flow, etc....)
 - Use the right tool/language for the right job.
 - ... and most important: Enjoy what you do, understand that things are generally not perfect and that your help would be welcome to go in that direction!

> **Note:** VexRiscv (and its successors NaxRiscv and VexiiRiscv), the most popular CPUs used with LiteX, are written in SpinalHDL and the [Linux on LiteX VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv) project is a good example of the possible interoperability between various high level HDLs.

# What are the long term plans regarding LiteX?

Things are still not fully decided, if:
 - current LiteX codebase should be converted to Amaranth/our own DSL.
 - current LiteX codebase should stay in Migen and new modules/cores developed with Amaranth or our own DSL.
 
...For now, there **are still lots of things to do** and in the short term Migen is not really limiting the project and a full DSL switch is not yet justified, so the project is going to keep evolving slowly but surely and **if developers want to help us improving things** on the different fronts (including the Amaranth one) we'll be **happy to collaborate**!

See also [The LiteX approach](LiteX-Approach.md) for how the pieces fit together.
