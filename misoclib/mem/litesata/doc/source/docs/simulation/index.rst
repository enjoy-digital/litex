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

Models for all the layers of SATA and a simplified HDD model are provided.
To run a simulation, go to ./test and run:
  - make <simulation_name>