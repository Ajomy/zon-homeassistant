"""Translation files cover the same keys."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "zon_forecast"


def _keys(value, prefix=""):
    """Flatten translation keys."""
    if isinstance(value, dict):
        found = set()
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            found.add(path)
            found.update(_keys(item, path))
        return found
    return set()


def test_english_and_dutch_have_the_same_keys() -> None:
    """Dutch strings cover every English key, and English matches strings.json."""
    strings = json.loads((ROOT / "strings.json").read_text())
    english = json.loads((ROOT / "translations" / "en.json").read_text())
    dutch = json.loads((ROOT / "translations" / "nl.json").read_text())
    assert english == strings
    assert _keys(dutch) == _keys(strings)
