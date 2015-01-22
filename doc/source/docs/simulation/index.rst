.. _simulation-index:

========================
Simulation
========================

.. note::
	Please contribute to this document, or support us financially to write it.

Simulations are available in ./lib/sata/test:
  - crc_tb
  - scrambler_tb
  - phy_datapath_tb
  - link_tb
  - command_tb
  - bist_tb

hdd.py is a simplified HDD model implementing all SATA layers.
To run a simulation, move to ./lib/sata/test and run:
  - make simulation_name