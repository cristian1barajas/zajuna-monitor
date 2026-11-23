"""Días hábiles de Colombia (lunes a viernes sin festivos nacionales).

Los festivos se calculan por año, sin dependencias externas:

- Fijos: 1 ene, 1 may, 20 jul, 7 ago, 8 dic, 25 dic.
- Ley Emiliani (Ley 51 de 1983), se trasladan al lunes siguiente:
  6 ene, 19 mar, 29 jun, 15 ago, 12 oct, 1 nov y 11 nov.
- Según la Pascua: Jueves y Viernes Santo, y Ascensión, Corpus Christi y
  Sagrado Corazón (trasladados a lunes: Pascua + 43, + 64 y + 71 días).

Colombia no tiene horario de verano: la hora local es UTC-5 todo el año.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

COLOMBIA_TZ = timezone(timedelta(hours=-5), "America/Bogota")

_FIXED = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
_EMILIANI = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]
# Días desde el domingo de Pascua; los positivos ya son el lunes trasladado.
_EASTER_OFFSETS = [-3, -2, 43, 64, 71]


def _easter(year: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo, Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 — nombre del algoritmo
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _next_monday(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7)


@lru_cache(maxsize=32)
def colombian_holidays(year: int) -> frozenset[date]:
    """Festivos nacionales de Colombia en el año dado."""
    days = {date(year, m, d) for m, d in _FIXED}
    days |= {_next_monday(date(year, m, d)) for m, d in _EMILIANI}
    easter = _easter(year)
    days |= {easter + timedelta(days=n) for n in _EASTER_OFFSETS}
    return frozenset(days)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in colombian_holidays(day.year)


def next_business_day(day: date) -> date:
    """Primer día hábil estrictamente después de ``day``."""
    current = day + timedelta(days=1)
    while not is_business_day(current):
        current += timedelta(days=1)
    return current


def business_days_between(start: date, end: date) -> int:
    """Días hábiles en (start, end]: cuántos han pasado desde ``start``."""
    if end <= start:
        return 0
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if is_business_day(current):
            count += 1
    return count


def today_colombia() -> date:
    return datetime.now(COLOMBIA_TZ).date()


def local_date(moment: datetime) -> date:
    """Fecha en Colombia de un instante (sin zona se asume hora de Colombia)."""
    if moment.tzinfo is None:
        return moment.date()
    return moment.astimezone(COLOMBIA_TZ).date()
