Introduction
############

Migen is a Python-based tool that aims at automating further the VLSI design process.

Migen makes it possible to apply modern software concepts such as object-oriented programming and metaprogramming to design hardware. This results in more elegant and easily maintained designs and reduces the incidence of human errors.

.. _background:

Background
**********

Even though the Milkymist system-on-chip [mm]_ had many successes, it suffers from several limitations stemming from its implementation in manually written Verilog HDL:

.. [mm] http://m-labs.hk

#. The "event-driven" paradigm of today's dominant hardware descriptions languages (Verilog and VHDL, collectively referred to as "V*HDL" in the rest of this document) is often too general. Today's FPGA architectures are optimized for the implementation of fully synchronous circuits. This means that the bulk of the code for an efficient FPGA design falls into three categories:

   #. Combinatorial statements
   #. Synchronous statements
   #. Initialization of registers at reset

   V*HDL do not follow this organization. This means that a lot of repetitive manual coding is needed, which brings sources of human errors, petty issues, and confusion for beginners:
   
   #. wire vs. reg in Verilog
   #. forgetting to initialize a register at reset
   #. deciding whether a combinatorial statement must go into a process/always block or not
   #. simulation mismatches with combinatorial processes/always blocks
   #. and more...
   
   A little-known fact about FPGAs is that many of them have the ability to initialize their registers from the bitstream contents. This can be done in a portable and standard way using an "initial" block in Verilog, and by affecting a value at the signal declaration in VHDL. This renders an explicit reset signal unnecessary in practice in some cases, which opens the way for further design optimization. However, this form of initialization is entirely not synthesizable for ASIC targets, and it is not easy to switch between the two forms of reset using V*HDL.

#. V*HDL support for composite types is very limited. Signals having a record type in VHDL are unidirectional, which makes them clumsy to use e.g. in bus interfaces. There is no record type support in Verilog, which means that a lot of copy-and-paste has to be done when forwarding grouped signals.

#. V*HDL support for procedurally generated logic is extremely limited. The most advanced forms of procedural generation of synthesizable logic that V*HDL offers are CPP-style directives in Verilog, combinatorial functions, and ``generate`` statements. Nothing really fancy, and it shows. To give a few examples:

   #. Building highly flexible bus interconnect is not possible. Even arbitrating any given number of bus masters for commonplace protocols such as Wishbone is difficult with the tools that V*HDL puts at our disposal.
   #. Building a memory infrastructure (including bus interconnect, bridges and caches) that can automatically adapt itself at compile-time to any word size of the SDRAM is clumsy and tedious.
   #. Building register banks for control, status and interrupt management of cores can also largely benefit from automation.
   #. Many hardware acceleration problems can fit into the dataflow programming model. Manual dataflow implementation in V*HDL has, again, a lot of redundancy and potential for human errors. See the Milkymist texture mapping unit [mthesis]_ [mxcell]_ for an example of this. The amount of detail to deal with manually also makes the design space exploration difficult, and therefore hinders the design of efficient architectures.
   #. Pre-computation of values, such as filter coefficients for DSP or even simply trigonometric tables, must often be done using external tools whose results are copy-and-pasted (in the best case, automatically) into the V*HDL source.

.. [mthesis] http://m-labs.hk/thesis/thesis.pdf
.. [mxcell] http://www.xilinx.com/publications/archives/xcell/Xcell77.pdf p30-35
   
Enter Migen, a Python toolbox for building complex digital hardware. We could have designed a brand new programming language, but that would have been reinventing the wheel instead of being able to benefit from Python's rich features and immense library. The price to pay is a slightly cluttered syntax at times when writing descriptions in FHDL, but we believe this is totally acceptable, particularly when compared to VHDL ;-)

Migen is made up of several related components:

#. the base language, FHDL
#. a library of small generic cores
#. a simulator
#. a build system

Installing Migen
****************

Either run the ``setup.py`` installation script or simply set ``PYTHONPATH`` to the root of the source directory.

If you wish to contribute patches, the suggest way to install is;
   #. Clone from the git repository at http://github.com/m-labs/migen
   #. Install using ``python3 ./setup.py develop --user``
   #. Edit the code in your git checkout.

Alternative install methods
===========================

 * Migen is available for the Anaconda Python distribution. The package can be found at at https://anaconda.org/m-labs/migen
 * Migen can be referenced in a requirements.txt file (used for ``pip install -r requirements.txt``) via ``-e git+http://github.com/m-labs/migen.git#egg=migen``. See the pip documentation for more information.

Feedback
********
Feedback concerning Migen or this manual should be sent to the M-Labs developers' mailing list ``devel`` on lists.m-labs.hk.
