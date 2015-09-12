import collections
from itertools import combinations

from migen.util.misc import flat_iteration
from migen.fhdl.structure import *
from migen.fhdl.structure import _Fragment
from migen.fhdl.tools import rename_clock_domain


__all__ = ["Module", "FinalizeError"]


class FinalizeError(Exception):
    pass


def _flat_list(e):
    if isinstance(e, collections.Iterable):
        return flat_iteration(e)
    else:
        return [e]


class _ModuleProxy:
    def __init__(self, fm):
        object.__setattr__(self, "_fm", fm)


class _ModuleComb(_ModuleProxy):
    def __iadd__(self, other):
        self._fm._fragment.comb += _flat_list(other)
        return self


def _cd_append(d, key, statements):
    try:
        l = d[key]
    except KeyError:
        l = []
        d[key] = l
    l += _flat_list(statements)


class _ModuleSyncCD:
    def __init__(self, fm, cd):
        self._fm = fm
        self._cd = cd

    def __iadd__(self, other):
        _cd_append(self._fm._fragment.sync, self._cd, other)
        return self


class _ModuleSync(_ModuleProxy):
    def __iadd__(self, other):
        _cd_append(self._fm._fragment.sync, "sys", other)
        return self

    def __getattr__(self, name):
        return _ModuleSyncCD(self._fm, name)

    def __setattr__(self, name, value):
        if not isinstance(value, _ModuleSyncCD):
            raise AttributeError("Attempted to assign sync property - use += instead")


# _ModuleForwardAttr enables user classes to do e.g.:
# self.subm.foobar = SomeModule()
# and then access the submodule with self.foobar.
class _ModuleForwardAttr:
    def __setattr__(self, name, value):
        self.__iadd__(value)
        setattr(self._fm, name, value)


class _ModuleSpecials(_ModuleProxy, _ModuleForwardAttr):
    def __iadd__(self, other):
        self._fm._fragment.specials |= set(_flat_list(other))
        return self


class _ModuleSubmodules(_ModuleProxy):
    def __setattr__(self, name, value):
        self._fm._submodules += [(name, e) for e in _flat_list(value)]
        setattr(self._fm, name, value)

    def __iadd__(self, other):
        self._fm._submodules += [(None, e) for e in _flat_list(other)]
        return self


class _ModuleClockDomains(_ModuleProxy, _ModuleForwardAttr):
    def __iadd__(self, other):
        self._fm._fragment.clock_domains += _flat_list(other)
        return self


class Module:
    def get_fragment(self):
        assert(not self.get_fragment_called)
        self.get_fragment_called = True
        self.finalize()
        return self._fragment

    def __getattr__(self, name):
        if name == "comb":
            return _ModuleComb(self)
        elif name == "sync":
            return _ModuleSync(self)
        elif name == "specials":
            return _ModuleSpecials(self)
        elif name == "submodules":
            return _ModuleSubmodules(self)
        elif name == "clock_domains":
            return _ModuleClockDomains(self)

        # hack to have initialized regular attributes without using __init__
        # (which would require derived classes to call it)
        elif name == "finalized":
            self.finalized = False
            return self.finalized
        elif name == "_fragment":
            self._fragment = _Fragment()
            return self._fragment
        elif name == "_submodules":
            self._submodules = []
            return self._submodules
        elif name == "_clock_domains":
            self._clock_domains = []
            return self._clock_domains
        elif name == "get_fragment_called":
            self.get_fragment_called = False
            return self.get_fragment_called

        else:
            raise AttributeError("'"+self.__class__.__name__+"' object has no attribute '"+name+"'")

    def __setattr__(self, name, value):
        if name in ["comb", "sync", "specials", "submodules", "clock_domains"]:
            if not isinstance(value, _ModuleProxy):
                raise AttributeError("Attempted to assign special Module property - use += instead")
        else:
            object.__setattr__(self, name, value)

    def _collect_submodules(self):
        r = []
        for name, submodule in self._submodules:
            if not submodule.get_fragment_called:
                r.append((name, submodule.get_fragment()))
        return r

    def finalize(self, *args, **kwargs):
        if not self.finalized:
            self.finalized = True
            # finalize existing submodules before finalizing us
            subfragments = self._collect_submodules()
            self.do_finalize(*args, **kwargs)
            # finalize submodules created by do_finalize
            subfragments += self._collect_submodules()
            # resolve clock domain name conflicts
            needs_renaming = set()
            for (mod_name1, f1), (mod_name2, f2) in combinations(subfragments, 2):
                f1_names = set(cd.name for cd in f1.clock_domains)
                f2_names = set(cd.name for cd in f2.clock_domains)
                common_names = f1_names & f2_names
                if common_names:
                    if mod_name1 is None or mod_name2 is None:
                        raise ValueError("Multiple submodules with local clock domains cannot be anonymous")
                    if mod_name1 == mod_name2:
                        raise ValueError("Multiple submodules with local clock domains cannot have the same name")
                needs_renaming |= common_names
            for mod_name, f in subfragments:
                for cd in f.clock_domains:
                    if cd.name in needs_renaming:
                        rename_clock_domain(f, cd.name, mod_name + "_" + cd.name)
            # sum subfragments
            for mod_name, f in subfragments:
                self._fragment += f

    def do_finalize(self):
        pass

    def do_exit(self, *args, **kwargs):
        for name, submodule in self._submodules:
            submodule.do_exit(*args, **kwargs)
