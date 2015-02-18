def dec2bin(d, nb=0):
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

def get_bits(values, width, low, high=None):
	r = []
	for val in values:
		t = dec2bin(val, width)[::-1]
		if high == None:
			t = t[low]
		else:
			t = t[low:high]
		t = t[::-1]
		t = int(t,2)
		r.append(t)
	return r

class Dat(list):
	def __init__(self, width):
		self.width = width

	def __getitem__(self, key):
		if isinstance(key, int):
			return get_bits(self, self.width, key)
		elif isinstance(key, slice):
			if key.start != None:
				start = key.start
			else:
				start = 0
			if key.stop != None:
				stop = key.stop
			else:
				stop = self.width
			if stop > self.width:
				stop = self.width
			if key.step != None:
				raise KeyError
			return get_bits(self, self.width, start, stop)
		else:
			raise KeyError

	def decode_rle(self):
		rle_bit = self[-1]
		rle_dat = self[:self.width-1]

		dat = Dat(self.width)
		i=0
		last = 0
		for d in self:
			if rle_bit[i]:
				if len(dat) >= 1:
					# FIX ME... why is rle_dat in reverse order...
					for j in range(int(dec2bin(rle_dat[i])[::-1],2)):
						dat.append(last)
			else:
				dat.append(d)
				last = d
			i +=1
		return dat

class Var:
	def __init__(self, name, width, values=[], type="wire", default="x"):
		self.type = type
		self.width = width
		self.name = name
		self.val = default
		self.values = values
		self.vcd_id = None

	def set_vcd_id(self, s):
		self.vcd_id = s

	def __len__(self):
		return len(self.values)

	def change(self, cnt):
		r = ""
		try :
			if self.values[cnt+1] != self.val:
				r += "b"
				r += dec2bin(self.values[cnt+1], self.width)
				r += " "
				r += self.vcd_id
				r += "\n"
				return r
		except :
			return r
		return r

class Dump:
	def __init__(self):
		self.vars = []
		self.vcd_id = "!"

	def add(self, var):
		var.set_vcd_id(self.vcd_id)
		self.vcd_id = chr(ord(self.vcd_id)+1)
		self.vars.append(var)

	def add_from_layout(self, layout, var):
		i=0
		for s, n in layout:
			self.add(Var(s, n, var[i:i+n]))
			i += n

	def __len__(self):
		l = 0
		for var in self.vars:
			l = max(len(var),l)
		return l
