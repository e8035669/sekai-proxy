"""Capture logic adapted from holodori_profile_export/sources/mitm.py
(https://github.com/HolodoriDB/holodori-profile-export, AGPL-3.0, see LICENSE)."""

from __future__ import annotations

from dataclasses import dataclass

from . import profile, proto, schema

HOST = "game-hololive-dreams.com"
CONTENT_TYPE = "application/grpc+proto-enc"
PATH_SUFFIXES = ("User/Get", "Home/Login")


@dataclass
class Hdbest:
    public_user_id: str
    summary: dict
    data: bytes


def is_target(host: str, path: str, content_type: str) -> bool:
    return (HOST in host and content_type.startswith(CONTENT_TYPE)
            and path.endswith(PATH_SUFFIXES))


def _userdata_from(path: str, body: bytes) -> dict[int, list] | None:
    from holodori_asset_tools import api

    resp = proto.decode(api.decode_response(body))
    if path.endswith("User/Get"):
        ud = proto.get(resp, schema.field("UserGetResponse", "user_data"))
    elif path.endswith("Home/Login"):
        common = proto.get(
            resp, schema.field("HomeLoginResponse", "common_response"))
        cm = proto.decode(common) if isinstance(common,
                                                (bytes, bytearray)) else {}
        ud = proto.get(cm, schema.field("Response", "updated_data"))
    else:
        return None
    return proto.decode(ud) if isinstance(ud, (bytes, bytearray)) else None


def build_hdbest(path: str, body: bytes) -> Hdbest | None:
    """Returns None for packets without a usable (non-empty) account snapshot."""
    ud = _userdata_from(path, body)
    if not ud:
        return None
    obj = profile.build(ud)
    info = profile.summary(obj)
    if not info["cards"] and not info["songs"]:
        return None
    user_id = info["publicUserId"].strip() or "profile"
    return Hdbest(user_id, info, profile.dumps(obj))
