from migen.fhdl import structure as f

def MultiMux(sel, inputs, output):
	n = len(inputs)
	i = 0
	comb = []
	for osig in output:
		choices = [x[i] for x in inputs]
		cases = [(f.Constant(j, sel.bv), [f.Assign(osig, choices[j])]) for j in range(n)]
		default = cases.pop()[1]
		comb.append(f.Case(sel, cases, default))
		i += 1
	return comb