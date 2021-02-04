#
# This file is part of LiteX.
#
# Copyright (c) 2020 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

import os
import pathlib
import datetime

from litex.soc.interconnect.csr import _CompoundCSR
from litex.soc.integration import export
from .csr import DocumentedCSRRegion
from .module import gather_submodules, ModuleNotDocumented, DocumentedModule, DocumentedInterrupts
from .rst import reflow

default_sphinx_configuration = """
project = '{}'
copyright = '{}, {}'
author = '{}'
extensions = [
    'sphinx.ext.autosectionlabel',
    'sphinxcontrib.wavedrom',{}
]
templates_path = ['_templates']
exclude_patterns = []
offline_skin_js_path = "https://wavedrom.com/skins/default.js"
offline_wavedrom_js_path = "https://wavedrom.com/WaveDrom.js"
html_theme = 'alabaster'
html_static_path = ['_static']
master_doc = 'index'
"""

def generate_svd(soc, buildpath, filename=None, name="soc", **kwargs):
    if filename is None:
        filename = name + ".svd"
    kwargs["name"] = name
    with open(buildpath + "/" + filename, "w", encoding="utf-8") as svd:
        svd.write(export.get_csr_svd(soc, **kwargs))


def generate_docs(soc, base_dir,
    project_name          = "LiteX SoC Project",
    author                = "Anonymous",
    sphinx_extensions     = [],
    quiet                 = False,
    note_pulses           = False,
    from_scratch          = True,
    sphinx_extra_config   = ""):
    """Possible extra extensions:
        [
            'm2r',
            'recommonmark',
            'sphinx_rtd_theme',
            'sphinx_autodoc_typehints',
        ]
    """

    # Ensure the target directory is a full path
    if base_dir[-1] != '/':
        base_dir = base_dir + '/'

    # Ensure the output directory exists
    pathlib.Path(base_dir + "/_static").mkdir(parents=True, exist_ok=True)

    # Create the sphinx configuration file if the user has requested,
    # or if it doesn't exist already.
    if from_scratch or not os.path.isfile(base_dir + "conf.py"):
        with open(base_dir + "conf.py", "w", encoding="utf-8") as conf:
            year = datetime.datetime.now().year
            sphinx_ext_str = ""
            for ext in sphinx_extensions:
                sphinx_ext_str += "\n    \"{}\",".format(ext)
            print(default_sphinx_configuration.format(project_name, year,
                                                      author, author, sphinx_ext_str), file=conf)
            print(sphinx_extra_config, file=conf)

    if not quiet:
        print("Generate the documentation by running `sphinx-build -M html {} {}_build`".format(base_dir, base_dir))

    # Gather all interrupts so we can easily map IRQ numbers to CSR sections
    interrupts = {}
    for csr, irq in sorted(soc.irq.locs.items()):
        interrupts[csr] = irq

    # Convert each CSR region into a DocumentedCSRRegion.
    # This process will also expand each CSR into a DocumentedCSR,
    # which means that CompoundCSRs (such as CSRStorage and CSRStatus)
    # that are larger than the buswidth will be turned into multiple
    # DocumentedCSRs.
    documented_regions = []
    seen_modules       = set()
    for name, region in soc.csr.regions.items():
        module = None
        if hasattr(soc, name):
            module = getattr(soc, name)
            seen_modules.add(module)
        submodules = gather_submodules(module)
        documented_region = DocumentedCSRRegion(
            name           = name,
            region         = region,
            module         = module,
            submodules     = submodules,
            csr_data_width = soc.csr.data_width)
        if documented_region.name in interrupts:
            documented_region.document_interrupt(
                soc, submodules, interrupts[documented_region.name])
        documented_regions.append(documented_region)

    # Document any modules that are not CSRs.
    # TODO: Add memory maps here.
    additional_modules = [
        DocumentedInterrupts(interrupts),
    ]
    for (mod_name, mod) in soc._submodules:
        if mod not in seen_modules:
            try:
                additional_modules.append(DocumentedModule(mod_name, mod))
            except ModuleNotDocumented:
                pass

    # Create index.rst containing links to all of the generated files.
    # If the user has set `from_scratch=False`, then skip this step.
    if from_scratch or not os.path.isfile(base_dir + "index.rst"):
        with open(base_dir + "index.rst", "w", encoding="utf-8") as index:
            print("""
Documentation for {}
{}

""".format(project_name, "="*len("Documentation for " + project_name)), file=index)

            if len(additional_modules) > 0:
                print("""
Modules
=======

.. toctree::
    :maxdepth: 1
""", file=index)
                for module in additional_modules:
                    print("    {}".format(module.name), file=index)

            if len(documented_regions) > 0:
                print("""
Register Groups
===============

.. toctree::
    :maxdepth: 1
""", file=index)
                for region in documented_regions:
                    print("    {}".format(region.name), file=index)

            print("""
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
""", file=index)

    # Create a Region file for each of the documented CSR regions.
    for region in documented_regions:
        with open(base_dir + region.name + ".rst", "w", encoding="utf-8") as outfile:
            region.print_region(outfile, base_dir, note_pulses)

    # Create a Region file for each additional non-CSR module
    for region in additional_modules:
        with open(base_dir + region.name + ".rst", "w", encoding="utf-8") as outfile:
            region.print_region(outfile, base_dir, note_pulses)

    # Copy over wavedrom javascript and configuration files
    with open(os.path.dirname(__file__) + "/static/WaveDrom.js", "r") as wd_in:
        with open(base_dir + "/_static/WaveDrom.js", "w") as wd_out:
            wd_out.write(wd_in.read())
    with open(os.path.dirname(__file__) + "/static/default.js", "r") as wd_in:
        with open(base_dir + "/_static/default.js", "w") as wd_out:
            wd_out.write(wd_in.read())
