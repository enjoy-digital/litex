from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.corelogic.fsm import FSM

s = Signal()
myfsm = FSM('FOO', 'BAR')
myfsm.act(myfsm.FOO, s.eq(1), myfsm.next_state(myfsm.BAR))
myfsm.act(myfsm.BAR, s.eq(0), myfsm.next_state(myfsm.FOO))
print(verilog.convert(myfsm.get_fragment(), {s}))
