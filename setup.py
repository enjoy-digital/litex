#!/usr/bin/env python3

import sys
from setuptools import setup
from setuptools import find_packages


if sys.version_info[:3] < (3, 5):
    raise SystemExit("You need Python 3.5+")


setup(
    name="litex",
    version="0.2.dev",
    description="Python tools to design FPGA cores and SoCs",
    long_description=open("README.md").read(),
    author="Florent Kermarrec",
    author_email="florent@enjoy-digital.fr",
    url="http://enjoy-digital.fr",
    download_url="https://github.com/enjoy-digital/litex",
    test_suite="test",
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
    packages=find_packages(exclude=("test*", "sim*", "doc*")),
    install_requires=["migen", "pyserial"],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            # full names
            "litex_term=litex.tools.litex_term:main",
            "litex_server=litex.tools.litex_server:main",
            "litex_sim=litex.tools.litex_sim:main",
            "litex_read_verilog=litex.tools.litex_read_verilog:main",
            "litex_simple=litex.boards.targets.simple:main",
            # short names
            "lxterm=litex.tools.litex_term:main",
            "lxserver=litex.tools.litex_server:main",
            "lxsim=litex.tools.litex_sim:main",
        ],
    },
)
