import os
import struct
from distutils.version import StrictVersion
import re
import subprocess
import sys
import ctypes


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


def sub_rules(line, rules, max_matches=1):
    for pattern, color in rules:
        line, matches = re.subn(pattern, color, line, max_matches)
        max_matches -= matches
        if not max_matches:
            break
    return line


def subprocess_call_filtered(command, rules, *, max_matches=1, **kwargs):
    with subprocess.Popen(command, stdout=subprocess.PIPE,
                          universal_newlines=True, bufsize=1,
                          **kwargs) as proc:
        with open(proc.stdout.fileno(), errors="ignore", closefd=False) as stdout:
            for line in stdout:
                print(sub_rules(line, rules, max_matches), end="")
        return proc.wait()


if sys.platform == "cygwin":
    cygwin1 = ctypes.CDLL("/usr/bin/cygwin1.dll")
    cygwin_conv_path_proto = ctypes.CFUNCTYPE(
        ctypes.c_ssize_t, # Return
        ctypes.c_uint, # what
        ctypes.c_void_p, # from
        ctypes.c_void_p, # to
        ctypes.c_size_t) # size
    cygwin_conv_path = cygwin_conv_path_proto(("cygwin_conv_path", cygwin1),
        ((1, "what"),
        (1, "from"),
        (1, "to"),
        (1, "size")))


    def cygpath_to_windows(path):
        what = ctypes.c_uint(0) # CCP_POSIX_TO_WIN_A
        fro = ctypes.c_char_p(path.encode('utf-8'))
        to = ctypes.byref(ctypes.create_string_buffer(260))
        size = ctypes.c_size_t(260)

        cygwin_conv_path(what, fro, to, size)
        return ctypes.cast(to, ctypes.c_char_p).value.decode('utf-8')

    # Convert cygwin paths to Windows native paths. This is a noop otherwise.
    def cygpath(p):
        return cygpath_to_windows(p)
else:
    def cygpath(p):
        return p
