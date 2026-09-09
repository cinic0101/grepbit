"""Load language packs from JSON: the packaged default or a caller's file."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from grepbit.domain.language_pack import ShapePack


def load_shape_pack(path: Path | None = None) -> ShapePack:
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        text = (
            resources.files("grepbit.resources")
            .joinpath("unsupported_shapes.json")
            .read_text(encoding="utf-8")
        )
    return ShapePack.model_validate(json.loads(text))
