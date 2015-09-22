#!/usr/bin/env python3

import sys
import os
from setuptools import setup
from setuptools import find_packages


required_version = (3, 3)
if sys.version_info < required_version:
    raise SystemExit("Migen requires python {0} or greater".format(
        ".".join(map(str, required_version))))

setup(
    name="migen",
    version="1.0",
    description="Python toolbox for building complex digital hardware",
    long_description=open("README.md").read(),
    author="Sebastien Bourdeauducq",
    author_email="sb@m-labs.hk",
    url="http://m-labs.hk",
    download_url="https://github.com/m-labs/migen",
    packages=find_packages(),
    test_suite="migen.test",
    license="BSD",
    platforms=["Any"],
    keywords="HDL ASIC FPGA hardware design",
    classifiers=[
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Environment :: Console",
        "Development Status :: Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
)
