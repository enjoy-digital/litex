# This file is Copyright (c) 2020 Sean Cross <sean@xobs.io>
# License: BSD

import os
import pathlib
import datetime

from litex.soc.interconnect.csr import _CompoundCSR
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
"""


def sub_csr_bit_range(busword, csr, offset):
    nwords = (csr.size + busword - 1)//busword
    i = nwords - offset - 1
    nbits = min(csr.size - i*busword, busword) - 1
    name = (csr.name + str(i) if nwords > 1 else csr.name).upper()
    origin = i*busword
    return (origin, nbits, name)


def print_svd_register(csr, csr_address, description, length, svd):
    print('                <register>', file=svd)
    print('                    <name>{}</name>'.format(csr.short_numbered_name), file=svd)
    if description is not None:
        print(
            '                    <description><![CDATA[{}]]></description>'.format(description), file=svd)
    print(
        '                    <addressOffset>0x{:04x}</addressOffset>'.format(csr_address), file=svd)
    print(
        '                    <resetValue>0x{:02x}</resetValue>'.format(csr.reset_value), file=svd)
    print('                    <size>{}</size>'.format(length), file=svd)
    print('                    <access>{}</access>'.format(csr.access), file=svd)
    csr_address = csr_address + 4
    print('                    <fields>', file=svd)
    if hasattr(csr, "fields") and len(csr.fields) > 0:
        for field in csr.fields:
            print('                        <field>', file=svd)
            print(
                '                            <name>{}</name>'.format(field.name), file=svd)
            print('                            <msb>{}</msb>'.format(field.offset +
                                                                     field.size - 1), file=svd)
            print('                            <bitRange>[{}:{}]</bitRange>'.format(
                field.offset + field.size - 1, field.offset), file=svd)
            print(
                '                            <lsb>{}</lsb>'.format(field.offset), file=svd)
            print('                            <description><![CDATA[{}]]></description>'.format(
                reflow(field.description)), file=svd)
            print('                        </field>', file=svd)
    else:
        field_size = csr.size
        field_name = csr.short_name.lower()
        # Strip off "ev_" from eventmanager fields
        if field_name == "ev_enable":
            field_name = "enable"
        elif field_name == "ev_pending":
            field_name = "pending"
        elif field_name == "ev_status":
            field_name = "status"
        print('                        <field>', file=svd)
        print('                            <name>{}</name>'.format(field_name), file=svd)
        print('                            <msb>{}</msb>'.format(field_size - 1), file=svd)
        print(
            '                            <bitRange>[{}:{}]</bitRange>'.format(field_size - 1, 0), file=svd)
        print('                            <lsb>{}</lsb>'.format(0), file=svd)
        print('                        </field>', file=svd)
    print('                    </fields>', file=svd)
    print('                </register>', file=svd)


def generate_svd(soc, buildpath, vendor="litex", name="soc", filename=None, description=None):
    interrupts = {}
    for csr, irq in sorted(soc.soc_interrupt_map.items()):
        interrupts[csr] = irq

    documented_regions = []

    raw_regions = []
    if hasattr(soc, "get_csr_regions"):
        raw_regions = soc.get_csr_regions()
    else:
        for region_name, region in soc.csr_regions.items():
            raw_regions.append((region_name, region.origin,
                                region.busword, region.obj))
    for csr_region in raw_regions:
        documented_regions.append(DocumentedCSRRegion(
            csr_region, csr_data_width=soc.csr_data_width))

    if filename is None:
        filename = name + ".svd"
    with open(buildpath + "/" + filename, "w", encoding="utf-8") as svd:
        print('<?xml version="1.0" encoding="utf-8"?>', file=svd)
        print('', file=svd)
        print('<device schemaVersion="1.1" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="CMSIS-SVD.xsd" >', file=svd)
        print('    <vendor>{}</vendor>'.format(vendor), file=svd)
        print('    <name>{}</name>'.format(name.upper()), file=svd)
        if description is not None:
            print(
                '    <description><![CDATA[{}]]></description>'.format(reflow(description)), file=svd)
        print('', file=svd)
        print('    <addressUnitBits>8</addressUnitBits>', file=svd)
        print('    <width>32</width>', file=svd)
        print('    <size>32</size>', file=svd)
        print('    <access>read-write</access>', file=svd)
        print('    <resetValue>0x00000000</resetValue>', file=svd)
        print('    <resetMask>0xFFFFFFFF</resetMask>', file=svd)
        print('', file=svd)
        print('    <peripherals>', file=svd)

        for region in documented_regions:
            csr_address = 0
            print('        <peripheral>', file=svd)
            print('            <name>{}</name>'.format(region.name.upper()), file=svd)
            print(
                '            <baseAddress>0x{:08X}</baseAddress>'.format(region.origin), file=svd)
            print(
                '            <groupName>{}</groupName>'.format(region.name.upper()), file=svd)
            if len(region.sections) > 0:
                print('            <description><![CDATA[{}]]></description>'.format(
                    reflow(region.sections[0].body())), file=svd)
            print('            <registers>', file=svd)
            for csr in region.csrs:
                description = None
                if hasattr(csr, "description"):
                    description = csr.description
                if isinstance(csr, _CompoundCSR) and len(csr.simple_csrs) > 1:
                    is_first = True
                    for i in range(len(csr.simple_csrs)):
                        (start, length, name) = sub_csr_bit_range(
                            region.busword, csr, i)
                        if length > 0:
                            bits_str = "Bits {}-{} of `{}`.".format(
                                start, start+length, csr.name)
                        else:
                            bits_str = "Bit {} of `{}`.".format(
                                start, csr.name)
                        if is_first:
                            if description is not None:
                                print_svd_register(
                                    csr.simple_csrs[i], csr_address, bits_str + " " + description, length, svd)
                            else:
                                print_svd_register(
                                    csr.simple_csrs[i], csr_address, bits_str, length, svd)
                            is_first = False
                        else:
                            print_svd_register(
                                csr.simple_csrs[i], csr_address, bits_str, length, svd)
                        csr_address = csr_address + 4
                else:
                    length = ((csr.size + region.busword - 1) //
                              region.busword) * region.busword
                    print_svd_register(
                        csr, csr_address, description, length, svd)
                    csr_address = csr_address + 4
            print('            </registers>', file=svd)
            print('            <addressBlock>', file=svd)
            print('                <offset>0</offset>', file=svd)
            print(
                '                <size>0x{:x}</size>'.format(csr_address), file=svd)
            print('                <usage>registers</usage>', file=svd)
            print('            </addressBlock>', file=svd)
            if region.name in interrupts:
                print('            <interrupt>', file=svd)
                print('                <name>{}</name>'.format(region.name), file=svd)
                print(
                    '                <value>{}</value>'.format(interrupts[region.name]), file=svd)
                print('            </interrupt>', file=svd)
            print('        </peripheral>', file=svd)
        print('    </peripherals>', file=svd)
        print('</device>', file=svd)


def generate_docs(soc, base_dir, project_name="LiteX SoC Project",
                  author="Anonymous", sphinx_extensions=[], quiet=False, note_pulses=False,
                  from_scratch=True):
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

    if not quiet:
        print("Generate the documentation by running `sphinx-build -M html {} {}_build`".format(base_dir, base_dir))

    # Gather all interrupts so we can easily map IRQ numbers to CSR sections
    interrupts = {}
    for csr, irq in sorted(soc.soc_interrupt_map.items()):
        interrupts[csr] = irq

    # Convert each CSR region into a DocumentedCSRRegion.
    # This process will also expand each CSR into a DocumentedCSR,
    # which means that CompoundCSRs (such as CSRStorage and CSRStatus)
    # that are larger than the buswidth will be turned into multiple
    # DocumentedCSRs.
    documented_regions = []
    seen_modules = set()
    regions = []

    # Previously, litex contained a function to gather csr regions.
    if hasattr(soc, "get_csr_regions"):
        regions = soc.get_csr_regions()
    else:
        # Now we just access the regions directly.
        for region_name, region in soc.csr_regions.items():
            regions.append((region_name, region.origin,
                            region.busword, region.obj))

    for csr_region in regions:
        module = None
        if hasattr(soc, csr_region[0]):
            module = getattr(soc, csr_region[0])
            seen_modules.add(module)
        submodules = gather_submodules(module)

        documented_region = DocumentedCSRRegion(
            csr_region, module, submodules, csr_data_width=soc.csr_data_width)
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
-------

.. toctree::
    :maxdepth: 1
""", file=index)
                for module in additional_modules:
                    print("    {}".format(module.name), file=index)

            if len(documented_regions) > 0:
                print("""
Register Groups
---------------

.. toctree::
    :maxdepth: 1
""", file=index)
                for region in documented_regions:
                    print("    {}".format(region.name), file=index)

            print("""
Indices and tables
------------------

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
