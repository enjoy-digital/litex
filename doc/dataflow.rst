Dataflow
########

Many hardware acceleration problems can be expressed in the dataflow paradigm. It models a program as a directed graph of the data flowing between functions. The nodes of the graph are functional units called actors, and the edges represent the connections (transporting data) between them.

Actors communicate by exchanging data units called tokens. A token contains arbitrary (user-defined) data, which is a record containing one or many fields, a field being a bit vector or another record. Token exchanges are atomic (i.e. all fields are transferred at once from the transmitting actor to the receiving actor).

Actors
******

Actors and endpoints
====================

Actors in Migen are implemented in FHDL. This low-level approach maximizes the practical flexibility: for example, an actor can manipulate the bus signals to implement a DMA master in order to read data from system memory.

Token exchange ports of actors are called endpoints. Endpoints are unidirectional and can be sources (which transmit tokens out of the actor) or sinks (which receive tokens into the actor).

.. figure:: actors_endpoints.png
   :scale: 50 %

   Actors and endpoints.

The flow of tokens is controlled using two handshake signals (strobe and acknowledgement) which are implemented by every endpoint. The strobe signal is driven by sources, and the acknowledgement signal by sinks.

======= ======= ====================================================================================================
``stb`` ``ack`` Situation
======= ======= ====================================================================================================
0       0       The source endpoint does not have data to send, and the sink endpoint is not ready to 
                accept data.
0       1       The sink endpoint is ready to accept data, but the source endpoint has currently no data
                to send. The sink endpoint is not required to keep its ``ack`` signal asserted.
1       0       The source endpoint is trying to send data to the sink endpoint, which is currently not
                ready to accept it. The transaction is *stalled*. The source endpoint must keep ``stb``
                asserted and continue to present valid data until the transaction is completed.
1       1       The source endpoint is sending data to the sink endpoint which is ready to accept it. The
                transaction is *completed*. The sink endpoint must register the incoming data, as the
                source endpoint is not required to hold it valid at the next cycle.
======= ======= ====================================================================================================

It is permitted to generate an ``ack`` signal combinatorially from one or several ``stb`` signals. However, there should not be any combinatorial path from an ``ack`` to a ``stb`` signal.

Actors are derived from the the ``migen.flow.actor.Actor`` base class. The constructor of this base class takes a variable number of parameters, each describing one endpoint of the actor.

An endpoint description is a triple consisting of:

* The endpoint's name.
* A reference to the ``migen.flow.actor.Sink`` or the ``migen.flow.actor.Source`` class, defining the token direction of the endpoint.
* The layout of the data record that the endpoint is dealing with.

Record layouts are a list of fields. Each field is described by a pair consisting of:

* The field's name.
* Either a BV object (see :ref:`bv`) if the field is a bit vector, or another record layout if the field is a lower-level record.

For example, this code: ::

  Actor(
    ("operands", Sink, [("a", BV(16)), ("b", BV(16))]),
    ("result", Source, [("r", BV(17))]))

creates an actor with:

* One sink named ``operands`` accepting data structured as a 16-bit field ``a`` and a 16-bit field ``b``. Note that this is functionally different from having two endpoints ``a`` and ``b``, each accepting a single 16-bit field. With a single endpoint, the data is strobed when *both* ``a`` and ``b`` are valid, and ``a`` and ``b`` are *both* acknowledged *atomically*. With two endpoints, the actor has to deal with accepting ``a`` and ``b`` independently. Plumbing actors (see :ref:`plumbing`) and abstract networks (see :ref:`actornetworks`) provide a systematic way of converting between these two behaviours, so user actors should implement the behaviour that results in the simplest or highest performance design.
* One source named ``result`` transmitting a single 17-bit field named ``r``.

Implementing the functionality of the actor can be done in two ways:

* Overloading the ``get_fragment`` method.
* Overloading both the ``get_control_fragment`` and ``get_process_fragment`` methods. The ``get_control_fragment`` method should return a fragment that manipulates the control signals (strobes, acknowledgements and the actor's busy signal) while ``get_process_fragment`` should return a fragment that manipulates the token payload. Overloading ``get_control_fragment`` alone allows you to define abstract actor classes implementing a given scheduling model. Migen comes with a library of such abstract classes for the most common schedules (see :ref:`schedmod`).

Accessing the endpoints is done via the ``endpoints`` dictionary, which is keyed by endpoint names and contains instances of the ``migen.flow.actor.Endpoint`` class. The latter holds:

* A signal object ``stb``.
* A signal object ``ack``.
* The data payload ``token``. The individual fields are the items (in the Python sense) of this object.

Busy signal
===========

The basic actor class creates a ``busy`` control signal that actor implementations should drive.

This signal represents whether the actor's state holds information that will cause the completion of the transmission of output tokens. For example:

* A "buffer" actor that simply registers and forwards incoming tokens should drive 1 on ``busy`` when its register contains valid data pending acknowledgement by the receiving actor, and 0 otherwise.
* An actor sequenced by a finite state machine should drive ``busy`` to 1 whenever the state machine leaves its idle state.
* An actor made of combinatorial logic is stateless and should tie ``busy`` to 0.

.. _schedmod:

Common scheduling models
========================

For the simplest and most common scheduling cases, Migen provides logic to generate the handshake signals and the busy signal. This is done through abstract actor classes that overload ``get_control_fragment`` only, and the user should overload ``get_process_fragment`` to implement the actor's payload.

These classes are usable only when the actor has exactly one sink and one source (but those endpoints can contain an arbitrary data structure), and in the cases listed below.

Combinatorial
-------------
The actor datapath is made entirely of combinatorial logic. The handshake signals pass through. A small integer adder would use this model.

This model is implemented by the ``migen.flow.actor.CombinatorialActor`` class. There are no parameters or additional control signals.

N-sequential
------------
The actor consumes one token at its input, and it produces one output token after N cycles. It cannot accept new input tokens until it has produced its output. A multicycle integer divider would use this model.

This model is implemented by the ``migen.flow.actor.SequentialActor`` class. The constructor of this class takes as parameter the number of cycles N. The class provides an extra control signal ``trigger`` that pulses to 1 for one cycle when the actor should register the inputs and start its processing. The actor is then expected to provide an output after the N cycles and hold it constant until the next trigger pulse.

N-pipelined
-----------
This is similar to the sequential model, but the actor can always accept new input tokens. It produces an output token N cycles of latency after accepting an input token. A pipelined multiplier would use this model.

This model is implemented by the ``migen.flow.actor.PipelinedActor`` class. The constructor takes the number of pipeline stages N. There is an extra control signal ``pipe_ce`` that should enable or disable all synchronous statements in the datapath (i.e. it is the common clock enable signal for all the registers forming the pipeline stages).

The Migen actor library
***********************

.. _plumbing:

Plumbing actors
===============

Plumbing actors arbitrate the flow of data between actors. For example, when a source feeds two sinks, they ensure that each sink receives exactly one copy of each token transmitted by the source.

Most of the time, you will not need to instantiate plumbing actors directly, as abstract actor networks (see :ref:`actornetworks`) provide a more powerful solution and let Migen insert plumbing actors behind the scenes.

Buffer
------

The ``Buffer`` registers the incoming token and retransmits it. It is a pipelined actor with one stage. It can be used to relieve some performance problems or ease timing closure when many levels of combinatorial logic are accumulated in the datapath of a system.

When used in a network, abstract instances of ``Buffer`` are automatically configured by Migen (i.e. the appropriate token layout is set).

Combinator
----------

This actor combines tokens from several sinks into one source.

For example, when the operands of a pipelined multiplier are available independently, the ``Combinator`` can turn them into a structured token that is sent atomically into the multiplier when both operands are available, simplifying the design of the multiplier actor.

Splitter
--------

This actor does the opposite job of the ``Combinator``. It receives a token from its sink, duplicates it into an arbitrary number of copies, and transmits one through each of its sources. It can optionally omit certain fields of the token (i.e. take a subrecord).

For example, an Euclidean division actor generating the quotient and the remainder in one step can transmit both using one token. The ``Splitter`` can then forward the quotient and the remainder independently, as integers, to other actors.

Structuring actors
==================

Simulation actors
=================

Arithmetic and logic actors
===========================

Bus actors
==========

.. _actornetworks:

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
