from migen.fhdl.structure import *
from migen.fhdl.module import Module


class BitonicSort(Module):
    """Combinatorial sorting network

    The Bitonic sort is implemented as a combinatorial sort using
    comparators and multiplexers. Its asymptotic complexity (in terms of
    number of comparators/muxes) is O(n log(n)**2), like mergesort or
    shellsort.

    http://www.dps.uibk.ac.at/~cosenza/teaching/gpu/sort-batcher.pdf

    http://www.inf.fh-flensburg.de/lang/algorithmen/sortieren/bitonic/bitonicen.htm

    http://www.myhdl.org/doku.php/cookbook:bitonic

    Parameters
    ----------
    n : int
        Number of inputs and output signals.
    m : int
        Bit width of inputs and outputs. Or a tuple of `(m, signed)`.
    ascending : bool
        Sort direction. `True` if input is to be sorted ascending,
        `False` for descending. Defaults to ascending.

    Attributes
    ----------
    i : list of Signals, in
        Input values, each `m` wide.
    o : list of Signals, out
        Output values, sorted, each `m` bits wide.
    """
    def __init__(self, n, m, ascending=True):
        self.i = [Signal(m) for i in range(n)]
        self.o = [Signal(m) for i in range(n)]
        self._sort(self.i, self.o, int(ascending), m)

    def _sort_two(self, i0, i1, o0, o1, dir):
        self.comb += [
                o0.eq(i0),
                o1.eq(i1),
                If(dir == (i0 > i1),
                    o0.eq(i1),
                    o1.eq(i0),
                )]

    def _merge(self, i, o, dir, m):
        n = len(i)
        k = n//2
        if n > 1:
            t = [Signal(m) for j in range(n)]
            for j in range(k):
                self._sort_two(i[j], i[j + k], t[j], t[j + k], dir)
            self._merge(t[:k], o[:k], dir, m)
            self._merge(t[k:], o[k:], dir, m)
        else:
            self.comb += o[0].eq(i[0])

    def _sort(self, i, o, dir, m):
        n = len(i)
        k = n//2
        if n > 1:
            t = [Signal(m) for j in range(n)]
            self._sort(i[:k], t[:k], 1, m)  # ascending
            self._sort(i[k:], t[k:], 0, m)  # descending
            self._merge(t, o, dir, m)
        else:
            self.comb += o[0].eq(i[0])
