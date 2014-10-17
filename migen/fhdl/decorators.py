from migen.fhdl.structure import *
from migen.fhdl.tools import insert_reset, rename_clock_domain

class ModuleDecorator:
	def __init__(self, decorated):
		object.__setattr__(self, "_md_decorated", decorated)

	def __getattr__(self, name):
		return getattr(self._md_decorated, name)

	def __setattr__(self, name, value):
		return setattr(self._md_decorated, name, value)

	# overload this in derived classes
	def transform_fragment(self, f):
		pass

	def get_fragment(self):
		f = self._md_decorated.get_fragment()
		self.transform_fragment(f)
		return f

	def __dir__(self):
		return dir(self._md_decorated)

class DecorateModule:
	def __init__(self, decorator, *dec_args, **dec_kwargs):
		self.decorator = decorator
		self.dec_args = dec_args
		self.dec_kwargs = dec_kwargs

	def __call__(self, decorated):
		def dfinit(dfself, *args, **kwargs):
			self.decorator.__init__(dfself, decorated(*args, **kwargs),
				*self.dec_args, **self.dec_kwargs)
		typename = self.decorator.__name__ + "(" + decorated.__name__ + ")"
		return type(typename, (self.decorator,), dict(__init__=dfinit))

class InsertControl(ModuleDecorator):
	def __init__(self, control_name, decorated, clock_domains=None):
		ModuleDecorator.__init__(self, decorated)

		object.__setattr__(self, "_ic_control_name", control_name)
		object.__setattr__(self, "_ic_clock_domains", clock_domains)

		if clock_domains is None:
			ctl = Signal(name=control_name)
			assert(not hasattr(decorated, control_name))
			object.__setattr__(self, control_name, ctl)
		else:
			for cd in clock_domains:
				name = control_name + "_" + cd
				ctl = Signal(name=name)
				assert(not hasattr(decorated, name))
				object.__setattr__(self, name, ctl)

	def transform_fragment(self, f):
		control_name = self._ic_control_name
		clock_domains = self._ic_clock_domains
		if clock_domains is None:
			if len(f.sync) != 1:
				raise ValueError("Control signal clock domains must be specified when module has more than one domain")
			cdn = list(f.sync.keys())[0]
			to_insert = [(getattr(self, control_name), cdn)]
		else:
			to_insert = [(getattr(self, control_name+"_"+cdn), cdn) for cdn in clock_domains]
		self.transform_fragment_insert(f, to_insert)

class InsertCE(InsertControl):
	def __init__(self, *args, **kwargs):
		InsertControl.__init__(self, "ce", *args, **kwargs)

	def transform_fragment_insert(self, f, to_insert):
		for ce, cdn in to_insert:
			f.sync[cdn] = [If(ce, *f.sync[cdn])]

class InsertReset(InsertControl):
	def __init__(self, *args, **kwargs):
		InsertControl.__init__(self, "reset", *args, **kwargs)

	def transform_fragment_insert(self, f, to_insert):
		for reset, cdn in to_insert:
			f.sync[cdn] = insert_reset(reset, f.sync[cdn])

class RenameClockDomains(ModuleDecorator):
	def __init__(self, decorated, cd_remapping):
		ModuleDecorator.__init__(self, decorated)
		if isinstance(cd_remapping, str):
			cd_remapping = {"sys": cd_remapping}
		object.__setattr__(self, "_rc_cd_remapping", cd_remapping)

	def transform_fragment(self, f):
		for old, new in self._rc_cd_remapping.items():
			rename_clock_domain(f, old, new)
