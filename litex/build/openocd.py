#
# This file is part of LiteX.
#
# Copyright (c) 2015-2017 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess

from litex.build.tools import write_to_file
from litex.build.generic_programmer import GenericProgrammer


class OpenOCD(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, config, flash_proxy_basename=None):
        GenericProgrammer.__init__(self, flash_proxy_basename)
        self.config = config

    def load_bitstream(self, bitstream):
        config = self.find_config()
        script = "; ".join([
            "init",
            "pld load 0 {{{}}}".format(bitstream),
            "exit",
        ])
        subprocess.call(["openocd", "-f", config, "-c", script])

    def flash(self, address, data, set_qe=False):
        config      = self.find_config()
        flash_proxy = self.find_flash_proxy()
        script = "; ".join([
            "init",
            "jtagspi_init 0 {{{}}}".format(flash_proxy),
            "jtagspi set_qe 0 1" if set_qe else "",
            "jtagspi_program {{{}}} 0x{:x}".format(data, address),
            "fpga_program",
            "exit"
        ])
        subprocess.call(["openocd", "-f", config, "-c", script])


    def stream(self, port=20000):
        """
        Create a Telnet server to stream data to/from the internal JTAG TAP of the FPGA

        Wire format: 10 bits LSB first
        Host to Target:
          - TX ready : bit 0
          - RX data: : bit 1 to 8
          - RX valid : bit 9

        Target to Host:
          - RX ready : bit 0
          - TX data  : bit 1 to 8
          - TX valid : bit 9
        """
        cfg = """
proc jtagstream_poll {tap tx n} {
    set m [string length $tx]
    set n [expr ($m>$n)?$m:$n]
    set txi [lrepeat $n {10 0x001}]
    set i 0
    foreach txj [split $tx ""] {
        lset txi $i 1 [format 0x%4.4X [expr 0x201 | ([scan $txj %c] << 1)]]
        incr i
    }
    set txi [concat {*}$txi]
    set rxi [split [drscan $tap {*}$txi -endstate DRPAUSE] " "]
    #echo $txi:$rxi
    set rx ""
    set writable 1
    foreach {rxj} $rxi {
        set readable [expr 0x$rxj & 0x200]
        set writable [expr 0x$rxj & $writable]
        if {$readable} {
            append rx [format %c [expr (0x$rxj >> 1) & 0xff]]
        }
    }
    return [list $rx $readable $writable]
}

proc jtagstream_drain {tap tx chunk_rx max_rx} {
    lassign [jtagstream_poll $tap $tx $chunk_rx] rx readable writable
    while {[expr $writable && ($readable > 0) && ([string length $rx] < $max_rx)]} {
        lassign [jtagstream_poll $tap "" $chunk_rx] rxi readable writable
        append rx $rxi
    }
    #if {!$writable} {
    #    echo "write overflow"
    #}
    return $rx
}

proc jtagstream_rxtx {tap client is_poll} {
    if {![$client eof]} {
        if {!$is_poll} {
            set tx [$client gets]
        } else {
            set tx ""
        }
        set rx [jtagstream_drain $tap $tx 64 4096]
        if {[string length $rx]} {
            $client puts -nonewline $rx
        }
        if {$is_poll} {
            after 1 [list jtagstream_rxtx $tap $client 1]
        }
    } else {
        $client readable {}
        $client onexception {}
        $client close
    }
}

proc jtagstream_client {tap sock} {
    set client [$sock accept]
    fconfigure $client -buffering none
    $client readable [list jtagstream_rxtx $tap $client 0]
    $client onexception [list $client close]
    after 1 [list jtagstream_rxtx $tap $client 1]
}

proc jtagstream_exit {sock} {
    stdin readable {}
    $sock readable {}
}

proc jtagstream_serve {tap port} {
    set sock [socket stream.server $port]
    $sock readable [list jtagstream_client $tap $sock]
    stdin readable [list jtagstream_exit $sock]
    vwait forever
    $sock close
}
"""
        write_to_file("stream.cfg", cfg)
        script = "; ".join([
            "init",
            "irscan $_CHIPNAME.tap $_USER1",
            "jtagstream_serve $_CHIPNAME.tap {:d}".format(port),
            "exit",
        ])
        config = self.find_config()
        subprocess.call(["openocd", "-f", config, "-f", "stream.cfg", "-c", script])
