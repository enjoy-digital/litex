#!/usr/bin/env python3.2
""" Migen's distutils distribution and installation script. """

import sys, os
from distutils.core import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, "README")).read()

if sys.version_info < (3, 2):
	raise SystemExit("migen requires python 3.2 or greater")

setup(
	name="migen",
	version="unknown",
	description="Python toolbox for building complex digital hardware",
	long_description=README,
	author="Sebastien Bourdeauducq",
	author_email="sebastien@milkymist.org",
	url="http://www.milkymist.org",
	download_url="https://github.com/milkymist/migen",
	packages=['', 'migen'],
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
