#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages


setup(
    name="litex",
    description="Python SoC/Core builder for building FPGA based systems.",
    author="Florent Kermarrec",
    author_email="florent@enjoy-digital.fr",
    url="http://enjoy-digital.fr",
    download_url="https://github.com/enjoy-digital/litex",
    test_suite="test",
    license="BSD",
    python_requires="~=3.6",
    install_requires=["migen", "pyserial"],
    packages=find_packages(exclude=("test*", "sim*", "doc*")),
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
