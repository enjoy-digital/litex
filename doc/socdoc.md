# Litex Documentation: Document your LiteX SoC Automatically

Litex lets you take a synthesized SoC and generate full
register-level documentation.  Additionally, it will generate `.svd` files,
suitable for use with various header generation programs.

## Required Software

You must have `sphinx` and `sphinx.wavedrom` installed in order to build
the documentation.  These can be installed with pip:

```
$ pip3 install sphinxcontrib-wavedrom sphinx
```

## Usage

To document your modules, import the `doc` module and call `doc.generate_docs(soc, path)`.
You can also generate an SVD file.  For example:

```python
from litex.soc.doc import generate_docs, generate_svd

...
    soc = BaseSoC(platform)
    builder = Builder(soc)
    vns = builder.build()
    soc.do_exit(vns)
    generate_docs(soc, "build/documentation",
                        project_name="My SoC",
                        author="LiteX User")
    generate_svd(soc, "build/software")
```

After you build your design, you will have a Sphinx documentation source available
in the above directory.  To build this into a target document, use `sphinx-build`.

For example, if `sphinx-build` is in your path, you can run:

`sphinx-build -M html build/documentation/ build/documentation/_build`

`sphinx-build` may be located in `~/.local/bin/` depending on your installation environment.

You can then verify the contents by opening the file `build/documentation/_build/html/index.html`

## Documenting your Registers

You can add documentation to your registers by defining your `CSRStorage` and `CSRStatus` registers with an additional `field` list.  For example:

```python
self.bitbang = CSRStorage(4, fields=[
    CSRField("mosi", description="Output value for MOSI..."
    CSRField("clk", description="Output value for SPI CLK..."
    CSRField("cs_n", description="Output value for SPI C..."
    CSRField("dir", description="Sets the dir...", values=[
        ("0", "OUT", "SPI pins are all output"),
        ("1", "IN", "SPI pins are all input"),
    ])
], description="""Bitbang controls for SPI output.  Only
    standard 1x SPI is supported, and as a result all
    four wires are ganged together.  This means that it
    is only possible to perform half-duplex operations,
    using this SPI core.""")
```

There are several interesting properties here:

* The first argument to a `CSRStorage` or `CSRStatus` is the bit width.
* You can pass a list of `CSRField` objects, which will get turned into bit fields
* Both `CSRStorage` and `CSRStatus` support a freeform `description` property that will be used to describe the overall register.

A `CSRField` object has the following properties:

* `name`: The short name of the register.  This should be just a few characters long, as it will be used in the register diagram as well as accessor objects.  **Required**
* `size`: The size of this field.  This is optional, and defaults to `1`
* `offset`: The offset of this particular field.  If unspecified, defaults to following the previous field.  Use this to add gaps to your register definitions, for example to have reserved fields.
* `reset`: If specified, the value of this field at reset.  Defaults to `0`.
* `description`: A textual description of this register.  This is optional, but should be specified because it provides critical information to the user about what this field does.
* `pulse`: If `True`, then this value is `1` only for one clock cycle after the user writes a `1` to this field.  This is especially useful for `START` bits used to initiate operations, or `RESET` bits used to clear an operation.
* `access`: The accessibility of this field.  One of `CSRAccess.ReadWrite`, `CSRAccess.WriteOnly`, or `CSRAccess.ReadOnly`
* `values`: If present, a list of tuples of values.  The first field is the numeric value, with `x` for `don't care`.  The second field, if present, is the short name of the value.  The final field is a textual description of the value.  For example:

```python
    [
        ("0b0000", "disable the timer"),
        ("0b0001", "slow", "slow timer"),
        ("0b1xxx", "fast timer"),
    ]
```

## Further Module Documentation

You can add additional documentation to your module with the `ModuleDoc` class.  Add it to your base object.

**To use further Module Documentation, your Module must inherit from `AutoDoc`**.  For example:

```python
from litex.soc.integration.doc import AutoDoc, ModuleDoc
class DocExample(Module, AutoCSR, AutoDoc):
    def __init__(self):
        self.mydoc = ModuleDoc("Some documentation")
```

You may pass a single string to the constructor, in which case the first line becomes the title, or you may pass a separate `title` and `body` parameters to the constructor.  For example:

```python
    self.intro = ModuleDoc("""Introduce ModuleDoc

    This is an example of how to document using ModuleDoc.  An additional
    section will get added to the output documentation for this module,
    with the title ``Introduce ModuleDoc`` and with this paragraph
    as a body""")
```

Note that the default documentation format is `rst`. You can switch to markdown by passing `format="markdown"` to the constructor, however support is not very good.

### Additional Sphinx Extensions

The `generate_docs()` call produces Sphinx output. By default it only includes
additional extensions for `sphinxcontrib.wavedrom`, which is required to display
register listings. You can add additional modules by passing an array to
`generate_docs()`. For example, to add `mathjax` support:

```python
    generate_docs("build/documentation", sphinx_extensions=['sphinx.ext.mathjax'])
```

You may need to pass additional configuration to `conf.py`. In this case, pass it
as `sphinx_extra_config`. For example:

```python
    generate_docs("build/documentation",
            sphinx_extensions=['sphinx_math_dollar', 'sphinx.ext.mathjax'],
            sphinx_extra_config=r"""
   mathjax_config = {
       'tex2jax': {
           'inlineMath': [ ["\\(","\\)"] ],
           'displayMath': [["\\[","\\]"] ],
       },
   }""")
```

By default, `socdoc` unconditionally overwrites all files in the output
directory, including the sphinx `conf.py` file. To disable this feature
so you can customize your own `conf.py` file, pass `from_scratch=False`:

```python
    generate_docs("build/documentation", from_scratch=False)
```

In this case, `conf.py` will only be created if it does not already exist.

### External Documentation

You can have external documentation by passing `file` to the constructor.
For example:

```python
    self.extra_doc = ModuleDoc(file="extra_doc.rst")
```

This will be included at build-time.

### Using Python Docstrings

You can also simply have your module inherit from `ModuleDoc`, in which case
the documentation will be taken from the docstring.  For example:

```python
from litex.soc.integration.doc import AutoDoc, ModuleDoc
class DocExample(Module, AutoCSR, AutoDoc, ModuleDoc):
    """
    Automatically Documented Module

    This module will be automatically documented, and included in the
    generated module documentation output.  You can add additional
    ModuleDoc objects to this module, in order to add further subsections
    to the output docs.
    """
    def __init__(self):
        pass
```
