.. _about:

================
About LiteEth
================

LiteEth provides a small footprint and configurable Ethernet core.

LiteEth is part of MiSoC libraries whose aims are to lower entry level of
complex FPGA cores by providing simple, elegant and efficient implementations
ofcomponents used in today's SoC such as Ethernet, SATA, PCIe, SDRAM Controller...

The core uses simple and specific streaming buses and will provides in the future
adapters to use standardized AXI or Avalon-ST streaming buses.

Since Python is used to describe the HDL, the core is highly and easily
configurable.

LiteEth uses technologies developed in partnership with M-Labs Ltd:
 - Migen enables generating HDL with Python in an efficient way.
 - MiSoC provides the basic blocks to build a powerful and small footprint SoC.

LiteEth can be used as MiSoC library or can be integrated with your standard
design flow by generating the verilog rtl that you will use as a standard core.

.. _about-toolchain:

Features
========
- Ethernet MAC with various interfaces and various PHYs (GMII, MII, Loopback)
- Hardware UDP/IP stack with ARP and ICMP

Possibles improvements
======================
- add standardized interfaces (AXI, Avalon-ST)
- add DMA interface to MAC
- add hardware Etherbone support
- add RGMII/SGMII PHYs
- ... See below Support and Consulting :)

Support and Consulting
======================
We love open-source hardware and like sharing our designs with others.

LiteEth is mainly developed and maintained by EnjoyDigital.

If you would like to know more about LiteEth or if you are already a happy user
and would like to extend it for your needs, EnjoyDigital can provide standard
commercial support as well as consulting services.

So feel free to contact us, we'd love to work with you! (and eventually shorten
the list of the possible improvements :)

Contact
=======
E-mail: florent [AT] enjoy-digital.fr


