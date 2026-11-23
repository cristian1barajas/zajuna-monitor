"""Imprime correos con la opción "Imprimir" de Outlook Web y los guarda en PDF.

No se arma ninguna plantilla: Outlook Web prepara la vista de impresión en
un iframe oculto y llama a ``print()``. Aquí se intercepta esa llamada, se
toma el documento que Outlook preparó y Chrome lo imprime a PDF con el
encabezado y pie de página del navegador (fecha, título, URL y página), igual
que "Imprimir → Guardar como PDF".
"""
from __future__ import annotations

import base64
import contextlib
import html
import json
import time
from urllib.parse import quote, urlparse

from src.outlook.chrome import CdpSession, ChromeError, ChromeProcess
from src.outlook.session import OWA_HOSTS

# Instalado en cada documento de la pestaña de Outlook (y en sus iframes):
# print() guarda el HTML que Outlook iba a imprimir en vez de abrir el diálogo.
PRINT_HOOK_JS = r"""
(() => {
  const hook = (w) => {
    try {
      if (w.__zajunaPrintHook) return;
      w.__zajunaPrintHook = true;
      w.print = function () {
        const top = window.top;
        top.__zajunaPrints = top.__zajunaPrints || [];
        top.__zajunaPrints.push(w.document.documentElement.outerHTML);
      };
    } catch (e) {}
  };
  hook(window);
  new MutationObserver(() => {
    document.querySelectorAll('iframe').forEach((f) => { try { hook(f.contentWindow); } catch (e) {} });
  }).observe(document, { childList: true, subtree: true });
})();
"""

# Hace clic en "Imprimir" cuando el correo ya cargó; devuelve false si aún no.
_CLICK_PRINT_JS = """
((needle) => {
  const buttons = [...document.querySelectorAll('button[aria-label="Imprimir"], button[aria-label="Print"]')];
  if (!buttons.length || !document.body.innerText.includes(needle)) return false;
  window.__zajunaPrints = window.__zajunaPrints || [];
  window.__zajunaBefore = window.__zajunaPrints.length;
  buttons[buttons.length - 1].click();
  return true;
})(%s)
"""

LOAD_TIMEOUT_S = 40
CAPTURE_TIMEOUT_S = 25
DEFAULT_ORIGIN = "https://outlook.office.com"

# Encabezado y pie como los pone Chrome al imprimir.
_HF_STYLE = (
    "<style>.zr{font-family:system-ui,'Segoe UI',Arial,sans-serif;font-size:8px;width:100%;"
    "display:flex;justify-content:space-between;gap:12px;margin:0 0.4in}"
    ".zc{flex:1;text-align:center}.zt{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}</style>"
)
_PDF_OPTIONS = {
    "displayHeaderFooter": True,
    "printBackground": False,
    "paperWidth": 8.5,
    "paperHeight": 11,
    "marginTop": 0.4,
    "marginBottom": 0.4,
    "marginLeft": 0.4,
    "marginRight": 0.4,
}


def _wait(condition, timeout: float, error: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if condition():
                return
        except ChromeError:
            pass  # la página está navegando
        time.sleep(0.2)
    raise ChromeError(error)


def message_url(origin: str, message_id: str) -> str:
    """Dirección final del correo en Outlook Web.

    No se usa el ``WebLink`` de la API (``/owa/?ItemID=…``): redirige, y tras
    unas diez redirecciones seguidas Outlook muestra su página de error
    ``olkerror.html?msg=ReoccurringRedirectErrorMessage``.
    """
    return f"{origin}/mail/deeplink/read/{quote(message_id, safe='')}"


def capture_outlook_print(page: CdpSession, url: str, needle: str) -> tuple[str, str, str]:
    """Abre el correo en Outlook Web, pulsa "Imprimir" y devuelve (html, título, url) de la impresión.

    ``needle`` es un texto del asunto para confirmar que cargó el correo correcto.
    """
    page.call("Page.navigate", {"url": url})
    page.events.clear()
    _wait(
        lambda: page.evaluate(_CLICK_PRINT_JS % json.dumps(needle), timeout=10),
        LOAD_TIMEOUT_S,
        "Outlook no abrió el correo para imprimirlo",
    )
    _wait(
        lambda: page.evaluate("(window.__zajunaPrints || []).length > window.__zajunaBefore", timeout=10),
        CAPTURE_TIMEOUT_S,
        "Outlook no preparó la impresión del correo",
    )
    doc = page.evaluate("window.__zajunaPrints[window.__zajunaPrints.length - 1]", timeout=10)
    title = page.evaluate("document.title", timeout=10) or ""
    url = page.evaluate("location.href", timeout=10) or ""
    return doc, title, url


def render_pdf(tab: CdpSession, doc: str, title: str, url: str) -> bytes:
    """Imprime a PDF el documento que preparó Outlook, con el encabezado y pie del navegador."""
    tab.evaluate(
        f"document.open(); document.write({json.dumps('<!DOCTYPE html>' + doc)}); document.close();"
        f"document.title = {json.dumps(title)}; true"
    )
    _wait(
        lambda: tab.evaluate("document.readyState === 'complete' && [...document.images].every(i => i.complete)"),
        20,
        "El correo no terminó de cargar para el PDF",
    )
    header = (
        f"{_HF_STYLE}<div class='zr'><span class='date'></span>"
        f"<span class='zc zt'>{html.escape(title)}</span><span style='width:40px'></span></div>"
    )
    footer = (
        f"{_HF_STYLE}<div class='zr'><span class='zt'>{html.escape(url)}</span>"
        "<span><span class='pageNumber'></span>/<span class='totalPages'></span></span></div>"
    )
    result = tab.call("Page.printToPDF", {**_PDF_OPTIONS, "headerTemplate": header, "footerTemplate": footer}, timeout=60)
    return base64.b64decode(result["data"])


class OutlookPrinter:
    """Imprime varios correos con la pestaña de Outlook y una pestaña auxiliar para el PDF."""

    def __init__(self, chrome: ChromeProcess, page: CdpSession):
        self.chrome = chrome
        self.page = page
        self._tab_id: str | None = None
        self._tab: CdpSession | None = None
        self._hook_id: str | None = None
        self._origin = DEFAULT_ORIGIN

    def __enter__(self) -> OutlookPrinter:
        self.page.call("Page.enable")
        current = urlparse(self.page.evaluate("location.href") or "")
        if current.hostname in OWA_HOSTS:
            self._origin = f"https://{current.hostname}"
        hook = self.page.call("Page.addScriptToEvaluateOnNewDocument", {"source": PRINT_HOOK_JS})
        self._hook_id = hook.get("identifier")
        self._tab_id, self._tab = self.chrome.open_tab(self.page)
        return self

    def __exit__(self, *exc) -> None:
        if self._tab is not None:
            self._tab.close()
        if self._tab_id is not None:
            with contextlib.suppress(ChromeError):
                self.page.call("Target.closeTarget", {"targetId": self._tab_id})
        if self._hook_id is not None:
            with contextlib.suppress(ChromeError):
                self.page.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier": self._hook_id})
        self.page.events.clear()

    def _recover(self) -> None:
        """Vuelve a la bandeja si Outlook quedó en su página de error."""
        self.page.call("Page.navigate", {"url": f"{self._origin}/mail/sentitems"})
        _wait(
            lambda: "/mail/sentitems" in (self.page.evaluate("location.href", timeout=10) or "")
            and self.page.evaluate("document.readyState", timeout=10) == "complete",
            LOAD_TIMEOUT_S,
            "Outlook no volvió a cargar la bandeja",
        )
        time.sleep(3)

    def print_pdf(self, message_id: str, needle: str) -> bytes:
        """PDF del correo tal como lo imprime Outlook; reintenta una vez si Outlook falla."""
        url = message_url(self._origin, message_id)
        try:
            doc, title, href = capture_outlook_print(self.page, url, needle)
        except ChromeError:
            self._recover()
            doc, title, href = capture_outlook_print(self.page, url, needle)
        assert self._tab is not None
        return render_pdf(self._tab, doc, title, href)
