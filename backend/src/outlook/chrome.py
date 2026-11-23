"""Chrome con perfil temporal controlado por el DevTools Protocol (CDP).

Sin Selenium ni chromedriver: se lanza ``chrome.exe`` con
``--remote-debugging-port=0`` y un perfil desechable, se lee el puerto del
archivo ``DevToolsActivePort`` y se habla CDP por websocket (``websockets``
ya viene con ``uvicorn[standard]``).

El perfil es temporal porque Chrome no permite depuración remota sobre el
perfil real del usuario; se borra al cerrar.
"""
from __future__ import annotations

import contextlib
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

_CHROME_CANDIDATES = [
    os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
    os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


class ChromeError(RuntimeError):
    """Chrome no se pudo abrir o se cerró."""


def find_chrome() -> str:
    """Ruta de Chrome: ``ZAJUNA_CHROME_PATH`` o la instalación habitual."""
    custom = os.environ.get("ZAJUNA_CHROME_PATH")
    if custom and Path(custom).is_file():
        return custom
    for candidate in _CHROME_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    raise ChromeError("No se encontró Google Chrome en este equipo")


class CdpSession:
    """Conexión CDP a una pestaña. Los eventos que llegan se guardan en ``events``."""

    def __init__(self, ws_url: str, timeout: float = 30.0):
        self._ws = connect(ws_url, max_size=None, open_timeout=timeout)
        self._ids = itertools.count(1)
        self._timeout = timeout
        self.events: list[dict[str, Any]] = []

    def call(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict:
        msg_id = next(self._ids)
        deadline = time.monotonic() + (timeout or self._timeout)
        try:
            self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        except WebSocketException as exc:
            raise ChromeError("Se cerró la pestaña de Chrome") from exc
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ChromeError(f"Chrome no respondió a {method}")
            try:
                data = json.loads(self._ws.recv(timeout=remaining))
            except TimeoutError as exc:
                raise ChromeError(f"Chrome no respondió a {method}") from exc
            except WebSocketException as exc:
                raise ChromeError("Se cerró la pestaña de Chrome") from exc
            if data.get("id") == msg_id:
                if "error" in data:
                    raise ChromeError(f"{method}: {data['error'].get('message', 'error')}")
                return data.get("result", {})
            if "method" in data:
                self.events.append(data)

    def evaluate(self, expression: str, timeout: float | None = None) -> Any:
        """Evalúa JS en la página y devuelve el valor (las promesas se esperan)."""
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        if "exceptionDetails" in result:
            raise ChromeError("Error de JavaScript en la página")
        return result.get("result", {}).get("value")

    def close(self) -> None:
        with contextlib.suppress(Exception):  # cerrar es best effort
            self._ws.close()


class ChromeProcess:
    """Chrome desechable. Usar como context manager: al salir se cierra y se borra el perfil."""

    def __init__(self, *, headless: bool, url: str = "about:blank", window_size: str = "1280,900"):
        self.headless = headless
        self.url = url
        self.window_size = window_size
        self.port: int | None = None
        self._proc: subprocess.Popen | None = None
        self._profile: str | None = None

    def __enter__(self) -> ChromeProcess:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self, timeout: float = 20.0) -> None:
        self._profile = tempfile.mkdtemp(prefix="zajuna_chrome_")
        args = [
            find_chrome(),
            f"--user-data-dir={self._profile}",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-search-engine-choice-screen",
            "--disable-features=Translate",
            # Fechas del encabezado de impresión en formato colombiano.
            "--lang=es-CO",
            f"--window-size={self.window_size}",
        ]
        if self.headless:
            args += ["--headless=new", "--disable-gpu"]
        args.append(self.url)
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        port_file = Path(self._profile) / "DevToolsActivePort"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise ChromeError("Chrome se cerró al abrir")
            try:
                first_line = port_file.read_text(encoding="utf-8").splitlines()[0]
                self.port = int(first_line)
                return
            except (OSError, IndexError, ValueError):
                time.sleep(0.2)
        raise ChromeError("Chrome no abrió el puerto de depuración")

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def pages(self) -> list[dict]:
        """Pestañas abiertas (``type == "page"``)."""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=5) as resp:  # nosec B310 # nosemgrep - URL fija a 127.0.0.1
                targets = json.loads(resp.read().decode("utf-8"))
        except OSError as exc:
            raise ChromeError("Chrome se cerró") from exc
        return [t for t in targets if t.get("type") == "page"]

    def first_page(self, timeout: float = 10.0) -> CdpSession:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pages = self.pages()
            if pages:
                return CdpSession(pages[0]["webSocketDebuggerUrl"])
            time.sleep(0.2)
        raise ChromeError("Chrome no abrió ninguna pestaña")

    def open_tab(self, via: CdpSession) -> tuple[str, CdpSession]:
        """Pestaña nueva en segundo plano; devuelve su id y su sesión CDP."""
        target_id = via.call("Target.createTarget", {"url": "about:blank", "background": True})["targetId"]
        for _ in range(50):
            match = [p for p in self.pages() if p.get("id") == target_id]
            if match:
                return target_id, CdpSession(match[0]["webSocketDebuggerUrl"])
            time.sleep(0.1)
        raise ChromeError("Chrome no abrió la pestaña")

    def minimize(self, via: CdpSession) -> None:
        window = via.call("Browser.getWindowForTarget")
        via.call("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"windowState": "minimized"}})

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._profile:
            # Chrome suelta los archivos del perfil unos instantes después de salir.
            for _ in range(10):
                shutil.rmtree(self._profile, ignore_errors=True)
                if not Path(self._profile).exists():
                    break
                time.sleep(0.3)
