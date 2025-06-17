#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2014 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2016-2017 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import struct
import re
import threading
import subprocess
import sys
import ctypes
import time
import datetime


def language_by_filename(name):
    extension = name.rsplit(".")[-1]
    if extension in ["v", "vh", "vo", "vp"]:
        return "verilog"
    elif extension in ["vhd", "vhdl", "vho"]:
        return "vhdl"
    elif extension in ["sv", "svo"]:
        return "systemverilog"
    return None


def write_to_file(filename, contents, force_unix=False):
    newline = None
    if force_unix:
        newline = "\n"
    old_contents = None
    if os.path.exists(filename):
        with open(filename, "r", newline=newline) as f:
            old_contents = f.read()
    if old_contents != contents:
        with open(filename, "w", newline=newline) as f:
            f.write(contents)

def replace_in_file(filename, _from, _to):
    # Read in the file
    with open(filename, "r") as file :
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace(_from, _to)

    # Write the file out again
    with open(filename, "w") as file:
        file.write(filedata)

def sub_rules(line, rules, max_matches=1):
    for pattern, color in rules:
        line, matches = re.subn(pattern, color, line, max_matches)
        max_matches -= matches
        if not max_matches:
            break
    return line

def _tail_file(path, proc, rules, max_matches=1, poll=0.1):
    """
    Very small 'tail -f' clone:
      • waits until *path* exists,
      • echoes new lines while *proc* is alive,
      • flushes the remainder when *proc* ends.
    """
    # Wait for the file to appear (efx_run.py creates it lazily)
    while proc.poll() is None and not os.path.exists(path):
        time.sleep(poll)

    try:
        with open(path, "r", errors="ignore") as f:
            # show full content, not just the end
            while proc.poll() is None:
                where = f.tell()
                line  = f.readline()
                if line:
                    print(sub_rules(line, rules, max_matches), end="")
                else:
                    time.sleep(poll)
                    f.seek(where)
            # grab what is still pending
            for line in f:
                print(sub_rules(line, rules, max_matches), end="")
    except FileNotFoundError:
        # wrong path → nothing to tail, but the main process may still fail normally
        pass

def subprocess_call_filtered(command, rules, *, max_matches=1, tail_log=None, tail_poll=0.25, **kwargs):
    """
    Spawn *command* and stream its stdout/stderr through `sub_rules(...)`
    exactly as before.

    Extra feature:
        tail_log="path/to/file"
            → while the command runs, also stream every new line written
              to that file (works like `tail -f`).
    """
    with subprocess.Popen(command,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          universal_newlines=True,
                          bufsize=1,
                          **kwargs) as proc:

        # launch the background tail (non-blocking)
        tail_thread = None
        if tail_log:
            tail_thread = threading.Thread(
                target=_tail_file,
                args=(tail_log, proc, rules, max_matches, tail_poll),
                daemon=True)
            tail_thread.start()

        # forward the real stdout
        with open(proc.stdout.fileno(), errors="ignore", closefd=False) as stdout:
            for line in stdout:
                print(sub_rules(line, rules, max_matches), end="")

        rc = proc.wait()
        if tail_thread:
            tail_thread.join()
        return rc

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

def get_litex_git_revision():
    import litex
    d = os.getcwd()
    os.chdir(os.path.dirname(litex.__file__))
    try:
        r = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL)[:-1].decode("utf-8")
    except:
        r = "--------"
    os.chdir(d)
    return r

def generated_separator(line_comment="//", msg=""):
    r = line_comment + "-"*80 + "\n"
    r += line_comment + " " + msg + "\n"
    r += line_comment + "-"*80 + "\n"
    return r

def generated_banner(line_comment="//"):
    msg = "Auto-generated by LiteX ({}) on {}".format(
        get_litex_git_revision(),
        datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"),
    )
    return generated_separator(line_comment, msg)
