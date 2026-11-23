"""JSON file storage for scraper snapshots."""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR, SNAPSHOTS_DIR
from src.models.schemas import GradeStatus, ScraperSnapshot, StudentStatus

logger = logging.getLogger(__name__)


class SnapshotEncoder(json.JSONEncoder):
    """Custom JSON encoder for dataclass fields."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, (GradeStatus, StudentStatus)):
            return obj.value
        return super().default(obj)


def save_snapshot(snapshot: ScraperSnapshot, base_dir: Path | None = None) -> Path:
    """Save a snapshot to disk as JSON.

    Creates (relative to ``base_dir`` or al layout global por defecto):
    - snapshots/{timestamp}.json (timestamped archive)
    - latest.json (copy of the latest snapshot)

    ``base_dir`` permite el layout particionado por instructor
    (data/instructors/<cmm_user_id>/) del paso 3 multi-instructor.

    Returns the path to the saved snapshot file.
    """
    snapshots_dir = (base_dir / "snapshots") if base_dir else SNAPSHOTS_DIR
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    ts = snapshot.timestamp.strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"{ts}.json"
    filepath = snapshots_dir / filename

    data = asdict(snapshot)
    json_str = json.dumps(data, cls=SnapshotEncoder, ensure_ascii=False, indent=2)

    filepath.write_text(json_str, encoding="utf-8")
    logger.info("Saved snapshot to %s (%d bytes)", filepath, len(json_str))

    # Update latest.json (copy, not symlink, for Windows compatibility)
    latest_path = (base_dir or DATA_DIR) / "latest.json"
    shutil.copy2(filepath, latest_path)
    logger.info("Updated %s", latest_path)

    _rotate_snapshots(snapshots_dir, max_keep=30)

    return filepath


def _rotate_snapshots(snapshots_dir: Path, max_keep: int = 30) -> None:
    """Remove old snapshot files, keeping only the most recent ones."""
    snapshots = sorted(snapshots_dir.glob("*.json"), reverse=True)
    for old in snapshots[max_keep:]:
        old.unlink()
        logger.debug("Removed old snapshot: %s", old.name)
