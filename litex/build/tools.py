import os
import struct
from distutils.version import StrictVersion
import re
import subprocess
import sys


def language_by_filename(name):
    extension = name.rsplit(".")[-1]
    if extension in ["v", "vh", "vo"]:
        return "verilog"
    if extension in ["vhd", "vhdl", "vho"]:
        return "vhdl"
    return None


def write_to_file(filename, contents, force_unix=False):
    newline = None
    if force_unix:
        newline = "\n"
    with open(filename, "w", newline=newline) as f:
        f.write(contents)


def arch_bits():
    return struct.calcsize("P")*8


def versions(path):
    for n in os.listdir(path):
        full = os.path.join(path, n)
        if not os.path.isdir(full):
            continue
        try:
            yield StrictVersion(n)
        except ValueError:
            continue


def sub_rules(lines, rules, max_matches=1):
    for line in lines:
        n = max_matches
        for pattern, color in rules:
            line, m = re.subn(pattern, color, line, n)
            n -= m
            if not n:
                break
        yield line


def subprocess_call_filtered(command, rules, *, max_matches=1, **kwargs):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                            universal_newlines=True, bufsize=1,
                            **kwargs)
    with proc:
        for line in sub_rules(iter(proc.stdout.readline, ""),
                              rules, max_matches):
            sys.stdout.write(line)
    return proc.returncode
