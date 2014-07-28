import os
from distutils.version import StrictVersion

from mibuild import tools

def settings(path, ver=None, sub=None):
	vers = list(tools.versions(path))
	if ver is None:
		ver = max(vers)
	else:
		ver = StrictVersion(ver)
		assert ver in vers

	full = os.path.join(path, str(ver))
	if sub:
		full = os.path.join(full, sub)

	search = [64, 32]
	if tools.arch_bits() == 32:
		search.reverse()

	for b in search:
		settings = os.path.join(full, "settings{0}.sh".format(b))
		if os.path.exists(settings):
			return settings

	raise ValueError("no settings file found")
