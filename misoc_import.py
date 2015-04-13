import sys
import importlib


def misoc_import(default, external, name):
    if external:
        try:
            del sys.modules[name] # force external path search
        except KeyError:
            pass
        loader = importlib.find_loader(name, [external])
        if loader is None:
            # try internal import
            return importlib.import_module(default + "." + name)
        return loader.load_module()
    else:
        return importlib.import_module(default + "." + name)
