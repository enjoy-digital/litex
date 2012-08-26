import datetime

def dec2bin(d,nb=0):
	if d=="x":
		return "x"*nb
	elif d==0:
		b="0"
	else:
		b=""
		while d!=0:
			b="01"[d&1]+b
			d=d>>1
	return b.zfill(nb)