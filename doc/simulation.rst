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
#. Additional keyword arguments (if any) are passed to the Verilog conversion function.

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

Simulation examples
*******************

Most basic
==========
.. include:: ../examples/sim/basic1.py
   :code: python

A few more features
===================
.. include:: ../examples/sim/basic2.py
   :code: python

Memory access
=============
.. include:: ../examples/sim/memory.py
   :code: python

A FIR filter
============
.. include:: ../examples/sim/fir.py
   :code: python
   
Abstract bus transactions
=========================
.. include:: ../examples/sim/abstract_transactions.py
   :code: python

.. _dfsimexample:
   
Dataflow simulation actors
==========================
.. include:: ../examples/sim/dataflow.py
   :code: python
