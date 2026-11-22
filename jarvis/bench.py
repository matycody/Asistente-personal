"""Mide cuánto tarda Jarvis en tu PC y te dice qué conviene cambiar.

    python -m jarvis --banco
"""
from __future__ import annotations

import json
import time
import urllib.request

from .config import load_config
from .listener import SAMPLE_RATE, Listener, elegir_dispositivo
from .llm import OllamaPlanner


def _seg(t0: float) -> float:
    return time.monotonic() - t0


def _modelos_ollama(url: str) -> list[str]:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


def medir_escucha(cfg: dict) -> float | None:
    """Graba 3 segundos tuyos y mide lo que tarda en pasarlos a texto."""
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as e:
        print(f"   No puedo usar el micrófono: {e}")
        return None

    device, compute = elegir_dispositivo(cfg.get("whisper_device", "auto"))
    print(f"   Dispositivo: {device} ({compute})")
    t0 = time.monotonic()
    oyente = Listener(cfg["whisper_model"], umbral=cfg.get("umbral_voz", 4.0),
                      dispositivo=cfg.get("whisper_device", "auto"))
    print(f"   Cargar el modelo '{cfg['whisper_model']}': {_seg(t0):.1f} s (una sola vez al arrancar)")

    print("\n   Decí ahora, fuerte y claro: «Jarvis, abrí Brave»")
    for n in (3, 2, 1):
        print(f"   {n}...", end="", flush=True)
        time.sleep(0.6)
    print(" grabando 3 segundos")
    audio = sd.rec(int(3 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    t0 = time.monotonic()
    texto = oyente.transcribe(np.squeeze(audio))
    tardo = _seg(t0)
    print(f"   Entendió: «{texto or '(nada)'}»")
    print(f"   Tiempo en entender: {tardo:.2f} s")
    return tardo


def medir_modelo(cfg: dict) -> float | None:
    planner = OllamaPlanner(cfg)
    url = cfg["llm"].get("url", "http://127.0.0.1:11434")
    modelos = _modelos_ollama(url)
    if not modelos:
        print("   Ollama no responde. Las órdenes libres están apagadas (Jarvis igual funciona).")
        return None
    print(f"   Modelos instalados: {', '.join(modelos)}")
    print(f"   Usando: {planner.modelo}")

    t0 = time.monotonic()
    planner.plan("llevame a lo que baje hoy")
    primera = _seg(t0)
    t0 = time.monotonic()
    planner.plan("abrime el correo")
    segunda = _seg(t0)
    print(f"   Primera orden (carga el modelo): {primera:.1f} s")
    print(f"   Siguientes órdenes:              {segunda:.1f} s")
    return segunda


def consejos(escucha: float | None, modelo: float | None, cfg: dict) -> None:
    print("\n" + "=" * 58)
    print(" QUÉ CONVIENE CAMBIAR")
    print("=" * 58)
    hay = False
    if escucha is not None:
        if escucha > 2.0:
            hay = True
            print(f'\n • Entender tu voz tarda {escucha:.1f} s. Probá un modelo más chico:')
            print('     "whisper_model": "base"     en config.json')
            print("   Si tenés placa NVIDIA, instalá CUDA y va a volar sola.")
        elif escucha > 1.0:
            print(f"\n • Escucha: {escucha:.1f} s. Está bien. Si querés más, probá \"base\".")
        else:
            print(f"\n • Escucha: {escucha:.1f} s. Muy bien, no toques nada.")
    if modelo is not None:
        if modelo > 8:
            hay = True
            print(f'\n • El modelo tarda {modelo:.0f} s por orden libre. Es mucho. Opciones:')
            print('     ollama pull qwen2.5:1.5b   y  "llm": {"model": "qwen2.5:1.5b"}')
            print('     o apagalo:                    "llm": {"enabled": false}')
            print("   Las órdenes de las tablas del README siguen siendo instantáneas.")
        elif modelo > 4:
            hay = True
            print(f'\n • El modelo tarda {modelo:.0f} s. Aceptable. Si lo querés más ágil:')
            print('     ollama pull qwen2.5:1.5b')
        else:
            print(f"\n • Órdenes libres: {modelo:.1f} s. Muy bien.")
            print('   Si querés que entienda MEJOR y tenés RAM de sobra:')
            print('     ollama pull qwen2.5:7b     y  "llm": {"model": "qwen2.5:7b"}')
    if not hay:
        print("\n Todo en orden.")
    print()


def correr() -> None:
    cfg = load_config()
    print("\n" + "=" * 58)
    print(" BANCO DE PRUEBAS DE JARVIS")
    print("=" * 58)
    print("\n1) Escucha (Whisper)")
    escucha = medir_escucha(cfg)
    print("\n2) Órdenes libres (Ollama)")
    modelo = medir_modelo(cfg)
    consejos(escucha, modelo, cfg)
