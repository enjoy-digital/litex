#!/usr/bin/env python3
# vim: noexpandtab:tabstop=8:softtabstop=8
""" Migen's distutils distribution and installation script. """

import sys, os
from distutils.core import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, "README")).read()

required_version = (3, 1)
if sys.version_info < required_version:
	raise SystemExit("migen requires python {0} or greater".format(
		".".join(map(str, required_version))))

packages = ["migen"]
packages_dir = os.path.sep.join((here, packages[0]))
for entry in os.listdir(packages_dir):
	if (os.path.isdir(os.path.sep.join((packages_dir, entry))) and
	 os.path.isfile(os.path.sep.join((packages_dir, entry, "__init__.py")))):
		packages.append(".".join((packages[0], entry)))

packages_dir={"": "migen"}
setup(
	name="migen",
	version="unknown",
	description="Python toolbox for building complex digital hardware",
	long_description=README,
	author="Sebastien Bourdeauducq",
	author_email="sebastien@milkymist.org",
	url="http://www.milkymist.org",
	download_url="https://github.com/milkymist/migen",
	packages=packages,
	license="GPL",
	platforms=["Any"],
	keywords="HDL ASIC FPGA hardware design",
	classifiers=[
		"Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
		"Environment :: Console",
		"Development Status :: Alpha",
		"Intended Audience :: Developers",
		"License :: OSI Approved :: GNU General Public License (GPL)",
		"Operating System :: OS Independent",
		"Programming Language :: Python",
	],
)
