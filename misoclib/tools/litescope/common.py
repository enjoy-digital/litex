from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fsm import FSM, NextState
from migen.flow.actor import *
from migen.genlib.misc import Counter, Timeout
from migen.actorlib.fifo import AsyncFIFO, SyncFIFO
from migen.flow.plumbing import Buffer
from migen.fhdl.specials import Memory


def data_layout(dw):
    return [("data", dw, DIR_M_TO_S)]


def hit_layout():
    return [("hit", 1, DIR_M_TO_S)]
