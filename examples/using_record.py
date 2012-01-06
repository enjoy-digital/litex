from migen.fhdl.structure import *
from migen.corelogic.record import *

TPL = [
	("x", BV(10)),
	("y", BV(10)),
	("level2", [
		("a", BV(5)),
		("b", BV(5))
	])
]

myrec = Record(TPL)
print(myrec.flatten())
s = myrec.subrecord("level2/a", "x")
print(s.flatten())
print(s.level2.template())
myrec2 = myrec.copy()
print(myrec2.flatten())
