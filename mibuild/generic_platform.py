import os, sys

from migen.fhdl.std import *
from migen.fhdl.structure import _Fragment
from migen.genlib.record import Record
from migen.fhdl import verilog, edif
from migen.util.misc import autotype

from mibuild import tools

class ConstraintError(Exception):
	pass
	
class Pins:
	def __init__(self, *identifiers):
		self.identifiers = []
		for i in identifiers:
			self.identifiers += i.split()

class IOStandard:
	def __init__(self, name):
		self.name = name

class Drive:
	def __init__(self, strength):
		self.strength = strength

class Misc:
	def __init__(self, misc):
		self.misc = misc

class Subsignal:
	def __init__(self, name, *constraints):
		self.name = name
		self.constraints = list(constraints)

class PlatformInfo:
	def __init__(self, info):
		self.info = info

def _lookup(description, name, number):
	for resource in description:
		if resource[0] == name and (number is None or resource[1] == number):
			return resource
	raise ConstraintError("Resource not found: " + name + ":" + str(number))
		
def _resource_type(resource):
	t = None
	for element in resource[2:]:
		if isinstance(element, Pins):
			assert(t is None)
			t = len(element.identifiers)
		elif isinstance(element, Subsignal):
			if t is None:
				t = []
			assert(isinstance(t, list))
			n_bits = None
			for c in element.constraints:
				if isinstance(c, Pins):
					assert(n_bits is None)
					n_bits = len(c.identifiers)
			t.append((element.name, n_bits))
	return t

class ConnectorManager:
	def __init__(self, connectors):
		self.connector_table = dict()
		for connector in connectors:
			cit = iter(connector)
			conn_name = next(cit)
			pin_list = []
			for pins in cit:
				pin_list += pins.split()
			pin_list = [None if pin == "None" else pin for pin in pin_list]
			if conn_name in self.connector_table:
				raise ValueError("Connector specified more than once: "+conn_name)
			self.connector_table[conn_name] = pin_list

	def resolve_identifiers(self, identifiers):
		r = []
		for identifier in identifiers:
			if ":" in identifier:
				conn, pn = identifier.split(":")
				pn = int(pn)
				r.append(self.connector_table[conn][pn])
			else:
				r.append(identifier)
		return r

def _separate_pins(constraints):
	pins = None
	others = []
	for c in constraints:
		if isinstance(c, Pins):
			assert(pins is None)
			pins = c.identifiers
		else:
			others.append(c)
	return pins, others

class ConstraintManager:
	def __init__(self, io, connectors):
		self.available = list(io)
		self.matched = []
		self.platform_commands = []
		self.connector_manager = ConnectorManager(connectors)

	def add_extension(self, io):
		self.available.extend(io)
		
	def request(self, name, number=None):
		resource = _lookup(self.available, name, number)
		rt = _resource_type(resource)		
		if isinstance(rt, int):
			obj = Signal(rt, name_override=resource[0])
		else:
			obj = Record(rt, name=resource[0])
		for element in resource[2:]:
			if isinstance(element, PlatformInfo):
				obj.platform_info = element.info
				break
		self.available.remove(resource)
		self.matched.append((resource, obj))
		return obj

	def lookup_request(self, name, number=None):
		for resource, obj in self.matched:
			if resource[0] == name and (number is None or resource[1] == number):
				return obj
		raise ConstraintError("Resource not found: " + name + ":" + str(number))
	
	def add_platform_command(self, command, **signals):
		self.platform_commands.append((command, signals))
	
	def get_io_signals(self):
		r = set()
		for resource, obj in self.matched:
			if isinstance(obj, Signal):
				r.add(obj)
			else:
				r.update(obj.flatten())
		return r
	
	def get_sig_constraints(self):
		r = []
		for resource, obj in self.matched:
			name = resource[0]
			number = resource[1]
			has_subsignals = False
			top_constraints = []
			for element in resource[2:]:
				if isinstance(element, Subsignal):
					has_subsignals = True
				else:
					top_constraints.append(element)
			if has_subsignals:
				for element in resource[2:]:
					if isinstance(element, Subsignal):
						sig = getattr(obj, element.name)
						pins, others = _separate_pins(top_constraints + element.constraints)
						pins = self.connector_manager.resolve_identifiers(pins)
						r.append((sig, pins, others, (name, number, element.name)))
			else:
				pins, others = _separate_pins(top_constraints)
				pins = self.connector_manager.resolve_identifiers(pins)
				r.append((obj, pins, others, (name, number, None)))
		return r

	def get_platform_commands(self):
		return self.platform_commands

class GenericPlatform:
	def __init__(self, device, io, default_crg_factory=None, connectors=[], name=None):
		self.device = device
		self.constraint_manager = ConstraintManager(io, connectors)
		self.default_crg_factory = default_crg_factory
		if name is None:
			name = self.__module__.split(".")[-1]
		self.name = name
		self.sources = []
		self.verilog_include_paths = []
		self.finalized = False

	def request(self, *args, **kwargs):
		return self.constraint_manager.request(*args, **kwargs)

	def lookup_request(self, *args, **kwargs):
		return self.constraint_manager.lookup_request(*args, **kwargs)

	def add_platform_command(self, *args, **kwargs):
		return self.constraint_manager.add_platform_command(*args, **kwargs)

	def add_extension(self, *args, **kwargs):
		return self.constraint_manager.add_extension(*args, **kwargs)

	def finalize(self, fragment, *args, **kwargs):
		if self.finalized:
			raise ConstraintError("Already finalized")
		# if none exists, create a default clock domain and drive it
		if not fragment.clock_domains:
			if self.default_crg_factory is None:
				raise NotImplementedError("No clock/reset generator defined by either platform or user")
			crg = self.default_crg_factory(self)
			fragment += crg.get_fragment()
		self.do_finalize(fragment, *args, **kwargs)
		self.finalized = True

	def do_finalize(self, fragment, *args, **kwargs):
		"""overload this and e.g. add_platform_command()'s after the
		modules had their say"""
		pass

	def add_source(self, filename, language=None):
		if language is None:
			language = tools.language_by_filename(filename)
		if language is None:
			language = "verilog" # default to Verilog
		filename = os.path.abspath(filename)
		self.sources.append((filename, language))

	def add_sources(self, path, *filenames, language=None):
		for f in filenames:
			self.add_source(os.path.join(path, f), language)

	def add_source_dir(self, path):
		for root, dirs, files in os.walk(path):
			for filename in files:
				language = tools.language_by_filename(filename)
				if language is not None:
					self.add_source(os.path.join(root, filename), language)

	def add_verilog_include_path(self, path):
		self.verilog_include_paths.append(os.path.abspath(path))

	def _resolve_signals(self, vns):
		# resolve signal names in constraints
		sc = self.constraint_manager.get_sig_constraints()
		named_sc = [(vns.get_name(sig), pins, others, resource) for sig, pins, others, resource in sc]
		# resolve signal names in platform commands
		pc = self.constraint_manager.get_platform_commands()
		named_pc = []
		for template, args in pc:
			name_dict = dict((k, vns.get_name(sig)) for k, sig in args.items())
			named_pc.append(template.format(**name_dict))
		return named_sc, named_pc

	def _get_source(self, fragment, gen_fn):
		if not isinstance(fragment, _Fragment):
			fragment = fragment.get_fragment()
		# generate source
		src, vns = gen_fn(fragment)
		named_sc, named_pc = self._resolve_signals(vns)
		return src, named_sc, named_pc

	def get_verilog(self, fragment, **kwargs):
		return self._get_source(fragment, lambda f: verilog.convert(f, self.constraint_manager.get_io_signals(),
				return_ns=True, create_clock_domains=False, **kwargs))
		
	def get_edif(self, fragment, cell_library, vendor, device, **kwargs):
		return self._get_source(fragment, lambda f: edif.convert(f, self.constraint_manager.get_io_signals(),
				cell_library, vendor, device, return_ns=True, **kwargs))

	def build(self, fragment):
		raise NotImplementedError("GenericPlatform.build must be overloaded")

	def build_cmdline(self, *args, **kwargs):
		arg = sys.argv[1:]
		if len(arg) % 2:
			print("Missing value for option: "+sys.argv[-1])
			sys.exit(1)
		argdict = dict((k, autotype(v)) for k, v in zip(*[iter(arg)]*2))
		kwargs.update(argdict)
		self.build(*args, **kwargs)
