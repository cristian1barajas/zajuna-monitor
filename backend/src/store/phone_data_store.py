"""Store for phone/contact data imported from Excel files."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import DATA_DIR
from src.store.instructor_scope import scoped_dir

logger = logging.getLogger(__name__)

PHONE_DATA_DIR = DATA_DIR / "phone_data"


def load_phone_data(ficha: str) -> dict[str, str]:
    """Load phone data for a ficha. Returns {document: phone} dict."""
    path = scoped_dir(PHONE_DATA_DIR) / f"{ficha}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_phone_data(ficha: str, data: dict[str, str]) -> Path:
    """Save phone data for a ficha. Returns the path written."""
    scoped_dir(PHONE_DATA_DIR).mkdir(parents=True, exist_ok=True)
    path = scoped_dir(PHONE_DATA_DIR) / f"{ficha}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Saved phone data for ficha %s: %d entries", ficha, len(data))
    return path
