from migen.fhdl.structure import *
from migen.transform.unroll import unroll_sync
from migen.fhdl import verilog

x = Signal(BV(4))
y = Signal(BV(4))
acc = Signal(BV(4), variable=True)
z = Signal()

sync = [
	If(acc == 2, acc.eq(3)),
	acc.eq(acc + x + y),
	z.eq(acc == 0)
]

n = 5
xs = [Signal(BV(4)) for i in range(n)]
ys = [Signal(BV(4)) for i in range(n)]
accs = [Signal(BV(4)) for i in range(n)]
zs = [Signal() for i in range(n)]

sync_u = unroll_sync(sync, {x: xs, y: ys, acc: accs, z: zs})
print(verilog.convert(Fragment(sync=sync_u), ios=set(xs+ys+zs)))
