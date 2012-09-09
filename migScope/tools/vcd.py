import sys
import datetime

sys.path.append("../../")
from migScope.tools.conv import *

class Var:
	def __init__(self,type , width , name, values=[], default="x"):
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
				r += dec2bin(self.values[cnt+1],self.width)
				r += " "
				r += self.vcd_id
				r += "\n"
				return r
		except :
			return r
		return r
	
		
class Vcd:
	def __init__(self,timescale = "1ps", comment = ""):
		self.timescale = timescale
		self.comment = comment
		self.vars = []
		self.vcd_id = "!"
		self.cnt = -1
		
	def add(self, var):
		var.set_vcd_id(self.vcd_id)
		self.vcd_id = chr(ord(self.vcd_id)+1)
		self.vars.append(var)
	
	def __len__(self):
		l = 0
		for var in self.vars:
			l = max(len(var),l)
		return l
	
	def change(self):
		r = ""
		c = ""
		for var in self.vars:
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
		for var in self.vars:
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
		for var in self.vars:
			r += "b"
			r += dec2bin(var.val, var.width)
			r += " "
			r += var.vcd_id
			r+= "\n"
		r += "$end\n"
		return r
		
	def p_valuechange(self):
		r = ""
		for i in range(len(self)):
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
	

def main():
	myvcd = Vcd()
	myvcd.add(Var("wire",1,"foo1",[0,1,0,1,0,1]))
	myvcd.add(Var("wire",2,"foo2",[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]))
	myvcd.add(Var("wire",3,"foo3"))
	myvcd.add(Var("wire",4,"foo4"))
	ramp = [i%128 for i in range(1024)]
	myvcd.add(Var("wire",16,"ramp",ramp))
	print(myvcd)
	
if __name__ == '__main__':
  main()

