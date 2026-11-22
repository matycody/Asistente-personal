"""Micrófono -> frases -> texto, todo local (faster-whisper).

Whisper a veces "inventa" texto cuando solo hay ruido o silencio: siempre devuelve
algo, aunque no haya nadie hablando. Por eso acá se descarta una frase cuando el
audio fue muy corto o flojo, cuando el propio modelo dice que probablemente no hubo
voz, o cuando el texto es una de las muletillas típicas que inventa.
"""
from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
import unicodedata
from collections import deque

log = logging.getLogger("jarvis")

SAMPLE_RATE = 16000
BLOCK = 512  # ~32 ms
# Pista para que Whisper acierte mejor las palabras que más usamos
PROMPT = "Jarvis, abrí Brave. Abrí el explorador de archivos. Entrá al disco H. Subí el volumen."

# Frases que Whisper inventa cuando escucha ruido o silencio (vienen de subtítulos de videos)
BASURA = [
    "subtitulos realizados por", "subtitulado por", "amara.org", "gracias por ver",
    "suscribete", "suscribanse", "no olvides suscribirte", "hasta la proxima",
    "hasta el proximo video", "nos vemos en el proximo", "mas videos",
    "subtitles", "thanks for watching", "www.", ".com",
]
# Si lo único que se oyó es una de estas, es ruido (y no una orden)
SOLO_RUIDO = {"", "musica", "aplausos", "risas", "gracias", "si", "ah", "eh", "mmm", "oh"}


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9. ]+", " ", t).strip()


def es_alucinacion(texto: str) -> bool:
    """True si el texto parece inventado por el modelo y no algo que dijiste."""
    plano = _plano(texto)
    sin_puntos = plano.replace(".", "").strip()
    if sin_puntos in SOLO_RUIDO:
        return True
    if any(b in plano for b in BASURA):
        return True
    # Una sola palabra repetida ("gracias gracias gracias")
    palabras = sin_puntos.split()
    if len(palabras) >= 3 and len(set(palabras)) == 1:
        return True
    return False


def elegir_dispositivo(pedido: str = "auto") -> tuple[str, str]:
    """Devuelve (device, compute_type). Si hay GPU NVIDIA, Whisper vuela."""
    if pedido == "cpu":
        return "cpu", "int8"
    if pedido == "cuda":
        return "cuda", "float16"
    try:  # auto
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


class Listener:
    def __init__(self, model_size: str = "small", busy: threading.Event | None = None,
                 umbral: float = 4.0, pausado: threading.Event | None = None,
                 silencio_final: float = 0.65, dispositivo: str = "auto"):
        from faster_whisper import WhisperModel  # import tardío: es pesado

        device, compute = elegir_dispositivo(dispositivo)
        hilos = max(1, os.cpu_count() or 1)
        log.info("Cargando Whisper '%s' en %s (%s, %d hilos)...", model_size, device, compute, hilos)
        t0 = time.monotonic()
        self.model = WhisperModel(model_size, device=device, compute_type=compute,
                                  cpu_threads=hilos)
        self.device = device
        self.busy = busy or threading.Event()        # activo mientras Jarvis habla
        self.pausado = pausado or threading.Event()  # activo si el usuario pausó
        self.umbral_factor = umbral
        self.silencio_final = silencio_final
        self.umbral = 0.0
        self.q: "queue.Queue" = queue.Queue()
        self._precalentar()
        log.info("Whisper listo en %.1f s", time.monotonic() - t0)

    def _precalentar(self) -> None:
        """Primera transcripción en vacío: así la de verdad no paga el arranque."""
        try:
            import numpy as np
            list(self.model.transcribe(np.zeros(SAMPLE_RATE // 2, dtype="float32"),
                                       language="es", beam_size=1)[0])
        except Exception:
            log.debug("No pude precalentar Whisper", exc_info=True)

    def _callback(self, indata, frames, time_info, status):
        self.q.put(indata[:, 0].copy())

    def _rms(self, block) -> float:
        import numpy as np
        return float(np.sqrt(np.mean(block * block)))

    def utterances(self, stop: threading.Event | None = None):
        """Genera un array de audio por cada frase que decís."""
        import numpy as np
        import sounddevice as sd

        stop = stop or threading.Event()
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=BLOCK, callback=self._callback):
            # calibrar ruido de fondo ~1 s
            ruido = []
            while len(ruido) < 30 and not stop.is_set():
                try:
                    ruido.append(self._rms(self.q.get(timeout=0.5)))
                except queue.Empty:
                    continue
            if stop.is_set():
                return
            base = float(np.median(ruido)) if ruido else 0.0
            self.umbral = max(base * self.umbral_factor, 0.018)
            log.info("Ruido de fondo %.4f, umbral de voz %.4f", base, self.umbral)

            preroll = deque(maxlen=10)
            speech: list = []
            hablando, silencio, fuerte = False, 0, 0
            fin_silencio = max(8, int(self.silencio_final * SAMPLE_RATE / BLOCK))
            max_bloques = int(12 * SAMPLE_RATE / BLOCK)

            while not stop.is_set():
                try:
                    block = self.q.get(timeout=0.3)
                except queue.Empty:
                    continue
                if self.busy.is_set() or self.pausado.is_set():
                    # no me escucho a mí mismo, y si estoy en pausa descarto todo
                    preroll.clear(); speech.clear(); hablando = False
                    silencio = fuerte = 0
                    continue
                nivel = self._rms(block)
                if not hablando:
                    preroll.append(block)
                    # 3 bloques fuertes seguidos: un chasquido suelto no alcanza
                    fuerte = fuerte + 1 if nivel > self.umbral else 0
                    if fuerte >= 3:
                        hablando, silencio = True, 0
                        speech = list(preroll)
                else:
                    speech.append(block)
                    silencio = silencio + 1 if nivel < self.umbral else 0
                    if silencio >= fin_silencio or len(speech) >= max_bloques:
                        audio = np.concatenate(speech)
                        hablando, fuerte = False, 0
                        preroll.clear(); speech = []
                        # al menos medio segundo y con energía real
                        if len(audio) > SAMPLE_RATE * 0.5 and self._rms(audio) > self.umbral * 0.6:
                            yield audio

    def transcribe(self, audio) -> str:
        t0 = time.monotonic()
        segments, info = self.model.transcribe(
            audio, language="es", beam_size=1, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=PROMPT,
            without_timestamps=True,
        )
        partes, no_voz, logprob, n = [], 0.0, 0.0, 0
        for s in segments:
            partes.append(s.text.strip())
            no_voz = max(no_voz, getattr(s, "no_speech_prob", 0.0) or 0.0)
            logprob += getattr(s, "avg_logprob", 0.0) or 0.0
            n += 1
        texto = " ".join(p for p in partes if p).strip()
        log.info("Transcripción en %.2f s", time.monotonic() - t0)
        if not texto:
            return ""
        if no_voz > 0.6:
            log.info("DESCARTADO (probablemente no hubo voz, %.2f): %s", no_voz, texto)
            return ""
        if n and logprob / n < -1.0:
            log.info("DESCARTADO (el modelo dudó mucho): %s", texto)
            return ""
        if es_alucinacion(texto):
            log.info("DESCARTADO (frase inventada por el modelo): %s", texto)
            return ""
        return texto
