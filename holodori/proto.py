"""minimal protobuf wire codec (no generated stubs).
Vendored from https://github.com/HolodoriDB/holodori-profile-export (AGPL-3.0, see LICENSE)."""

from __future__ import annotations


def _uvarint(buf: bytes | bytearray, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        x = buf[i]
        i += 1
        result |= (x & 0x7F) << shift
        if not x & 0x80:
            return result, i
        shift += 7


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def string_field(field: int, value: str | bytes) -> bytes:
    b = value.encode() if isinstance(value, str) else value
    return _tag(field, 2) + _varint(len(b)) + b


def varint_field(field: int, value: int) -> bytes:
    return _tag(field, 0) + _varint(value)


def message(*parts: bytes) -> bytes:
    return b"".join(parts)


def decode(buf: bytes | bytearray) -> dict[int, list]:
    out: dict[int, list] = {}
    i, n = 0, len(buf)
    while i < n:
        tag, i = _uvarint(buf, i)
        field, wt = tag >> 3, tag & 7
        if wt == 2:
            ln, i = _uvarint(buf, i)
            v = buf[i : i + ln]
            i += ln
        elif wt == 0:
            v, i = _uvarint(buf, i)
        elif wt == 1:
            v, i = buf[i : i + 8], i + 8
        elif wt == 5:
            v, i = buf[i : i + 4], i + 4
        else:
            break
        out.setdefault(field, []).append(v)
    return out


def get(d: dict[int, list], field: int, default=None):
    v = d.get(field)
    return v[-1] if v else default


def get_str(d: dict[int, list], field: int, default: str = "") -> str:
    v = get(d, field)
    return (
        v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else default
    )


def get_int(d: dict[int, list], field: int, default: int = 0) -> int:
    v = get(d, field)
    return v if isinstance(v, int) else default


def get_list(d: dict[int, list], field: int) -> list:
    return d.get(field, [])
