"""Vendored from https://github.com/HolodoriDB/holodori-profile-export (AGPL-3.0, see LICENSE).
Modified: `write` replaced by `dumps` (in-memory bytes)."""

from __future__ import annotations

import gzip
import json

from . import proto, schema

_FIELDS: dict[str, list[tuple[str, type]]] = {
    "User": [("public_user_id", str)],
    "UserProfile": [("name", str), ("exp", int)],
    "UserCard": [
        ("card_id", str),
        ("exp", int),
        ("level_limit_break_count", int),
        ("potential_upgrade_count", int),
    ],
    "UserMusic": [("music_id", str)],
    "UserCharacter": [("character_id", str), ("exp", int)],
    "UserCharacterSkillTree": [
        ("character_id", str),
        ("released_skill_tree_node_group_ids", list),
        ("connected_skill_tree_node_group_ids", list),
        ("connected_skill_tree_node_card_ids", list),
    ],
    "UserPoster": [("poster_id", str)],
    "UserParkQuest": [("park_quest_id", str), ("clear_time", int)],
    "UserParkTreasure": [("park_treasure_ids", list)],
    "UserParkTalkFreePickResultDetail": [
        ("park_talk_free_id", str),
        ("already_read_character_ids", list),
    ],
}

_USER_DATA: dict[str, tuple[str, bool]] = {
    "user": ("User", False),
    "user_profile": ("UserProfile", False),
    "user_card_list": ("UserCard", True),
    "user_music_list": ("UserMusic", True),
    "user_character_list": ("UserCharacter", True),
    "user_character_skill_tree_list": ("UserCharacterSkillTree", True),
    "user_poster_list": ("UserPoster", True),
    "user_park_quest_list": ("UserParkQuest", True),
    "user_park_treasure": ("UserParkTreasure", False),
    "user_park_talk_free_pick_result_detail_list": (
        "UserParkTalkFreePickResultDetail",
        True,
    ),
}


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.title() for w in rest)


def _message(raw: dict[int, list], message: str) -> dict:
    out: dict = {}
    for name, kind in _FIELDS[message]:
        num = schema.field(message, name)
        if kind is list:
            out[_camel(name)] = [
                v.decode("utf-8", "replace")
                for v in proto.get_list(raw, num)
                if isinstance(v, (bytes, bytearray))
            ]
        elif kind is int:
            out[_camel(name)] = proto.get_int(raw, num)
        else:
            out[_camel(name)] = proto.get_str(raw, num)
    return out


def build(ud: dict[int, list]) -> dict:
    game: dict = {}
    for field, (message, repeated) in _USER_DATA.items():
        num = schema.field("UserData", field)
        if repeated:
            game[_camel(field)] = [
                _message(proto.decode(r), message) for r in proto.get_list(ud, num)
            ]
        else:
            raw = proto.get(ud, num)
            game[_camel(field)] = _message(
                proto.decode(raw) if isinstance(raw, (bytes, bytearray)) else {},
                message,
            )
    # the detail list is the whole current rotation; only talks someone has read are progress
    detail = _camel("user_park_talk_free_pick_result_detail_list")
    game[detail] = [d for d in game[detail] if d["alreadyReadCharacterIds"]]

    payload: dict = {"kind": "profile"}
    if game["userProfile"]["name"]:
        payload["name"] = game["userProfile"]["name"]
    payload["userData"] = game
    return {"kind": "profile", "payload": payload, "version": ""}


def summary(obj: dict) -> dict:
    ud = obj["payload"]["userData"]
    return {
        "userName": ud["userProfile"]["name"],
        "publicUserId": ud["user"]["publicUserId"],
        "cards": len(ud["userCardList"]),
        "songs": len(ud["userMusicList"]),
        "holomems": len(ud["userCharacterList"]),
    }


def dumps(obj: dict) -> bytes:
    return gzip.compress(
        json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
