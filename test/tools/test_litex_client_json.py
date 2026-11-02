#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import io
import json
import unittest
import contextlib
from unittest import mock

from litex.tools import litex_client
from litex.tools.remote.csr_builder import CSRElements, CSRRegister

# Fake Remote Client -------------------------------------------------------------------------------

class FakeClient:
    """RemoteClient stand-in: an identifier and one CSR in a word-addressed memory."""
    kwargs = {}
    def __init__(self, **kwargs):
        FakeClient.kwargs = kwargs
        self.mem = {0xf0000004: 0x12345678}
        for i, c in enumerate("SoC\0"):
            self.mem[0xf0001000 + 4*i] = ord(c)
        self.bases = CSRElements({"identifier_mem": 0xf0001000})
        self.regs  = CSRElements({"ctrl_scratch": CSRRegister(self.read, self.write, "ctrl_scratch", 0xf0000004, 1, 32, "rw")})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, addr, length=None, burst="incr"):
        datas = [self.mem.get(addr + 4*i, 0) for i in range(1 if length is None else length)]
        return datas[0] if length is None else datas

    def write(self, addr, datas, burst="incr"):
        for i, data in enumerate(datas if isinstance(datas, list) else [datas]):
            self.mem[addr + 4*i] = data

def _run(*args):
    out = io.StringIO()
    with mock.patch("sys.argv", ["litex_cli"] + list(args)), \
         mock.patch("litex.tools.litex_client.RemoteClient", FakeClient), \
         contextlib.redirect_stdout(out):
        try:
            litex_client.main()
            code = 0
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()

# Test LiteX Client JSON ---------------------------------------------------------------------------

class TestLiteXClientJSON(unittest.TestCase):
    def test_json(self):
        code, out = _run("--json", "--ident", "--regs", "--read", "0xf0000004", "--length", "8")
        r = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(r["schema"], 1)
        self.assertEqual(r["ident"], "SoC")
        self.assertEqual(r["registers"], [{"name": "ctrl_scratch", "address": 0xf0000004, "value": 0x12345678}])
        self.assertEqual([w["value"] for w in r["read"]], [0x12345678, 0])
        # JSON mode raises on timeouts instead of returning 0 values.
        self.assertTrue(FakeClient.kwargs["raise_on_timeout"])

    def test_json_error(self):
        with mock.patch.object(FakeClient, "read", side_effect=TimeoutError("Timeout occurred during read.")):
            code, out = _run("--json", "--ident")
        self.assertEqual(code, 1)
        self.assertIn("TimeoutError", json.loads(out)["error"])

    def test_text_unchanged(self):
        code, out = _run("--regs")
        self.assertEqual(out, "0xf0000004 : 0x12345678 ctrl_scratch\n")
        self.assertFalse(FakeClient.kwargs["raise_on_timeout"])

if __name__ == "__main__":
    unittest.main()
