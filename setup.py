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
    install_requires=[
        "migen",
        "pyserial",
        "requests",
        "pythondata-software-compiler_rt",
    ],
    packages=find_packages(exclude=("test*", "sim*", "doc*")),
    include_package_data=True,
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
    entry_points={
        "console_scripts": [
            # full names
            "litex_term=litex.tools.litex_term:main",
            "litex_server=litex.tools.litex_server:main",
            "litex_jtag_uart=litex.tools.litex_jtag_uart:main",
            "litex_crossover_uart=litex.tools.litex_crossover_uart:main",
            "litex_sim=litex.tools.litex_sim:main",
            "litex_read_verilog=litex.tools.litex_read_verilog:main",
            "litex_simple=litex.boards.targets.simple:main",
            "litex_json2dts=litex.tools.litex_json2dts:main",
            # short names
            "lxterm=litex.tools.litex_term:main",
            "lxserver=litex.tools.litex_server:main",
            "lxsim=litex.tools.litex_sim:main",
        ],
    },
)
