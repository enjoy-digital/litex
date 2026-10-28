`--doc` builds a [Sphinx](https://www.sphinx-doc.org/) site of your SoC's registers (every
`CSRStorage` and `CSRStatus` with its fields and descriptions, the memory map, the interrupts,
the module descriptions, with register diagrams), and `--soc-svd` the `.svd` file `svd2rust`
and the debuggers read. Both come from the same Python objects as `csr.h`, so they cannot
disagree with the hardware.

## Generating it

With the Builder, on any target:

```sh
pip3 install sphinx sphinxcontrib-wavedrom
python3 target.py --build --no-compile-gateware --doc        # generates build/<platform>/doc/ and runs sphinx-build
xdg-open build/<platform>/doc/_build/html/index.html
```

`--soc-svd soc.svd` writes the SVD (also `generate_svd(soc, path)` from Python). From a script,
after the build:

```python
from litex.soc.doc import generate_docs, generate_svd

builder = Builder(soc)
builder.build()
generate_docs(soc, "build/documentation", project_name="My SoC", author="LiteX User")
generate_svd(soc, "build/software")
```

then `sphinx-build -M html build/documentation/ build/documentation/_build`. `generate_docs`
takes `sphinx_extensions=[...]` and `sphinx_extra_config="..."` to extend `conf.py` (mathjax,
for example) and `from_scratch=False` to keep a customized `conf.py`.

## Documenting your registers

Give the registers and their fields a description: `CSRStorage`/`CSRStatus` accept
`description=` and a `fields=[CSRField(...)]` list; a field has a `name`, a `size` (1 by
default), an `offset` (after the previous field by default), a `reset` value, a `description`,
`pulse=True` for self-clearing bits, an `access` (`CSRAccess.ReadWrite`, `WriteOnly`,
`ReadOnly`) and optional `values` (a list of `(value, [short name], description)` tuples):

```python
self.bitbang = CSRStorage(4, fields=[
    CSRField("mosi", description="Output value for MOSI."),
    CSRField("clk",  description="Output value for SPI CLK."),
    CSRField("cs_n", description="Output value for SPI CS_n."),
    CSRField("dir",  description="Direction of the SPI pins.", values=[
        ("0", "OUT", "SPI pins are all output"),
        ("1", "IN",  "SPI pins are all input"),
    ])
], description="""Bitbang controls for SPI output. Only standard 1x SPI is supported, and as
    a result all four wires are ganged together: half-duplex operations only.""")
```

The fields also give you the `<reg>_<field>_read()`/`_write()` accessors in `csr.h` and the
`CSR_<MOD>_<REG>_<FIELD>_OFFSET/SIZE` defines ([CSR-Bus](CSR-Bus.md)).

## Documenting a module

A module that inherits `AutoDoc` (every `LiteXModule` does) can carry `ModuleDoc` sections:

```python
from litex.soc.integration.doc import AutoDoc, ModuleDoc

class DocExample(LiteXModule):
    """Automatically Documented Module

    The docstring of a module that also inherits ModuleDoc becomes its documentation.
    """
    def __init__(self):
        self.intro = ModuleDoc("""Introduce ModuleDoc

        A ModuleDoc attribute adds a section with this title and this paragraph as its body.""")
        self.extra = ModuleDoc(file="extra_doc.rst")      # or from a file, included at build time
```

The text is reStructuredText by default (`format="markdown"` is possible, with limited
support); the first line is the title, or pass `title=` and `body=`. The register listings are
drawn by `sphinxcontrib.wavedrom`, hence the install line above.

## What the output contains

- An index with the SoC summary and the memory map (`mem.h` regions).
- One page per module with CSRs: its `ModuleDoc` sections, then each register with its address,
  the wavedrom bit-field diagram, the fields and their values.
- The interrupt table.
- The SVD describes the same registers for the tools that read CMSIS-SVD (Rust `svd2rust`,
  debuggers, register viewers).

## Next

- [CSR bus](CSR-Bus.md): the registers and fields this documentation describes, and the `csr.h` accessors.
- [Add a new core](Add-A-New-Core.md): where the descriptions are written.
- [Write firmware for it](Write-Firmware-For-Your-SoC.md): the headers generated next to the documentation.
