from math import gcd
import collections


def flat_iteration(l):
    for element in l:
        if isinstance(element, collections.Iterable):
            for element2 in flat_iteration(element):
                yield element2
        else:
            yield element


def xdir(obj, return_values=False):
    for attr in dir(obj):
        if attr[:2] != "__" and attr[-2:] != "__":
            if return_values:
                yield attr, getattr(obj, attr)
            else:
                yield attr


def gcd_multiple(numbers):
    l = len(numbers)
    if l == 1:
        return numbers[0]
    else:
        s = l//2
        return gcd(gcd_multiple(numbers[:s]), gcd_multiple(numbers[s:]))
