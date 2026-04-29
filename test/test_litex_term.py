import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from litex.tools import litex_term
from litex.tools.litex_term import (
    LiteXTerm,
    SFLFrame,
    SFLUploadError,
    crc16,
    sfl_ack_crcerror,
    sfl_ack_error,
    sfl_ack_success,
    sfl_cmd_abort,
    sfl_cmd_load,
    sfl_magic_ack,
)


class FakePort:
    def __init__(self, read_data=b"", write_replies=None, baudrate=115200):
        self._read_data = bytearray(read_data)
        self._write_replies = list(write_replies or [])
        self.written = bytearray()
        self.timeout = None
        self.baudrate = baudrate

    @property
    def in_waiting(self):
        return len(self._read_data)

    def read(self, size=1):
        if not self._read_data:
            return b""
        data = self._read_data[:size]
        del self._read_data[:size]
        return bytes(data)

    def write(self, data):
        self.written += data
        if self._write_replies:
            self._read_data += self._write_replies.pop(0)
        return len(data)


def make_term(port):
    term = LiteXTerm.__new__(LiteXTerm)
    term.port = port
    term.safe = True
    term.delay = 0
    term.length = 64
    term.outstanding = 1
    return term


class TestSFLFrame(unittest.TestCase):
    def test_zero_length_abort_frame(self):
        frame = SFLFrame()
        frame.cmd = sfl_cmd_abort

        encoded = frame.encode()

        self.assertEqual(encoded[0], 0)
        self.assertEqual(encoded[1:3], crc16(sfl_cmd_abort).to_bytes(2, "big"))
        self.assertEqual(encoded[3:4], sfl_cmd_abort)
        self.assertEqual(len(encoded), 4)

    def test_send_frame_retries_after_crc_error(self):
        port = FakePort(read_data=sfl_ack_crcerror + sfl_ack_success)
        term = make_term(port)
        frame = SFLFrame()
        frame.cmd = sfl_cmd_abort

        self.assertEqual(term.send_frame(frame), 1)
        self.assertEqual(port.written, frame.encode() * 2)


class TestLiteXTermSFL(unittest.TestCase):
    def test_receive_upload_response_raises_on_device_error(self):
        term = make_term(FakePort(read_data=sfl_ack_error))

        with self.assertRaisesRegex(SFLUploadError, "serial frame error"):
            term.receive_upload_response()

    def test_abort_serialboot_drains_stale_data_and_sends_abort(self):
        port = FakePort(read_data=b"E", write_replies=[sfl_ack_success])
        term = make_term(port)

        with mock.patch.object(litex_term.time, "sleep"), redirect_stdout(io.StringIO()):
            self.assertTrue(term.abort_serialboot())

        frame = SFLFrame()
        frame.cmd = sfl_cmd_abort
        self.assertEqual(port.written, frame.encode())

    def test_answer_magic_aborts_on_upload_error(self):
        port = FakePort()
        term = make_term(port)
        term.mem_regions = {"image.bin": "0x40000000"}
        term.upload = mock.Mock(side_effect=SFLUploadError("boom"))
        term.boot = mock.Mock()
        term.abort_serialboot = mock.Mock(return_value=True)

        with redirect_stdout(io.StringIO()):
            term.answer_magic()

        self.assertEqual(port.written, sfl_magic_ack)
        term.upload.assert_called_once_with("image.bin", 0x40000000)
        term.boot.assert_not_called()
        term.abort_serialboot.assert_called_once()

    def test_upload_raises_on_device_error_ack(self):
        port = FakePort(read_data=sfl_ack_error)
        term = make_term(port)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"LiteX")
            filename = f.name
        try:
            with redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(SFLUploadError, "serial frame error"):
                    term.upload(filename, 0x40000000)
        finally:
            os.unlink(filename)

        self.assertTrue(port.written)

    def test_upload_calibration_requires_all_acks(self):
        port = FakePort(read_data=sfl_ack_success * 3)
        term = make_term(port)
        term.safe = False
        term.outstanding = 128

        with mock.patch.object(litex_term.time, "sleep"), redirect_stdout(io.StringIO()):
            term.upload_calibration(0x40000000)

        self.assertEqual(term.delay, 0)
        self.assertEqual(term.length, 64)
        self.assertEqual(term.outstanding, 1)

    def test_upload_retries_crc_error_in_stop_and_wait_mode(self):
        port = FakePort(read_data=sfl_ack_crcerror + sfl_ack_success)
        term = make_term(port)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"LiteX")
            filename = f.name
        try:
            with redirect_stdout(io.StringIO()):
                term.upload(filename, 0x40000000)
        finally:
            os.unlink(filename)

        frame = SFLFrame()
        frame.cmd = sfl_cmd_load
        frame.payload = (0x40000000).to_bytes(4, "big") + b"LiteX"
        self.assertEqual(port.written, frame.encode() * 2)

    def test_upload_retries_with_smaller_window_after_optimized_error(self):
        port = FakePort(
            read_data=sfl_ack_success + sfl_ack_error,
            write_replies=[b"", b"", sfl_ack_success, sfl_ack_success],
        )
        term = make_term(port)
        term.safe = False
        term.length = 4
        term.outstanding = 2

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"LiteXSoC")
            filename = f.name
        try:
            output = io.StringIO()
            with mock.patch.object(term, "upload_calibration", return_value=True), \
                 mock.patch.object(litex_term.time, "sleep"), \
                 redirect_stdout(output):
                term.upload(filename, 0x40000000)
        finally:
            os.unlink(filename)

        self.assertIn("Retrying with length 4, window 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
