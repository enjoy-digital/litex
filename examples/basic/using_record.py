from migen.fhdl.structure import *
from migen.corelogic.record import *

L = [
	("x", 10, 8),
	("y", 10, 8),
	("level2", [
		("a", 5, 32),
		("b", 5, 16)
	])
]

myrec = Record(L)
print(myrec.flatten())
print(myrec.flatten(True))
s = myrec.subrecord("level2/a", "x")
print(s.flatten())
print(s.level2.layout())
myrec2 = myrec.copy()
print(myrec2.flatten())
