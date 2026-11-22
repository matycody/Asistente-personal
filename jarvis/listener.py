"""Micrófono -> frases -> texto, todo local (faster-whisper)."""
from __future__ import annotations

import logging
import queue
import threading
from collections import deque

log = logging.getLogger("jarvis")

SAMPLE_RATE = 16000
BLOCK = 512  # ~32 ms
# Pista para que Whisper acierte mejor las palabras que más usamos
PROMPT = "Jarvis, abrí Brave. Abrí el explorador de archivos. Entrá al disco H. Subí el volumen."


class Listener:
    def __init__(self, model_size: str = "small", busy: threading.Event | None = None):
        from faster_whisper import WhisperModel  # import tardío: es pesado

        log.info("Cargando modelo Whisper '%s'...", model_size)
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.busy = busy or threading.Event()  # se activa mientras Jarvis habla
        self.q: "queue.Queue" = queue.Queue()

    def _callback(self, indata, frames, time_info, status):
        self.q.put(indata[:, 0].copy())

    def _rms(self, block) -> float:
        import numpy as np
        return float(np.sqrt(np.mean(block * block)))

    def utterances(self):
        """Genera un array de audio por cada frase que dices."""
        import numpy as np
        import sounddevice as sd

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=BLOCK, callback=self._callback):
            # calibrar ruido de fondo ~1 s
            noise = [self._rms(self.q.get()) for _ in range(30)]
            threshold = max(float(np.median(noise)) * 3.0, 0.012)
            log.info("Umbral de voz: %.4f", threshold)

            preroll = deque(maxlen=10)
            speech: list = []
            talking, silent, loud = False, 0, 0
            end_silence = int(0.9 * SAMPLE_RATE / BLOCK)
            max_blocks = int(12 * SAMPLE_RATE / BLOCK)

            while True:
                block = self.q.get()
                if self.busy.is_set():          # no me escucho a mí mismo
                    preroll.clear(); speech.clear(); talking = False
                    silent = loud = 0
                    continue
                level = self._rms(block)
                if not talking:
                    preroll.append(block)
                    loud = loud + 1 if level > threshold else 0
                    if loud >= 2:
                        talking, silent = True, 0
                        speech = list(preroll)
                else:
                    speech.append(block)
                    silent = silent + 1 if level < threshold else 0
                    if silent >= end_silence or len(speech) >= max_blocks:
                        audio = np.concatenate(speech)
                        talking, loud = False, 0
                        preroll.clear(); speech = []
                        if len(audio) > SAMPLE_RATE * 0.4:
                            yield audio

    def transcribe(self, audio) -> str:
        segments, _ = self.model.transcribe(
            audio, language="es", beam_size=1, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=PROMPT,
        )
        return " ".join(s.text.strip() for s in segments).strip()
