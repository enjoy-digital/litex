#!/usr/bin/env python3

import sys
from setuptools import setup
from setuptools import find_packages


required_version = (3, 3)
if sys.version_info < required_version:
    raise SystemExit("MiSoC requires python {0} or greater".format(
        ".".join(map(str, required_version))))

setup(
    name="misoc",
    version="1.0",
    description="a high performance and small footprint SoC based on Migen",
    long_description=open("README.rst").read(),
    author="Sebastien Bourdeauducq",
    author_email="sb@m-labs.hk",
    url="http://m-labs.hk",
    download_url="https://github.com/m-labs/misoc",
    packages=find_packages(),
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
