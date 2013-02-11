from copy import copy
import os, argparse

from migen.fhdl.structure import *
from migen.corelogic.record import Record
from migen.fhdl import verilog

from mibuild import tools

class ConstraintError(Exception):
	pass
	
class Pins:
	def __init__(self, *identifiers):
		self.identifiers = identifiers

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

def _lookup(description, name, number):
	for resource in description:
		if resource[0] == name and (number is None or resource[1] == number):
			return resource
	raise ConstraintError("Resource not found: " + name + "." + str(number))
		
def _resource_type(resource, name_map):
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
			t.append((name_map(element.name), n_bits))
	return t

def _match(description, requests):
	available = list(description)
	matched = []
	
	# 1. Match requests for a specific number
	for request in requests:
		if request[1] is not None:
			resource = _lookup(available, request[0], request[1])
			available.remove(resource)
			matched.append((resource, request[2], request[3]))
			
	# 2. Match requests for no specific number
	for request in requests:
		if request[1] is None:
			resource = _lookup(available, request[0], request[1])
			available.remove(resource)
			matched.append((resource, request[2], request[3]))
	
	return matched

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
	def __init__(self, description):
		self.description = description
		self.requests = []
		self.platform_commands = []
		
	def request(self, name, number=None, obj=None, name_map=lambda s: s):
		r = _lookup(self.description, name, number)
		t = _resource_type(r, name_map)
		
		# If obj is None, then create it.
		# If it already exists, do some sanity checking.
		if obj is None:
			if isinstance(t, int):
				obj = Signal(t, name_override=name_map(r[0]))
			else:
				obj = Record(t)
		else:
			if isinstance(t, int):
				assert(isinstance(obj, Signal) and obj.nbits == t)
			else:
				for attr, nbits in t:
					sig = getattr(obj, attr)
					assert(isinstance(sig, Signal) and sig.nbits == nbits)

		# Register the request
		self.requests.append((name, number, obj, name_map))
		
		return obj
	
	def add_platform_command(self, command, **signals):
		self.platform_commands.append((command, signals))
	
	def get_io_signals(self):
		s = set()
		for req in self.requests:
			obj = req[2]
			if isinstance(obj, Signal):
				s.add(obj)
			else:
				for p in obj.__dict__.values():
					if isinstance(p, Signal):
						s.add(p)
		return s
	
	def get_sig_constraints(self):
		r = []
		matched = _match(self.description, self.requests)
		for resource, obj, name_map in matched:
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
						sig = getattr(obj, name_map(element.name))
						pins, others = _separate_pins(top_constraints + element.constraints)
						r.append((sig, pins, others, (name, number, element.name)))
			else:
				pins, others = _separate_pins(top_constraints)
				r.append((obj, pins, others, (name, number, None)))
		return r

	def get_platform_commands(self):
		return self.platform_commands

	def save(self):
		return copy(self.requests), copy(self.platform_commands)

	def restore(self, backup):
		self.request, self.platform_commands = backup

class GenericPlatform:
	def __init__(self, device, io, default_crg_factory=None):
		self.device = device
		self.constraint_manager = ConstraintManager(io)
		self.default_crg_factory = default_crg_factory
		self.sources = []

	def request(self, *args, **kwargs):
		return self.constraint_manager.request(*args, **kwargs)

	def add_platform_command(self, *args, **kwargs):
		return self.constraint_manager.add_platform_command(*args, **kwargs)

	def add_source(self, filename, language=None):
		if language is None:
			language = tools.language_by_filename(filename)
		if language is None:
			language = "verilog" # default to Verilog
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

	def get_verilog(self, fragment, clock_domains=None):
		# We may create a temporary clock/reset generator that would request pins.
		# Save the constraint manager state so that such pin requests disappear
		# at the end of this function.
		backup = self.constraint_manager.save()
		try:
			# if none exists, create a default clock domain and drive it
			if clock_domains is None:
				if self.default_crg_factory is None:
					raise NotImplementedError("No clock/reset generator defined by either platform or user")
				crg = self.default_crg_factory(self)
				frag = fragment + crg.get_fragment()
				clock_domains = crg.get_clock_domains()
			else:
				frag = fragment
			# generate Verilog
			src, vns = verilog.convert(frag, self.constraint_manager.get_io_signals(),
				clock_domains=clock_domains, return_ns=True)
			# resolve signal names in constraints
			sc = self.constraint_manager.get_sig_constraints()
			named_sc = [(vns.get_name(sig), pins, others, resource) for sig, pins, others, resource in sc]
			# resolve signal names in platform commands
			pc = self.constraint_manager.get_platform_commands()
			named_pc = []
			for template, args in pc:
				name_dict = dict((k, vns.get_name(sig)) for k, sig in args.items())
				named_pc.append(template.format(**name_dict))
		finally:
			self.constraint_manager.restore(backup)
		return src, named_sc, named_pc
		
	def build(self, fragment, clock_domains=None):
		raise NotImplementedError("GenericPlatform.build must be overloaded")

	def add_arguments(self, parser):
		pass # default: no arguments

	def build_arg_ns(self, ns, *args, **kwargs):
		self.build(*args, **kwargs)

	def build_cmdline(self, *args, **kwargs):
		parser = argparse.ArgumentParser(description="FPGA bitstream build system")
		self.add_arguments(parser)
		ns = parser.parse_args()
		self.build_arg_ns(ns, *args, **kwargs)
