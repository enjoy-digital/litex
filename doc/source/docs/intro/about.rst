.. _about:

================
About LiteScope
================

LiteScope is a small footprint and configurable embedded logic analyzer that you
can use in your FPGA and aims to provide a free, portable and flexible
alternatve to vendor's solutions!

LiteScope is part of LiteX libraries whose aims are to lower entry level of complex
FPGA cores by providing simple, elegant and efficient implementations of
components used in today's SoC such as Ethernet, SATA, PCIe, SDRAM Controller...

The core uses simple and specific streaming buses and will provides in the future
adapters to use standardized AXI or Avalon-ST streaming buses.

Since Python is used to describe the HDL, the core is highly and easily
configurable.

LiteScope uses technologies developed in partnership with M-Labs Ltd:
 - Migen enables generating HDL with Python in an efficient way.
 - MiSoC provides the basic blocks to build a powerful and small footprint SoC.

LiteScope can be used as a Migen/MiSoC library (by simply installing  it
with the provided setup.py) or can be integrated with your standard design flow
by generating the verilog rtl that you will use as a standard core.

LiteScope produces "vcd" files that can be read in your regular waveforms viewer.

Since LiteScope also provides a UART <--> Wishbone brige so you only need 2
external Rx/Tx pins to be ready to debug or control all your Wishbone peripherals!

.. _about-toolchain:

Features
========
- IO peek and poke with LiteScopeIO
- Logic analyser with LiteScopeLA:
  - Various triggering modules: Term, Range, Edge (add yours! :)
  - Run Length Encoder to "compress" data and increase recording depth
  - Subsampling
  - Storage qualifier
  - Data storage in block rams


Possibles improvements
======================
- add standardized interfaces (AXI, Avalon-ST)
- add protocols analyzers
- add signals injection/generation
- add storage in DRAM
- add storage in HDD with LiteSATA core (to be released soon!)
- add Ethernet Wishbone bridge
- add PCIe Wishbone bridge with LitePCIe (to be released soon!)
- ... See below Support and Consulting :)

Support and Consulting
======================
We love open-source hardware and like sharing our designs with others.

LiteScope is developed and maintained by EnjoyDigital.

If you would like to know more about LiteScope or if you are already a happy user
and would like to extend it for your needs, EnjoyDigital can provide standard
commercial support as well as consulting services.

So feel free to contact us, we'd love to work with you! (and eventually shorten
the list of the possible improvements :)

Contact
=======
E-mail: florent [AT] enjoy-digital.fr


