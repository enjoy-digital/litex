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

#. The module to simulate.
#. A top-level object (see :ref:`toplevel`). With the default value of ``None``, the simulator creates a default top-level object itself.
#. A simulator runner object (see :ref:`simrunner`). With the default value of ``None``, Icarus Verilog is used with the default parameters.
#. The name of the UNIX domain socket used to communicate with the external simulator through the VPI plug-in (default: "simsocket").
#. Additional keyword arguments (if any) are passed to the Verilog conversion function.

For proper initialization and clean-up, the simulator object should be used as a context manager, e.g. ::

  with Simulator(tb) as s:
    s.run()

Running the simulation
======================

Running the simulation is achieved by calling the ``run`` method of the ``Simulator`` object.

It takes an optional parameter that defines the maximum number of clock cycles that this call simulates. The default value of ``None`` sets no cycle limit.

The cycle counter
=================

Simulation functions can read the current simulator cycle by reading the ``cycle_counter`` property of the ``Simulator``. The cycle counter's value is 0 for the cycle immediately following the reset cycle.

Simplified simulation set-up
============================

Most simulations are run in the same way and do not need the slightly heavy syntax needed to create and run a Simulator object. There is a function that exposes the most common features with a simpler syntax: ::

  run_simulation(module, ncycles=None, vcd_name=None, keep_files=False)

Module-level simulation API
***************************

Simulation functions and generators
===================================

Whenever a ``Module`` declares a ``do_simulation`` method, it is executed at each cycle and can manipulate values from signal and memories (as explained in the next section).

Instead of defining such a method, ``Modules`` can declare a ``gen_simulation`` generator that is initialized at the beginning of the simulation, and yields (usually multiple times) to proceed to the next simulation cycle.

Simulation generators can yield an integer in order to wait for that number of cycles, or yield nothing (``None``) to wait for 1 cycle.

Reading and writing values
===========================

Simulation functions and generators take as parameter a special object that gives access to the values of the signals of the current module using the regular Python read/write syntax. Nested objects, lists and dictionaries containing signals are supported, as well as Migen memories, for reading and writing.

Here are some examples: ::

  def do_simulation(self, selfp):
    selfp.foo = 42
    self.last_foo_value = selfp.foo
    selfp.dut.banks[2].bar["foo"] = 1
    self.last_memory_data = selfp.dut.mem[self.memory_index]

The semantics of reads and writes (respectively immediately before and after the clock edge) match those of the non-blocking assignment in Verilog. Note that because of Verilog's design, reading "variable" signals (i.e. written to using blocking assignment) directly may give unexpected and non-deterministic results and is not supported. You should instead read the values of variables after they have gone through a non-blocking assignment in the same ``always`` block.

Those constructs are syntactic sugar for calling the ``Simulator`` object's methods ``rd`` and ``wr``, that respectively read and write data from and to the simulated design. The simulator object can be accessed as ``selfp.simulator``, and for special cases it is sometimes desirable to call the lower-level methods directly.

The ``rd`` method takes the FHDL ``Signal`` object to read and returns its value as a Python integer. The returned integer is the value of the signal immediately before the clock edge.

The ``wr`` method takes a ``Signal`` object and the value to write as a Python integer. The signal takes the new value immediately after the clock edge.

References to FHDL ``Memory`` objects can also be passed to the ``rd`` and ``wr`` methods. In this case, they take an additional parameter for the memory address.

Simulation termination management
=================================

Simulation functions and generators can raise the ``StopSimulation`` exception. It is automatically raised when a simulation generator is exhausted. This exception disables the current simulation function, i.e. it is no longer run by the simulator. The simulation is over when all simulation functions are disabled (or the specified maximum number of cycles, if any, has been reached - whichever comes first).

Some simulation modules only respond to external stimuli - e.g. the ``bus.wishbone.Tap`` that snoops on bus transactions and prints them on the console - and have simulation functions that never end. To deal with those, the new API introduces "passive" simulation functions that are not taken into account when deciding to continue to run the simulation. A simulation function is declared passive by setting a "passive" attribute on it that evaluates to True. Raising ``StopSimulation`` in such a function still makes the simulator stop running it for the rest of the simulation.

.. _simrunner:

The external simulator runner
*****************************

Role
====

The runner object is responsible for starting the external simulator, loading the VPI module, and feeding the generated Verilog into the simulator.

It must implement a ``start`` method, called by the ``Simulator``, which takes two strings as parameters. They contain respectively the Verilog source of the top-level design and the converted module.

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
