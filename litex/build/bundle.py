#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import sys
import json
import hashlib
import tarfile
import datetime
import subprocess
import importlib.util


# LiteX Build Bundle ------------------------------------------------------------------------------

_EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _abspath(path, cwd=None):
    if path is None:
        return None
    if cwd is None:
        cwd = os.getcwd()
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.abspath(path)


def _is_subpath(path, root):
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _sanitize(name):
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name.strip("._") or "root"


def _file_digest(path):
    h = hashlib.sha256()
    if os.path.islink(path):
        h.update(b"symlink:")
        h.update(os.readlink(path).encode("utf-8"))
        return h.hexdigest()
    with open(path, "rb") as f:
        while True:
            data = f.read(1024 * 1024)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _git_info(path):
    cwd = path if os.path.isdir(path) else os.path.dirname(path)
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except (OSError, subprocess.CalledProcessError):
        return None

    info = {"root": root}
    for key, command in [
        ("revision", ["git", "rev-parse", "HEAD"]),
        ("short_revision", ["git", "rev-parse", "--short", "HEAD"]),
    ]:
        try:
            info[key] = subprocess.check_output(
                command,
                cwd=root,
                stderr=subprocess.DEVNULL,
            ).decode("utf-8").strip()
        except (OSError, subprocess.CalledProcessError):
            pass

    try:
        status = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=root,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").splitlines()
        info["dirty"] = bool(status)
        info["status"] = status
    except (OSError, subprocess.CalledProcessError):
        pass

    return info


def _module_pythonpath_root(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return None

    if spec.submodule_search_locations:
        locations = list(spec.submodule_search_locations)
        if locations:
            return os.path.dirname(os.path.abspath(locations[0]))

    if spec.origin:
        return os.path.dirname(os.path.dirname(os.path.abspath(spec.origin)))

    return None


def get_pythonpath_roots(module_names=("litex", "litex_boards")):
    roots = []
    for module_name in module_names:
        root = _module_pythonpath_root(module_name)
        if root is not None and root not in roots:
            roots.append(root)
    return roots


_PATH_MAP_ENV        = "LITEX_BUILD_BUNDLE_PATH_MAP"
_path_map_cache_raw  = None
_path_map_cache      = []


def get_path_map():
    global _path_map_cache_raw
    global _path_map_cache

    raw = os.getenv(_PATH_MAP_ENV)
    if raw == _path_map_cache_raw:
        return _path_map_cache

    _path_map_cache_raw = raw
    if not raw:
        _path_map_cache = []
        return _path_map_cache

    try:
        path_map = json.loads(raw)
    except json.JSONDecodeError:
        path_map = []

    _path_map_cache = path_map if isinstance(path_map, list) else []
    return _path_map_cache


def remap_path(path):
    if path is None or not os.path.isabs(path):
        return path

    path = os.path.abspath(path)
    for entry in get_path_map():
        if not isinstance(entry, dict):
            continue
        source = entry.get("path")
        target = entry.get("mapped")
        if source is None or target is None:
            continue

        if entry.get("kind") == "root" and _is_subpath(path, source):
            rel = os.path.relpath(path, source)
            return os.path.join(target, rel)
        if path == source:
            return target

    return path


class BuildBundle:
    def __init__(self,
        output_dir,
        archive_path  = None,
        command       = None,
        env           = None,
        strict        = "warn",
        exclude_dirs  = None):

        if strict not in ["warn", "error"]:
            raise ValueError(f"Unsupported bundle strict mode: {strict}.")

        self.output_dir    = _abspath(output_dir)
        self.archive_path  = _abspath(archive_path) if archive_path else None
        self.command       = list(command or sys.argv)
        self.env           = dict(env or {})
        self.strict        = strict
        self.exclude_dirs  = [_abspath(p) for p in _as_list(exclude_dirs)]
        self.exclude_dirs.append(self.output_dir)

        self._records         = {}
        self._missing         = []
        self._roots           = []
        self._root_paths      = {}
        self._input_dirs      = []
        self._input_dir_paths = {}
        self._pythonpath      = []
        self._warnings        = []
        self._git_probes      = []

    def _is_excluded(self, path):
        for exclude_dir in self.exclude_dirs:
            if _is_subpath(path, exclude_dir):
                return True
        return False

    def add_root(self, path, role="root"):
        path = _abspath(path)
        if path is None:
            return
        if not os.path.exists(path):
            self._missing.append({"path": path, "role": role})
            return
        self._git_probes.append(path)
        if not os.path.isdir(path):
            self.add_path(path, role=role)
            return

        if path in self._root_paths:
            root = self._root_paths[path]
            root["roles"].append(role)
            root["roles"] = sorted(set(root["roles"]))
            return root

        root_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()[:8]
        root_name = _sanitize(os.path.basename(path) or "root")
        arc_root  = f"roots/{root_name}-{root_hash}"
        root = {
            "path"        : path,
            "archive_path": arc_root,
            "role"        : role,
            "roles"       : [role],
        }
        self._roots.append(root)
        self._root_paths[path] = root
        self._add_dir(path, role=role, archive_prefix=arc_root, base_dir=path, honor_exclude=True)
        return root

    def add_pythonpath(self, path, role="pythonpath"):
        root = self.add_root(path, role=role)
        if root is None:
            return
        if root not in self._pythonpath:
            self._pythonpath.append(root)

    def add_path(self, path, role="input"):
        path = _abspath(path)
        if path is None:
            return
        if not os.path.lexists(path):
            self._missing.append({"path": path, "role": role})
            return
        self._git_probes.append(path)
        if os.path.isdir(path) and not os.path.islink(path):
            path_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()[:8]
            path_name = _sanitize(os.path.basename(path) or "input")
            archive_prefix = f"inputs/{path_name}-{path_hash}"
            if path in self._input_dir_paths:
                input_dir = self._input_dir_paths[path]
                input_dir["roles"].append(role)
                input_dir["roles"] = sorted(set(input_dir["roles"]))
            else:
                input_dir = {
                    "path"        : path,
                    "archive_path": archive_prefix,
                    "role"        : role,
                    "roles"       : [role],
                }
                self._input_dirs.append(input_dir)
                self._input_dir_paths[path] = input_dir
            self._add_dir(
                path           = path,
                role           = role,
                archive_prefix = archive_prefix,
                base_dir       = path,
                honor_exclude  = False,
            )
        else:
            self._add_file(path, role=role)

    def add_paths(self, paths, role="input"):
        for path in _as_list(paths):
            self.add_path(path, role=role)

    def _add_dir(self, path, role, archive_prefix, base_dir, honor_exclude):
        if honor_exclude and self._is_excluded(path):
            return
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(
                d for d in dirs
                if d not in _EXCLUDED_DIR_NAMES and not (honor_exclude and self._is_excluded(os.path.join(root, d)))
            )
            for filename in sorted(files):
                full_path = os.path.join(root, filename)
                if honor_exclude and self._is_excluded(full_path):
                    continue
                rel_path = os.path.relpath(full_path, base_dir).replace(os.sep, "/")
                self._add_file(full_path, role=role, archive_path=f"{archive_prefix}/{rel_path}", honor_exclude=honor_exclude)

    def _add_file(self, path, role, archive_path=None, honor_exclude=False):
        if honor_exclude and self._is_excluded(path):
            return
        key = os.path.abspath(path)
        if key in self._records:
            self._records[key]["roles"].append(role)
            self._records[key]["roles"] = sorted(set(self._records[key]["roles"]))
            return

        if archive_path is None:
            path_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
            archive_path = f"files/{path_hash}/{os.path.basename(key)}"

        st = os.lstat(key)
        record = {
            "path"        : key,
            "archive_path": archive_path,
            "roles"       : [role],
            "sha256"      : _file_digest(key),
            "size"        : st.st_size,
            "mtime_ns"    : st.st_mtime_ns,
            "mode"        : st.st_mode,
            "kind"        : "symlink" if os.path.islink(key) else "file",
        }
        if os.path.islink(key):
            record["link_target"] = os.readlink(key)
        self._records[key] = record

    def _input_digest(self):
        h = hashlib.sha256()
        for record in sorted(self._records.values(), key=lambda r: r["archive_path"]):
            h.update(record["archive_path"].encode("utf-8"))
            h.update(b"\0")
            h.update(record["sha256"].encode("utf-8"))
            h.update(b"\0")
        return h.hexdigest()

    def _handle_missing(self):
        if not self._missing:
            return
        msg = "Missing build bundle input(s):\n"
        msg += "\n".join(f"- {m['path']} ({m['role']})" for m in self._missing)
        if self.strict == "error":
            raise OSError(msg)
        self._warnings.append(msg)
        print(msg)

    def _manifest(self, archive_path, input_digest):
        git_roots = {}
        for path in self._git_probes:
            info = _git_info(path)
            if info is not None and info["root"] not in git_roots:
                git_roots[info["root"]] = info

        return {
            "format"       : "litex-build-bundle-v1",
            "created_at"   : datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "input_digest" : input_digest,
            "archive"      : os.path.abspath(archive_path),
            "cwd"          : os.getcwd(),
            "output_dir"   : self.output_dir,
            "command"      : self.command,
            "python"       : {
                "executable": sys.executable,
                "version"   : sys.version,
                "platform"  : sys.platform,
            },
            "env"        : self.env,
            "roots"      : sorted(self._roots,      key=lambda r: r["archive_path"]),
            "input_dirs" : sorted(self._input_dirs, key=lambda r: r["archive_path"]),
            "pythonpath" : sorted(self._pythonpath, key=lambda r: r["archive_path"]),
            "files"      : sorted(self._records.values(), key=lambda r: r["archive_path"]),
            "missing"    : self._missing,
            "warnings"   : self._warnings,
            "git"        : sorted(git_roots.values(), key=lambda r: r["root"]),
        }

    def create(self):
        self._handle_missing()

        input_digest = self._input_digest()
        if self.archive_path is None:
            archive_dir       = os.path.join(self.output_dir, "bundles")
            archive_basename  = f"litex-build-input-{input_digest[:12]}.tar.gz"
            self.archive_path = os.path.join(archive_dir, archive_basename)

        os.makedirs(os.path.dirname(self.archive_path), exist_ok=True)
        manifest = self._manifest(self.archive_path, input_digest)
        manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

        with tarfile.open(self.archive_path, "w:gz", dereference=False) as archive:
            info = tarfile.TarInfo("manifest.json")
            info.size  = len(manifest_bytes)
            info.mtime = int(datetime.datetime.utcnow().timestamp())
            archive.addfile(info, fileobj=_BytesReader(manifest_bytes))
            for record in manifest["files"]:
                archive.add(record["path"], arcname=record["archive_path"], recursive=False)

        manifest_path = self.archive_path + ".manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            f.write("\n")

        return {
            "archive" : self.archive_path,
            "manifest": manifest_path,
            "digest"  : input_digest,
        }


class _BytesReader:
    def __init__(self, data):
        self.data = data
        self.pos  = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self.data) - self.pos
        data = self.data[self.pos:self.pos + size]
        self.pos += len(data)
        return data
