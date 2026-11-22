"""Voz de Jarvis con las voces de Windows (SAPI), sin internet."""
from __future__ import annotations

import logging
import queue
import threading

log = logging.getLogger("jarvis")


class Speaker:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.busy = threading.Event()
        self.q: "queue.Queue[str | None]" = queue.Queue()
        if enabled:
            threading.Thread(target=self._worker, daemon=True).start()

    def say(self, text: str) -> None:
        log.info("JARVIS: %s", text)
        print(f"Jarvis: {text}")
        if self.enabled:
            self.busy.set()
            self.q.put(text)

    def _worker(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                blob = f"{v.id} {v.name}".lower()
                if any(t in blob for t in ("spanish", "es-", "es_", "sabina", "helena", "raul", "laura", "pablo")):
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 175)
        except Exception:
            log.exception("No pude iniciar la voz; sigo sin hablar")
            self.enabled = False
            self.busy.clear()
            return
        while True:
            text = self.q.get()
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                log.exception("Error al hablar")
            if self.q.empty():
                self.busy.clear()
