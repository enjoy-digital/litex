import warnings

from migen.fhdl.structure import *
from migen.fhdl.tools import insert_reset, rename_clock_domain

class ModuleTransformer:
	# overload this in derived classes
	def transform_instance(self, i):
		pass

	# overload this in derived classes
	def transform_fragment(self, i, f):
		pass

	def wrap_class(self, victim):
		class Wrapped(victim):
			def __init__(i, *args, **kwargs):
				victim.__init__(i, *args, **kwargs)
				self.transform_instance(i)

			def get_fragment(i):
				f = victim.get_fragment(i)
				self.transform_fragment(i, f)
				return f

		Wrapped.__name__ = victim.__name__
		# "{}_{}".format(self.__class__.__name__, victim.__name__)
		return Wrapped

	def wrap_instance(self, victim):
		self.transform_instance(victim)
		orig_get_fragment = victim.get_fragment

		def get_fragment():
			f = orig_get_fragment()
			self.transform_fragment(victim, f)
			return f

		victim.get_fragment = get_fragment
		return victim

	def __call__(self, victim):
		try:
			return self.wrap_class(victim)
		except TypeError:
			return self.wrap_instance(victim)

	@classmethod
	def adhoc(cls, i, *args, **kwargs):
		warnings.warn("deprecated, use the plain transformer", DeprecationWarning)
		return cls(*args, **kwargs)(i)

def DecorateModule(transformer, *args, **kwargs):
	warnings.warn("deprecated, use the plain transformer", DeprecationWarning)
	return transformer.__self__(*args, **kwargs)

class ControlInserter(ModuleTransformer):
	control_name = None  # override this

	def __init__(self, clock_domains=None):
		self.clock_domains = clock_domains

	def transform_instance(self, i):
		if self.clock_domains is None:
			ctl = Signal(name=self.control_name)
			assert not hasattr(i, self.control_name)
			setattr(i, self.control_name, ctl)
		else:
			for cd in self.clock_domains:
				name = self.control_name + "_" + cd
				ctl = Signal(name=name)
				assert not hasattr(i, name)
				setattr(i, name, ctl)

	def transform_fragment(self, i, f):
		if self.clock_domains is None:
			if len(f.sync) != 1:
				raise ValueError("Control signal clock domains must be specified when module has more than one domain")
			cdn = list(f.sync.keys())[0]
			to_insert = [(getattr(i, self.control_name), cdn)]
		else:
			to_insert = [(getattr(i, self.control_name + "_" + cdn), cdn)
				for cdn in clock_domains]
		self.transform_fragment_insert(i, f, to_insert)

class CEInserter(ControlInserter):
	control_name = "ce"

	def transform_fragment_insert(self, i, f, to_insert):
		for ce, cdn in to_insert:
			f.sync[cdn] = [If(ce, *f.sync[cdn])]

InsertCE = CEInserter.adhoc

class ResetInserter(ControlInserter):
	control_name = "reset"

	def transform_fragment_insert(self, i, f, to_insert):
		for reset, cdn in to_insert:
			f.sync[cdn] = insert_reset(reset, f.sync[cdn])

InsertReset = ResetInserter.adhoc

class ClockDomainsRenamer(ModuleTransformer):
	def __init__(self, cd_remapping):
		if isinstance(cd_remapping, str):
			cd_remapping = {"sys": cd_remapping}
		self.cd_remapping = cd_remapping

	def transform_fragment(self, i, f):
		for old, new in self.cd_remapping.items():
			rename_clock_domain(f, old, new)

RenameClockDomains = ClockDomainsRenamer.adhoc
