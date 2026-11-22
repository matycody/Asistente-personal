"""Uso:
    python -m jarvis                # escucha el micrófono y abre la interfaz web
    python -m jarvis --text         # escribís las órdenes en vez de hablarlas (para probar)
    python -m jarvis --dry-run      # no ejecuta nada de verdad, solo dice qué haría
    python -m jarvis --sin-hud      # sin interfaz (solo consola)
    python -m jarvis --banco        # mide qué tan rápido va en tu PC
    python -m jarvis --voz          # prueba la voz y dice qué motor anda
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

log = logging.getLogger("jarvis")


def setup_logging() -> None:
    logging.basicConfig(
        filename=data_dir() / "jarvis.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )


def armar(cfg: dict, args, ui, pausado: threading.Event):
    """Arma el asistente con todas sus partes y devuelve (speaker, assistant, procesar)."""
    from .llm import OllamaPlanner

    speaker = Speaker(cfg, enabled=not args.mute and not args.text, ui=ui)
    tareas = Tasks(cfg)
    ex = Executor(cfg, dry_run=args.dry_run, tasks=tareas, pausar=pausado.set)

    def al_despertar():
        if cfg.get("sonidos", True) and not args.text:
            beep("wake")
        ui.status("procesando")

    planner = OllamaPlanner(cfg)
    if cfg.get("llm", {}).get("precargar", True) and not args.text:
        planner.precalentar()   # deja el modelo en memoria mientras carga Whisper
    asistente = Assistant(cfg, ex, planner=planner, on_wake=al_despertar)

    turno = threading.Lock()   # que no se pisen el micrófono y la interfaz

    def refrescar_pendientes():
        if hasattr(ui, "pendientes"):
            try:
                ui.pendientes([i["texto"] for i in tareas._leer()])
            except Exception:
                log.debug("No pude refrescar pendientes", exc_info=True)

    def procesar(texto: str, de_voz: bool = True) -> None:
        """Atiende una orden, venga del micrófono o de la interfaz."""
        with turno:
            if not de_voz:
                ui.heard(texto)
                ui.status("procesando")
            respuestas = asistente.handle(texto)
            for r in respuestas:
                ui.status("hablando")
                speaker.say(r)
            refrescar_pendientes()
            ui.status("en pausa" if pausado.is_set() else "escuchando")

    return speaker, asistente, procesar, refrescar_pendientes


def bucle_voz(cfg, args, ui, pausado, parar, partes=None) -> None:
    """Escucha el micrófono hasta que se pida parar. Corre en su propio hilo."""
    speaker, asistente, procesar, refrescar = partes or armar(cfg, args, ui, pausado)
    try:
        from .listener import Listener
        ui.status("iniciando")
        ui.log("cargando el modelo de voz…")
        listener = Listener(cfg["whisper_model"], busy=speaker.busy,
                            umbral=cfg.get("umbral_voz", 4.0), pausado=pausado,
                            silencio_final=cfg.get("silencio_final", 0.65),
                            dispositivo=cfg.get("whisper_device", "auto"),
                            on_level=getattr(ui, "nivel", None))
    except Exception:
        log.exception("No pude iniciar el micrófono")
        ui.status("error")
        ui.log("no pude iniciar el micrófono (mirá el log)")
        return

    for _ in range(40):          # el motor de voz se elige en otro hilo
        if speaker.motor != "cargando":
            break
        import time as _t
        _t.sleep(0.05)
    if speaker.motor == "ninguno":
        ui.log("sin voz: corré  python -m jarvis --voz")
    if hasattr(ui, "info"):
        ui.info({
            "whisper": f"{cfg['whisper_model']} · {listener.device}",
            "llm": cfg["llm"]["model"] if cfg["llm"].get("enabled", True) else "apagado",
            "voz": speaker.motor,
            "detalle": {"Navegador": cfg.get("browser") or "el de Windows",
                        "Ubicación": cfg["ubicacion"]["nombre"],
                        "Órdenes fijas": "instantáneas",
                        "Modo": "simulación" if args.dry_run else "normal"},
        })
    refrescar()
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
            procesar(texto)
        except Exception:
            log.exception("Error procesando una frase")
            ui.status("error")
    ui.log("Jarvis se detuvo.")
    ui.close()


def modo_texto(cfg, args) -> None:
    ui = NullUI()
    speaker, asistente, procesar, _ = armar(cfg, args, ui, threading.Event())
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
    ap.add_argument("--sin-hud", dest="sin_hud", action="store_true", help="sin interfaz")
    ap.add_argument("--banco", action="store_true", help="medir velocidad en esta PC")
    ap.add_argument("--voz", action="store_true", help="probar la voz y diagnosticar")
    ap.add_argument("--fijar-voz", dest="fijar_voz", nargs=2, metavar=("MOTOR", "VOZ"),
                    help="guardar el motor y la voz en config.json")
    args = ap.parse_args()

    setup_logging()
    cfg = load_config()

    if args.fijar_voz:
        from .voz import fijar_voz
        return fijar_voz(*args.fijar_voz)
    if args.voz:
        from .voz import diagnostico
        return diagnostico()
    if args.banco:
        from .bench import correr
        return correr()
    if args.text:
        return modo_texto(cfg, args)

    pausado, parar = threading.Event(), threading.Event()
    cual = "ninguna" if args.sin_hud else cfg.get("interfaz", "web")
    if cual == "ventana" and not cfg.get("hud", True):
        cual = "ninguna"

    # ---------- interfaz web (la de siempre) ----------
    if cual == "web":
        from .webui import WebUI
        ui = WebUI(pausado, parar, puerto=int(cfg.get("puerto", 8777)))
        try:
            ui.iniciar()
        except Exception:
            log.exception("No pude levantar la interfaz web")
            print("No pude levantar la interfaz web; sigo sin ella.")
            ui = NullUI()
        else:
            partes = armar(cfg, args, ui, pausado)
            ui.on_orden = lambda t: partes[2](t, de_voz=False)
            if cfg.get("bandeja", True):
                from .tray import iniciar
                iniciar(pausado, parar, ui)
            if cfg.get("abrir_al_arrancar", True):
                ui.abrir_navegador(cfg.get("browser", ""))
            print(f"Interfaz: {ui.url}")
            return bucle_voz(cfg, args, ui, pausado, parar, partes)

    # ---------- ventana simple (tkinter) ----------
    if cual == "ventana":
        try:
            import tkinter  # noqa: F401
            from .hud import Hud
        except Exception:
            log.warning("Sin tkinter: sigo sin ventana.")
            cual = "ninguna"
        else:
            hud = Hud(pausado, parar)
            if cfg.get("bandeja", True):
                from .tray import iniciar
                iniciar(pausado, parar, hud)
            threading.Thread(target=bucle_voz, args=(cfg, args, hud, pausado, parar),
                             daemon=True).start()
            return hud.run()   # la ventana tiene que vivir en el hilo principal

    # ---------- sin interfaz ----------
    if cfg.get("bandeja", True):
        from .tray import iniciar
        iniciar(pausado, parar)
    return bucle_voz(cfg, args, NullUI(), pausado, parar)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
