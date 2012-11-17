import operator

def bitslice(val, low, up=None):
	if up is None:
		up = low + 1
	nbits = up - low
	mask = (2**nbits - 1) << low
	return (val & mask) >> low

class Register:
	def __init__(self, nbits):
		self._nbits = nbits
		self._val = 0
	
	def _set_store(self, val):
		self._val = val & (2**self._nbits - 1)
	store = property(None, _set_store)

	def __nonzero__(self):
		if self._val:
			return 1
		else:
			return 0

	def __len__(self):
		return self._nbits

	def __add__(self, other):
		if isinstance(other, Register):
			return self._val + other._val
		else:
			return self._val + other
	def __radd__(self, other):
		return other + self._val

	def __sub__(self, other):
		if isinstance(other, Register):
			return self._val - other._val
		else:
			return self._val - other
	def __rsub__(self, other):
		return other - self._val

	def __mul__(self, other):
		if isinstance(other, Register):
			return self._val * other._val
		else:
			return self._val * other
	def __rmul__(self, other):
		return other * self._val

	def __div__(self, other):
		if isinstance(other, Register):
			return self._val / other._val
		else:
			return self._val / other
	def __rdiv__(self, other):
		return other / self._val

	def __truediv__(self, other):
		if isinstance(other, Register):
			return operator.truediv(self._val, other._val)
		else:
			return operator.truediv(self._val, other)
	def __rtruediv__(self, other):
		return operator.truediv(other, self._val)

	def __floordiv__(self, other):
		if isinstance(other, Register):
			return self._val // other._val
		else:
			return self._val // other
	def __rfloordiv__(self, other):
		return other //  self._val

	def __mod__(self, other):
		if isinstance(other, Register):
			return self._val % other._val
		else:
			return self._val % other
	def __rmod__(self, other):
		return other % self._val

	def __pow__(self, other):
		if isinstance(other, Register):
			return self._val ** other._val
		else:
			return self._val ** other
	def __rpow__(self, other):
		return other ** self._val

	def __lshift__(self, other):
		if isinstance(other, Register):
			return self._val << other._val
		else:
			return self._val << other
	def __rlshift__(self, other):
		return other << self._val
		
	def __rshift__(self, other):
		if isinstance(other, Register):
			return self._val >> other._val
		else:
			return self._val >> other
	def __rrshift__(self, other):
		return other >> self._val

	def __and__(self, other):
		if isinstance(other, Register):
			return self._val & other._val
		else:
			return self._val & other
	def __rand__(self, other):
		return other & self._val

	def __or__(self, other):
		if isinstance(other, Register):
			return self._val | other._val
		else:
			return self._val | other
	def __ror__(self, other):
		return other | self._val

	def __xor__(self, other):
		if isinstance(other, Register):
			return self._val ^ other._val
		else:
			return self._val ^ other
	def __rxor__(self, other):
		return other ^ self._val

	def __neg__(self):
		return -self._val

	def __pos__(self):
		return +self._val

	def __abs__(self):
		return abs(self._val)

	def __invert__(self):
		return ~self._val

	def __int__(self):
		return int(self._val)

	def __float__(self):
		return float(self._val)

	def __oct__(self):
		return oct(self._val)

	def __hex__(self):
		return hex(self._val)

	def __index__(self):
		return int(self._val)

	def __lt__(self, other):
		return self._val < other

	def __le__(self, other):
		return self._val <= other

	def __eq__(self, other):
		return self._val == other

	def __ge__(self, other):
		return self._val >= other

	def __gt__(self, other):
		return self._val > other

	def __ne__(self, other):
		return self._val != other

	def __str__(self):
		return str(self._val)

	def __repr__(self):
		return "Register(" + repr(self._val) + ")"

	def _augm(self, other):
		raise TypeError("Register objects do not support augmented assignment")
	__iadd__ = __isub__ = __idiv__ = __imul__ = __ipow__ = __imod__ = _augm
	__ior__ = __iand__ = __ixor__ = __irshift__ = __ilshift__ = _augm

	def __setitem__(self, key, val):
		raise TypeError("Register objects do not support item/slice assignment")
