The FHDL layer
##############

The Fragmented Hardware Description Language (FHDL) is the lowest layer of Migen. It consists of a formal system to describe signals, and combinatorial and synchronous statements operating on them. The formal system itself is low level and close to the synthesizable subset of Verilog, and we then rely on Python algorithms to build complex structures by combining FHDL elements and encapsulating them in "fragments".
The FHDL module also contains a back-end to produce synthesizable Verilog, and some basic analysis functions. It would be possible to develop a VHDL back-end as well, though more difficult than for Verilog - we are "cheating" a bit now as Verilog provides most of the FHDL semantics.

FHDL differs from MyHDL [myhdl]_ in fundamental ways. MyHDL follows the event-driven paradigm of traditional HDLs (see :ref:`background`) while FHDL separates the code into combinatorial statements, synchronous statements, and reset values. In MyHDL, the logic is described directly in the Python AST. The converter to Verilog or VHDL then examines the Python AST and recognizes a subset of Python that it translates into V*HDL statements. This seriously impedes the capability of MyHDL to generate logic procedurally. With FHDL, you manipulate a custom AST from Python, and you can more easily design algorithms that operate on it.

.. [myhdl] http://www.myhdl.org

FHDL is made of several elements, which are briefly explained below.

Expressions
***********

.. _bv:

Bit vector (BV)
===============
The bit vector (BV) object defines if a constant or signal is signed or unsigned, and how many bits it has. This is useful e.g. to:

* Determine when to perform sign extension (FHDL uses the same rules as Verilog).
* Determine the size of registers.
* Determine how many bits should be used by each value in concatenations.

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

* A bit vector description
* A name, used as a hint for the V*HDL back-end name mangler.
* A boolean "variable". If true, the signal will behave like a VHDL variable, or a Verilog reg that uses blocking assignment. This parameter only has an effect when the signal's value is modified in a synchronous statement.
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
The ``Case`` object constructor takes as first parameter the expression to be tested, then a variable number of lists describing the various cases.

Each list contains an expression (typically a constant) describing the value to be matched, followed by the statements to be executed when there is a match. The head of the list can be the an instance of the ``Default`` object.

Arrays
======
The ``Array`` object represents lists of other objects that can be indexed by FHDL expressions. It is explicitely possible to:

* nest ``Array`` objects to create multidimensional tables.
* list any Python object in a ``Array`` as long as every expression appearing in a fragment ultimately evaluates to a ``Signal`` for all possible values of the indices. This allows the creation of lists of structured data.
* use expressions involving ``Array`` objects in both directions (assignment and reading).

For example, this creates a 4x4 matrix of 1-bit signals: ::

  my_2d_array = Array(Array(Signal() for a in range(4)) for b in range(4))

You can then read the matrix with (``x`` and ``y`` being 2-bit signals): ::

  out.eq(my_2d_array[x][y])

and write it with: ::

  my_2d_array[x][y].eq(inp)

Since they have no direct equivalent in Verilog, ``Array`` objects are lowered into multiplexers and conditional statements before the actual conversion takes place. Such lowering happens automatically without any user intervention.

Special elements
****************

Instances
=========
Instance objects represent the parametrized instantiation of a V*HDL module, and the connection of its ports to FHDL signals. They are useful in a number of cases:

* Reusing legacy or third-party V*HDL code.
* Using special FPGA features (DCM, ICAP, ...).
* Implementing logic that cannot be expressed with FHDL (asynchronous circuits, ...).
* Breaking down a Migen system into multiple sub-systems, possibly using different clock domains.

The properties of the instance object are:

* The type of the instance (i.e. name of the instantiated module).
* A list of output ports of the instantiated module. Each element of the list is a pair containing a string, which is the name of the module's port, and either an existing signal (on which the port will be connected to) or a BV (which will cause the creation of a new signal).
* A list of input ports (likewise).
* A list of (name, value) pairs for the parameters ("generics" in VHDL) of the module.
* The name of the clock port of the module (if any). If this is specified, the port will be connected to the system clock.
* The name of the reset port of the module (likewise).
* The name of the instance (can be mangled like signal names).

Memories
========
Memories (on-chip SRAM) are supported using a mechanism similar to instances.

A memory object has the following parameters:

* The width, which is the number of bits in each word.
* The depth, which represents the number of words in the memory.
* An optional list of integers used to initialize the memory.
* A list of port descriptions.

Each port description contains:

* The address signal (mandatory).
* The data read signal (mandatory).
* The write enable signal (optional). If the port is using masked writes, the width of the write enable signal should match the number of sub-words.
* The data write signal (iff there is a write enable signal).
* Whether reads are synchronous (default) or asynchronous.
* The read enable port (optional, ignored for asynchronous ports).
* The write granularity (default 0), which defines the number of bits in each sub-word. If it is set to 0, the port is using whole-word writes only and the width of the write enable signal must be 1. This parameter is ignored if there is no write enable signal.
* The mode of the port (default ``WRITE_FIRST``, ignored for asynchronous ports). It can be:

  * ``READ_FIRST``: during a write, the previous value is read.
  * ``WRITE_FIRST``: the written value is returned.
  * ``NO_CHANGE``: the data read signal keeps its previous value on a write.

Migen generates behavioural V*HDL code that should be compatible with all simulators and, if the number of ports is <= 2, most FPGA synthesizers. If a specific code is needed, the memory generator function can be overriden using the ``memory_handler`` parameter of the conversion function.

Fragments
*********
A "fragment" is a unit of logic, which is composed of:

* A list of combinatorial statements.
* A list of synchronous statements.
* A list of instances.
* A list of memories.
* A list of simulation functions (see :ref:`simulating`).

Fragments can reference arbitrary signals, including signals that are referenced in other fragments. Fragments can be combined using the "+" operator, which returns a new fragment containing the concatenation of each pair of lists.

Fragments can be passed to the back-end for conversion to Verilog.

By convention, classes that generate logic implement a method called ``get_fragment``. When called, this method builds a new fragment implementing the desired functionality of the class, and returns it. This convention allows fragments to be built automatically by combining the fragments from all relevant objects in the local scope, by using the autofragment module.

Conversion for synthesis
************************

Any FHDL fragment (except, of course, its simulation functions) can be converted into synthesizable Verilog HDL. This is accomplished by using the ``convert`` function in the ``verilog`` module.

Migen does not provide support for any specific synthesis tools or ASIC/FPGA technologies. Users must run themselves the generated code through the appropriate tool flow for hardware implementation.
