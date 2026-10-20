"""Canonical identities and bounded, descriptor-relative filesystem operations."""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import secrets

MAX_RUN = 100 * 1024 * 1024
MAX_WAV = 50 * 1024 * 1024
MAX_EVENTS_BYTES = 16 * 1024 * 1024
MAX_EVENT = 16 * 1024
MAX_EVENTS = 10000
MAX_ARTIFACTS = 100
MAX_SELECTION = 128
MAX_JSON = 4 * 1024 * 1024
MAX_EXTENSIONS = 64 * 1024

class Invalid(ValueError):
    """Invalid or contradictory evidence; safe to display only the fixed message."""

class Incomplete(ValueError):
    """Missing evidence; never a passing result."""

def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise Invalid("noncanonical JSON") from exc

def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9_-]{1,128}", value, flags=re.ASCII):
        raise Invalid("invalid identifier")
    return value

def relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
        or ":" in value or value.startswith("/") or any(x in ("", ".", "..") for x in value.split("/"))):
        raise Invalid("unsafe relative path")
    return PurePosixPath(value).parts

@contextlib.contextmanager
def root_descriptor(root):
    # Open every absolute component with O_NOFOLLOW. Do not resolve away links.
    if os.name != "posix": raise Invalid("safe filesystem operations require macOS or Linux/POSIX")
    path = Path(os.path.abspath(root))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
    except OSError as exc:
        os.close(fd)
        raise Invalid("unsafe or inaccessible input root") from exc
    try:
        yield fd
    finally:
        os.close(fd)

def read_bytes(root, name, limit=MAX_JSON):
    parts = relative(name)
    try:
        with root_descriptor(root) as base:
            fd = os.dup(base)
            try:
                for part in parts[:-1]:
                    nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = nxt
                handle = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                with os.fdopen(handle, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                        raise Invalid("artifact is special or exceeds size limit")
                    data = stream.read(limit + 1)
                    after = os.fstat(stream.fileno())
                    if len(data) > limit or (info.st_size, info.st_mtime_ns, info.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                        raise Invalid("artifact changed while reading")
                    return data
            finally:
                os.close(fd)
    except FileNotFoundError as exc:
        raise Incomplete("required local file is missing") from exc
    except OSError as exc:
        raise Invalid("unsafe or inaccessible artifact") from exc

def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite JSON number")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Invalid("invalid JSON") from exc

def read_json(root, name):
    return parse(read_bytes(root, name))

def write_bytes(root, name, data):
    parts = relative(name)
    with root_descriptor(root) as base:
        fd = os.dup(base)
        try:
            for part in parts[:-1]:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            handle = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(fd)

def write_json(root, name, value):
    write_bytes(root, name, canonical(value) + b"\n")

@contextlib.contextmanager
def atomic_output(destination):
    target = Path(os.path.abspath(destination))
    with root_descriptor(target.parent) as parent_fd:
        try:
            os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise Invalid("output exists; refusing overwrite")
        staging_name = ".incomplete-smb-" + secrets.token_hex(12)
        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging = target.parent / staging_name
        try:
            yield staging
            # Reserve and complete relative to the same verified parent descriptor.
            os.mkdir(target.name, 0o700, dir_fd=parent_fd)
            try:
                os.rename(staging_name, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except BaseException:
                os.rmdir(target.name, dir_fd=parent_fd)
                raise
        except BaseException:
            # Keep interrupted evidence, explicitly named incomplete.
            raise
