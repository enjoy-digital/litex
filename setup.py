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
        "packaging",
        "pyserial",
        "requests",
    ],
    packages=find_packages(exclude=("test*", "sim*", "doc*")),
    include_package_data=True,
    package_data={
        'litex.soc.doc': ['static/*']
    },
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
            # Terminal/Server/Client.
            "litex_term   = litex.tools.litex_term:main",
            "litex_server = litex.tools.litex_server:main",
            "litex_cli    = litex.tools.litex_client:main",

            # SoC Generators.
            "litex_soc_gen    = litex.tools.litex_soc_gen:main",
            "litex_periph_gen = litex.tools.litex_periph_gen:main",

            # Simulation.
            "litex_sim=litex.tools.litex_sim:main",

            # Demos.
            "litex_bare_metal_demo=litex.soc.software.demo.demo:main",

            # Export tools.
            "litex_json2dts_linux  = litex.tools.litex_json2dts_linux:main",
            "litex_json2dts_zephyr = litex.tools.litex_json2dts_zephyr:main",
            "litex_json2renode     = litex.tools.litex_json2renode:main",

            # Development tools.
            "litex_read_verilog = litex.tools.litex_read_verilog:main",
            "litex_contributors = litex.tools.litex_contributors:main",
        ],
    },
)
