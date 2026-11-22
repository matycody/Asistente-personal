"""Interfaz web local de Jarvis.

Levanta un servidor chiquito en tu propia máquina (127.0.0.1) y sirve una página.
Los eventos van del servidor a la página por SSE, que es parte de Python: no hace
falta instalar nada.

Seguridad: escucha solo en 127.0.0.1, y cada arranque genera un token al azar que
va en la dirección. Sin ese token no se puede ni leer el estado ni mandar órdenes,
así que otro programa de la misma PC no puede manejar a Jarvis.
"""
from __future__ import annotations

import json
import logging
import queue
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("jarvis")
WEB = Path(__file__).resolve().parent / "web"

TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon"}


class WebUI:
    """Habla el mismo idioma que Hud y NullUI: status / heard / said / log / close."""

    def __init__(self, pausado: threading.Event, parar: threading.Event,
                 puerto: int = 8777, on_orden=None):
        self.pausado = pausado
        self.parar = parar
        self.token = secrets.token_urlsafe(16)
        self.on_orden = on_orden
        self.clientes: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.ultimo: dict[str, dict] = {}   # último evento de cada tipo, para quien se conecte
        self.servidor = None
        self.puerto = puerto

    # ---------- API de la interfaz ----------
    def _emitir(self, tipo: str, dato) -> None:
        ev = {"tipo": tipo, "dato": dato}
        if tipo != "nivel":
            self.ultimo[tipo] = ev
        with self.lock:
            muertos = []
            for q in self.clientes:
                try:
                    q.put_nowait(ev)
                except queue.Full:
                    muertos.append(q)
            for q in muertos:
                self.clientes.remove(q)

    def status(self, estado: str) -> None:
        self._emitir("estado", estado)

    def heard(self, texto: str) -> None:
        self._emitir("oido", texto)

    def said(self, texto: str) -> None:
        self._emitir("dijo", texto)

    def log(self, texto: str) -> None:
        self._emitir("nota", texto)

    def nivel(self, valor: float) -> None:
        self._emitir("nivel", round(min(1.0, max(0.0, valor)), 3))

    def pendientes(self, lista: list[str]) -> None:
        self._emitir("pendientes", lista)

    def info(self, datos: dict) -> None:
        self._emitir("info", datos)

    def close(self) -> None:
        self._emitir("cerrar", "")
        if self.servidor:
            threading.Thread(target=self.servidor.shutdown, daemon=True).start()

    def alternar_pausa(self) -> None:
        if self.pausado.is_set():
            self.pausado.clear()
            self.status("escuchando")
        else:
            self.pausado.set()
            self.status("en pausa")

    def mostrar(self) -> None:
        self.abrir_navegador()

    # ---------- servidor ----------
    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}/?t={self.token}"

    def _handler(self):
        ui = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):   # sin ruido en la consola
                pass

            def _ok(self, cuerpo: bytes, tipo: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(cuerpo)

            def _no(self, codigo: int = 403) -> None:
                self.send_response(codigo)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _token_ok(self) -> bool:
                from urllib.parse import parse_qs, urlparse
                pedido = parse_qs(urlparse(self.path).query).get("t", [""])[0]
                return secrets.compare_digest(pedido, ui.token)

            def _ruta(self) -> str:
                from urllib.parse import urlparse
                return urlparse(self.path).path

            # ---- GET ----
            def do_GET(self):
                ruta = self._ruta()
                if not self._token_ok():
                    return self._no()
                if ruta == "/eventos":
                    return self._sse()
                if ruta == "/indice":
                    from . import indice
                    vistos, lista = set(), []
                    for dato in indice.cargar().values():
                        clave = (dato.get("titulo"), dato.get("tipo"))
                        if clave in vistos:
                            continue
                        vistos.add(clave)
                        lista.append({"titulo": dato.get("titulo", ""),
                                      "tipo": dato.get("tipo", "")})
                    lista.sort(key=lambda d: d["titulo"].lower())
                    return self._ok(json.dumps(lista, ensure_ascii=False).encode(),
                                    "application/json")
                nombre = "index.html" if ruta == "/" else ruta.lstrip("/")
                archivo = (WEB / nombre).resolve()
                if WEB not in archivo.parents or not archivo.is_file():
                    return self._no(404)
                self._ok(archivo.read_bytes(), TIPOS.get(archivo.suffix, "application/octet-stream"))

            def _sse(self):
                q: queue.Queue = queue.Queue(maxsize=400)
                with ui.lock:
                    ui.clientes.append(q)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    for ev in ui.ultimo.values():     # estado actual para quien recién llega
                        self._mandar(ev)
                    while not ui.parar.is_set():
                        try:
                            self._mandar(q.get(timeout=12))
                        except queue.Empty:
                            self.wfile.write(b": ping\n\n")   # mantiene viva la conexión
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with ui.lock:
                        if q in ui.clientes:
                            ui.clientes.remove(q)

            def _mandar(self, ev: dict) -> None:
                self.wfile.write(b"data: " + json.dumps(ev, ensure_ascii=False).encode() + b"\n\n")
                self.wfile.flush()

            # ---- POST ----
            def do_POST(self):
                if not self._token_ok():
                    return self._no()
                largo = int(self.headers.get("Content-Length") or 0)
                try:
                    cuerpo = json.loads(self.rfile.read(largo) or b"{}")
                except Exception:
                    cuerpo = {}
                ruta = self._ruta()
                if ruta == "/orden":
                    texto = str(cuerpo.get("texto", ""))[:500].strip()
                    if texto and ui.on_orden:
                        threading.Thread(target=ui.on_orden, args=(texto,), daemon=True).start()
                elif ruta == "/pausa":
                    ui.alternar_pausa()
                elif ruta == "/salir":
                    ui.parar.set()
                    ui.close()
                else:
                    return self._no(404)
                self._ok(b'{"ok":true}', "application/json")

        return H

    def iniciar(self) -> str:
        """Levanta el servidor en un hilo aparte y devuelve la dirección."""
        ultimo_error = None
        for puerto in range(self.puerto, self.puerto + 12):
            try:
                self.servidor = ThreadingHTTPServer(("127.0.0.1", puerto), self._handler())
                self.servidor.daemon_threads = True
                self.puerto = puerto
                break
            except OSError as e:
                ultimo_error = e
        if self.servidor is None:
            raise RuntimeError(f"no pude abrir ningún puerto libre: {ultimo_error}")
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        log.info("Interfaz web en %s", self.url)
        return self.url

    def abrir_navegador(self, navegador: str = "") -> bool:
        """Abre la interfaz. En Brave/Chrome/Edge queda como ventana propia, sin barra."""
        from .navegador import abrir
        ok = abrir(self.url, navegador, modo_app=True)
        if not ok:
            print(f"\nNo pude abrir el navegador solo. Pegá esta dirección:\n  {self.url}\n")
        return ok
