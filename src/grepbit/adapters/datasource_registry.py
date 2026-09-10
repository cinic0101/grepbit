"""Load ``datasources.json`` and resolve its relative paths."""

from __future__ import annotations

import json
from pathlib import Path

from grepbit.domain.datasource import DatasourceRegistration, DatasourceRegistry


def load_registry(path: Path) -> DatasourceRegistry:
    return DatasourceRegistry.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def overlay_path(
    registry_path: Path, registration: DatasourceRegistration
) -> Path | None:
    if registration.overlay is None:
        return None
    return (registry_path.parent / registration.overlay).resolve()
