"""Voz de Jarvis.

Dos motores, los dos gratis y sin internet:
  - Piper: voz neural, suena natural. Hay que bajar el modelo una vez (bajar_voz.bat).
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


class _Piper:
    """Voz neural local. Devuelve False si no se puede usar."""

    def __init__(self, modelo: str):
        from piper.voice import PiperVoice  # type: ignore
        import sounddevice as sd  # noqa: F401  (se usa al hablar)
        self.voice = PiperVoice.load(str(modelo))
        self.rate = int(self.voice.config.sample_rate)

    def _chunks(self, texto: str):
        # La API de Piper cambió entre versiones: soportamos las dos.
        if hasattr(self.voice, "synthesize_stream_raw"):
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
            motor = _Piper(ruta)
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
            for v in engine.getProperty("voices"):
                blob = f"{v.id} {v.name}".lower()
                if any(t in blob for t in ("spanish", "es-", "es_", "sabina", "helena",
                                           "raul", "laura", "pablo")):
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", int(self.opts.get("velocidad", 175)))
            log.info("Voz: SAPI (Windows)")
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
