from migen.fhdl.structure import *

def multimux(sel, inputs, output):
	n = len(inputs)
	i = 0
	comb = []
	for osig in output:
		choices = [x[i] for x in inputs]
		cases = [[Constant(j, sel.bv), osig.eq(choices[j])] for j in range(n)]
		cases[n-1][0] = Default()
		comb.append(Case(sel, *cases))
		i += 1
	return comb
