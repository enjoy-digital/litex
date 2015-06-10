.. _about:

==============
About LiteSATA
==============

LiteSATA provides a small footprint and configurable SATA gen1/2/3 core.

LiteSATA is part of the MiSoC libraries whose aims are to lower entry level of complex FPGA cores by providing simple, elegant and efficient implementations of components used in modern SoCs such as Ethernet, SATA, PCIe, SDRAM controller...

The core uses simple and specific streaming buses and will provide in the future
adapters to use standardized AXI or Avalon-ST streaming buses.

Since Python is used to describe the gateware, the core is highly and easily
configurable.

The synthetizable BIST can be used as a starting point to integrate SATA in
your own SoC.

LiteSATA uses technologies developed in partnership with M-Labs Ltd:
 - Migen enables generating HDL with Python in an efficient way.
 - MiSoC provides the basic blocks to build a powerful and small footprint SoC.

LiteSATA can be used as a Python library or can be integrated with your standard
design flow by generating the Verilog RTL that you will use as a standard core.

.. _about-toolchain:

Features
========
PHY:
  - OOB, COMWAKE, COMINIT
  - ALIGN inserter/remover and bytes alignment on K28.5
  - 8B/10B encoding/decoding in transceiver
  - Errors detection and reporting
  - 32 bits interface
  - 1.5/3.0/6.0GBps supported speeds (respectively 37.5/75/150MHz system clk)
Core:
  Link:
    - CONT inserter/remover
    - Scrambling/Descrambling of data
    - CRC inserter/checker
    - HOLD insertion/detection
    - Errors detection and reporting
  Transport/Command:
    - Easy to use user interfaces (Can be used with or without CPU)
    - 48 bits sector addressing
    - 3 supported commands: READ_DMA(_EXT), WRITE_DMA(_EXT), IDENTIFY_DEVICE
    - Errors detection and reporting

Frontend:
  - Configurable crossbar (simply declare your crossbar and use core.crossbar.get_port() to add a new port!)
  - Ports arbitration transparent to the user
  - Synthesizable BIST
  - Striping module to segment data on multiple HDDs and increase write/read speed and capacity. (RAID0 equivalent)
  - Mirroring module for data redundancy and increase read speeds. (RAID1 equivalent)


Possibles improvements
======================
- add standardized interfaces (AXI, Avalon-ST)
- add NCQ support
- add AES hardware encryption
- add on-the-flow compression/decompression
- add support for Altera PHYs.
- add support for Lattice PHYs.
- add support for Xilinx 7-Series GTP/GTH (currently only 7-Series GTX are
  supported)
- add Zynq Linux drivers.
- ... See below Support and Consulting :)

Support and Consulting
======================
We love open-source hardware and like sharing our designs with others.

LiteSATA is developed and maintained by EnjoyDigital.

If you would like to know more about LiteSATA or if you are already a happy user
and would like to extend it for your needs, EnjoyDigital can provide standard
commercial support as well as consulting services.

So feel free to contact us, we'd love to work with you! (and eventually shorten
the list of the possible improvements :)

Contact
=======
E-mail: florent [AT] enjoy-digital.fr
