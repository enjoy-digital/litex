from migen.fhdl.structure import *
from migen.fhdl.module import Module, FinalizeError
from migen.fhdl.specials import TSTriple, Instance, Memory
from migen.fhdl.bitcontainer import log2_int, bits_for, flen, fiter, fslice, freversed
from migen.fhdl.decorators import DecorateModule, InsertCE, InsertReset, RenameClockDomains
