The FHDL layer
##############

The Fragmented Hardware Description Language (FHDL) is the lowest layer of Migen. It consists of a formal system to describe signals, and combinatorial and synchronous statements operating on them. The formal system itself is low level and close to the synthesizable subset of Verilog, and we then rely on Python algorithms to build complex structures by combining FHDL elements.
The FHDL module also contains a back-end to produce synthesizable Verilog, and some structure analysis and manipulation functionality.

FHDL differs from MyHDL [myhdl]_ in fundamental ways. MyHDL follows the event-driven paradigm of traditional HDLs (see :ref:`background`) while FHDL separates the code into combinatorial statements, synchronous statements, and reset values. In MyHDL, the logic is described directly in the Python AST. The converter to Verilog or VHDL then examines the Python AST and recognizes a subset of Python that it translates into V*HDL statements. This seriously impedes the capability of MyHDL to generate logic procedurally. With FHDL, you manipulate a custom AST from Python, and you can more easily design algorithms that operate on it.

.. [myhdl] http://www.myhdl.org

FHDL is made of several elements, which are briefly explained below. They all can be imported from the ``migen.fhdl.std`` module.

Expressions
***********

Integers and booleans
=====================

Python integers and booleans can appear in FHDL expressions to represent constant values in a circuit. ``True`` and ``False`` are interpreted as 1 and 0, respectively.

Negative integers are explicitly supported. As with MyHDL [countin]_, arithmetic operations return the natural results.

.. [countin] http://www.jandecaluwe.com/hdldesign/counting.html

Signal
======
The signal object represents a value that is expected to change in the circuit. It does exactly what Verilog's "wire" and "reg" and VHDL's "signal" do.

The main point of the signal object is that it is identified by its Python ID (as returned by the :py:func:`id` function), and nothing else. It is the responsibility of the V*HDL back-end to establish an injective mapping between Python IDs and the V*HDL namespace. It should perform name mangling to ensure this. The consequence of this is that signal objects can safely become members of arbitrary Python classes, or be passed as parameters to functions or methods that generate logic involving them.

The properties of a signal object are:

* An integer or a (integer, boolean) pair that defines the number of bits and whether the bit of higher index of the signal is a sign bit (i.e. the signal is signed). The defaults are one bit and unsigned. Alternatively, the ``min`` and ``max`` parameters can be specified to define the range of the signal and determine its bit width and signedness. As with Python ranges, ``min`` is inclusive and defaults to 0, ``max`` is exclusive and defaults to 2.
* A name, used as a hint for the V*HDL back-end name mangler.
* The signal's reset value. It must be an integer, and defaults to 0. When the signal's value is modified with a synchronous statement, the reset value is the initialization value of the associated register. When the signal is assigned to in a conditional combinatorial statement (``If`` or ``Case``), the reset value is the value that the signal has when no condition that causes the signal to be driven is verified. This enforces the absence of latches in designs. If the signal is permanently driven using a combinatorial statement, the reset value has no effect.
  
The sole purpose of the name property is to make the generated V*HDL code easier to understand and debug. From a purely functional point of view, it is perfectly OK to have several signals with the same name property. The back-end will generate a unique name for each object. If no name property is specified, Migen will analyze the code that created the signal object, and try to extract the variable or member name from there. For example, the following statements will create one or several signals named "bar": ::

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
The ``Case`` object constructor takes as first parameter the expression to be tested, and a dictionary whose keys are the values to be matched, and values the statements to be executed in the case of a match. The special value ``"default"`` can be used as match value, which means the statements should be executed whenever there is no other match.

Arrays
======
The ``Array`` object represents lists of other objects that can be indexed by FHDL expressions. It is explicitly possible to:

* nest ``Array`` objects to create multidimensional tables.
* list any Python object in a ``Array`` as long as every expression appearing in a module ultimately evaluates to a ``Signal`` for all possible values of the indices. This allows the creation of lists of structured data.
* use expressions involving ``Array`` objects in both directions (assignment and reading).

For example, this creates a 4x4 matrix of 1-bit signals: ::

  my_2d_array = Array(Array(Signal() for a in range(4)) for b in range(4))

You can then read the matrix with (``x`` and ``y`` being 2-bit signals): ::

  out.eq(my_2d_array[x][y])

and write it with: ::

  my_2d_array[x][y].eq(inp)

Since they have no direct equivalent in Verilog, ``Array`` objects are lowered into multiplexers and conditional statements before the actual conversion takes place. Such lowering happens automatically without any user intervention.

Specials
********

Tri-state I/O
=============
A triplet (O, OE, I) of one-way signals defining a tri-state I/O port is represented by the ``TSTriple`` object. Such objects are only containers for signals that are intended to be later connected to a tri-state I/O buffer, and cannot be used as module specials. Such objects, however, should be kept in the design as long as possible as they allow the individual one-way signals to be manipulated in a non-ambiguous way.

The object that can be used in as a module special is ``Tristate``, and it behaves exactly like an instance of a tri-state I/O buffer that would be defined as follows: ::

  Instance("Tristate",
    io_target=target,
    i_o=o,
    i_oe=oe,
    o_i=i
  )

Signals ``target``, ``o`` and ``i`` can have any width, while ``oe`` is 1-bit wide. The ``target`` signal should go to a port and not be used elsewhere in the design. Like modern FPGA architectures, Migen does not support internal tri-states.

A ``Tristate`` object can be created from a ``TSTriple`` object by calling the ``get_tristate`` method.

By default, Migen emits technology-independent behavioral code for a tri-state buffer. If a specific code is needed, the tristate handler can be overriden using the appropriate parameter of the V*HDL conversion function.

Instances
=========
Instance objects represent the parametrized instantiation of a V*HDL module, and the connection of its ports to FHDL signals. They are useful in a number of cases:

* Reusing legacy or third-party V*HDL code.
* Using special FPGA features (DCM, ICAP, ...).
* Implementing logic that cannot be expressed with FHDL (e.g. latches).
* Breaking down a Migen system into multiple sub-systems.

The instance object constructor takes the type (i.e. name of the instantiated module) of the instance, then multiple parameters describing how to connect and parametrize the instance.

These parameters can be:

* ``Instance.Input``, ``Instance.Output`` or ``Instance.InOut`` to describe signal connections with the instance. The parameters are the name of the port at the instance, and the FHDL expression it should be connected to.
* ``Instance.Parameter`` sets a parameter (with a name and value) of the instance.
* ``Instance.ClockPort`` and ``Instance.ResetPort`` are used to connect clock and reset signals to the instance. The only mandatory parameter is the name of the port at the instance. Optionally, a clock domain name can be specified, and the ``invert`` option can be used to interface to those modules that require a 180-degree clock or a active-low reset.

Memories
========
Memories (on-chip SRAM) are supported using a mechanism similar to instances.

A memory object has the following parameters:

* The width, which is the number of bits in each word.
* The depth, which represents the number of words in the memory.
* An optional list of integers used to initialize the memory.

To access the memory in hardware, ports can be obtained by calling the ``get_port`` method. A port always has an address signal ``a`` and a data read signal ``dat_r``. Other signals may be available depending on the port's configuration.

Options to ``get_port`` are:

* ``write_capable`` (default: ``False``): if the port can be used to write to the memory. This creates an additional ``we`` signal.
* ``async_read`` (default: ``False``): whether reads are asychronous (combinatorial) or synchronous (registered).
* ``has_re`` (default: ``False``): adds a read clock-enable signal ``re`` (ignored for asychronous ports).
* ``we_granularity`` (default: ``0``): if non-zero, writes of less than a memory word can occur. The width of the ``we`` signal is increased to act as a selection signal for the sub-words.
* ``mode`` (default: ``WRITE_FIRST``, ignored for aynchronous ports).  It can be:

  * ``READ_FIRST``: during a write, the previous value is read.
  * ``WRITE_FIRST``: the written value is returned.
  * ``NO_CHANGE``: the data read signal keeps its previous value on a write.

* ``clock_domain`` (default: ``"sys"``): the clock domain used for reading and writing from this port.

Migen generates behavioural V*HDL code that should be compatible with all simulators and, if the number of ports is <= 2, most FPGA synthesizers. If a specific code is needed, the memory handler can be overriden using the appropriate parameter of the V*HDL conversion function.

Inline synthesis directives
===========================

Inline synthesis directives (pseudo-comments such as ``// synthesis attribute keep of clock_signal_name is true``) are supported using the ``SynthesisDirective`` object. Its constructor takes as parameters a string containing the body of the directive, and optional keyword parameters that are used to replace signal names similarly to the Python string method ``format``. The above example could be represented as follows: ::

  SynthesisDirective("attribute keep of {clksig} is true", clksig=clock_domain.clk)

Modules
*******

Modules play the same role as Verilog modules and VHDL entities. Similarly, they are organized in a tree structure. A FHDL module is a Python object that derives from the ``Module`` class. This class defines special attributes to be used by derived classes to describe their logic. They are explained below.

Combinatorial statements
========================

A combinatorial statement is a statement that is executed whenever one of its inputs changes.

Combinatorial statements are added to a module by using the ``comb`` special attribute. Like most module special attributes, it must be accessed using the ``+=`` incrementation operator, and either a single statement, a tuple of statements or a list of statements can appear on the right hand side.

For example, the module below implements a OR gate: ::

  class ORGate(Module):
    def __init__(self):
      self.a = Signal()
      self.b = Signal()
      self.x = Signal()

      ###

      self.comb += x.eq(a | b)

To improve code readability, it is recommended to place the interface of the module at the beginning of the ``__init__`` function, and separate it from the implementation using three hash signs.

Synchronous statements
======================

A synchronous statements is a statement that is executed at each edge of some clock signal.

They are added to a module by using the ``sync`` special attribute, which has the same properties as the ``comb`` attribute.

The ``sync`` special attribute also has sub-attributes that correspond to abstract clock domains. For example, to add a statement to the clock domain named ``foo``, one would write ``self.sync.foo += statement``. The default clock domain is ``sys`` and writing ``self.sync += statement`` is equivalent to writing ``self.sync.sys += statement``.

Submodules and specials
=======================

Submodules and specials can be added by using the ``submodules`` and ``specials`` attributes respectively. This can be done in two ways:

#. anonymously, by using the ``+=`` operator on the special attribute directly, e.g. ``self.submodules += some_other_module``. Like with the ``comb`` and ``sync`` attributes, a single module/special or a tuple or list can be specified.
#. by naming the submodule/special using a subattribute of the ``submodules`` or ``specials`` attribute, e.g. ``self.submodules.foo = module_foo``. The submodule/special is then accessible as an attribute of the object, e.g. ``self.foo`` (and not ``self.submodules.foo``). Only one submodule/special can be added at a time using this form.

Clock domains
=============

Specifying the implementation of a clock domain is done using the ``ClockDomain`` object. It contains the name of the clock domain, a clock signal that can be driven like any other signal in the design (for example, using a PLL instance), and optionally a reset signal. Clock domains without a reset signal are reset using e.g. ``initial`` statements in Verilog, which in many FPGA families initalize the registers during configuration.

The name can be omitted if it can be extracted from the variable name. When using this automatic naming feature, prefixes ``_``, ``cd_`` and ``_cd_`` are removed.

Clock domains are then added to a module using the ``clock_domains`` special attribute, which behaves exactly like ``submodules`` and ``specials``.

Summary of special attributes
=============================

.. table:: Summary of special attributes

   +--------------------------------------------+--------------------------------------------------------------+
   | Syntax                                     | Action                                                       |
   +============================================+==============================================================+
   | self.comb += stmt                          | Add combinatorial statement to current module.               |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.comb += stmtA, stmtB                  | Add combinatorial statements A and B to current module.      |
   |                                            |                                                              |
   | self.comb += [stmtA, stmtB]                |                                                              |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.sync += stmt                          | Add synchronous statement to current module, in default      |
   |                                            | clock domain sys.                                            |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.sync.foo += stmt                      | Add synchronous statement to current module, in clock domain |
   |                                            | foo.                                                         |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.sync.foo += stmtA, stmtB              | Add synchronous statements A and B to current module, in     |
   |                                            | clock domain foo.                                            |
   | self.sync.foo += [stmtA, stmtB]            |                                                              |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.submodules += mod                     | Add anonymous submodule to current module.                   |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.submodules += modA, modB              | Add anonymous submodules A and B to current module.          |
   |                                            |                                                              |
   | self.submodules += [modA, modB]            |                                                              |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.submodules.bar = mod                  | Add submodule named bar to current module. The submodule can |
   |                                            | then be accessed using self.bar.                             |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.specials += spe                       | Add anonymous special to current module.                     |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.specials += speA, speB                | Add anonymous specials A and B to current module.            |
   |                                            |                                                              |
   | self.specials += [speA, speB]              |                                                              |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.specials.bar = spe                    | Add special named bar to current module. The special can     |
   |                                            | then be accessed using self.bar.                             |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.clock_domains += cd                   | Add clock domain to current module.                          |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.clock_domains += cdA, cdB             | Add clock domains A and B to current module.                 |
   |                                            |                                                              |
   | self.clock_domains += [cdA, cdB]           |                                                              |
   +--------------------------------------------+--------------------------------------------------------------+
   | self.clock_domains.pix = ClockDomain()     | Create and add clock domain pix to current module. The clock |
   |                                            | domain name is pix in all cases. It can be accessed using    |
   | self.clock_domains._pix = ClockDomain()    | self.pix, self._pix, self.cd_pix and self._cd_pix,           |
   |                                            | respectively.                                                |
   | self.clock_domains.cd_pix = ClockDomain()  |                                                              |
   |                                            |                                                              |
   | self.clock_domains._cd_pix = ClockDomain() |                                                              |
   +--------------------------------------------+--------------------------------------------------------------+

Clock domain management
=======================

When a module has named submodules that define one or several clock domains with the same name, those clock domain names are prefixed with the name of each submodule plus an underscore.

An example use case of this feature is a system with two independent video outputs. Each video output module is made of a clock generator module that defines a clock domain ``pix`` and drives the clock signal, plus a driver module that has synchronous statements and other elements in clock domain ``pix``. The designer of the video output module can simply use the clock domain name ``pix`` in that module. In the top-level system module, the video output submodules are named ``video0`` and ``video1``. Migen then automatically renames the ``pix`` clock domain of each module to ``video0_pix`` and ``video1_pix``. Note that happens only because the clock domain is defined (using ClockDomain objects), not simply referenced (using e.g. synchronous statements) in the video output modules.

Clock domain name overlap is an error condition when any of the submodules that defines the clock domains is anonymous.

Finalization mechanism
======================

Sometimes, it is desirable that some of a module logic be created only after the user has finished manipulating that module. For example, the FSM module supports that states be defined dynamically, and the width of the state signal can be known only after all states have been added. One solution is to declare the final number of states in the FSM constructor, but this is not user-friendly. A better solution is to automatically create the state signal just before the FSM module is converted to V*HDL. Migen supports this using the so-called finalization mechanism.

Modules can overload a ``do_finalize`` method that can create logic and is called using the algorithm below:

#. Finalization of the current module begins.
#. If the module has already been finalized (e.g. manually), the procedure stops here.
#. Submodules of the current module are recursively finalized.
#. ``do_finalize`` is called for the current module.
#. Any new submodules created by the current module's ``do_finalize`` are recursively finalized.

Finalization is automatically invoked at V*HDL conversion and at simulation. It can be manually invoked for any module by calling its ``finalize`` method.

The clock domain management mechanism explained above happens during finalization.

Simulation
==========

The ``do_simulation`` method of the ``Module`` class can be defined and will be executed at each clock cycle, or the generator-style API can be used by defining ``gen_simulation`` instead. The generator yields the number of cycles it wants to wait for. See :ref:`simulating` for more information on using the simulator.

Simulation of designs with several clock domains is not supported yet.

Conversion for synthesis
************************

Any FHDL module (except, of course, its simulation functions) can be converted into synthesizable Verilog HDL. This is accomplished by using the ``convert`` function in the ``verilog`` module.

The Mibuild component provides scripts to interface third-party FPGA tools to Migen and a database of boards for the easy deployment of designs.
