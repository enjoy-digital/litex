#
# This file is part of LiteX.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import json
import os
from pathlib import Path
import socket
import time

import pytest
import serial

from litex.tools.litex_term import JTAGUART


@pytest.fixture
def backend(tmp_path, monkeypatch):
    executable = tmp_path / "openocd"
    executable.write_text('''#!/usr/bin/env python3
import json, os, re, signal, socket, sys, time
from pathlib import Path
mode = os.environ.get("FAKE_JTAG_MODE", "echo")
cfg = sys.argv[sys.argv.index("-c") - 1]
Path(os.environ["FAKE_JTAG_STATE"]).write_text(json.dumps({"pid": os.getpid(), "cfg": cfg}))
assert "jtag arp_init" in sys.argv[-1]
if mode == "failure":
    sys.exit(3)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode == "timeout":
    while True:
        time.sleep(1)
port = int(re.search(r"jtagstream_serve \\S+ (\\d+)", sys.argv[-1])[1])
with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen()
    while True:
        connection, _ = listener.accept()
        with connection:
            while True:
                data = connection.recv(4096)
                if not data:
                    break
                connection.sendall(data)
''')
    executable.chmod(0o755)
    config = tmp_path / "target.cfg"
    config.write_text("# xc7 test fixture\n")
    state = tmp_path / "state.json"
    monkeypatch.setenv("OPENOCD", str(executable))
    monkeypatch.setenv("FAKE_JTAG_STATE", str(state))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    return JTAGUART(str(config), port=port), state


def assert_reaped(state):
    record = json.loads(state.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(record["pid"], 0)
    assert not Path(record["cfg"]).exists()


def test_repeated_open_close_reaps_openocd_and_closes_both_pty_ends(backend):
    uart, state = backend
    descriptors = len(list(Path("/proc/self/fd").iterdir()))
    for _ in range(3):
        try:
            uart.open()
            with serial.Serial(os.ttyname(uart.name), timeout=2) as port:
                payload = bytes(range(256))
                port.write(payload)
                assert port.read(len(payload)) == payload
        finally:
            workers = list(uart.threads)
            uart.close()
        assert all(not worker.is_alive() for worker in workers)
        uart.close()
        assert_reaped(state)
        assert len(list(Path("/proc/self/fd").iterdir())) == descriptors


@pytest.mark.parametrize("mode", ["failure", "timeout"])
def test_failed_startup_cleans_up_and_can_be_retried(backend, monkeypatch, mode):
    uart, state = backend
    monkeypatch.setenv("FAKE_JTAG_MODE", mode)
    descriptors = len(list(Path("/proc/self/fd").iterdir()))
    started = time.monotonic()
    with pytest.raises(ConnectionError):
        uart.open(timeout=0.3)
    assert time.monotonic() - started < 3
    assert_reaped(state)
    assert len(list(Path("/proc/self/fd").iterdir())) == descriptors
    monkeypatch.setenv("FAKE_JTAG_MODE", "echo")
    try:
        uart.open()
        assert uart.alive
    finally:
        uart.close()
    assert_reaped(state)
