from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr

import migScope

#
#Test Term
#
#term = migScope.Term(32,True)
#v = verilog.convert(term.get_fragment())
#print(v)

#
#Test RangeDetector
#
#rangeDetector = migScope.RangeDetector (32,True)
#v = verilog.convert(rangeDetector.get_fragment())
#print(v)

#
#Test EdgeDetector
#
#edgeDetector = migScope.EdgeDetector (32,True,"RFB")
#v = verilog.convert(edgeDetector.get_fragment())
#print(v)

#
#Test Timer
#
#timer = migScope.Timer(32)
#v = verilog.convert(timer.get_fragment())
#print(v)

#
#Test Sum
#
#sum = migScope.Sum(4,pipe=True)
#v = verilog.convert(sum.get_fragment())
#print(v)

#
#Test MigIo
#
#migIo = migScope.MigIo(32,"IO")
#v = verilog.convert(migIo.get_fragment())
#print(v)

#
#Test Storage
#
#storage = migScope.Storage(32,1024)
#v = verilog.convert(storage.get_fragment())
#print(v)

#
#Test Sequencer
#
#sequencer = migScope.Sequencer(1024)
#v = verilog.convert(sequencer.get_fragment())
#print(v)

#
#Test Recorder
#
#recorder = migScope.Recorder(0,32,1024)
#v = verilog.convert(recorder.get_fragment())
#print(v)

#
#Test Trigger
#
term0 = migScope.Term(32)
term1 = migScope.RangeDetector(32)
term2 = migScope.EdgeDetector(32)
term3 = migScope.Term(32)

trigger0 = migScope.Trigger(0,32,64,[term0, term1, term2, term3])
#trigger0 = migScope.Trigger(0,32,64,[term0])
v = verilog.convert(trigger0.get_fragment())
print(v)

