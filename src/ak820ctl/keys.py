"""AK820 LED slot names as a strict enum.

`Key` is the static, typecheckable side: 144 members, one per LED slot, name
identical to the entry in `data/keymap.json`. `KEY_INDEX` maps each `Key` to
its 0-143 slot index; it is built once at import time by reading the bundled
keymap JSON, with a drift guard that refuses to import if the JSON and the
enum disagree.
"""

from __future__ import annotations

from enum import StrEnum
from importlib import resources

from pydantic import TypeAdapter

NUM_KEYS = 144


class Key(StrEnum):
    """Symbolic name for one of the AK820's 144 LED slots.

    Members listed in slot-index order for readability — the index↔name
    mapping is sourced from `data/keymap.json` at import time, not from
    enum definition order.
    """

    idx_0 = "idx_0"
    esc = "esc"
    f1 = "f1"
    f2 = "f2"
    f3 = "f3"
    f4 = "f4"
    f5 = "f5"
    f6 = "f6"
    f7 = "f7"
    f8 = "f8"
    f9 = "f9"
    f10 = "f10"
    f11 = "f11"
    f12 = "f12"
    idx_14 = "idx_14"
    idx_15 = "idx_15"
    idx_16 = "idx_16"
    idx_17 = "idx_17"
    idx_18 = "idx_18"
    grave = "grave"
    digit_1 = "digit_1"
    digit_2 = "digit_2"
    digit_3 = "digit_3"
    digit_4 = "digit_4"
    digit_5 = "digit_5"
    digit_6 = "digit_6"
    digit_7 = "digit_7"
    digit_8 = "digit_8"
    digit_9 = "digit_9"
    digit_0 = "digit_0"
    minus = "minus"
    equal = "equal"
    idx_32 = "idx_32"
    idx_33 = "idx_33"
    idx_34 = "idx_34"
    idx_35 = "idx_35"
    idx_36 = "idx_36"
    tab = "tab"
    q = "q"
    w = "w"
    e = "e"
    r = "r"
    t = "t"
    y = "y"
    u = "u"
    i = "i"
    o = "o"
    p = "p"
    lbracket = "lbracket"
    rbracket = "rbracket"
    idx_50 = "idx_50"
    idx_51 = "idx_51"
    idx_52 = "idx_52"
    idx_53 = "idx_53"
    idx_54 = "idx_54"
    caps = "caps"
    a = "a"
    s = "s"
    d = "d"
    f = "f"
    g = "g"
    h = "h"
    j = "j"
    k = "k"
    l = "l"  # noqa: E741 — physical key on the keyboard
    semicolon = "semicolon"
    apostrophe = "apostrophe"
    backslash = "backslash"
    idx_68 = "idx_68"
    idx_69 = "idx_69"
    idx_70 = "idx_70"
    idx_71 = "idx_71"
    idx_72 = "idx_72"
    lshift = "lshift"
    z = "z"
    x = "x"
    c = "c"
    v = "v"
    b = "b"
    n = "n"
    m = "m"
    comma = "comma"
    dot = "dot"
    slash = "slash"
    rshift = "rshift"
    enter = "enter"
    idx_86 = "idx_86"
    idx_87 = "idx_87"
    idx_88 = "idx_88"
    idx_89 = "idx_89"
    idx_90 = "idx_90"
    lctrl = "lctrl"
    win = "win"
    lalt = "lalt"
    space = "space"
    ralt = "ralt"
    fn = "fn"
    idx_97 = "idx_97"
    rctrl = "rctrl"
    left = "left"
    down = "down"
    up = "up"
    right = "right"
    backspace = "backspace"
    idx_104 = "idx_104"
    idx_105 = "idx_105"
    idx_106 = "idx_106"
    idx_107 = "idx_107"
    idx_108 = "idx_108"
    idx_109 = "idx_109"
    idx_110 = "idx_110"
    idx_111 = "idx_111"
    idx_112 = "idx_112"
    idx_113 = "idx_113"
    idx_114 = "idx_114"
    idx_115 = "idx_115"
    idx_116 = "idx_116"
    home = "home"
    pgup = "pgup"
    delete = "delete"
    idx_120 = "idx_120"
    pgdn = "pgdn"
    idx_122 = "idx_122"
    idx_123 = "idx_123"
    idx_124 = "idx_124"
    idx_125 = "idx_125"
    idx_126 = "idx_126"
    idx_127 = "idx_127"
    idx_128 = "idx_128"
    idx_129 = "idx_129"
    idx_130 = "idx_130"
    idx_131 = "idx_131"
    idx_132 = "idx_132"
    idx_133 = "idx_133"
    idx_134 = "idx_134"
    idx_135 = "idx_135"
    idx_136 = "idx_136"
    idx_137 = "idx_137"
    idx_138 = "idx_138"
    idx_139 = "idx_139"
    idx_140 = "idx_140"
    idx_141 = "idx_141"
    idx_142 = "idx_142"
    idx_143 = "idx_143"


_KEYMAP_ADAPTER: TypeAdapter[dict[int, Key]] = TypeAdapter(dict[int, Key])


def _build_key_index() -> dict[Key, int]:
    """Parse keymap.json into a {Key: index} mapping with full drift checks.

    Pydantic does the heavy lifting: stringified JSON keys coerce to `int`, and
    each value is coerced into the `Key` enum (unknown names raise ValidationError).
    The post-load checks then enforce that every enum member is present and
    that indices form a clean 0..NUM_KEYS-1 permutation.
    """
    text = (resources.files("ak820ctl") / "data" / "keymap.json").read_text("utf-8")
    parsed: dict[int, Key] = _KEYMAP_ADAPTER.validate_json(text)
    if len(parsed) != NUM_KEYS:
        msg = f"keymap.json has {len(parsed)} entries, expected {NUM_KEYS}"
        raise RuntimeError(msg)
    mapping: dict[Key, int] = {key: idx for idx, key in parsed.items()}
    missing = set(Key) - mapping.keys()
    if missing:
        names = ", ".join(sorted(k.value for k in missing))
        msg = f"Key enum members missing from keymap.json: {names}"
        raise RuntimeError(msg)
    if set(mapping.values()) != set(range(NUM_KEYS)):
        msg = "keymap.json indices are not a 0..143 permutation"
        raise RuntimeError(msg)
    return mapping


KEY_INDEX: dict[Key, int] = _build_key_index()
