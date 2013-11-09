Bus support
###########

Migen Bus contains classes providing a common structure for master and slave interfaces of the following buses:

* Wishbone [wishbone]_, the general purpose bus recommended by Opencores.
* CSR-2 (see :ref:`csr2`), a low-bandwidth, resource-sensitive bus designed for accessing the configuration and status registers of cores from software.
* LASMIbus (see :ref:`lasmi`), a bus optimized for use with a high-performance frequency-ratio SDRAM controller.
* DFI [dfi]_ (partial), a standard interface protocol between memory controller logic and PHY interfaces.

.. [wishbone] http://cdn.opencores.org/downloads/wbspec_b4.pdf
.. [dfi] http://www.ddr-phy.org/

It also provides interconnect components for these buses, such as arbiters and address decoders. The strength of the Migen procedurally generated logic can be illustrated by the following example: ::

  self.submodules.wbcon = wishbone.InterconnectShared(
      [cpu.ibus, cpu.dbus, ethernet.dma, audio.dma],
      [(lambda a: a[27:] == 0, norflash.bus),
       (lambda a: a[27:] == 1, wishbone2lasmi.wishbone),
       (lambda a: a[27:] == 3, wishbone2csr.wishbone)])

In this example, the interconnect component generates a 4-way round-robin arbiter, multiplexes the master bus signals into a shared bus, and connects all slave interfaces to the shared bus, inserting the address decoder logic in the bus cycle qualification signals and multiplexing the data return path. It can recognize the signals in each core's bus interface thanks to the common structure mandated by Migen Bus. All this happens automatically, using only that much user code.


Configuration and Status Registers
**********************************

.. _csr2:

CSR-2 bus
=========
The CSR-2 bus, is a low-bandwidth, resource-sensitive bus designed for accessing the configuration and status registers of cores from software.

It is the successor of the CSR bus used in Milkymist SoC 1.x, with two modifications:

* Up to 32 slave devices (instead of 16)
* Data words are 8 bits (instead of 32)

.. _bank:

Generating register banks
=========================
Migen Bank is a system comparable to wishbone-gen [wbgen]_, which automates the creation of configuration and status register banks and interrupt/event managers implemented in cores.

.. [wbgen] http://www.ohwr.org/projects/wishbone-gen

Bank takes a description made up of a list of registers and generates logic implementing it with a slave interface compatible with Migen Bus.

The lowest-level description of a register is provided by the ``CSR`` class, which maps to the value at a single address on the target bus. The width of the register needs to be inferior or equal to the bus word width. All accesses are atomic. It has the following signal properties as interface to the user design:

* ``r``, which contains the data written from the bus interface.
* ``re``, which is the strobe signal for ``r``. It is active for one cycle, after or during a write from the bus. ``r`` is only valid when ``re`` is high.
* ``w``, which must provide at all times the value to be read from the bus.

Names of CSRs can be omitted if they can be extracted from the variable name. When using this automatic naming feature, prefixes ``_``, ``r_`` and ``_r_`` are removed.

Compound CSRs (which are transformed into ``CSR`` plus additional logic for implementation) provide additional features optimized for common applications.

The ``CSRStatus`` class is meant to be used as a status register that is read-only from the CPU. The user design is expected to drive its ``status`` signal. The advantage of using ``CSRStatus`` instead of using ``CSR`` and driving ``w`` is that the width of ``CSRStatus`` can be arbitrary. Status registers larger than the bus word width are automatically broken down into several ``CSR`` registers to span several addresses. Be careful that the atomicity of reads is not guaranteed.

The ``CSRStorage`` class provides a memory location that can be read and written by the CPU, and read and optionally written by the design. It can also span several CSR addresses. An optional mechanism for atomic CPU writes is provided; when enabled, writes to the first CSR addresses go to a back-buffer whose contents are atomically copied to the main buffer when the last address is written. When ``CSRStorage`` can be written to by the design, the atomicity of reads by the CPU is not guaranteed.

A module can provide bus-independent CSRs by implementing a ``get_csrs`` method that returns a list of instances of the classes described above. Similary, bus-independent memories can be returned as a list by a ``get_memories`` method.

To avoid listing those manually, a module can inherit from the ``AutoCSR`` class, which provides ``get_csrs`` and ``get_memories`` methods that scan for CSR and memory attributes and return their list. If the module has child objects that implement ``get_csrs`` or ``get_memories``, they will be called by the ``AutoCSR`` methods and their CSR and memories added to the lists returned, with the child objects' names as prefixes.

Generating interrupt controllers
================================
The event manager provides a systematic way to generate standard interrupt controllers.

Its constructor takes as parameters one or several *event sources*. An event source is an instance of either:

* ``EventSourcePulse``, which contains a signal ``trigger`` that generates an event when high. The event stays asserted after the ``trigger`` signal goes low, and until software acknowledges it. An example use is to pulse ``trigger`` high for 1 cycle after the reception of a character in a UART.
* ``EventSourceProcess``, which contains a signal ``trigger`` that generates an event on its falling edge. The purpose of this event source is to monitor the status of processes and generate an interrupt on their completion. The signal ``trigger`` can be connected to the ``busy`` signal of a dataflow actor, for example.
* ``EventSourceLevel``, whose ``trigger`` contains the instantaneous state of the event. It must be set and released by the user design. For example, a DMA controller with several slots can use this event source to signal that one or more slots require CPU attention.

The ``EventManager`` provides a signal ``irq`` which is driven high whenever there is a pending and unmasked event. It is typically connected to an interrupt line of a CPU.

The ``EventManager`` provides a method ``get_csrs``, that returns a bus-independent list of CSRs to be used with Migen Bank as explained above. Each event source is assigned one bit in each of those registers. They are:

* ``status``: contains the current level of the trigger line of ``EventSourceProcess`` and ``EventSourceLevel`` sources. It is 0 for ``EventSourcePulse``. This register is read-only.
* ``pending``: contains the currently asserted events. Writing 1 to the bit assigned to an event clears it.
* ``enable``: defines which asserted events will cause the ``irq`` line to be asserted. This register is read-write.

.. _lasmi:

Lightweight Advanced System Memory Infrastructure
*************************************************

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

Migen and MiSoC implement their own bus, called LASMIbus, that features the last two techniques. Grouping by row had been previously explored with ASMI, but difficulties in achieving timing closure at reasonable latencies in FPGA combined with uncertain performance pay-off for some applications discouraged work in that direction.

Topology and transactions
=========================
The LASMI consists of one or several memory controllers (e.g. LASMIcon from MiSoC), multiple masters, and crossbar interconnect.

Each memory controller can expose several bank machines to the crossbar. This way, requests to different SDRAM banks can be processed in parallel.

Transactions on LASMI work as follows:

1. The master presents a valid address and write enable signals, and asserts its strobe signal.
2. The crossbar decodes the bank address and, in a multi-controller configuration, the controller address and connects the master to the appropriate bank machine.
3. The bank machine acknowledges the request from the master. The master can immediately issue a new request to the same bank machine, without waiting for data.
4. The bank machine sends data acknowledgements to the master, in the same order as it issued requests. After receiving a data acknowldegement, the master must either:

  * present valid data after a fixed number of cycles (for writes). Masters must hold their data lines at 0 at all other times so that they can be simply ORed for each controller to produce the final SDRAM write data.
  * sample the data bus after a fixed number of cycles (for reads).

5. In a multi-controller configuration, the crossbar multiplexes write and data signals to route data to and from the appropriate controller.

When there are queued requests (i.e. more request acknowledgements than data acknowledgements), the bank machine asserts its ``lock`` signal which freezes the crossbar connection between the master and the bank machine. This simplifies two problems:

#. Determining to which master a data acknowledgement from a bank machine should be sent.
#. Having to deal with a master queuing requests into multiple different bank machines which may collectively complete them in a different order than the master issued them.

For each master, transactions are completed in-order by the memory system. Reordering may only occur between masters, e.g. a master issuing a request that hits a page may have it completed sooner than a master requesting earlier a precharge/activate cycle of another bank.

It is suggested that memory controllers use an interface to a PHY compatible with DFI [dfi]_. The DFI clock can be the same as the LASMIbus clock, with optional serialization and deserialization taking place across the PHY, as specified in the DFI standard.

SDRAM burst length and clock ratios
===================================
A system using LASMI must set the SDRAM burst length B, the LASMIbus word width W and the ratio between the LASMIbus clock frequency Fa and the SDRAM I/O frequency Fi so that all data transfers last for exactly one LASMIbus cycle.

More explicitly, these relations must be verified:

B = Fi/Fa

W = B*[number of SDRAM I/O pins]

For DDR memories, the I/O frequency is twice the logic frequency.
