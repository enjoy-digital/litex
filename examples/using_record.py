from migen.fhdl.structure import *
from migen.corelogic.record import *

L = [
	("x", BV(10)),
	("y", BV(10)),
	("level2", [
		("a", BV(5)),
		("b", BV(5))
	])
]

myrec = Record(L)
print(myrec.flatten())
s = myrec.subrecord("level2/a", "x")
print(s.flatten())
print(s.level2.layout())
myrec2 = myrec.copy()
print(myrec2.flatten())
