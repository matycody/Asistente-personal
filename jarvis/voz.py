"""Motores de voz para Windows, del más confiable al menos.

1. Piper        — voz neural local (si bajaste el modelo con voz_natural.bat).
2. PowerShell   — System.Speech, que viene con Windows. No necesita instalar nada.
                  Se deja UN proceso abierto y se le pasan los textos, así no paga el
                  arranque de PowerShell en cada frase.
3. pyttsx3      — el paquete de Python. Anda, pero a veces se queda mudo cuando se lo
                  usa desde un hilo que no es el principal (problema conocido de COM).

Cada motor levanta excepción si no se puede usar, y Speaker pasa al siguiente.
"""
from __future__ import annotations

import atexit
import base64
import logging
import subprocess
import sys

log = logging.getLogger("jarvis")
IS_WIN = sys.platform == "win32"

# Pistas para elegir una voz masculina entre las instaladas
MASCULINAS = ("pablo", "raul", "raúl", "jorge", "diego", "miguel", "carlos", "male", "hombre")
FEMENINAS = ("sabina", "helena", "laura", "elena", "female", "mujer")
ESPANOL = ("spanish", "español", "es-", "es_")

_SIN_VENTANA = 0x08000000 if IS_WIN else 0   # CREATE_NO_WINDOW


def _ps(script: str, entrada: str | None = None, timeout: int = 25) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        input=entrada, capture_output=True, text=True, timeout=timeout,
        creationflags=_SIN_VENTANA)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "powershell falló").strip()[:300])
    return r.stdout


def listar_voces_windows() -> list[tuple[str, str, str]]:
    """[(nombre, idioma, género)] de las voces instaladas en Windows."""
    if not IS_WIN:
        return []
    salida = _ps(
        "Add-Type -AssemblyName System.Speech;"
        "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices()"
        " | ForEach-Object { $i = $_.VoiceInfo;"
        " Write-Output ($i.Name + '|' + $i.Culture.Name + '|' + $i.Gender) }")
    voces = []
    for linea in salida.splitlines():
        partes = linea.strip().split("|")
        if len(partes) == 3 and partes[0]:
            voces.append((partes[0], partes[1], partes[2]))
    return voces


def elegir_voz(voces: list[tuple[str, str, str]], genero: str = "masculina") -> str | None:
    """De las voces instaladas, la mejor: en español y del género pedido."""
    if not voces:
        return None
    quiere_m = genero.lower().startswith("m")
    espanolas = [v for v in voces
                 if v[1].lower().startswith("es") or any(t in v[0].lower() for t in ESPANOL)]
    candidatas = espanolas or voces
    # 1) lo que dice Windows sobre el género
    objetivo = "male" if quiere_m else "female"
    for v in candidatas:
        if v[2].lower() == objetivo:
            return v[0]
    # 2) por el nombre
    deseadas = MASCULINAS if quiere_m else FEMENINAS
    for v in candidatas:
        if any(t in v[0].lower() for t in deseadas):
            return v[0]
    # 3) al menos que no sea del género contrario
    evitar = FEMENINAS if quiere_m else MASCULINAS
    for v in candidatas:
        if not any(t in v[0].lower() for t in evitar):
            return v[0]
    return candidatas[0][0]


def _ritmo_sapi(palabras_por_minuto: int) -> int:
    """System.Speech usa -10..10; 0 es más o menos 200 palabras por minuto."""
    return max(-10, min(10, round((palabras_por_minuto - 200) / 22)))


class VozPowerShell:
    """Deja un PowerShell abierto esperando textos. Es el motor por defecto en Windows."""

    GUION = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.Rate={ritmo};"
        "{seleccion}"
        "[Console]::Out.WriteLine('listo');[Console]::Out.Flush();"
        "while($true){{"
        " $l=[Console]::In.ReadLine();"
        " if($l -eq $null){{break}};"
        " if($l.Trim() -eq ''){{continue}};"
        " $t=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($l));"
        " $s.Speak($t);"
        " [Console]::Out.WriteLine('ok');[Console]::Out.Flush()"
        "}}"
    )

    def __init__(self, voz: str | None = None, velocidad: int = 185):
        if not IS_WIN:
            raise RuntimeError("System.Speech es solo de Windows")
        seleccion = ""
        if voz:
            seguro = voz.replace("'", "''")
            seleccion = f"try{{$s.SelectVoice('{seguro}')}}catch{{}};"
        guion = self.GUION.format(ritmo=_ritmo_sapi(velocidad), seleccion=seleccion)
        self.proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", guion],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, creationflags=_SIN_VENTANA)
        saludo = self.proc.stdout.readline().strip()
        if saludo != "listo":
            err = (self.proc.stderr.read() or "")[:300] if self.proc.poll() is not None else ""
            self.cerrar()
            raise RuntimeError(f"PowerShell no arrancó la voz: {saludo} {err}".strip())
        self.voz = voz
        atexit.register(self.cerrar)

    def say(self, texto: str) -> None:
        if self.proc.poll() is not None:
            raise RuntimeError("el proceso de voz se cerró")
        dato = base64.b64encode(texto.encode("utf-8")).decode("ascii")
        self.proc.stdin.write(dato + "\n")
        self.proc.stdin.flush()
        self.proc.stdout.readline()   # espera el 'ok': así no se pisa con el micrófono

    def cerrar(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


class VozPyttsx3:
    def __init__(self, voz: str | None = None, velocidad: int = 185):
        if IS_WIN:   # COM necesita estar iniciado en este hilo
            try:
                import comtypes
                comtypes.CoInitialize()
            except Exception:
                log.debug("No pude iniciar COM para pyttsx3", exc_info=True)
        import pyttsx3
        self.engine = pyttsx3.init()
        if voz:
            for v in self.engine.getProperty("voices"):
                if voz.lower() in f"{v.id} {v.name}".lower():
                    self.engine.setProperty("voice", v.id)
                    break
        self.engine.setProperty("rate", int(velocidad))
        self.voz = voz

    def say(self, texto: str) -> None:
        self.engine.say(texto)
        self.engine.runAndWait()


class VozPiper:
    """Voz neural local. Necesita el modelo bajado con voz_natural.bat."""

    def __init__(self, modelo, ritmo: float = 0.95):
        from piper.voice import PiperVoice  # type: ignore
        self.voice = PiperVoice.load(str(modelo))
        self.rate = int(self.voice.config.sample_rate)
        self.ritmo = ritmo   # menos de 1 habla más rápido
        self.voz = str(modelo)

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


# ---------------------------------------------------------------- diagnóstico
def diagnostico() -> None:
    """`python -m jarvis --voz`: prueba cada motor y dice qué anda y qué no."""
    from .config import load_config, project_dir

    cfg = load_config()
    opts = cfg.get("voz", {})
    print("\n" + "=" * 58)
    print(" PRUEBA DE VOZ")
    print("=" * 58)
    print(f"\nSistema: {sys.platform}")
    print(f"Config:  motor={opts.get('motor', 'auto')}  genero={opts.get('genero', 'masculina')}"
          f"  velocidad={opts.get('velocidad', 185)}")

    # --- voces de Windows ---
    print("\n1) Voces instaladas en Windows")
    voces = []
    try:
        voces = listar_voces_windows()
    except Exception as e:
        print(f"   No pude listarlas: {e}")
    if not voces:
        print("   NINGUNA. Agregá una desde Configuración > Hora e idioma > Voz > Agregar voces.")
    for n, c, g in voces:
        marca = "  <- español" if c.lower().startswith("es") else ""
        print(f"   · {n}  ({c}, {g}){marca}")
    if voces:
        print(f"\n   Elegiría para voz masculina: {elegir_voz(voces, 'masculina')}")
        print(f"   Elegiría para voz femenina:  {elegir_voz(voces, 'femenina')}")

    # --- modelo de Piper ---
    print("\n2) Voz neural (Piper)")
    modelo = opts.get("modelo", "")
    ruta = project_dir() / modelo if modelo else None
    if ruta and ruta.exists():
        print(f"   Modelo encontrado: {ruta.name}")
    else:
        print(f"   Sin modelo ({ruta}). Corré voz_natural.bat si la querés.")

    # --- probar cada motor ---
    frase = "Hola Matías, soy Jarvis. Si escuchás esto, la voz funciona."
    print("\n3) Probando los motores (deberías ESCUCHAR cada uno)")
    anduvo = []
    for nombre, fabrica in [
        ("piper", lambda: VozPiper(ruta, float(opts.get("ritmo", 0.95)))
            if ruta and ruta.exists() else None),
        ("powershell", lambda: VozPowerShell(
            elegir_voz(voces, opts.get("genero", "masculina")) if voces else None,
            int(opts.get("velocidad", 185)))),
        ("pyttsx3", lambda: VozPyttsx3(
            elegir_voz(voces, opts.get("genero", "masculina")) if voces else None,
            int(opts.get("velocidad", 185)))),
    ]:
        print(f"\n   [{nombre}] ", end="", flush=True)
        try:
            motor = fabrica()
            if motor is None:
                print("salteado (no está disponible)")
                continue
            motor.say(frase)
            print("sonó bien")
            anduvo.append(nombre)
            if hasattr(motor, "cerrar"):
                motor.cerrar()
        except Exception as e:
            print(f"FALLÓ -> {str(e)[:220]}")

    # --- conclusión ---
    print("\n" + "=" * 58)
    if not anduvo:
        print(" NINGÚN MOTOR FUNCIONÓ")
        print(" Revisá, en este orden:")
        print("  1. Que el volumen de Windows no esté en silencio.")
        print("  2. Que haya al menos una voz instalada (punto 1 de arriba).")
        print("  3. Pegame todo este texto y lo resolvemos.")
    else:
        print(f" FUNCIONAN: {', '.join(anduvo)}")
        if anduvo[0] != "piper":
            print(f'\n Para fijar el que anda, en config.json:')
            print(f'   "voz": {{ "motor": "{anduvo[0]}" }}')
        print("\n Si escuchaste alguno pero Jarvis sigue mudo, pegame el final de")
        print("   %LOCALAPPDATA%\\Jarvis\\jarvis.log")
    print("=" * 58 + "\n")
