"""Load a semantic overlay document from JSON."""

from __future__ import annotations

import json
from pathlib import Path

from grepbit.domain.overlay import SemanticOverlay


def load_semantic_overlay(path: Path) -> SemanticOverlay:
    return SemanticOverlay.model_validate(json.loads(path.read_text(encoding="utf-8")))
