"""Voz de Jarvis.

Dos motores, los dos gratis y sin internet:
  - Piper: voz neural, suena natural. Hay que bajar el modelo una vez (voz_natural.bat).
  - SAPI: las voces que ya trae Windows. Es el respaldo si Piper no está.
"""
from __future__ import annotations

import logging
import queue
import sys
import threading

from .config import project_dir

log = logging.getLogger("jarvis")
IS_WIN = sys.platform == "win32"

# Pistas para elegir una voz masculina entre las que tenga instaladas Windows
MASCULINAS = ("pablo", "raul", "jorge", "diego", "miguel", "carlos", "male")
FEMENINAS = ("sabina", "helena", "laura", "elena", "female")
ESPANOL = ("spanish", "es-", "es_", "espa")


class _Piper:
    """Voz neural local. Lanza excepción si no se puede usar."""

    def __init__(self, modelo, ritmo: float = 1.0):
        from piper.voice import PiperVoice  # type: ignore
        self.voice = PiperVoice.load(str(modelo))
        self.rate = int(self.voice.config.sample_rate)
        self.ritmo = ritmo   # <1 habla más rápido

    def _chunks(self, texto: str):
        # La API de Piper cambió entre versiones: probamos las dos, con y sin ritmo.
        if hasattr(self.voice, "synthesize_stream_raw"):
            try:
                yield from self.voice.synthesize_stream_raw(texto, length_scale=self.ritmo)
            except TypeError:
                yield from self.voice.synthesize_stream_raw(texto)
            return
        for ch in self.voice.synthesize(texto):
            data = getattr(ch, "audio_int16_bytes", None)
            yield data if data is not None else bytes(ch)

    def say(self, texto: str) -> None:
        import numpy as np
        import sounddevice as sd
        partes = [np.frombuffer(c, dtype=np.int16) for c in self._chunks(texto) if c]
        if not partes:
            return
        sd.play(np.concatenate(partes), self.rate)
        sd.wait()


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


def elegir_voz_sapi(voces, genero: str = "masculina"):
    """De las voces de Windows, la mejor que haya: español y del género pedido."""
    quiere_m = genero.startswith("m")
    deseadas = MASCULINAS if quiere_m else FEMENINAS
    evitar = FEMENINAS if quiere_m else MASCULINAS
    espanolas = [v for v in voces
                 if any(t in f"{v.id} {v.name}".lower() for t in ESPANOL)]
    candidatas = espanolas or list(voces)
    for v in candidatas:
        blob = f"{v.id} {v.name}".lower()
        if any(t in blob for t in deseadas):
            return v
    for v in candidatas:
        blob = f"{v.id} {v.name}".lower()
        if not any(t in blob for t in evitar):
            return v
    return candidatas[0] if candidatas else None


class Speaker:
    def __init__(self, cfg: dict | None = None, enabled: bool = True, ui=None):
        self.cfg = cfg or {}
        self.opts = self.cfg.get("voz", {})
        self.enabled = enabled
        self.ui = ui
        self.busy = threading.Event()
        self.q: "queue.Queue[str | None]" = queue.Queue()
        self.motor = "ninguno"
        if enabled:
            threading.Thread(target=self._worker, daemon=True).start()

    def say(self, text: str) -> None:
        log.info("JARVIS: %s", text)
        print(f"Jarvis: {text}")
        if self.ui:
            self.ui.said(text)
        if self.enabled:
            self.busy.set()
            self.q.put(text)

    # ---------- motores ----------
    def _cargar_piper(self):
        modelo = self.opts.get("modelo", "")
        if not modelo:
            return None
        ruta = project_dir() / modelo
        if not ruta.exists():
            log.info("Piper: no está el modelo en %s, uso la voz de Windows.", ruta)
            return None
        try:
            motor = _Piper(ruta, float(self.opts.get("ritmo", 0.95)))
            log.info("Voz: Piper (%s)", ruta.name)
            self.motor = "piper"
            return motor
        except Exception as e:
            log.warning("Piper no se pudo cargar (%s). Uso la voz de Windows.", e)
            return None

    def _cargar_sapi(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            elegida = elegir_voz_sapi(engine.getProperty("voices"),
                                      self.opts.get("genero", "masculina"))
            if elegida is not None:
                engine.setProperty("voice", elegida.id)
                log.info("Voz: SAPI (%s)", elegida.name)
            else:
                log.info("Voz: SAPI (la predeterminada)")
            engine.setProperty("rate", int(self.opts.get("velocidad", 185)))
            self.motor = "sapi"

            class _Sapi:
                def say(self, texto: str) -> None:
                    engine.say(texto)
                    engine.runAndWait()
            return _Sapi()
        except Exception:
            log.exception("No pude iniciar ninguna voz; sigo sin hablar")
            return None

    def _worker(self) -> None:
        pedido = self.opts.get("motor", "auto")
        motor = None
        if pedido in ("auto", "piper"):
            motor = self._cargar_piper()
        if motor is None and pedido != "piper":
            motor = self._cargar_sapi()
        if motor is None:
            self.enabled = False
            self.busy.clear()
            return
        while True:
            text = self.q.get()
            try:
                motor.say(text)
            except Exception:
                log.exception("Error al hablar")
            if self.q.empty():
                self.busy.clear()
