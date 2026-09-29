# SPDX-License-Identifier: BSD-2-Clause

"""Execute the generated Tcl without a JTAG adapter.

Set JIMSH to a Jim Tcl built with --utf8 to exercise character/byte differences.
OPENOCD selects an OpenOCD executable; its Jim interpreter runs without init.
Each interpreter is optional, with an explicit skip when it is unavailable.
"""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from litex.build.openocd import OpenOCD


@pytest.mark.parametrize("engine", ["jimsh", "openocd"])
@pytest.mark.parametrize("without_binary", [False, True])
def test_stream_bytes(tmp_path, monkeypatch, engine, without_binary):
    executable = os.environ.get(engine.upper()) or shutil.which(engine)
    if executable is None:
        pytest.skip(f"{engine} is not installed")

    config = tmp_path / "target.cfg"
    config.write_text("# xc7 test fixture\n")
    programmer = OpenOCD(str(config))
    script = tmp_path / "stream.tcl"

    def capture(command):
        # Capture the actual generated helpers before stream() deletes its
        # temporary file. Never launch its hardware initialization command.
        script.write_text(Path(command[4]).read_text())

    monkeypatch.setattr(programmer, "call", capture)
    programmer.stream()
    prefix = ""
    if without_binary:
        prefix = 'if {[llength [info commands binary]]} {rename binary ""}\n'
    script.write_text(prefix + script.read_text() + r'''
proc bytes {values} {
    set result ""
    set offset 0
    foreach value $values {
        pack result $value -intbe 8 $offset
        incr offset 8
    }
    return $result
}

set mode echo
proc drscan {tap args} {
    if {$::mode eq "drain"} {
        incr ::calls
        if {$::calls > 8} {error "drain failed to stop"}
        # Two UTF-8 codepoints, four raw bytes per poll.
        return "385 353 385 353"
    }
    set result {}
    set i 0
    set m [llength $::expected]
    set scans [expr {$m > $::minimum ? $m : $::minimum}]
    if {[llength $args] != 2 * $scans} {error "wrong scan count: $args"}
    foreach {width word} $args {
        if {$width != 11} {error "wrong scan width: $width"}
        set expected_word 1
        if {$i < $m} {
            set expected_word [expr {0x201 | ([lindex $::expected $i] << 1)}]
        }
        if {$word != $expected_word} {
            error "TX mismatch at byte $i: $word != $expected_word"
        }
        # Exercise bare, lowercase-prefixed and uppercase-prefixed words,
        # including OpenOCD's newline-separated output and empty fields.
        switch [expr {$i % 3}] {
            0 {lappend result [format %03x $expected_word]}
            1 {lappend result [format 0x%03x $expected_word]}
            2 {lappend result [format 0X%03X $expected_word]}
        }
        incr i
    }
    return " [join $result "\n"] "
}

proc check {values {minimum 0}} {
    set ::expected $values
    set ::minimum $minimum
    set payload [bytes $values]
    lassign [jtagstream_poll test.tap $payload $minimum] rx readable writable
    if {$rx ne $payload} {error "RX data mismatch for $values"}
    if {[string bytelength $rx] != [llength $values]} {error "RX length mismatch"}
    if {$writable != 1} {error "wrong writable flag"}
    set expected_readable [expr {[llength $values] > 0 && [llength $values] >= $minimum ? 512 : 0}]
    if {$readable != $expected_readable} {error "wrong readable flag"}
}

# Every single byte and every byte pair, including valid/invalid UTF-8.
for {set a 0} {$a < 256} {incr a} {
    check [list $a]
    for {set b 0} {$b < 256} {incr b} {
        check [list $a $b]
    }
}
check {} 4
check {0 13 10 127 128 255} 16
check {222 173 190 239}
check {1 1 60 0 0 1 222 173 190 239} 16
check {226 130 172 240 159 146 169}
# A UTF-8 sequence split across separate socket reads must remain bytes.
check {194}
check {169}

# The RX drain limit is a byte budget, not a Unicode character budget.
set mode drain
set calls 0
set rx [jtagstream_drain test.tap "" 4 8]
if {$calls != 2 || [string bytelength $rx] != 8} {error "wrong drain byte budget"}

# A NUL response must also reach the socket writer.
set mode echo
set expected {0}
set minimum 128
set written missing
proc client {operation args} {
    switch $operation {
        eof {return 0}
        read {return [bytes $::expected]}
        puts {
            if {[lindex $args 0] ne "-nonewline"} {error "unexpected socket write"}
            set ::written [lindex $args 1]
        }
        default {error "unexpected client operation: $operation"}
    }
}
jtagstream_rxtx test.tap client 0
if {$written ne [bytes {0}]} {error "lost NUL socket response"}
puts "PASS: stream byte encoding, RX drain budget and socket output"
''')
    if engine == "openocd":
        command = [executable, "-f", str(script), "-c", "shutdown"]
    else:
        command = [executable, str(script)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "PASS: stream byte encoding" in output
