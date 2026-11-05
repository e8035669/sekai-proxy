"""Vendored from https://github.com/HolodoriDB/holodori-profile-export (AGPL-3.0, see LICENSE).
Modified: uses `requests` instead of curl_cffi and a fixed error message."""

from __future__ import annotations

import re
import tempfile
from functools import lru_cache
from pathlib import Path

import requests

PROTO_URL = (
    "https://raw.githubusercontent.com/HolodoriDB/holodori-app-protos/"
    "refs/heads/main/global/protobufs/merged_flat.proto"
)
_CACHE = Path(tempfile.gettempdir()) / "holodori-profile-export" / "merged_flat.proto"

_OPEN = re.compile(r"\s*(message|enum|oneof|extend|service|rpc)\b\s*([.\w]*)")
_FIELD = re.compile(r"\s*(?:optional|required|repeated)\s+[.\w]+\s+(\w+)\s*=\s*(\d+)")


def _fetch() -> str:
    r = requests.get(PROTO_URL, timeout=60)
    if r.status_code != 200 or "message UserData" not in r.text:
        raise RuntimeError(f"bad proto response (http={r.status_code})")
    body = r.text
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(body, encoding="utf-8")
    except OSError:
        pass
    return body


def _load() -> str:
    try:
        return _fetch()
    except Exception as e:
        if _CACHE.is_file():
            return _CACHE.read_text(encoding="utf-8")
        raise RuntimeError(f"couldn't download the proto schema: {e}") from e


@lru_cache(maxsize=1)
def _messages() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    stack: list[tuple[str, str]] = []
    for raw in _load().splitlines():
        line = raw.rstrip()
        if line.endswith("{"):
            m = _OPEN.match(line)
            kind, name = (m.group(1), m.group(2)) if m else ("other", "")
            if kind == "message" and name:
                out.setdefault(name, {})
            stack.append((kind, name))
        elif line.strip() == "}":
            if stack:
                stack.pop()
        else:
            fm = _FIELD.match(line)
            if not fm:
                continue
            for kind, name in reversed(
                stack
            ):  # a field belongs to its message, not an extend
                if kind == "extend":
                    break
                if kind == "message":
                    out[name][fm.group(1)] = int(fm.group(2))
                    break
    return out


def field(message: str, name: str) -> int:
    fields = _messages().get(message)
    if fields is None or name not in fields:
        raise RuntimeError(
            f"the game's proto schema has no {message}.{name}; this tool is out of date."
        )
    return fields[name]
