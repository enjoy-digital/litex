#
# This file is part of LiteX.
#
# Copyright (c) 2015-2017 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile

from litex.build.generic_programmer import GenericProgrammer

# OpenOCD ------------------------------------------------------------------------------------------

def get_openocd_cmd():
    """Get OpenOCD command, respecting OPENOCD environment variable."""
    return os.environ.get("OPENOCD", "openocd")

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
        self.call([get_openocd_cmd(), "-f", config, "-c", script])

    def flash(self, address, data, set_qe=False, init_commands=[]):
        config      = self.find_config()
        flash_proxy = self.find_flash_proxy()
        script = "; ".join([
            "init",
            "jtagspi_init 0 {{{}}}".format(flash_proxy)
        ] + init_commands + [
            "jtagspi set_qe 0 1" if set_qe else "",
            "jtagspi_program {{{}}} 0x{:x}".format(data, address),
            "fpga_program",
            "exit"
        ])
        self.call([get_openocd_cmd(), "-f", config, "-c", script])

    def get_tap_name(self, config):
        cfg_str = open(config).read()
        if "zynq_7000" in cfg_str:
            return "zynq_pl.bs"
        return "$_CHIPNAME.tap"

    def get_ir(self, chain, config):
        cfg_str = open(config).read()

        def lookup_ir(family, irs):
            if chain not in irs:
                raise ValueError(
                    f"Unsupported chain {chain} for {family}, supported chain(s): {sorted(irs.keys())}.")
            return irs[chain]

        def warn_ignored(family, ir):
            if chain != 1:
                print(f"Warning: chain={chain} ignored on {family} (hardcoded IR 0x{ir:x}).")

        # Lattice ECP5.
        if "ecp5" in cfg_str:
            warn_ignored("Lattice ECP5", 0x32)
            return 0x32
        # Intel Max10.
        elif "10m50" in cfg_str:
            warn_ignored("Intel Max10", 0xc)
            return 0xc
        # Intel Arria10.
        elif "10ax" in cfg_str:
            warn_ignored("Intel Arria10", 0xc)
            return 0xc
        # Intel CycloneIV.
        elif "ep4ce" in cfg_str:
            warn_ignored("Intel CycloneIV", 0xe)
            return 0xe
        # Xilinx ZynqMP.
        elif "zynqmp" in cfg_str:
            return lookup_ir("Xilinx ZynqMP", {
                1: 0x902, # USER1.
                2: 0x903, # USER2.
                3: 0x922, # USER3.
                4: 0x923, # USER4.
            })
        # Efinix titanium
        elif "titanium" in cfg_str:
            return lookup_ir("Efinix Titanium", {
                1: 0x08,
            })
        # Xilinx 7-Series.
        else:
            return lookup_ir("Xilinx 7-Series", {
                1: 0x02, # USER1.
                2: 0x03, # USER2.
                3: 0x22, # USER3.
                4: 0x23, # USER4.
            })

    def get_endstate(self, config):
        cfg_str = open(config).read()
        # Lattice ECP5.
        if "ecp5" in cfg_str:
            return "-endstate DRPAUSE" # CHECKME: Can we avoid it?
        # Intel Max10.
        elif "10m50" in cfg_str:
            return "-endstate DRPAUSE" # CHECKME: Is it required on Intel?
        else:
            return ""

    def stream(self, port=20000, chain=1):
        """
        Create a TCP server to stream data to/from the internal JTAG TAP of the FPGA

        Wire format: 11 bits LSB first (11 shift cycles for 10 bits of data)
        Due to JTAG timing, we need N+1 shift cycles to capture N bits because
        the last falling edge is in Exit1-DR state (doesn't capture TDO).

        Host to Target:
          - TX ready : bit 0
          - RX data  : bit 1 to 8
          - RX valid : bit 9
          - Padding  : bit 10 (ignored)

        Target to Host:
          - RX ready : bit 0
          - TX data  : bit 1 to 8
          - TX valid : bit 9
          - Padding  : bit 10 (repeat of valid)
        """
        config   = self.find_config()
        tap_name = self.get_tap_name(config)
        ir       = self.get_ir(chain, config)
        endstate = self.get_endstate(config)
        cfg = """
if {[catch {binary format c 0x41}]} {
    # Jim Tcl builds without the binary command (e.g. OpenOCD 0.11): format %c is byte-exact
    # there (strings have no UTF-8 representation), so it can build the byte stream directly.
    proc jtagstream_byte {value} {
        return [format %c $value]
    }
} else {
    # Jim Tcl builds with UTF-8 string representation: format %c would encode bytes >= 0x80
    # as two bytes, corrupting the stream; use the byte-exact binary command instead.
    proc jtagstream_byte {value} {
        return [binary format c $value]
    }
}

proc jtagstream_word {word} {
    set word [string trim $word]
    if {[string equal [string range $word 0 1] "0x"] || [string equal [string range $word 0 1] "0X"]} {
        set word [string range $word 2 end]
    }
    scan $word %x value
    return $value
}

proc jtagstream_poll {tap tx n} {
    set m [string length $tx]
    set n [expr ($m>$n)?$m:$n]
    # 11 bits per word: bit0=ready, bits1-8=data, bit9=valid, bit10=padding
    # We need 11 shift cycles to capture all 10 bits because JTAGG only
    # captures TDO on falling edge in Shift-DR, and the last falling edge
    # is in Exit1-DR (doesn't capture).
    set txi [lrepeat $n {11 0x001}]
    set i 0
    foreach txj [split $tx ""] {
        # 0x401 = ready(1) + valid(1) = bit0 + bit9
        lset txi $i 1 [format 0x%4.4X [expr { 0x201 | ([scan $txj %c] << 1) }]]
        incr i
        #echo tx[scan $txj %c]
    }
    set txi [concat {*}$txi]
"""
        cfg += f"""
    # drscan returns newline-separated values in newer OpenOCD versions
    # Convert newlines to spaces and then split
    set raw_result [drscan $tap {{*}}$txi {endstate}]
    set rxi [split [string map {{"\n" " "}} $raw_result]]
"""
        cfg += """
    #echo $txi:$rxi
    set rx ""
    set readable 0
    set writable 1
    foreach rxj $rxi {
        if {[string length $rxj] == 0} {
            continue
        }
        set rxj [jtagstream_word $rxj]
        set readable [expr { $rxj & 0x200 }]
        set writable [expr { $rxj & $writable }]
        if {$readable} {
            append rx [jtagstream_byte [expr { ($rxj >> 1) & 0xff }]]
        }
    }
    return [list $rx $readable $writable]
}

proc jtagstream_drain {tap tx chunk_rx max_rx} {
    lassign [jtagstream_poll $tap $tx $chunk_rx] rx readable writable
    while {[expr { $writable && ($readable > 0) && ([string length $rx] < $max_rx) }]} {
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
        set tx [$client read 16]
        set rx [jtagstream_drain $tap $tx 128 4096]
        if {[string length $rx]} {
            #echo [string length $rx]
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
    fconfigure $client -blocking 0
    $client readable [list jtagstream_rxtx $tap $client 0]
    $client onexception [list $client close]
    after 1 [list jtagstream_rxtx $tap $client 1]
}

proc jtagstream_exit {sock} {
    $sock readable {}
}

proc jtagstream_serve {tap port} {
    set sock [socket stream.server $port]
    $sock readable [list jtagstream_client $tap $sock]
    # Note: Don't use stdin readable - it causes issues when running in background
    vwait forever
    $sock close
}
"""
        # Write Tcl helpers to a unique temporary file to avoid clobbering files in CWD.
        cfg_fd, cfg_file = tempfile.mkstemp(suffix=".cfg", prefix="litex_openocd_stream_")
        try:
            with os.fdopen(cfg_fd, "w") as f:
                f.write(cfg)
            script = "; ".join([
                "init",
                #"poll off", # FIXME: not supported for ECP5
                "irscan {} {:d}".format(tap_name, ir),
                "jtagstream_serve {} {:d}".format(tap_name, port),
                "exit",
            ])
            self.call([get_openocd_cmd(), "-f", config, "-f", cfg_file, "-c", script])
        finally:
            os.remove(cfg_file)
