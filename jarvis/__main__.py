"""Uso:
    python -m jarvis                # escucha el micrófono y abre la ventana
    python -m jarvis --text         # escribís las órdenes en vez de hablarlas (para probar)
    python -m jarvis --dry-run      # no ejecuta nada de verdad, solo dice qué haría
    python -m jarvis --sin-hud      # sin ventana (solo consola)
    python -m jarvis --banco        # mide qué tan rápido va en tu PC
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading

from .actions import Executor
from .assistant import Assistant
from .config import data_dir, load_config
from .hud import NullUI
from .speaker import Speaker, beep
from .tasks import Tasks


def setup_logging() -> None:
    logging.basicConfig(
        filename=data_dir() / "jarvis.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )


def armar(cfg: dict, args, ui, pausado: threading.Event):
    """Arma el asistente con todas sus partes."""
    from .llm import OllamaPlanner

    speaker = Speaker(cfg, enabled=not args.mute and not args.text, ui=ui)
    ex = Executor(cfg, dry_run=args.dry_run, tasks=Tasks(cfg), pausar=pausado.set)

    def al_despertar():
        if cfg.get("sonidos", True) and not args.text:
            beep("wake")
        ui.status("procesando")

    planner = OllamaPlanner(cfg)
    if cfg.get("llm", {}).get("precargar", True) and not args.text:
        planner.precalentar()   # deja el modelo en memoria mientras carga Whisper
    asistente = Assistant(cfg, ex, planner=planner, on_wake=al_despertar)
    return speaker, asistente


def bucle_voz(cfg, args, ui, pausado: threading.Event, parar: threading.Event) -> None:
    """Escucha el micrófono hasta que se pida parar. Corre en su propio hilo."""
    log = logging.getLogger("jarvis")
    speaker, asistente = armar(cfg, args, ui, pausado)
    try:
        from .listener import Listener
        ui.status("iniciando")
        ui.log("cargando el modelo de voz…")
        listener = Listener(cfg["whisper_model"], busy=speaker.busy,
                            umbral=cfg.get("umbral_voz", 4.0), pausado=pausado,
                            silencio_final=cfg.get("silencio_final", 0.65),
                            dispositivo=cfg.get("whisper_device", "auto"))
    except Exception:
        log.exception("No pude iniciar el micrófono")
        ui.status("error")
        ui.log("no pude iniciar el micrófono (mirá el log)")
        return

    speaker.say("Jarvis en línea.")
    ui.status("escuchando")
    log.info("Escuchando...")
    for audio in listener.utterances(parar):
        if parar.is_set():
            break
        try:
            ui.status("procesando")
            texto = listener.transcribe(audio)
            if not texto:
                ui.status("en pausa" if pausado.is_set() else "escuchando")
                continue
            log.info("OIDO: %s", texto)
            ui.heard(texto)
            respuestas = asistente.handle(texto)
            for r in respuestas:
                ui.status("hablando")
                speaker.say(r)
            ui.status("en pausa" if pausado.is_set() else "escuchando")
        except Exception:
            log.exception("Error procesando una frase")
            ui.status("error")
    ui.log("Jarvis se detuvo.")
    ui.close()


def modo_texto(cfg, args) -> None:
    ui = NullUI()
    speaker, asistente = armar(cfg, args, ui, threading.Event())
    print("Modo texto. Escribí órdenes (ej: 'jarvis abrí brave'). Ctrl+C para salir.")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            return
        for reply in asistente.handle(line):
            speaker.say(reply)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="store_true", help="modo texto (sin micrófono)")
    ap.add_argument("--dry-run", action="store_true", help="simular acciones")
    ap.add_argument("--mute", action="store_true", help="sin voz de respuesta")
    ap.add_argument("--sin-hud", dest="sin_hud", action="store_true", help="sin ventana")
    ap.add_argument("--banco", action="store_true", help="medir velocidad en esta PC")
    args = ap.parse_args()

    setup_logging()
    cfg = load_config()

    if args.banco:
        from .bench import correr
        return correr()

    if args.text:
        return modo_texto(cfg, args)

    pausado, parar = threading.Event(), threading.Event()
    con_ventana = cfg.get("hud", True) and not args.sin_hud

    if not con_ventana:
        ui = NullUI()
        if cfg.get("bandeja", True):
            from .tray import iniciar
            iniciar(pausado, parar)
        return bucle_voz(cfg, args, ui, pausado, parar)

    try:
        import tkinter  # noqa: F401  (si falta, seguimos sin ventana)
        from .hud import Hud
    except Exception:
        logging.getLogger("jarvis").warning("Sin tkinter: sigo sin ventana.")
        print("Sin ventana (falta tkinter). Jarvis igual escucha.")
        return bucle_voz(cfg, args, NullUI(), pausado, parar)

    hud = Hud(pausado, parar)
    if cfg.get("bandeja", True):
        from .tray import iniciar
        iniciar(pausado, parar, hud)
    threading.Thread(target=bucle_voz, args=(cfg, args, hud, pausado, parar),
                     daemon=True).start()
    hud.run()   # la ventana tiene que vivir en el hilo principal


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
