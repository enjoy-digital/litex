# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

import subprocess
import os
import time


class Runner:
    def __init__(self, options=None, extra_files=None, top_file="migensim_top.v", dut_file="migensim_dut.v", vvp_file=None, keep_files=False):
        if extra_files is None: extra_files = []
        if vvp_file is None: vvp_file = dut_file + "vp"
        if options is None: options = []
        self.options = options
        self.extra_files = extra_files
        self.top_file = top_file
        self.dut_file = dut_file
        self.vvp_file = vvp_file
        self.data_files = []
        self.keep_files = keep_files

    def start(self, c_top, c_dut):
        with open(self.top_file, "w") as f:
            f.write(c_top)
        c_dut.write(self.dut_file)
        self.data_files += c_dut.data_files.keys()
        subprocess.check_call(["iverilog", "-o", self.vvp_file] + self.options + [self.top_file, self.dut_file] + self.extra_files)
        self.process = subprocess.Popen(["vvp", "-mmigensim", "-Mvpi", self.vvp_file])

    def close(self):
        if hasattr(self, "process"):
            self.process.terminate()
            if self.process.poll() is None:
                time.sleep(.1)
                self.process.kill()
            self.process.wait()
        if not self.keep_files:
            for f in [self.top_file, self.dut_file, self.vvp_file] + self.data_files:
                try:
                    os.remove(f)
                except OSError:
                    pass
        self.data_files.clear()
