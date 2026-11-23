"""Tests for email template generation."""
from src.api.email_templates import generate_email

SAMPLE_EVIDENCES = ["GA1-220501092-AA1-EV01 Informe de requisitos", "GA2-220501092-AA2-EV01 Proyecto"]
SAMPLE_HISTORY = [
    {"stage": "primer_llamado", "date": "2026-02-15T10:00:00"},
    {"stage": "segundo_llamado", "date": "2026-02-20T10:00:00"},
]


class TestGenerateEmail:
    def test_dispatches_primer_llamado(self):
        result = generate_email(
            stage="primer_llamado",
            student_name="JUAN PEREZ",
            student_document="1234567890",
            ficha="3388997",
            evidence_names=SAMPLE_EVIDENCES,
        )
        assert result["stage"] == "primer_llamado"
        assert result["stage_label"] == "Primer llamado de atención"
        assert "Primer llamado" in result["subject"]
        assert "JUAN PEREZ" in result["subject"]
        assert "3388997" in result["subject"]

    def test_dispatches_segundo_llamado(self):
        result = generate_email(
            stage="segundo_llamado",
            student_name="MARIA LOPEZ",
            student_document="9876543210",
            ficha="3388997",
            evidence_names=SAMPLE_EVIDENCES,
            history=SAMPLE_HISTORY[:1],
        )
        assert result["stage"] == "segundo_llamado"
        assert "Segundo llamado" in result["subject"]
        assert "Plan de Mejoramiento" in result["body"]

    def test_dispatches_plan_mejoramiento(self):
        result = generate_email(
            stage="plan_mejoramiento",
            student_name="CARLOS GARCIA",
            student_document="5555555555",
            ficha="3388997",
            evidence_names=SAMPLE_EVIDENCES,
            history=SAMPLE_HISTORY,
        )
        assert result["stage"] == "plan_mejoramiento"
        assert "Plan de mejoramiento" in result["subject"]
        assert "Coordinación Académica" in result["body"]
        assert "tres (3) días" in result["body"]

    def test_dispatches_comite(self):
        result = generate_email(
            stage="comite",
            student_name="ANA MARTINEZ",
            student_document="1111111111",
            ficha="3388997",
            evidence_names=SAMPLE_EVIDENCES,
            history=SAMPLE_HISTORY,
        )
        assert result["stage"] == "comite"
        assert "Comité de Evaluación" in result["subject"]
        assert "Comité de Evaluación y Seguimiento" in result["body"]

    def test_body_contains_student_info(self):
        result = generate_email(
            stage="primer_llamado",
            student_name="JUAN PEREZ",
            student_document="1234567890",
            ficha="3388997",
            evidence_names=SAMPLE_EVIDENCES,
            last_access_info="5 días",
        )
        assert "JUAN PEREZ" in result["body"]
        assert "1234567890" in result["body"]
        assert "3388997" in result["body"]
        assert "5 días" in result["body"]

    def test_evidence_list_numbered(self):
        result = generate_email(
            stage="primer_llamado",
            student_name="TEST",
            student_document="000",
            ficha="111",
            evidence_names=["EV01 Primer", "EV02 Segundo", "EV03 Tercero"],
        )
        assert "1. EV01 Primer" in result["body"]
        assert "2. EV02 Segundo" in result["body"]
        assert "3. EV03 Tercero" in result["body"]

    def test_empty_evidences(self):
        result = generate_email(
            stage="primer_llamado",
            student_name="TEST",
            student_document="000",
            ficha="111",
            evidence_names=[],
        )
        assert "Sin evidencias" in result["body"]

    def test_history_included_when_provided(self):
        result = generate_email(
            stage="comite",
            student_name="TEST",
            student_document="000",
            ficha="111",
            evidence_names=["EV01"],
            history=SAMPLE_HISTORY,
        )
        assert "2026-02-15" in result["body"]
        assert "2026-02-20" in result["body"]

    def test_unknown_stage_defaults_to_primer(self):
        result = generate_email(
            stage="unknown_stage",
            student_name="TEST",
            student_document="000",
            ficha="111",
            evidence_names=["EV01"],
        )
        # Should not crash, defaults to primer_llamado template
        assert "subject" in result
        assert "body" in result
