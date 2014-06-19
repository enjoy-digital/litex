import sys
import datetime

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
		t = t[::1]
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
				r += dec2bin(self.values[cnt+1], self.width)[::-1]
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

class VCDExport():
	def __init__(self, dump, timescale="1ps", comment=""):
		self.dump = dump
		self.timescale = timescale
		self.comment = comment
		self.cnt = -1

	def change(self):
		r = ""
		c = ""
		for var in self.dump.vars:
			c += var.change(self.cnt)
		if c != "":
			r += "#"
			r += str(self.cnt+1)
			r += "\n"
			r += c
		return r

	def p_date(self):
		now = datetime.datetime.now()
		r = "$date\n"
		r += "\t"
		r += now.strftime("%Y-%m-%d %H:%M")
		r += "\n"
		r += "$end\n"
		return r
		
	def p_version(self):
		r  = "$version\n"
		r += "\tmiscope VCD dump\n"
		r += "$end\n"
		return r
		
	def p_comment(self):
		r  = "$comment\n"
		r += self.comment
		r += "\n$end\n"
		return r
		
	def p_timescale(self):
		r  = "$timescale "
		r += self.timescale
		r += " $end\n"
		return r
		
	def p_scope(self):
		r  = "$scope "
		r += self.timescale
		r += " $end\n"
		return r

	def  p_vars(self):
		r = ""
		for var in self.dump.vars:
			r += "$var "
			r += var.type
			r += " "
			r += str(var.width)
			r += " "
			r += var.vcd_id
			r += " "
			r += var.name
			r += " $end\n"
		return r
		
	def p_unscope(self):
		r  = "$unscope "
		r += " $end\n"
		return r
	
	def p_enddefinitions(self):
		r  = "$enddefinitions "
		r += " $end\n"
		return r
	
	def p_dumpvars(self):
		r  = "$dumpvars\n"
		for var in self.dump.vars:
			r += "b"
			r += dec2bin(var.val, var.width)
			r += " "
			r += var.vcd_id
			r+= "\n"
		r += "$end\n"
		return r
		
	def p_valuechange(self):
		r = ""
		for i in range(len(self.dump)):
			r += self.change()
			self.cnt += 1
		return r

	def __repr__(self):
		r = ""
		r += self.p_date()
		r += self.p_version()
		r += self.p_comment()
		r += self.p_timescale()
		r += self.p_scope()
		r += self.p_vars()
		r += self.p_unscope()
		r += self.p_enddefinitions()
		r += self.p_dumpvars()
		r += self.p_valuechange()
		return r

	def write(self, filename):
		f = open(filename, "w")
		f.write(str(self))
		f.close()

class CSVExport():
	def __init__(self, dump):
		self.dump = dump

	def  p_vars(self):
		r = ""
		for var in self.dump.vars:
			r += var.name
			r += ","
		r += "\n"
		for var in self.dump.vars:
			r += str(var.width)
			r += ","
		r += "\n"
		return r
			
	def p_dumpvars(self):
		r  = ""
		for i in range(len(self.dump)):
			for var in self.dump.vars:
				try:
					var.val = var.values[i]
				except:
					pass
				if var.val == "x":
					r += "x"
				else:
					r += dec2bin(var.val, var.width)
				r += ", "
			r+= "\n"
		return r

	def __repr__(self):
		r = ""
		r += self.p_vars()
		r += self.p_dumpvars()
		return r

	def write(self, filename):
		f = open(filename, "w")
		f.write(str(self))
		f.close()

class PYExport():
	def __init__(self, dump):
		self.dump = dump

	def __repr__(self):
		r = "dump = {\n"
		for var in self.dump.vars:
			r += "\"" + var.name + "\""
			r += " : "
			r += str(var.values)
			r += ",\n"
		r += "}"
		return r

	def write(self, filename):
		f = open(filename, "w")
		f.write(str(self))
		f.close()		

def main():
	dump = Dump()
	dump.add(Var("foo1", 1, [0,1,0,1,0,1]))
	dump.add(Var("foo2", 2, [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]))
	ramp = [i%128 for i in range(1024)]
	dump.add(Var("ramp", 16, ramp))
	
	VCDExport(dump).write("mydump.vcd")
	CSVExport(dump).write("mydump.csv")
	PYExport(dump).write("mydump.py")
	
if __name__ == '__main__':
  main()

