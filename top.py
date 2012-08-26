from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr

from migScope import trigger
from migScope import recorder

import spi2Csr

from migScope.tools.truthtable import *

#
#Test Term
#
#term = trigger.Term(32,True)
#v = verilog.convert(term.get_fragment())
#print(v)

#
#Test RangeDetector
#
#rangeDetector = trigger.RangeDetector (32,True)
#v = verilog.convert(rangeDetector.get_fragment())
#print(v)

#
#Test EdgeDetector
#
#edgeDetector = trigger.EdgeDetector (32,True,"RFB")
#v = verilog.convert(edgeDetector.get_fragment())
#print(v)

#
#Test Timer
#
#timer = trigger.Timer(32)
#v = verilog.convert(timer.get_fragment())
#print(v)

#
#Test Sum
#
#sum = trigger.Sum(4,pipe=False)
#v = verilog.convert(sum.get_fragment())
#print(v)

#
#Test Storage
#
#storage = recorder.Storage(32,1024)
#v = verilog.convert(storage.get_fragment())
#print(v)

#
#Test Sequencer
#
#sequencer = recorder.Sequencer(1024)
#v = verilog.convert(sequencer.get_fragment())
#print(v)

#
#Test Recorder
#
#recorder = recorder.Recorder(0,32,1024)
#v = verilog.convert(recorder.get_fragment())
#print(v)

#
#Test Trigger
#
term0 = trigger.Term(32)
term1 = trigger.RangeDetector(32)
term2 = trigger.EdgeDetector(32)
term3 = trigger.Term(32)

trigger0 = trigger.Trigger(0,32,64,[term0, term1, term2, term3])
recorder0 = recorder.Recorder(0,32,1024)
v = verilog.convert(trigger0.get_fragment()+recorder0.get_fragment())
print(v)

#
#Test spi2Csr
#
#spi2csr0 = spi2Csr.Spi2Csr(16,8)
#v = verilog.convert(spi2csr0.get_fragment())
#print(v)

print(gen_truth_table("A&B&C"))


