.. _frontend-index:

========================
Frontend
========================

Crossbar and user ports
=======================

LiteSATA provides a crossbar to let the user request the number of port he needs.
Ports are automatically arbitrated and dispatched to and from the core. In the
following example we create a core and get a port from the crossbar:

.. code-block:: python

    self.submodules.sata_phy = LiteSATAPHY(platform.device,
                                           platform.request("sata"),
                                           "sata_gen2",
                                           clk_freq)
    self.submodules.sata = LiteSATA(self.sata_phy)
    user_port = self.sata.crossbar.get_port()

Our user_port has 2 endpoints:

 - A Sink used to send commands and write data.
 - A Source used to receive commands acknowledges and receive read data.

Packets description
===================

Sink and Source are packets with additional parameters. A packet has the following signals:

 - stb: Strobe signal indicates that command or data is valid.
 - sop: Start Of Packet signal indicates that current command or data is the first of the packet.
 - eop: End Of Packet signal indicates that current command or data is the last of the packet.
 - ack: Response from the endpoint indicates that core is able to accept our command or data.
 - data: Current data of the packet.

.. figure:: packets.png
   :scale: 30 %
   :align: center

   An example of packet transaction between endpoints.

.. tip::

	- When a packet only has a command or data, sop and eop must be set to 1 on the same clock cycle.
	- A data is accepted when stb=1 and ack=1.

User Commands
=============

All HDD transfers are initiated using the Sink endpoint which has the following signals:

 - write: 1 bit signal indicates if we want to write data to the HDD.
 - read: 1 bit signal indicaties if we want to read data from the HDD.
 - identify: 1 bit signal indicates if command is an identify device command (use to get HDD informations).
 - sector: 48 bits signal, the sector number we are going to write or read.
 - count: 16 bits signal, the number of sectors we are going to write or read.
 - data: 32 bits signal, the write data.

.. tip::

	- write, read, identify, sector, count are parameters so remain constant for a packet duration.
	- sector, count are ignored during an identify command.
	- data is ignored during a read or identify command.

User Responses
==============

HDD responses are obtained from the Source endpoint which has the following signals:

 - write: 1 bit signal indicates if command was a write.
 - read: 1 bit signal indicaties if command was a read.
 - identify: 1 bit signal indicates if command was an identify device command.
 - last: 1 bit signal indicates if this is the last packet of the response. (A Response can be return in several packets)
 - failed: 1 bit signal identicates if an error was detected in the response (CRC, FIS...)
 - data: 32 bits signal, the read data

.. tip::

	- write, read, identify, last are parameters so remain constant for a packet duration.
	- data can be ignored in the case of a write or identify command.
	- in case of a read command, read data packets are presented followed by an empty packet indicating the end of the transaction (last=1).

Examples
========

A BIST_ (Data generator and checker) design is provided. It can be used to understand how to connect
your logic to the user_port provided by the crossbar. (See LiteSATABISTGenerator, LiteSATABISTChecker and LiteSATABISTIdentify)

.. _BIST: https://github.com/m-labs/misoc/blob/master/misoclib/mem/litesata/frontend/bist.py

