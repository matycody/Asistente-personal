"""La voz de Jarvis: elige el mejor motor disponible y habla en segundo plano."""
from __future__ import annotations

import logging
import queue
import sys
import threading

from .config import project_dir
from .voz import (VozEdge, VozPiper, VozPowerShell, VozPyttsx3, elegir_voz,
                  listar_voces_windows)

log = logging.getLogger("jarvis")
IS_WIN = sys.platform == "win32"


def beep(tipo: str = "wake") -> None:
    """Pitido corto para saber que te escuchó, sin tener que mirar la pantalla."""
    if not IS_WIN:
        return
    try:
        import winsound
        if tipo == "wake":
            winsound.Beep(1100, 70)
        elif tipo == "error":
            winsound.Beep(380, 120)
        else:
            winsound.Beep(760, 60)
    except Exception:
        pass


def construir_motor(opts: dict, avisar=log.info):
    """Devuelve (motor, nombre, errores). motor es None si ninguno anduvo."""
    pedido = (opts.get("motor") or "auto").lower()
    errores: list[tuple[str, str]] = []

    def intento(nombre, fabrica):
        try:
            return fabrica(), nombre
        except Exception as e:
            errores.append((nombre, str(e)[:200]))
            avisar("Voz: %s no se pudo usar (%s)", nombre, str(e)[:200])
            return None, nombre

    # "edge" cae a los locales si no hay internet; "auto" nunca sale de la PC
    orden = {"auto": ["piper", "powershell", "pyttsx3"],
             "edge": ["edge", "piper", "powershell", "pyttsx3"],
             "piper": ["piper"], "powershell": ["powershell"], "sapi": ["powershell"],
             "pyttsx3": ["pyttsx3"]}.get(pedido, ["piper", "powershell", "pyttsx3"])

    voz_elegida = None
    if "powershell" in orden or "pyttsx3" in orden:
        voz_elegida = opts.get("nombre_voz") or None

    for nombre in orden:
        if nombre == "edge":
            motor, _ = intento("edge", lambda: VozEdge(
                opts.get("nombre_voz") or "es-AR-TomasNeural",
                int(opts.get("velocidad", 185))))
        elif nombre == "piper":
            ruta = project_dir() / opts.get("modelo", "")
            if not opts.get("modelo") or not ruta.exists():
                errores.append(("piper", f"no está el modelo en {ruta}"))
                continue
            motor, _ = intento("piper", lambda: VozPiper(ruta, float(opts.get("ritmo", 0.95))))
        elif nombre == "powershell":
            if voz_elegida is None:
                try:
                    voces = listar_voces_windows()
                    voz_elegida = elegir_voz(voces, opts.get("genero", "masculina"))
                    log.info("Voces de Windows: %s", [v[0] for v in voces] or "ninguna")
                except Exception as e:
                    errores.append(("listar voces", str(e)[:200]))
                    voz_elegida = None
            motor, _ = intento("powershell", lambda: VozPowerShell(
                voz_elegida, int(opts.get("velocidad", 185))))
        else:
            motor, _ = intento("pyttsx3", lambda: VozPyttsx3(
                voz_elegida, int(opts.get("velocidad", 185))))
        if motor is not None:
            log.info("Voz: %s (%s)", nombre, getattr(motor, "voz", "") or "predeterminada")
            return motor, nombre, errores
    return None, "ninguno", errores


class Speaker:
    def __init__(self, cfg: dict | None = None, enabled: bool = True, ui=None):
        self.cfg = cfg or {}
        self.opts = self.cfg.get("voz", {})
        self.enabled = enabled
        self.ui = ui
        self.busy = threading.Event()
        self.q: "queue.Queue[str]" = queue.Queue()
        self.motor = "cargando"
        self.errores: list[tuple[str, str]] = []
        if enabled:
            threading.Thread(target=self._worker, daemon=True).start()
        else:
            self.motor = "apagada"

    def say(self, text: str) -> None:
        log.info("JARVIS: %s", text)
        print(f"Jarvis: {text}")
        if self.ui:
            self.ui.said(text)
        if self.enabled:
            self.busy.set()
            self.q.put(text)

    def _worker(self) -> None:
        motor, nombre, errores = construir_motor(self.opts)
        self.motor, self.errores = nombre, errores
        if motor is None:
            detalle = "; ".join(f"{m}: {e}" for m, e in errores) or "sin motores"
            log.error("NO HAY VOZ. %s", detalle)
            print("\n*** Jarvis no puede hablar. Probá:  python -m jarvis --voz\n")
            if self.ui:
                self.ui.log("sin voz — probá: python -m jarvis --voz")
            self.enabled = False
            self.busy.clear()
            return
        if self.ui:
            self.ui.log(f"voz: {nombre}")
        while True:
            text = self.q.get()
            try:
                motor.say(text)
            except Exception:
                log.exception("Error al hablar")
                # si el motor se murió (por ejemplo cerraron el PowerShell), probamos otro
                motor, self.motor, _ = construir_motor(self.opts)
                if motor is None:
                    self.enabled = False
                    self.busy.clear()
                    return
            if self.q.empty():
                self.busy.clear()
