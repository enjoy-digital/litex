#
# This file is part of LiteX.
#
# This file is Copyright (c) 2019 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import DUID
from migen.util.misc import xdir

from litex.soc.interconnect.csr_eventmanager import EventManager

import textwrap
import inspect

class ModuleDoc(DUID):
    """Module Documentation Support

    ModuleDoc enables you to add documentation to your Module.  This documentation is in addition to
    any CSR-level documentation you may add to your module, if applicable.

    There are two ways to use :obj:`ModuleDoc`:

    1. Inherit :obj:`ModuleDoc` as part of your class.  The docstring of your class will become the
    first section of your class' module documentation
    2. Add a :obj:`ModuleDoc` object to your class and inherit from :obj:`AutoDoc`.

    If you inherit from :obj:`ModuleDoc`, then there is no need to call ``__init__()``

    Synopsis
    --------

    ::

        class SomeClass(Module, ModuleDoc, AutoDoc):
            \"\"\"Some Special Hardware Module

            This is a hardware module that implements something really cool.
            \"\"\"

            def __init__(self):
                self.other_section = ModuleDoc(title="Protocol Details", body="This section details more
                information about the protocol")

    """

    def __init__(self, body=None, title=None, file=None, format="rst"):
        """Construct a :obj:`ModuleDoc` object for use with :obj:`AutoDoc`

        Arguments
        ---------

        body (:obj:`str`): Main body of the document.  If ``title`` is omitted, then the
        title is taken as the first line of ``body``.

        title (:obj:`str` Optional): Title of this particular section.

        file (:obj:`str` Optional): It is possible to load the documentation from an external
        file instead of specifying it inline.  This allows for the use of an external text
        editor.  If a ``file`` is specified, then it will override the ``body`` argument.

        format (:obj:`str` Optional): The text format.  Python prefers reStructured Text, so this
        defaults to `rst`.  If specifying a `file`, then the suffix will be used instead of
        `format`.  If you specify a format other than `rst`, you may need to install a converter.
        """

        import os
        DUID.__init__(self)
        self._title = title
        self._format = format

        if file is None and body is None and self.__doc__ is None:
            raise ValueError("Must specify `file` or `body` when constructing a ModuleDoc()")
        if file is not None:
            if not os.path.isabs(file):
                relative_path = inspect.stack()[1][1]
                file = os.path.dirname(relative_path) + os.path.sep + file
            (_, self._format) = os.path.splitext(file)
            self._format = self._format[1:] # Strip off "." from extension

            # If it's a reStructured Text file, read the whole thing in.
            if self._format == "rst":
                with open(file, "r") as f:
                    self.__doc__ = f.read()
            # Otherwise, we'll simply make a link to it and let sphinx take care of it
            else:
                self._path = file
        elif body is not None:
            self.__doc__ = body

    def title(self):
        # This object might not have _title as an attribute, because
        # the ModuleDoc constructor may not have been called.  If this
        # is the case, manipulate the __doc__ string directly.
        if hasattr(self, "_title") and self._title is not None:
            return self._title
        _lines = self.__doc__.splitlines()
        return textwrap.dedent(_lines[0])

    def body(self):
        if hasattr(self, "_title") and self._title is not None:
            return self.__doc__
        _lines = self.__doc__.splitlines()
        _lines.pop(0)
        return textwrap.dedent("\n".join(_lines))

    def format(self):
        if hasattr(self, "_format") and self._format is not None:
            return self._format
        return "rst"

    def path(self):
        if hasattr(self, "_path"):
            return self._path
        return None

def documentationprefix(prefix, documents, done):
    for doc in documents:
        if doc.duid not in done:
            # doc.name = prefix + doc.name
            done.add(doc.duid)

def _make_gatherer(method, cls, prefix_cb):
    def gatherer(self):
        try:
            exclude = self.autodoc_exclude
        except AttributeError:
            exclude = {}
        try:
            prefixed = self.__prefixed
        except AttributeError:
            prefixed = self.__prefixed = set()
        r = []
        for k, v in xdir(self, True):
            if k not in exclude:
                if isinstance(v, cls):
                    r.append(v)
                elif hasattr(v, method) and callable(getattr(v, method)):
                    items = getattr(v, method)()
                    prefix_cb(k + "_", items, prefixed)
                    r += items
        return sorted(r, key=lambda x: x.duid)
    return gatherer

class AutoDoc:
    """MixIn to provide documentation support.

    A module can inherit from the ``AutoDoc`` class, which provides ``get_module_documentation``.
    This will iterate through all objects looking for ones that inherit from ModuleDoc.

    If the module has child objects that implement ``get_module_documentation``,
    they will be called by the``AutoCSR`` methods and their documentation added to the lists returned,
    with the child objects' names as prefixes.
    """
    get_module_documentation = _make_gatherer("get_module_documentation", ModuleDoc, documentationprefix)
