"""Tests del exportador de borradores a .eml (src/api/eml_export.py)."""
from __future__ import annotations

import io
import zipfile
from datetime import date
from email import message_from_bytes, policy

from src.api.eml_export import (
    EmlDraft,
    build_eml,
    build_eml_zip,
    eml_filename,
    zip_filename,
)

FORBIDDEN = set('\\/:*?"<>|')


def _draft(**overrides) -> EmlDraft:
    data = {
        "full_name": "ÁNGELA MUÑOZ PEÑA",
        "email": "angela@example.com",
        "subject": "Primer llamado de atención - Ficha 0000001 - Evidencias pendientes",
        "body": "Apreciada aprendiz ÁNGELA MUÑOZ PEÑA:\n\nRecuerde la sesión del miércoles.\n",
        "stage": "primer_llamado",
    }
    data.update(overrides)
    return EmlDraft(**data)


def _parse(raw: bytes):
    return message_from_bytes(raw, policy=policy.default)


class TestBuildEml:
    def test_cabeceras_borrador_sin_enviar(self):
        raw = build_eml(_draft())
        msg = _parse(raw)
        assert msg["X-Unsent"] == "1"
        assert msg["To"] == "angela@example.com"
        assert msg["From"] is None
        assert msg.get_content_type() == "text/plain"
        assert msg.get_content_charset() == "utf-8"

    def test_asunto_con_tildes_se_decodifica_igual(self):
        draft = _draft()
        raw = build_eml(draft)
        # El asunto viaja codificado (RFC 2047), no como bytes crudos.
        assert "atención".encode() not in raw.split(b"\r\n\r\n", 1)[0]
        assert _parse(raw)["Subject"] == draft.subject

    def test_cuerpo_utf8_intacto(self):
        draft = _draft()
        msg = _parse(build_eml(draft))
        # Las líneas viajan con CRLF (lo que espera Outlook).
        assert msg.get_content().replace("\r\n", "\n") == draft.body

    def test_usa_crlf(self):
        raw = build_eml(_draft())
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b"")

    def test_sin_correo_omite_to(self):
        msg = _parse(build_eml(_draft(email="  ")))
        assert msg["To"] is None
        assert msg["X-Unsent"] == "1"
        assert msg["Subject"]

    def test_saltos_de_linea_en_asunto_no_inyectan_cabeceras(self):
        msg = _parse(build_eml(_draft(subject="Hola\r\nBcc: x@example.com")))
        assert msg["Bcc"] is None
        assert msg["Subject"] == "Hola Bcc: x@example.com"


class TestNombres:
    def test_formato_y_ascii(self):
        assert eml_filename(1, _draft()) == "01 - Primer llamado - ANGELA MUNOZ PENA.eml"

    def test_quita_caracteres_prohibidos_en_windows(self):
        name = eml_filename(3, _draft(full_name='A/B\\C:D*E?F"G<H>I|J'))
        assert not FORBIDDEN & set(name)
        assert name.startswith("03 - Primer llamado - ")

    def test_recorta_nombres_largos(self):
        name = eml_filename(1, _draft(full_name="NOMBRE " * 40))
        assert len(name) <= 84
        assert name.endswith(".eml")
        assert not name[:-4].endswith(" ")

    def test_etapa_desconocida_y_nombre_vacio(self):
        assert eml_filename(2, _draft(stage="", full_name="")) == "02 - Llamado - Aprendiz.eml"

    def test_nombre_zip(self):
        assert (
            zip_filename("3388997", date(2026, 10, 28))
            == "correos-llamados-ficha-3388997-2026-10-28.zip"
        )


class TestBuildZip:
    def test_un_eml_por_borrador_sin_colisiones(self):
        drafts = [
            _draft(),
            _draft(full_name="PEDRO PÉREZ", stage="segundo_llamado"),
            _draft(full_name="ana", stage="comite"),
        ]
        content, names = build_eml_zip(drafts)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            assert zf.namelist() == names
            assert len(names) == 3
            assert len({n.lower() for n in names}) == 3
            for name in names:
                assert name.endswith(".eml")
                assert not FORBIDDEN & set(name)
                assert _parse(zf.read(name))["X-Unsent"] == "1"

    def test_nombres_repetidos_se_desambiguan(self):
        # Mismo índice forzado: dos borradores que darían el mismo nombre.
        from src.api.eml_export import _unique

        used: set[str] = set()
        assert _unique("01 - X - A.eml", used) == "01 - X - A.eml"
        assert _unique("01 - x - a.eml", used) == "01 - x - a (2).eml"
        assert _unique("01 - X - A.eml", used) == "01 - X - A (3).eml"
