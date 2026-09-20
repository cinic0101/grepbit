"""Closed structural metadata, never decoded content or an acceptance/repair path."""
from __future__ import annotations

import json
import math

_MAX_CHARS = 131_072
_WHITESPACE = " \t\r\n"
_ROOT_TYPES = {dict: "object", list: "array", str: "string", int: "number",
               float: "number", bool: "boolean", type(None): "null"}


def _character_class(value: str) -> str:
    if not value:
        return "empty"
    for characters, category in (("{}", "object"), ("[]", "array"), ("`", "backtick"),
                                 ("<>", "angle"), ("\"'", "quote")):
        if value in characters:
            return category
    return "alpha" if value.isalpha() else "other"


def invalid_json_fingerprint(content: str) -> dict[str, object]:
    """Observe one bounded content string; the caller must still use strict_json."""
    result: dict[str, object] = {
        "version": "invalid-json-structure-v1", "analysis_limited": False,
        "byte_length": None, "char_length": None, "has_ascii": None, "has_non_ascii": None,
        "leading_whitespace_bytes": None, "trailing_whitespace_bytes": None,
        "first_non_whitespace_class": "unavailable", "last_non_whitespace_class": "unavailable",
        "starts_with_object": None, "starts_with_array": None, "starts_with_markdown_fence": None,
        "contains_markdown_fence": None, "starts_with_think_tag": None, "contains_think_tag": None,
        "newline_count": None, "decoder_error_category": "unknown",
        "decoder_line": None, "decoder_column": None, "decoder_offset": None,
        "raw_decode_one_value": False, "parsed_root_type": None, "trailing_non_whitespace_bytes": None,
        "duplicate_key": None, "nonfinite": None, "invalid_unicode": None,
    }
    if len(content) > _MAX_CHARS:
        result.update(analysis_limited=True, decoder_error_category="size_limit")
        return result
    flags = {"duplicate_key": False, "nonfinite": False, "invalid_unicode": False}
    try:
        result["byte_length"] = len(content.encode("utf-8"))
    except UnicodeError:
        flags["invalid_unicode"] = True
    leading = len(content) - len(content.lstrip(_WHITESPACE))
    stripped = content.strip(_WHITESPACE)
    result.update(
        char_length=len(content), has_ascii=any(ord(c) < 128 for c in content),
        has_non_ascii=any(ord(c) >= 128 for c in content),
        leading_whitespace_bytes=leading,
        trailing_whitespace_bytes=len(content) - len(content.rstrip(_WHITESPACE)),
        first_non_whitespace_class=_character_class(stripped[:1]),
        last_non_whitespace_class=_character_class(stripped[-1:]),
        starts_with_object=stripped.startswith("{"), starts_with_array=stripped.startswith("["),
        starts_with_markdown_fence=stripped.startswith("```"), contains_markdown_fence="```" in content,
        starts_with_think_tag=stripped.startswith(("<think>", "</think>")),
        contains_think_tag="<think>" in content or "</think>" in content,
        newline_count=content.count("\n"),
    )

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        value = {}
        for key, item in items:
            if key in value:
                flags["duplicate_key"] = True
            value[key] = item
        return value

    def number(text: str) -> float:
        value = float(text)
        if not math.isfinite(value):
            flags["nonfinite"] = True
        return value

    decoder = json.JSONDecoder(object_pairs_hook=pairs, parse_constant=number, parse_float=number)
    try:
        value, end = decoder.raw_decode(content, idx=leading)
    except json.JSONDecodeError as exc:
        result.update(decoder_error_category="malformed_json", decoder_line=exc.lineno,
                      decoder_column=exc.colno, decoder_offset=exc.pos)
    except RecursionError:
        result["decoder_error_category"] = "depth_limit"
    except ValueError:
        result["decoder_error_category"] = "decoder_limit"
    else:
        result.update(raw_decode_one_value=True, parsed_root_type=_ROOT_TYPES[type(value)])
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, str):
                try:
                    item.encode("utf-8")
                except UnicodeError:
                    flags["invalid_unicode"] = True
        tail = content[end:]
        try:
            trailing = len(tail.encode("utf-8")) - sum(tail.count(c) for c in _WHITESPACE)
            result["trailing_non_whitespace_bytes"] = trailing
        except UnicodeError:
            flags["invalid_unicode"] = True
            trailing = None
        category = next((name for name in ("invalid_unicode", "duplicate_key", "nonfinite") if flags[name]), None)
        result["decoder_error_category"] = category or ("trailing_content" if trailing else "none")
        if category is None and trailing:
            offset = end + len(tail) - len(tail.lstrip(_WHITESPACE))
            result.update(decoder_line=content.count("\n", 0, offset) + 1,
                          decoder_column=offset - content.rfind("\n", 0, offset), decoder_offset=offset)
    if flags["invalid_unicode"] and not result["raw_decode_one_value"]:
        result.update(decoder_error_category="invalid_unicode",
                      decoder_line=None, decoder_column=None, decoder_offset=None)
    result.update(flags)
    return result
