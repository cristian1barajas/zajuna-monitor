"""Quitar un grupo lo oculta del monitor sin borrar sus datos."""
from __future__ import annotations

import copy
import json
import os
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import visible_snapshot
from src.api.response_cache import _snapshot_mtime
from src.api.server import app

from tests.test_api import MOCK_SNAPSHOT

OTHER_ID = 99999
OTHER_FICHA = "9999999"


def _two_courses() -> dict:
    """MOCK_SNAPSHOT (ficha 3388997) más un segundo curso idéntico con otra ficha."""
    snap = copy.deepcopy(MOCK_SNAPSHOT)
    for key in ("courses", "summaries", "participants"):
        extra = []
        for item in snap.get(key, []):
            clone = copy.deepcopy(item)
            clone["course_id"] = OTHER_ID
            if "ficha" in clone:
                clone["ficha"] = OTHER_FICHA
            extra.append(clone)
        snap[key] = snap.get(key, []) + extra
    return snap


def _write_tracked(base, course_ids: list[int]) -> None:
    folder = base / "instructors" / "1"
    folder.mkdir(parents=True, exist_ok=True)
    courses = [{"course_id": cid, "ficha": str(cid)} for cid in course_ids]
    (folder / "courses.json").write_text(json.dumps({"courses": courses}), encoding="utf-8")


class TestVisibleSnapshot:
    def test_without_registry_everything_is_visible(self):
        snap = _two_courses()
        assert visible_snapshot(snap, None) is snap

    def test_keeps_only_tracked_courses_everywhere(self):
        visible = visible_snapshot(_two_courses(), {89977})
        for key in ("courses", "summaries", "participants"):
            assert {item["course_id"] for item in visible[key]} <= {89977}
        assert [c["ficha"] for c in visible["courses"]] == ["3388997"]

    def test_does_not_touch_the_stored_snapshot(self):
        snap = _two_courses()
        visible_snapshot(snap, {89977})
        assert len(snap["courses"]) == 2


@pytest.fixture
def client(tmp_path):
    snap = _two_courses()
    with (
        patch("src.api.dependencies.load_snapshot", return_value=snap),
        patch(
            "src.store.tracked_courses_store.instructor_data_dir",
            lambda uid: tmp_path / "instructors" / str(uid),
        ),
        TestClient(app) as c,
    ):
        yield c, tmp_path


class TestRemoveAndAddBack:
    def test_removed_group_disappears_and_comes_back(self, client):
        c, base = client
        _write_tracked(base, [89977])
        fichas = {f["ficha"] for f in c.get("/api/fichas").json()}
        assert OTHER_FICHA not in fichas
        assert "3388997" in fichas

        _write_tracked(base, [89977, OTHER_ID])
        fichas = {f["ficha"] for f in c.get("/api/fichas").json()}
        assert {OTHER_FICHA, "3388997"} <= fichas


class TestCacheVersion:
    def test_changes_when_the_registry_changes(self, tmp_path):
        """Quitar un grupo no toca el snapshot: la caché debe enterarse igual."""
        snapshot = tmp_path / "latest.json"
        snapshot.write_text("{}", encoding="utf-8")
        _write_tracked(tmp_path, [89977])

        class Req:
            class state:
                user = {"id": "1"}

        with (
            patch("src.api.dependencies.snapshot_path_for", return_value=snapshot),
            patch("src.config.instructor_data_dir", lambda uid: tmp_path / "instructors" / str(uid)),
        ):
            before = _snapshot_mtime(Req)
            registry = tmp_path / "instructors" / "1" / "courses.json"
            later = time.time() + 5
            os.utime(registry, (later, later))
            after = _snapshot_mtime(Req)

        assert before is not None and after is not None
        assert before[0] == after[0]
        assert before != after
