#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import atexit
import datetime
import logging
import os
import re
import sys
import threading


_active_build_log = None
_build_log_buffer = None
_pending_build_log = None

_ansi_escape_re            = re.compile(rb"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_ansi_escape_text_re       = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_incomplete_ansi_escape_re = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*)?$")


def _flush_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass


def _logging_uses_stdio():
    for handler in logging.root.handlers:
        stream = getattr(handler, "stream", None)
        if stream is None:
            continue
        try:
            if stream.fileno() in (1, 2):
                return True
        except (AttributeError, OSError, ValueError):
            pass
    return False


def _strip_ansi_text(s):
    return _ansi_escape_text_re.sub("", s)


def _strip_ansi_bytes(data):
    return _ansi_escape_re.sub(b"", data)


class _ANSIPlainTextFilter:
    def __init__(self):
        self._pending = b""

    def feed(self, data):
        data = self._pending + data
        self._pending = b""

        incomplete = _incomplete_ansi_escape_re.search(data)
        if incomplete is not None:
            self._pending = data[incomplete.start():]
            data = data[:incomplete.start()]

        return _strip_ansi_bytes(data)

    def flush(self):
        data, self._pending = self._pending, b""
        return _strip_ansi_bytes(data)


class _PlainTextFormatter(logging.Formatter):
    def format(self, record):
        return _strip_ansi_text(logging.Formatter.format(self, record))


class _PlainTextFileHandler(logging.FileHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            self.stream.write(_strip_ansi_text(msg + self.terminator))
            self.flush()
        except Exception:
            self.handleError(record)


class _BuildLogBuffer(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []
        self.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))

    def emit(self, record):
        self.records.append(_strip_ansi_text(self.format(record) + "\n").encode("utf-8", errors="replace"))


class _BuildLogTextTee:
    def __init__(self, stream, log_fd, lock):
        self.stream  = stream
        self._log_fd = log_fd
        self._lock   = lock

    def write(self, s):
        ret = self.stream.write(s)
        if s:
            data = _strip_ansi_text(s).encode("utf-8", errors="replace")
            if data:
                with self._lock:
                    os.write(self._log_fd, data)
        return ret

    def flush(self):
        return self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _stream_uses_fd(stream, fd):
    try:
        return stream.fileno() == fd
    except (AttributeError, OSError, ValueError):
        return False


class BuildLogTee:
    def __init__(self, filename):
        self.filename = os.path.abspath(filename)
        self._log_fd  = None
        self._lock    = threading.Lock()
        self._fds     = []
        self._threads = []
        self._stdout  = None
        self._stderr  = None
        self._logging_handler = None
        self._closed = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        _flush_stdio()

        self._log_fd = os.open(self.filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND, 0o644)
        self._write_header()
        flush_build_log_buffer(self._log_fd)

        for fd in (1, 2):
            saved_fd = os.dup(fd)
            read_fd, write_fd = os.pipe()
            os.dup2(write_fd, fd)
            os.close(write_fd)
            thread = threading.Thread(target=self._tee_fd, args=(read_fd, saved_fd), daemon=True)
            thread.start()
            self._fds.append((fd, saved_fd))
            self._threads.append(thread)

        if not _stream_uses_fd(sys.stdout, 1):
            self._stdout = sys.stdout
            sys.stdout = _BuildLogTextTee(sys.stdout, self._log_fd, self._lock)
        if not _stream_uses_fd(sys.stderr, 2):
            self._stderr = sys.stderr
            sys.stderr = _BuildLogTextTee(sys.stderr, self._log_fd, self._lock)

        if logging.root.handlers and not _logging_uses_stdio():
            self._logging_handler = _PlainTextFileHandler(self.filename)
            self._logging_handler.setFormatter(_PlainTextFormatter("%(levelname)s:%(name)s:%(message)s"))
            logging.root.addHandler(self._logging_handler)

        return self

    def __exit__(self, *args):
        self.close()

    def _write_header(self):
        header = [
            "# LiteX build log",
            "# Started: {}".format(datetime.datetime.now().isoformat(timespec="seconds")),
            "# Command: {}".format(" ".join(sys.argv)),
            "# Working directory: {}".format(os.getcwd()),
            "",
        ]
        os.write(self._log_fd, ("\n".join(header) + "\n").encode("utf-8", errors="replace"))

    def _tee_fd(self, read_fd, saved_fd):
        log_filter = _ANSIPlainTextFilter()
        try:
            while True:
                data = os.read(read_fd, 8192)
                if not data:
                    break
                os.write(saved_fd, data)
                with self._lock:
                    data = log_filter.feed(data)
                    if data:
                        os.write(self._log_fd, data)
            with self._lock:
                data = log_filter.flush()
                if data:
                    os.write(self._log_fd, data)
        finally:
            os.close(read_fd)

    def close(self):
        if self._closed:
            return
        self._closed = True

        _flush_stdio()
        for handler in logging.root.handlers:
            try:
                handler.flush()
            except Exception:
                pass

        if self._logging_handler is not None:
            logging.root.removeHandler(self._logging_handler)
            self._logging_handler.close()
            self._logging_handler = None

        if self._stdout is not None:
            sys.stdout = self._stdout
            self._stdout = None
        if self._stderr is not None:
            sys.stderr = self._stderr
            self._stderr = None

        for fd, saved_fd in self._fds:
            os.dup2(saved_fd, fd)
        for thread in self._threads:
            thread.join(timeout=5)
            if thread.is_alive():
                print("Warning: Build log tee thread still alive (pipe still in use by a child process?), log may be incomplete.", file=sys.stderr)
        for _, saved_fd in self._fds:
            os.close(saved_fd)
        self._fds = []
        self._threads = []

        if self._log_fd is not None:
            os.close(self._log_fd)
            self._log_fd = None


class _NullBuildLog:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def start_build_log(filename):
    global _active_build_log

    if filename is None:
        return _NullBuildLog()

    filename = os.path.abspath(filename)
    if _active_build_log is not None:
        return _NullBuildLog()

    _active_build_log = BuildLogTee(filename)
    _active_build_log.__enter__()
    atexit.register(stop_build_log)
    return _active_build_log


def configure_build_log(build_log=True, output_dir=None):
    global _pending_build_log

    if not build_log:
        _pending_build_log = None
        discard_build_log_buffer()
        return

    if isinstance(build_log, str):
        start_build_log(build_log)
        _pending_build_log = None
        return

    if output_dir is not None:
        start_build_log(os.path.join(os.path.abspath(output_dir), "litex.log"))
        _pending_build_log = None
        return

    _pending_build_log = True


def start_pending_build_log(platform_name):
    global _pending_build_log

    if _pending_build_log is None:
        return
    start_build_log(os.path.join("build", platform_name, "litex.log"))
    _pending_build_log = None


def stop_build_log():
    global _active_build_log

    if _active_build_log is None:
        return
    build_log = _active_build_log
    _active_build_log = None
    build_log.close()


def build_log_context(filename):
    if filename is None:
        discard_build_log_buffer()
        return _NullBuildLog()

    filename = os.path.abspath(filename)
    if _active_build_log is not None:
        return _NullBuildLog()
    return BuildLogTee(filename)


def is_build_log_active(filename=None):
    if _active_build_log is None:
        return False
    if filename is None:
        return True
    return _active_build_log.filename == os.path.abspath(filename)


def buffer_build_log():
    global _build_log_buffer

    if _active_build_log is not None:
        return
    if _build_log_buffer is not None:
        return

    _build_log_buffer = _BuildLogBuffer()
    logging.root.addHandler(_build_log_buffer)


def flush_build_log_buffer(log_fd):
    global _build_log_buffer

    if _build_log_buffer is None:
        return

    logging.root.removeHandler(_build_log_buffer)
    for record in _build_log_buffer.records:
        os.write(log_fd, record)
    _build_log_buffer = None


def discard_build_log_buffer():
    global _build_log_buffer

    if _build_log_buffer is None:
        return
    logging.root.removeHandler(_build_log_buffer)
    _build_log_buffer = None
