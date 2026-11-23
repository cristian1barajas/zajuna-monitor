"""Descubrimiento de los cursos Zajuna de un instructor.

Reutiliza el login normal: el paso 3 de AuthManager ya descarga
/zajuna/my/, cuyo bloque de navegación lista los cursos del instructor.
Cuesta un solo login (sin requests adicionales).
"""
from __future__ import annotations

from src.auth.manager import AuthError, AuthManager
from src.config import ZajunaConfig
from src.parsers.my_courses import MyCoursesResult, parse_my_courses


def discover_courses(config: ZajunaConfig) -> MyCoursesResult:
    """Inicia sesión con las credenciales de ``config`` y lista sus cursos.

    Raises:
        AuthError: Zajuna rechazó las credenciales.
        ZajunaUnavailableError: Zajuna no respondió.
    """
    auth = AuthManager(config)
    auth.login()
    if auth.my_page_html is None:
        raise AuthError("El login no devolvió la página /zajuna/my/")
    return parse_my_courses(auth.my_page_html)
