"""Ejecuta intenciones en Windows. En otros sistemas (o con dry_run) solo simula."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from urllib.parse import quote_plus

from .commands import Intent
from .tasks import Tasks, fecha_larga, hora_corta

log = logging.getLogger("jarvis")
IS_WIN = sys.platform == "win32"

# Códigos de teclas virtuales de Windows
VK = {"mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF, "next": 0xB0, "prev": 0xB1,
      "play": 0xB3, "win": 0x5B, "d": 0x44, "alt": 0x12, "f4": 0x73, "shift": 0x10, "s": 0x53}


class Executor:
    def __init__(self, cfg: dict, dry_run: bool = False, tasks: Tasks | None = None,
                 pausar=None):
        self.cfg = cfg
        self.dry = dry_run or not IS_WIN
        self.done: list[str] = []  # registro de lo que se ejecutó (útil para tests)
        self.tasks = tasks if tasks is not None else Tasks(cfg, opener=self)
        self.tasks.opener = self
        self.pausar = pausar       # callback para dejar de escuchar

    # ---------- utilidades ----------
    def _record(self, what: str) -> None:
        self.done.append(what)
        log.info("ACCION %s%s", "[simulada] " if self.dry else "", what)

    def _tap(self, *keys: str) -> None:
        if self.dry:
            return
        import ctypes
        user32 = ctypes.windll.user32
        codes = [VK[k] for k in keys]
        for c in codes:
            user32.keybd_event(c, 0, 0, 0)
        for c in reversed(codes):
            user32.keybd_event(c, 0, 2, 0)

    def _start(self, *args: str) -> bool:
        """`start` de Windows: abre apps registradas, protocolos (spotify:) y carpetas."""
        if self.dry:
            return True
        r = subprocess.run(["cmd", "/c", "start", "", *args], capture_output=True)
        return r.returncode == 0

    # ---------- las usa también tasks.py ----------
    def open_url(self, url: str) -> bool:
        self._record(f"abrir web {url}")
        browser = (self.cfg.get("browser") or "").strip()
        if self.dry:
            return True
        if browser and self._start(browser, url):
            return True
        return webbrowser.open(url)

    def open_folder(self, path: str) -> bool:
        path = os.path.expanduser(path)
        self._record(f"abrir carpeta {path}")
        if self.dry:
            return True
        if not path.startswith("shell:") and not os.path.exists(path):
            return False
        return self._start("explorer", path)

    def open_file(self, path: str) -> bool:
        path = os.path.expanduser(path)
        self._record(f"abrir archivo {path}")
        if self.dry:
            return True
        if not os.path.exists(path):
            return False
        return self._start(path)

    # ---------- acciones ----------
    def run(self, it: Intent) -> str:
        k = it.kind
        if k == "open_path":
            path = os.path.expanduser(it.arg)
            es_archivo = not path.startswith("shell:") and os.path.isfile(path)
            ok = self.open_file(path) if es_archivo else self.open_folder(path)
            return f"Abriendo {it.label}." if ok else f"No encuentro {it.label}."
        if k == "open_app_id":
            # entradas del menú Inicio (incluidas las de la Store): shell:AppsFolder
            self._record(f"abrir app del menú {it.arg}")
            if self.dry:
                return f"Abriendo {it.label}."
            try:
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{it.arg}"])
                return f"Abriendo {it.label}."
            except Exception:
                log.exception("No pude abrir %s", it.arg)
                return f"No pude abrir {it.label}."
        if k == "open_shell":
            self._record(f"abrir {it.arg}")
            return f"Abriendo {it.label}." if self._start(it.arg) else f"No pude abrir {it.label}."
        if k == "open_steam":
            self._record(f"abrir juego de steam {it.arg}")
            ok = self._start(f"steam://rungameid/{it.arg}")
            return f"Abriendo {it.label}." if ok else f"No pude abrir {it.label}."
        if k == "open_app":
            self._record(f"abrir app {it.arg}")
            return f"Abriendo {it.label}." if self._start(*it.arg.split()) else f"No pude abrir {it.label}."
        if k == "open_url":
            return f"Abriendo {it.label}." if self.open_url(it.arg) else f"No pude abrir {it.label}."
        if k == "search":
            self.open_url("https://www.google.com/search?q=" + quote_plus(it.arg))
            return f"Buscando {it.arg}."
        if k == "search_youtube":
            self.open_url("https://www.youtube.com/results?search_query=" + quote_plus(it.arg))
            return f"Buscando {it.arg} en YouTube."

        # ---- tareas ----
        if k == "brief":
            self._record("parte del día")
            return self.tasks.parte()
        if k == "weather":
            self._record("clima")
            return self.tasks.clima()
        if k == "time":
            now = self.tasks.now()
            return f"Son las {hora_corta(now)} del {fecha_larga(now)}."
        if k == "note_add":
            self._record(f"anotar {it.arg}")
            return self.tasks.anotar(it.arg)
        if k == "note_list":
            self._record("leer pendientes")
            return self.tasks.pendientes()
        if k == "note_done":
            self._record(f"marcar pendiente {it.arg}")
            return self.tasks.listo(int(it.arg))
        if k == "note_clear":
            self._record("borrar pendientes")
            return self.tasks.borrar_pendientes()
        if k == "jobs":
            self._record(f"empleo {it.arg or 'por defecto'}")
            return self.tasks.empleo(it.arg)
        if k == "study":
            self._record("facultad")
            return self.tasks.facultad()
        if k == "pause_listening":
            self._record("pausar escucha")
            if self.pausar:
                self.pausar()
            return "Dejo de escuchar. Reanudame desde la ventana o el ícono."

        # ---- sistema ----
        if k == "volume_up":
            self._record("volumen +"); [self._tap("vol_up") for _ in range(5)]
            return "Listo."
        if k == "volume_down":
            self._record("volumen -"); [self._tap("vol_down") for _ in range(5)]
            return "Listo."
        if k == "mute":
            self._record("silencio"); self._tap("mute"); return "Listo."
        if k == "play_pause":
            self._record("play/pausa"); self._tap("play"); return "Listo."
        if k == "media_next":
            self._record("siguiente"); self._tap("next"); return "Listo."
        if k == "media_prev":
            self._record("anterior"); self._tap("prev"); return "Listo."
        if k == "show_desktop":
            self._record("mostrar escritorio"); self._tap("win", "d"); return "Listo."
        if k == "close_window":
            self._record("cerrar ventana"); self._tap("alt", "f4"); return "Cerrado."
        if k == "screenshot":
            self._record("captura"); self._tap("win", "shift", "s"); return "Elegí la zona."
        if k == "lock":
            self._record("bloquear")
            if not self.dry:
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Bloqueando."
        if k == "shutdown":
            self._record("apagar")
            if not self.dry:
                subprocess.run(["shutdown", "/s", "/t", "10"])
            return "Apagando en diez segundos."
        if k == "restart":
            self._record("reiniciar")
            if not self.dry:
                subprocess.run(["shutdown", "/r", "/t", "10"])
            return "Reiniciando en diez segundos."
        if k == "say":
            return it.arg
        if k == "unknown_target":
            return f"No sé abrir {it.arg}. Agregalo en config punto json."
        return "No entendí."
