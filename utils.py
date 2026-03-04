from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_config(path: str | None = None) -> Dict[str, Any]:
    """Load config.json from project root by default."""
    if path is None:
        root = Path(__file__).resolve().parents[1]
        path = str(root / "config.json")

    p = Path(path)
    if not p.exists():
        return {}

    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
