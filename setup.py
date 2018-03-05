#!/usr/bin/env python3

import sys
from setuptools import setup
from setuptools import find_packages


if sys.version_info[:3] < (3, 5):
    raise SystemExit("You need Python 3.5+")

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError) as e:
    import logging
    logging.warning("Unable to convert README to rst format!", exc_info=e)
    long_description = open('README.md').read()


setup(
    name="litex",
    version="0.2.dev",
    description="Python tools to design FPGA cores and SoCs",
    long_description=long_description,
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
    packages=find_packages(),
    install_requires=["pyserial"],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "litex_term=litex.soc.tools.litex_term:main",
            "mkmscimg=litex.soc.tools.mkmscimg:main",
            "litex_server=litex.soc.tools.remote.litex_server:main"
        ],
    },
)
