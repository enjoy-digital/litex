from importlib import import_module

def get_edatool(toolchain):
    return getattr(import_module(f"{__name__}.{toolchain}"), toolchain.capitalize())
