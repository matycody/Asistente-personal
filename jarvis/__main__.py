"""Uso:
    python -m jarvis            # modo normal: escucha el micrófono
    python -m jarvis --text     # escribís las órdenes en vez de hablarlas (para probar)
    python -m jarvis --dry-run  # no ejecuta nada de verdad, solo muestra qué haría
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .actions import Executor
from .assistant import Assistant
from .config import load_config
from .speaker import Speaker


def setup_logging() -> None:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jarvis"
    base.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=base / "jarvis.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="store_true", help="modo texto (sin micrófono)")
    ap.add_argument("--dry-run", action="store_true", help="simular acciones")
    ap.add_argument("--mute", action="store_true", help="sin voz de respuesta")
    args = ap.parse_args()

    setup_logging()
    log = logging.getLogger("jarvis")
    cfg = load_config()
    speaker = Speaker(enabled=not args.mute and not args.text)
    assistant = Assistant(cfg, Executor(cfg, dry_run=args.dry_run))

    if args.text:
        print("Modo texto. Escribí órdenes (ej: 'jarvis abrí brave'). Ctrl+C para salir.")
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                return
            for reply in assistant.handle(line):
                speaker.say(reply)

    from .listener import Listener
    listener = Listener(cfg["whisper_model"], busy=speaker.busy)
    speaker.say("Jarvis en línea.")
    log.info("Escuchando...")
    for audio in listener.utterances():
        try:
            text = listener.transcribe(audio)
            if not text:
                continue
            log.info("OIDO: %s", text)
            for reply in assistant.handle(text):
                speaker.say(reply)
        except Exception:
            log.exception("Error procesando una frase")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
