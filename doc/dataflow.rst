Dataflow synthesis
##################

Many hardware acceleration problems can be expressed in the dataflow paradigm, that is, using a directed graph representing the flow of data between actors.

Actors communicate by exchanging tokens, whose flow is controlled using handshake signals (strobe and acknowledgement).

Actors
******

Overview
========

Actors in Migen are written directly in FHDL. This maximizes the flexibility: for example, an actor can implement a DMA master to read data from system memory. 

Common scheduling models
========================

Combinatorial
-------------
The actor datapath is made entirely of combinatorial logic. The handshake signals pass through. A small integer adder would use this model.

N-sequential
------------
The actor consumes one token at its input, and it produces one output token after N cycles. It cannot accept new input tokens until it has produced its output. A multicycle integer divider would use this model.

N-pipelined
-----------
This is similar to the sequential model, but the actor can always accept new input tokens. It produces an output token N cycles of latency after accepting an input token. A pipelined multiplier would use this model.

The Migen actor library
***********************

Plumbing actors
===============

Structuring actors
==================

Simulation actors
=================

Arithmetic and logic actors
===========================

Bus actors
==========

Actor networks
**************

Actor networks are managed using the NetworkX [networkx]_ library.

.. [networkx] http://networkx.lanl.gov/

Performance tools
*****************


High-level actor description
****************************
.. WARNING::
   Not implemented yet, just an idea.

It is conceivable that a CAL [cal]_ to FHDL compiler be implemented at some point, to support higher level descriptions of some actors and reuse of third-party RVC-CAL applications. [orcc]_ [orcapps]_ [opendf]_

.. [cal] http://opendf.svn.sourceforge.net/viewvc/opendf/trunk/doc/GentleIntro/GentleIntro.pdf
.. [orcc] http://orcc.sourceforge.net/
.. [orcapps] http://orc-apps.sourceforge.net/
.. [opendf] http://opendf.sourceforge.net/
