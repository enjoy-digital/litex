import glob, os, re, json

import numpy as np
import matplotlib.pyplot as plt
import pandas


def extract(b, n, r, c=int):
	r = re.compile(r)
	try:
		f = open(b + n)
	except:
		return
	for l in f:
		m = r.search(l)
		if m:
			v = m.groups()[0]
			v = v.replace(",", "")
			return c(v)

def load(prefix, base):
	kw = json.load(open(base))
	b = os.path.splitext(base)[0]
	_, n = os.path.split(b)[1].split("_", 1)
	try:
		n, _ = n.rsplit("_", 1)
		kw["vary"] = n
	except:
		pass
	kw["slack"] = extract(b, ".par",
			"GRPclk.*SETUP +\\| +([\d,]+\\.\d+)", float)
	kw["freq"] = extract(b, ".srp",
			"Maximum Frequency: +([\d,]+\\.\d+) *MHz", float)
	kw["reg"] = extract(b, "_map.mrp",
			"Number of Slice Registers: +([\d,]+) ")
	kw["lut"] = extract(b, "_map.mrp",
			"Number of Slice LUTs: +([\d,]+) ")
	kw["slice"] = extract(b, "_map.mrp",
			"Number of occupied Slices: +([\d,]+) ")
	return kw

def run(prefix):
	dat = {}
	for base in glob.glob("build/{}_*.json".format(prefix)):
		kw = load(prefix, base)
		if "vary" in kw:
			dat[base] = kw
	df = pandas.DataFrame.from_dict(dat, orient="index")
	comp = "freq slice slack".split()
	dfg = df.groupby("vary")
	fig, ax = plt.subplots(len(dfg), len(comp))
	for axj, (v, dfi) in zip(ax, dfg):
		print(v, dfi)
		if v not in dfi:
			continue
		dfi = dfi.sort(v)
		for axi, n in zip(axj, comp):
			x = dfi[v]
			if type(x[0]) is type(""):
				xi = range(len(x))
				axi.set_xticks(xi)
				axi.set_xticklabels(x)
				x = xi
			axi.plot(x, dfi[n])
			axi.set_xlabel(v)
			axi.set_ylabel(n)
	fig.savefig("cordic_impl.pdf")
	plt.show()

if __name__ == "__main__":
	run("cordic")
