"""Soportes de llamados de atención desde Outlook Web (correo SENA).

El instructor inicia sesión en un Chrome temporal; con el token que Outlook
Web deja en el navegador se consultan los Elementos enviados por la API REST
de Outlook, y cada correo se imprime a PDF con Chrome headless.
"""
