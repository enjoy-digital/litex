Migen manual
############

Introduction
############

Migen is a Python-based tool that aims at automating further the VLSI design process.

Migen makes it possible to apply modern software concepts such as object-oriented programming and metaprogramming to design hardware. This results in more elegant and easily maintained designs and reduces the incidence of human errors.

.. _background:

Background
**********

Even though the Milkymist system-on-chip [mm]_ is technically successful, it suffers from several limitations stemming from its implementation in manually written Verilog HDL:

.. [mm] http://www.milkymist.org

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

#. V*HDL support for procedurally generated logic is extremely limited. The most advanced forms of procedural generation of synthesizable logic that V*HDL offers are CPP-style directives in Verilog, combinatorial functions, and generate statements. Nothing really fancy, and it shows. To give a few examples:

   #. Building highly flexible bus interconnect is not possible. Even arbitrating any given number of bus masters for commonplace protocols such as Wishbone is difficult with the tools that V*HDL puts at our disposal.
   #. Building a memory infrastructure (including bus interconnect, bridges and caches) that can automatically adapt itself at compile-time to any word size of the SDRAM is clumsy and tedious.
   #. Building register banks for control, status and interrupt management of cores can also largely benefit from automation.
   #. Many hardware acceleration problems can fit into the dataflow programming model. Manual dataflow implementation in V*HDL has, again, a lot of redundancy and potential for human errors. See the Milkymist texture mapping unit [mthesis]_ [mxcell]_ for an example of this. The amount of detail to deal with manually also makes the design space exploration difficult, and therefore hinders the design of efficient architectures.
   #. Pre-computation of values, such as filter coefficients for DSP or even simply trigonometric tables, must often be done using external tools whose results are copy-and-pasted (in the best cases, automatically) into the V*HDL source.

.. [mthesis] http://milkymist.org/thesis/thesis.pdf
.. [mxcell] http://www.xilinx.com/publications/archives/xcell/Xcell77.pdf p30-35
   
Enter Migen, a Python toolbox for building complex digital hardware. We could have designed a brand new programming language, but that would have been reinventing the wheel instead of being able to benefit from Python's rich features and immense library. The price to pay is a slightly cluttered syntax at times when writing descriptions in FHDL, but we believe this is totally acceptable, particularly when compared to VHDL ;-)

Migen is made up of several related components, which are described in this manual.

Installing Migen
****************
Either run the ``setup.py`` installation script or simply set ``PYTHONPATH`` to the root of the source directory.

For simulation support, an extra step is needed. See :ref:`vpisetup`.


The FHDL layer
##############

The Fragmented Hardware Description Language (FHDL) is the lowest layer of Migen. It consists of a formal system to describe signals, and combinatorial and synchronous statements operating on them. The formal system itself is low level and close to the synthesizable subset of Verilog, and we then rely on Python algorithms to build complex structures by combining FHDL elements and encapsulating them in "fragments".
The FHDL module also contains a back-end to produce synthesizable Verilog, and some basic analysis functions. It would be possible to develop a VHDL back-end as well, though more difficult than for Verilog - we are "cheating" a bit now as Verilog provides most of the FHDL semantics.

FHDL differs from MyHDL [myhdl]_ in fundamental ways. MyHDL follows the event-driven paradigm of traditional HDLs (see :ref:`background`) while FHDL separates the code into combinatorial statements, synchronous statements, and reset values. In MyHDL, the logic is described directly in the Python AST. The converter to Verilog or VHDL then examines the Python AST and recognizes a subset of Python that it translates into V*HDL statements. This seriously impedes the capability of MyHDL to generate logic procedurally. With FHDL, you manipulate a custom AST from Python, and you can more easily design algorithms that operate on it.

.. [myhdl] http://www.myhdl.org

FHDL is made of several elements, which are briefly explained below.

Expressions
***********

Bit vector (BV)
===============
The bit vector (BV) object defines if a constant or signal is signed or unsigned, and how many bits it has. This is useful e.g. to:

* determine when to perform sign extension (FHDL uses the same rules as Verilog).
* determine the size of registers.
* determine how many bits should be used by each value in concatenations.

Constant
========
This object should be self-explanatory. All constant objects contain a BV object and a value. If no BV object is specified, one will be made up using the following rules:

* If the value is positive, the BV is unsigned and has the minimum number of bits needed to represent the constant's value in the canonical base-2 system.
* If the value is negative, the BV is signed, and has the minimum number of bits needed to represent the constant's value in the canonical two's complement, base-2 system.

Signal
======
The signal object represents a value that is expected to change in the circuit. It does exactly what Verilog's "wire" and "reg" and VHDL's "signal" and "variable" do.

The main point of the signal object is that it is identified by its Python ID (as returned by the :py:func:`id` function), and nothing else. It is the responsibility of the V*HDL back-end to establish an injective mapping between Python IDs and the V*HDL namespace. It should perform name mangling to ensure this. The consequence of this is that signal objects can safely become members of arbitrary Python classes, or be passed as parameters to functions or methods that generate logic involving them.

The properties of a signal object are:

* a bit vector description
* a name, used as a hint for the V*HDL back-end name mangler.
* a boolean "variable". If true, the signal will behave like a VHDL variable, or a Verilog reg that uses blocking assignment. This parameter only has an effect when the signal's value is modified in a synchronous statement.
* the signal's reset value. It must be an integer, and defaults to 0. When the signal's value is modified with a synchronous statement, the reset value is the initialization value of the associated register. When the signal is assigned to in a conditional combinatorial statement (``If`` or ``Case``), the reset value is the value that the signal has when no condition that causes the signal to be driven is verified. This enforces the absence of latches in designs. If the signal is permanently driven using a combinatorial statement, the reset value has no effect.
  
The sole purpose of the name property is to make the generated V*HDL code easier to understand and debug. From a purely functional point of view, it is perfectly OK to have several signals with the same name property. The back-end will generate a unique name for each object. If no name property is specified, Migen will analyze the code that created the signal object, and try to extract the variable or member name from there. For example, the following statements will create one or several signal named "bar": ::

  bar = Signal()
  self.bar = Signal()
  self.baz.bar = Signal()
  bar = [Signal() for x in range(42)]

In case of conflicts, Migen tries first to resolve the situation by prefixing the identifiers with names from the class and module hierarchy that created them. If the conflict persists (which can be the case if two signal objects are created with the same name in the same context), it will ultimately add number suffixes.

Operators
=========
Operators are represented by the ``_Operator`` object, which generally should not be used directly. Instead, most FHDL objects overload the usual Python logic and arithmetic operators, which allows a much lighter syntax to be used. For example, the expression: ::

  a * b + c

is equivalent to::

  _Operator("+", [_Operator("*", [a, b]), c])

Slices
======
Likewise, slices are represented by the ``_Slice`` object, which often should not be used in favor of the Python slice operation [x:y]. Implicit indices using the forms [x], [x:] and [:y] are supported. Beware! Slices work like Python slices, not like VHDL or Verilog slices. The first bound is the index of the LSB and is inclusive. The second bound is the index of MSB and is exclusive. In V*HDL, bounds are MSB:LSB and both are inclusive.

Concatenations
==============
Concatenations are done using the ``Cat`` object. To make the syntax lighter, its constructor takes a variable number of arguments, which are the signals to be concatenated together (you can use the Python "*" operator to pass a list instead).
To be consistent with slices, the first signal is connected to the bits with the lowest indices in the result. This is the opposite of the way the "{}" construct works in Verilog.

Replications
============
The ``Replicate`` object represents the equivalent of {count{expression}} in Verilog.

Statements
**********

Assignment
==========
Assignments are represented with the ``_Assign`` object. Since using it directly would result in a cluttered syntax, the preferred technique for assignments is to use the ``eq()`` method provided by objects that can have a value assigned to them. They are signals, and their combinations with the slice and concatenation operators.
As an example, the statement: ::

  a[0].eq(b)

is equivalent to: ::

  _Assign(_Slice(a, 0, 1), b)

If
==
The ``If`` object takes a first parameter which must be an expression (combination of the ``Constant``, ``Signal``, ``_Operator``, ``_Slice``, etc. objects) representing the condition, then a variable number of parameters representing the statements (``_Assign``, ``If``, ``Case``, etc. objects) to be executed when the condition is verified.

The ``If`` object defines a ``Else()`` method, which when called defines the statements to be executed when the condition is not true. Those statements are passed as parameters to the variadic method.

For convenience, there is also a ``Elif()`` method.

Example: ::

  If(tx_count16 == 0,
      tx_bitcount.eq(tx_bitcount + 1),
      If(tx_bitcount == 8,
          self.tx.eq(1)
      ).Elif(tx_bitcount == 9,
          self.tx.eq(1),
          tx_busy.eq(0)
      ).Else(
          self.tx.eq(tx_reg[0]),
          tx_reg.eq(Cat(tx_reg[1:], 0))
      )
  )

Case
====
The ``Case`` object constructor takes as first parameter the expression to be tested, then a variable number of lists describing the various cases.

Each list contains an expression (typically a constant) describing the value to be matched, followed by the statements to be executed when there is a match. The head of the list can be the an instance of the ``Default`` object.

Special elements
****************

Instances
=========
Instance objects represent the parametrized instantiation of a V*HDL module, and the connection of its ports to FHDL signals. They are useful in a number of cases:

* reusing legacy or third-party V*HDL code.
* using special FPGA features (DCM, ICAP, ...).
* implementing logic that cannot be expressed with FHDL (asynchronous circuits, ...).
* breaking down a Migen system into multiple sub-systems, possibly using different clock domains.

The properties of the instance object are:

* the type of the instance (i.e. name of the instantiated module).
* a list of output ports of the instantiated module. Each element of the list is a pair containing a string, which is the name of the module's port, and either an existing signal (on which the port will be connected to) or a BV (which will cause the creation of a new signal).
* a list of input ports (likewise).
* a list of (name, value) pairs for the parameters ("generics" in VHDL) of the module.
* the name of the clock port of the module (if any). If this is specified, the port will be connected to the system clock.
* the name of the reset port of the module (likewise).
* the name of the instance (can be mangled like signal names).

Memories
========
Memories (on-chip SRAM) are supported using a mechanism similar to instances.

A memory object has the following parameters:

* the width, which is the number of bits in each word.
* the depth, which represents the number of words in the memory.
* an optional list of integers used to initialize the memory.
* a list of port descriptions.

Each port description contains:

* the address signal (mandatory).
* the data read signal (mandatory).
* the write enable signal (optional). If the port is using masked writes, the width of the write enable signal should match the number of sub-words.
* the data write signal (iff there is a write enable signal).
* whether reads are synchronous (default) or asynchronous.
* the read enable port (optional, ignored for asynchronous ports).
* the write granularity (default 0), which defines the number of bits in each sub-word. If it is set to 0, the port is using whole-word writes only and the width of the write enable signal must be 1. This parameter is ignored if there is no write enable signal.
* the mode of the port (default ``WRITE_FIRST``, ignored for asynchronous ports). It can be:

  * ``READ_FIRST``: during a write, the previous value is read.
  * ``WRITE_FIRST``: the written value is returned.
  * ``NO_CHANGE``: the data read signal keeps its previous value on a write.

Migen generates behavioural V*HDL code that should be compatible with all simulators and, if the number of ports is <= 2, most FPGA synthesizers. If a specific code is needed, the memory generator function can be overriden using the ``memory_handler`` parameter of the conversion function.

Fragments
*********
A "fragment" is a unit of logic, which is composed of:

* a list of combinatorial statements.
* a list of synchronous statements.
* a list of instances.
* a list of memories.
* a set of pads, which are signals intended to be connected to off-chip devices.
* a list of simulation functions (see :ref:`simulating`).

Fragments can reference arbitrary signals, including signals that are referenced in other fragments. Fragments can be combined using the "+" operator, which returns a new fragment containing the concatenation of each pair of lists.

Fragments can be passed to the back-end for conversion to Verilog.

By convention, classes that generate logic implement a method called ``get_fragment``. When called, this method builds a new fragment implementing the desired functionality of the class, and returns it. This convention allows fragments to be built automatically by combining the fragments from all relevant objects in the local scope, by using the autofragment module.

Conversion for synthesis
************************

Any FHDL fragment (except, of course, its simulation functions) can be converted into synthesizable Verilog HDL. This is accomplished by using the ``convert`` function in the ``verilog`` module.

Migen does not provide support for any specific synthesis tools or ASIC/FPGA technologies. Users must run themselves the generated code through the appropriate tool flow for hardware implementation.

Bus support
###########

Migen Bus contains classes providing a common structure for master and slave interfaces of the following buses:

* Wishbone [wishbone]_, the general purpose bus recommended by Opencores.
* CSR-2 (see :ref:`csr2`), a low-bandwidth, resource-sensitive bus designed for accessing the configuration and status registers of cores from software.
* ASMIbus (see :ref:`asmi`), a split-transaction bus optimized for use with a high-performance, out-of-order SDRAM controller.
* DFI [dfi]_ (partial), a standard interface protocol between memory controller logic and PHY interfaces.

.. [wishbone] http://cdn.opencores.org/downloads/wbspec_b4.pdf
.. [dfi] http://www.ddr-phy.org/

It also provides interconnect components for these buses, such as arbiters and address decoders. The strength of the Migen procedurally generated logic can be illustrated by the following example: ::

  wbcon = wishbone.InterconnectShared(
      [cpu.ibus, cpu.dbus, ethernet.dma, audio.dma],
      [(0, norflash.bus), (1, wishbone2asmi.wishbone),
      (3, wishbone2csr.wishbone)])

In this example, the interconnect component generates a 4-way round-robin arbiter, multiplexes the master bus signals into a shared bus, determines that the address decoding must occur on 2 bits, and connects all slave interfaces to the shared bus, inserting the address decoder logic in the bus cycle qualification signals and multiplexing the data return path. It can recognize the signals in each core's bus interface thanks to the common structure mandated by Migen Bus. All this happens automatically, using only that much user code. The resulting interconnect logic can be retrieved using ``wbcon.get_fragment()``, and combined with the fragments from the rest of the system.


Configuration and Status Registers
**********************************

.. _csr2:

CSR-2 bus
=========
The CSR-2 bus, is a low-bandwidth, resource-sensitive bus designed for accessing the configuration and status registers of cores from software.

It is the successor of the CSR bus used in Milkymist SoC 1.x, with two modifications:

* Up to 32 slave devices (instead of 16)
* Data words are 8 bits (instead of 32)

Generating register banks
=========================
Migen Bank is a system comparable to wishbone-gen [wbgen]_, which automates the creation of configuration and status register banks and interrupt/event managers implemented in cores.

.. [wbgen] http://www.ohwr.org/projects/wishbone-gen

Bank takes a description made up of a list of registers and generates logic implementing it with a slave interface compatible with Migen Bus.

A register can be "raw", which means that the core has direct access to it. It also means that the register width must be less or equal to the bus word width. In that case, the register object provides the following signals:

* ``r``, which contains the data written from the bus interface.
* ``re``, which is the strobe signal for ``r``. It is active for one cycle, after or during a write from the bus. r is only valid when re is high.
* ``w``, which must provide at all times the value to be read from the bus.

Registers that are not raw are managed by Bank and contain fields. If the sum of the widths of all fields attached to a register exceeds the bus word width, the register will automatically be sliced into words of the maximum size and implemented at consecutive bus addresses, MSB first. Field objects have two parameters, ``access_bus`` and ``access_dev``, determining respectively the access policies for the bus and core sides. They can take the values ``READ_ONLY``, ``WRITE_ONLY`` and ``READ_WRITE``.
If the device can read, the field object provides the r signal, which contains at all times the current value of the field (kept by the logic generated by Bank).
If the device can write, the field object provides the following signals:

* ``w``, which provides the value to be written into the field.
* ``we``, which strobes the value into the field.

As a special exception, fields that are read-only from the bus and write-only for the device do not use the ``we`` signal. Instead, the device must permanently drive valid data on the ``w`` signal.

Generating interrupt controllers
================================
TODO: please document me!

.. _asmi:

Advanced System Memory Infrastructure
*************************************

Rationale
=========
The lagging of the DRAM semiconductor processes behind the logic processes has led the industry into a subtle way of ever increasing memory performance.

Modern devices feature a DRAM core running at a fraction of the logic frequency, whose wide data bus is serialized and deserialized to and from the faster clock domain. Further, the presence of more banks increases page hit rate and provides opportunities for parallel execution of commands to different banks.

A first-generation SDR-133 SDRAM chip runs both DRAM, I/O and logic at 133MHz and features 4 banks. A 16-bit chip has a 16-bit DRAM core.

A newer DDR3-1066 chip still runs the DRAM core at 133MHz, but the logic at 533MHz (4 times the DRAM frequency) and the I/O at 1066Mt/s (8 times the DRAM frequency). A 16-bit chip has a 128-bit internal DRAM core. Such a device features 8 banks. Note that the serialization also introduces multiplied delays (e.g. CAS latency) when measured in number of cycles of the logic clock.

To take full advantage of these new architectures, the memory controller should be able to peek ahead at the incoming requests and service several of them in parallel, while respecting the various timing specifications of each DRAM bank and avoiding conflicts for the shared data lines. Going further in this direction, a controller able to complete transfers out of order can provide even more performance by:

#. grouping requests by DRAM row, in order to minimize time spent on precharging and activating banks.
#. grouping requests by direction (read or write) in order to minimize delays introduced by bus turnaround and write recovery times.
#. being able to complete a request that hits a page earlier than a concurrent one which requires the cycling of another bank.

The first two techniques are explained with more details in [drreorder]_.

.. [drreorder] http://www.xilinx.com/txpatches/pub/documentation/misc/improving%20ddr%20sdram%20efficiency.pdf

To enable the efficient implementation of these mechanisms, a new communication protocol with the memory controller must be devised. Migen and Milkymist SoC (-NG) implement their own bus, called ASMIbus, based on the split-transaction principle.

Topology
========
The ASMI consists of a memory controller (e.g. ASMIcon) containing a hub that connects the multiple masters, handles transaction tags, and presents a view of the pending requests to the rest of the memory controller.

Links between the masters and the hub are using the same ASMIbus protocol described below.

It is suggested that memory controllers use an interface to a PHY compatible with DFI [dfi]_. The DFI clock can be the same as the ASMIbus clock, with optional serialization and deserialization happening across the PHY, as specified in the DFI standard.

TODO: figure

Signals
=======
The ASMIbus consists of two parts: the control signals, and the data signals.

The control signals are used to issue requests.

* Master-to-Hub:

  * ``adr`` communicates the memory address to be accessed. The unit is the word width of the particular implementation of ASMIbus.
  * ``we`` is the write enable signal.
  * ``stb`` qualifies the transaction request, and should be asserted until ``ack`` goes high.

* Hub-to-Master

  * ``tag_issue`` is an integer representing the transaction ("tag") attributed by the hub. The width of this signal is determined by the maximum number of in-flight transactions that the hub port can handle.
  * ``ack`` is asserted when ``tag_issue`` is valid and the transaction has been registered by the hub. A hub may assert ``ack`` even when ``stb`` is low, which means it is ready to accept any new transaction and will do as soon as ``stb`` goes high.

The data signals are used to complete requests.

* Hub-to-Master

  * ``tag_call`` is used to identify the transaction for which the data is "called". It takes the tag value that has been previously attributed by the hub to that transaction during the issue phase.
  * ``call`` qualifies ``tag_call``.
  * ``data_r`` returns data from the DRAM in the case of a read transaction. It is valid for one cycle after CALL has been asserted and ``tag_call`` has identified the transaction. The value of this signal is undefined for the cycle after a write transaction data have been called.

* Master-to-Hub

  * ``data_w`` must supply data to the controller from the appropriate write transaction, on the cycle after they have been called using ``call`` and ``tag_call``.
  * ``data_wm`` are the byte-granular write data masks. They are used in combination with ``data_w`` to identify the bytes that should be modified in the memory. The ``data_wm`` bit should be high for its corresponding ``data_w`` byte to be written.

In order to avoid duplicating the tag matching and tracking logic, the master-to-hub data signals must be driven low when they are not in use, so that they can be simply ORed together inside the memory controller. This way, only masters have to track (their own) transactions for arbitrating the data lines.

Tags represent in-flight transactions. The hub can reissue a tag as soon as the cycle when it appears on ``tag_call``.

SDRAM burst length and clock ratios
===================================
A system using ASMI must set the SDRAM burst length B, the ASMIbus word width W and the ratio between the ASMIbus clock frequency Fa and the SDRAM I/O frequency Fi so that all data transfers last for exactly one ASMIbus cycle.

More explicitly, these relations must be verified:

B = Fi/Fa

W = B*[number of SDRAM I/O pins]

For DDR memories, the I/O frequency is twice the logic frequency.

Example transactions
====================
TODO: please document me!

Using ASMI with Migen
=====================
TODO: please document me!

Dataflow synthesis
##################
.. WARNING::
   This is experimental and incomplete.

Many hardware acceleration problems can be expressed in the dataflow paradigm, that is, using a directed graph representing the flow of data between actors.

Actors in Migen are written directly in FHDL. This maximizes the flexibility: for example, an actor can implement a DMA master to read data from system memory. It is conceivable that a CAL [cal]_ to FHDL compiler be implemented at some point, to support higher level descriptions of some actors and reuse of third-party RVC-CAL applications. [orcc]_ [orcapps]_ [opendf]_

.. [cal] http://opendf.svn.sourceforge.net/viewvc/opendf/trunk/doc/GentleIntro/GentleIntro.pdf
.. [orcc] http://orcc.sourceforge.net/
.. [orcapps] http://orc-apps.sourceforge.net/
.. [opendf] http://opendf.sourceforge.net/

Actors communicate by exchanging tokens, whose flow is typically controlled using handshake signals (strobe/ack).

Each actor has a "scheduling model". It can be:

* N-sequential: the actor fires when tokens are available at all its inputs, and it produces one output token after N cycles. It cannot accept new input tokens until it has produced its output. A multicycle integer divider would use this model.
* N-pipelined: similar to the sequential model, but the actor can always accept new input tokens. It produces an output token N cycles of latency after accepting input tokens. A pipelined multiplier would use this model.
* Dynamic: the general case, when no simple hypothesis can be made on the token flow behaviour of the actor. An actor accessing system memory on a shared bus would use this model.

Migen Flow automatically generates handshake logic for the first two scheduling models. In the third case, the FHDL descriptions for the logic driving the handshake signals must be provided by the actor.

An actor can be a composition of other actors.

Actor graphs are managed using the NetworkX [networkx]_ library.

.. [networkx] http://networkx.lanl.gov/

.. _simulating:

Simulating a Migen design
#########################
Migen allows you to easily simulate your FHDL design and interface it with arbitrary Python code.

To interpret the design, the FHDL structure is simply converted into Verilog and then simulated using an external program (e.g. Icarus Verilog). This is is intrinsically compatible with VHDL/Verilog instantiations from Migen and maximizes software reuse.

To interface the external simulator to Python, a VPI task is called at each clock cycle and implement the test bench functionality proper - which can be fully written in Python.

Signals inside the simulator can be read and written using VPI as well. This is how the Python test bench generates stimulus and obtains the values of signals for processing.

.. _vpisetup:

Installing the VPI module
*************************
To communicate with the external simulator, Migen uses a UNIX domain socket and a custom protocol which is handled by a VPI plug-in (written in C) on the simulator side.

To build and install this plug-in, run the following commands from the ``vpi`` directory: ::

  make [INCDIRS=-I/usr/...]
  make install [INSTDIR=/usr/...]

The variable ``INCDIRS`` (default: empty) can be used to give a list of paths where to search for the include files. This is useful considering that different Linux distributions put the ``vpi_user.h`` file in various locations.

The variable ``INSTDIR`` (default: ``/usr/lib/ivl``) specifies where the ``migensim.vpi`` file is to be installed.

This plug-in is designed for Icarus Verilog, but can probably be used with most Verilog simulators with minor modifications.

The generic simulator object
****************************
The generic simulator object (``migen.sim.generic.Simulator``) is the central component of the simulation.

Creating a simulator object
===========================
The constructor of the ``Simulator`` object takes the following parameters:

#. The fragment to simulate. The fragment can (and generally does) contain both synthesizable code and a non-synthesizable list of simulation functions.
#. A simulator runner object (see :ref:`simrunner`).
#. A top-level object (see :ref:`toplevel`). With the default value of ``None``, the simulator creates a default top-level object itself.
#. The name of the UNIX domain socket used to communicate with the external simulator through the VPI plug-in (default: "simsocket").

Running the simulation
======================
Running the simulation is achieved by calling the ``run`` method of the ``Simulator`` object.

It takes an optional parameter that defines the maximum number of clock cycles that this call simulates. The default value of -1 sets no cycle limit.

The simulation runs until the maximum number of cycles is reached, or a simulation function sets the property ``interrupt`` to ``True`` in the ``Simulator`` object.

At each clock cycle, the ``Simulator`` object runs in turn all simulation functions listed in the fragment. Simulation functions must take exactly one parameter which is used by the instance of the ``Simulator`` object to pass a reference to itself.

Simulation functions can read the current simulator cycle by reading the ``cycle_counter`` property of the ``Simulator``. The cycle counter's value is 0 for the cycle immediately following the reset cycle.

Reading and writing signals
===========================
Reading and writing signals is done by calling the ``Simulator`` object's methods ``rd`` and ``wr`` (respectively) from simulation functions.

The ``rd`` method takes the FHDL ``Signal`` object to read and returns its value as a Python integer. The returned integer is the value of the signal immediately before the clock edge.

The ``wr`` method takes a ``Signal`` object and the value to write as a Python integer. The signal takes the new value immediately after the clock edge.

The semantics of reads and writes (respectively immediately before and after the clock edge) match those of the non-blocking assignment in Verilog. Note that because of Verilog's design, reading "variable" signals (i.e. written to using blocking assignment) directly may give unexpected and non-deterministic results and is not supported. You should instead read the values of variables after they have gone through a non-blocking assignment in the same ``always`` block.

Reading and writing memories
============================
References to FHDL ``Memory`` objects can also be passed to the ``rd`` and ``wr`` methods. In this case, they take an additional parameter for the memory address.

Initializing signals and memories
=================================
A simulation function can access (and typically initialize) signals and memories during the reset cycle if it has its property ``initialize`` set to ``True``.

In this case, it will be run once at the beginning of the simulation with a cycle counter value of -1 indicating the reset cycle.

.. _simrunner:

The external simulator runner
*****************************

Role
====
The runner object is responsible for starting the external simulator, loading the VPI module, and feeding the generated Verilog into the simulator.

It must implement a ``start`` method, called by the ``Simulator``, which takes two strings as parameters. They contain respectively the Verilog source of the top-level design and the converted fragment.

Icarus Verilog support
======================
Migen comes with a ``migen.sim.icarus.Runner`` object that supports Icarus Verilog.

Its constructor has the following optional parameters:

#. ``extra_files`` (default: ``None``): lists additional Verilog files to simulate.
#. ``top_file`` (default: "migensim_top.v"): name of the temporary file containing the top-level.
#. ``dut_file`` (default: "migensim_dut.v"): name of the temporary file containing the converted fragment.
#. ``vvp_file`` (default: ``None``): name of the temporary file compiled by Icarus Verilog. When ``None``, becomes ``dut_file + "vp"``.
#. ``keep_files`` (default: ``False``): do not delete temporary files. Useful for debugging.

.. _toplevel:

The top-level object
********************

Role of the top-level object
============================
The top-level object is responsible for generating the Verilog source for the top-level test bench.

It must implement a method ``get`` that takes as parameter the name of the UNIX socket the VPI plugin should connect to, and returns the full Verilog source as a string.

It must have the following attributes (which are read by the ``Simulator`` object):

* ``clk_name``: name of the clock signal.
* ``rst_name``: name of the reset signal.
* ``dut_type``: module type of the converted fragment.
* ``dut_name``: name used for instantiating the converted fragment.
* ``top_name``: name/module type of the top-level design.

Role of the generated Verilog
=============================
The generated Verilog must:

#. instantiate the converted fragment and connect its clock and reset ports.
#. produce a running clock signal.
#. assert the reset signal for the first cycle and deassert it immediately after.
#. at the beginning, call the task ``$migensim_connect`` with the UNIX socket name as parameter.
#. at each rising clock edge, call the task ``$migensim_tick``. It is an error to call ``$migensim_tick`` before a call to ``$migensim_connect``.
#. set up the optional VCD output file.

The generic top-level object
============================
Migen comes with a ``migen.sim.generic.TopLevel`` object that implements the above behaviour. It should be usable in the majority of cases.

The main parameters of its constructor are the output VCD file (default: ``None``) and the levels of hierarchy that must be present in the VCD (default: 1).

Basic simulation example
========================
::

	from migen.fhdl.structure import *
	from migen.sim.generic import Simulator
	from migen.sim.icarus import Runner

	class Counter:
		def __init__(self):
			self.count = Signal(BV(4))
		
		def do_simulation(self, s):
			print("Count: " + str(s.rd(self.count)))
		
		def get_fragment(self):
			sync = [self.count.eq(self.count + 1)]
			sim = [self.do_simulation]
			return Fragment(sync=sync, sim=sim)

	def main():
		dut = Counter()
		sim = Simulator(dut.get_fragment(), Runner())
		sim.run(20)

	main()
