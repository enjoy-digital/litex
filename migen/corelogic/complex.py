from migen.fhdl.structure import *

class Complex:
	def __init__(self, real, imag):
		self.real = real
		self.imag = imag
	
	def __neg__(self):
		return Complex(-self.real, -self.imag)
	
	def __add__(self, other):
		if isinstance(other, Complex):
			return Complex(self.real + other.real, self.imag + other.imag)
		else:
			return Complex(self.real + other, self.imag)
	__radd__ = __add__
	def __sub__(self, other):
		if isinstance(other, Complex):
			return Complex(self.real - other.real, self.imag - other.imag)
		else:
			return Complex(self.real - other, self.imag)
	def __rsub__(self, other):
		if isinstance(other, Complex):
			return Complex(other.real - self.real, other.imag - self.imag)
		else:
			return Complex(other - self.real, -self.imag)
	def __mul__(self, other):
		if isinstance(other, Complex):
			return Complex(self.real*other.real - self.imag*other.imag,
				self.real*other.imag + self.imag*other.real)
		else:
			return Complex(self.real*other, self.imag*other)
	__rmul__ = __mul__
	
	def __lshift__(self, other):
		return Complex(self.real << other, self.imag << other)
	def __rshift__(self, other):
		return Complex(self.real >> other, self.imag >> other)

	def __repr__(self):
		return repr(self.real) + " + " + repr(self.imag) + "j"
	
	def eq(self, r):
		if isinstance(r, Complex):
			return self.real.eq(r.real), self.imag.eq(r.imag)
		else:
			return self.real.eq(r), self.imag.eq(0)

def SignalC(*args, **kwargs):
	real = Signal(*args, **kwargs)
	imag = Signal(*args, **kwargs)
	return Complex(real, imag)
