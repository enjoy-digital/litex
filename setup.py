#!/usr/bin/env python3

import sys, os
from setuptools import setup
from setuptools import find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, "README")).read()

required_version = (3, 3)
if sys.version_info < required_version:
	raise SystemExit("Mibuild requires python {0} or greater".format(
		".".join(map(str, required_version))))

setup(
	name="mibuild",
	version="unknown",
	description="Build system and board definitions for Migen FPGA designs",
	long_description=README,
	author="Sebastien Bourdeauducq",
	author_email="sebastien@milkymist.org",
	url="http://www.milkymist.org",
	download_url="https://github.com/milkymist/mibuild",
	packages=find_packages(here),
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
