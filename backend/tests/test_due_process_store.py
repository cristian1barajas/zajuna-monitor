"""Tests for the due process store."""
from unittest.mock import patch

from src.store.due_process_store import (
    STAGES,
    advance_due_process,
    delete_due_process,
    get_next_stage,
    load_due_process,
    save_due_process,
)


class TestGetNextStage:
    def test_none_returns_primer(self):
        assert get_next_stage(None) == "primer_llamado"

    def test_sin_proceso_returns_primer(self):
        assert get_next_stage("sin_proceso") == "primer_llamado"

    def test_full_sequence(self):
        assert get_next_stage("primer_llamado") == "segundo_llamado"
        assert get_next_stage("segundo_llamado") == "plan_mejoramiento"
        assert get_next_stage("plan_mejoramiento") == "comite"

    def test_comite_is_terminal(self):
        assert get_next_stage("comite") == "comite"

    def test_unknown_stage_defaults_to_primer(self):
        assert get_next_stage("unknown_value") == "primer_llamado"


class TestDueProcessStore:
    def test_load_nonexistent(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            result = load_due_process("9999999")
            assert result is None

    def test_save_and_load(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            data = {
                "records": {
                    "100": {
                        "user_id": 100,
                        "full_name": "JUAN PEREZ",
                        "document": "1234567890",
                        "current_stage": "primer_llamado",
                        "history": [],
                    }
                }
            }
            save_due_process("3388997", data)
            loaded = load_due_process("3388997")
            assert loaded is not None
            assert loaded["ficha"] == "3388997"
            assert "updated_at" in loaded
            assert "100" in loaded["records"]
            assert loaded["records"]["100"]["full_name"] == "JUAN PEREZ"

    def test_creates_directory(self, tmp_path):
        target = tmp_path / "nested" / "dir"
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", target):
            save_due_process("3388997", {"records": {}})
            assert target.exists()

    def test_delete_existing(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            save_due_process("3388997", {"records": {}})
            assert delete_due_process("3388997") is True
            assert load_due_process("3388997") is None

    def test_delete_nonexistent(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            assert delete_due_process("9999999") is False


class TestAdvanceDueProcess:
    def test_creates_new_record(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            record = advance_due_process(
                ficha="3388997",
                user_id=100,
                full_name="JUAN PEREZ",
                document="1234567890",
                evidence_ids=[1001, 1003],
                evidence_names=["AA1-EV01", "AA2-EV01"],
            )
            assert record["user_id"] == 100
            assert record["current_stage"] == "primer_llamado"
            assert len(record["history"]) == 1
            assert record["history"][0]["stage"] == "primer_llamado"
            assert record["history"][0]["evidence_ids"] == [1001, 1003]
            assert record["history"][0]["email_generated"] is True

    def test_advances_existing_record(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            # First advance: sin_proceso -> primer_llamado
            advance_due_process("3388997", 100, "JUAN", "123", [1001], ["EV01"])
            # Second advance: primer_llamado -> segundo_llamado
            record = advance_due_process("3388997", 100, "JUAN", "123", [1001], ["EV01"])
            assert record["current_stage"] == "segundo_llamado"
            assert len(record["history"]) == 2

    def test_full_advancement_sequence(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            for expected_stage in STAGES[1:]:  # primer, segundo, plan, comite
                record = advance_due_process(
                    "3388997", 100, "JUAN", "123", [1001], ["EV01"]
                )
                assert record["current_stage"] == expected_stage

    def test_terminal_stage_stays(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            # Advance through all stages
            for _ in range(4):
                advance_due_process("3388997", 100, "JUAN", "123", [1001], ["EV01"])
            # One more should stay at comite
            record = advance_due_process("3388997", 100, "JUAN", "123", [1001], ["EV01"])
            assert record["current_stage"] == "comite"
            assert len(record["history"]) == 5

    def test_multiple_students(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            advance_due_process("3388997", 100, "JUAN", "123", [1001], ["EV01"])
            advance_due_process("3388997", 200, "MARIA", "456", [1002], ["EV02"])

            loaded = load_due_process("3388997")
            assert len(loaded["records"]) == 2
            assert loaded["records"]["100"]["current_stage"] == "primer_llamado"
            assert loaded["records"]["200"]["current_stage"] == "primer_llamado"

    def test_history_preserves_evidence_names(self, tmp_path):
        with patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path):
            advance_due_process("3388997", 100, "JUAN", "123", [1001, 1002], ["EV01", "EV02"])
            record = advance_due_process("3388997", 100, "JUAN", "123", [1003], ["EV03"])

            assert record["history"][0]["evidence_names"] == ["EV01", "EV02"]
            assert record["history"][1]["evidence_names"] == ["EV03"]
