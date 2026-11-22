"""Motores de voz para Windows.

0. Edge         — las voces neurales de Microsoft Edge. Son las que mejor suenan y hay
                  una argentina de hombre (Tomás). Gratis y sin cuenta ni clave, pero
                  NO es local: manda el texto de las respuestas a Microsoft para que se
                  lo devuelva hablado. Lo que decís por el micrófono nunca sale de tu PC.
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

# Voces neurales en español de Edge, las mejores primero para un argentino
VOCES_EDGE = [
    ("es-AR-TomasNeural", "Argentina", "Male"),
    ("es-AR-ElenaNeural", "Argentina", "Female"),
    ("es-MX-JorgeNeural", "México", "Male"),
    ("es-CO-GonzaloNeural", "Colombia", "Male"),
    ("es-ES-AlvaroNeural", "España", "Male"),
    ("es-MX-DaliaNeural", "México", "Female"),
    ("es-ES-ElviraNeural", "España", "Female"),
]


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


def _candidatas(voces: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Las voces en español; si no hay ninguna, todas."""
    espanolas = [v for v in voces
                 if v[1].lower().startswith("es") or any(t in v[0].lower() for t in ESPANOL)]
    return espanolas or voces


def hay_del_genero(voces: list[tuple[str, str, str]], genero: str = "masculina") -> bool:
    """¿Hay voz del género pedido ENTRE LAS QUE SE USARÍAN? Mira el mismo conjunto
    que elegir_voz, así el aviso no miente cuando hay una masculina pero en inglés."""
    quiere_m = genero.lower().startswith("m")
    objetivo = "male" if quiere_m else "female"
    deseadas = MASCULINAS if quiere_m else FEMENINAS
    for n, _c, g in _candidatas(voces):
        if g.lower() == objetivo or any(t in n.lower() for t in deseadas):
            return True
    return False


def elegir_voz(voces: list[tuple[str, str, str]], genero: str = "masculina") -> str | None:
    """De las voces instaladas, la mejor: en español y del género pedido."""
    if not voces:
        return None
    quiere_m = genero.lower().startswith("m")
    candidatas = _candidatas(voces)
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


def reproducir_mp3(datos: bytes) -> None:
    """Reproduce un mp3 que está en memoria. Prueba tres caminos: el primero que ande."""
    if not datos:
        return
    # 1) soundfile + sounddevice: todo en memoria, es el más rápido
    try:
        import io
        import sounddevice as sd
        import soundfile as sf
        audio, sr = sf.read(io.BytesIO(datos), dtype="float32")
        sd.play(audio, sr)
        sd.wait()
        return
    except Exception as e:
        log.debug("soundfile no pudo con el mp3 (%s)", e)
    # 2) miniaudio, si está
    try:
        import miniaudio
        import numpy as np
        import sounddevice as sd
        dec = miniaudio.decode(datos)
        sd.play(np.frombuffer(dec.samples, dtype="int16").reshape(-1, dec.nchannels),
                dec.sample_rate)
        sd.wait()
        return
    except Exception as e:
        log.debug("miniaudio no pudo con el mp3 (%s)", e)
    # 3) Windows: archivo temporal + MediaPlayer. Siempre está, pero es más lento.
    if not IS_WIN:
        raise RuntimeError("no encontré con qué reproducir el audio")
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(datos)
        ruta = f.name.replace("'", "''")
    guion = (
        "Add-Type -AssemblyName PresentationCore;"
        "$p=New-Object System.Windows.Media.MediaPlayer;"
        "$p.Open([uri]'" + ruta + "');"
        "$n=0; while(-not $p.NaturalDuration.HasTimeSpan -and $n -lt 60)"
        "{ Start-Sleep -Milliseconds 50; $n++ };"
        "if($p.NaturalDuration.HasTimeSpan)"
        "{ $d=$p.NaturalDuration.TimeSpan.TotalMilliseconds } else { $d=3000 };"
        "$p.Play(); Start-Sleep -Milliseconds ([int]$d + 250); $p.Close()"
    )
    try:
        _ps(guion, timeout=90)
    finally:
        try:
            os.unlink(f.name)
        except Exception:
            pass


class VozEdge:
    """Voces neurales de Microsoft Edge. Gratis, sin clave, pero pasan por internet."""

    def __init__(self, voz: str = "es-AR-TomasNeural", velocidad: int = 185):
        import edge_tts  # noqa: F401  (si no está, Speaker pasa al siguiente motor)
        self.voz = voz
        porcentaje = max(-50, min(100, round((velocidad - 185) / 185 * 100)))
        self.rate = f"{porcentaje:+d}%"
        # Probamos la conexión y el nombre de la voz acá, sin reproducir nada: si no hay
        # internet, Speaker pasa a un motor local en vez de fallar en cada frase.
        if not self._audio("Hola"):
            raise RuntimeError("Edge no devolvió audio (¿sin internet?)")

    def _audio(self, texto: str) -> bytes:
        import asyncio

        import edge_tts

        async def traer() -> bytes:
            partes = []
            com = edge_tts.Communicate(texto, self.voz, rate=self.rate)
            async for ch in com.stream():
                if ch["type"] == "audio":
                    partes.append(ch["data"])
            return b"".join(partes)

        return asyncio.run(traer())

    def say(self, texto: str) -> None:
        texto = texto.strip()
        if not texto:
            return
        reproducir_mp3(self._audio(texto))


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


# ---------------------------------------------------------------- guardar la elección
def fijar_voz(motor: str, voz: str = "") -> None:
    """Guarda el motor y la voz en config.json sin pisar el resto. Lo usa voz_natural.bat."""
    import json

    from .config import project_dir

    ruta = project_dir() / "config.json"
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    except Exception:
        datos = {}
    cfg = datos.setdefault("voz", {})
    cfg["motor"] = motor
    # limpiamos lo que no corresponda, para que no quede una voz vieja dando vueltas
    cfg.pop("nombre_voz", None)
    if motor == "piper":
        cfg["modelo"] = voz
    elif motor == "edge":
        cfg["nombre_voz"] = voz
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado en config.json: motor={motor} voz={voz or '(la que elija sola)'}")


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
    quiere = opts.get("genero", "masculina")
    if voces:
        print(f"\n   Elegiría para voz masculina: {elegir_voz(voces, 'masculina')}")
        print(f"   Elegiría para voz femenina:  {elegir_voz(voces, 'femenina')}")
        if not hay_del_genero(voces, quiere):
            print(f"\n   *** No tenés instalada NINGUNA voz {quiere} en Windows.")
            print("   *** Por eso vas a escuchar una del otro género.")
            print("   *** Solución: corré voz_natural.bat y elegí la opción 1.")

    # --- Edge ---
    print("\n2) Voces neurales de Edge (las que mejor suenan)")
    try:
        import edge_tts  # noqa: F401
        print("   edge-tts instalado. Voces en español:")
        for n, pais, g in VOCES_EDGE:
            print(f"   · {n:24} {pais}, {'hombre' if g == 'Male' else 'mujer'}")
    except Exception:
        print("   edge-tts NO instalado. Corré voz_natural.bat y elegí la opción 1.")

    # --- modelo de Piper ---
    print("\n3) Voz neural local (Piper)")
    modelo = opts.get("modelo", "")
    ruta = project_dir() / modelo if modelo else None
    if ruta and ruta.exists():
        print(f"   Modelo encontrado: {ruta.name}")
    else:
        print(f"   Sin modelo ({ruta}). Corré voz_natural.bat si la querés.")

    # --- probar cada motor ---
    frase = "Hola, soy Jarvis. Si escuchás esto, la voz funciona."
    print("\n4) Probando los motores (tenés que ESCUCHAR cada uno)")
    elegida = elegir_voz(voces, quiere) if voces else None
    anduvo = []
    for nombre, fabrica in [
        ("edge", lambda: VozEdge(opts.get("nombre_voz") or "es-AR-TomasNeural",
                                 int(opts.get("velocidad", 185)))),
        ("piper", lambda: VozPiper(ruta, float(opts.get("ritmo", 0.95)))
            if ruta and ruta.exists() else None),
        ("powershell", lambda: VozPowerShell(elegida, int(opts.get("velocidad", 185)))),
        ("pyttsx3", lambda: VozPyttsx3(elegida, int(opts.get("velocidad", 185)))),
    ]:
        print(f"\n   [{nombre}] ", end="", flush=True)
        try:
            motor = fabrica()
            if motor is None:
                print("salteado (no está disponible)")
                continue
            motor.say(frase)
            usada = getattr(motor, "voz", None) or "la predeterminada"
            print(f"arrancó sin error, con la voz: {usada}")
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
        print(f" ARRANCARON SIN ERROR: {', '.join(anduvo)}")
        print(" (si no escuchaste nada, revisá el volumen y la salida de audio)")
        if voces and not hay_del_genero(voces, quiere):
            print(f"\n LA VOZ VA A SONAR DEL OTRO GÉNERO: no tenés ninguna voz {quiere}")
            print(" instalada en Windows. Corré voz_natural.bat y elegí la opción 1")
            print(" para bajar una voz masculina neural (63 MB, gratis, local).")
        if "edge" not in anduvo:
            print("\n Para la mejor voz (Tomás, argentino): corré voz_natural.bat, opción 1.")
        print(f'\n Para fijar el que anda, en config.json:')
        print(f'   "voz": {{ "motor": "{anduvo[0]}" }}')
        print("\n Si escuchaste alguno pero Jarvis sigue mudo, pegame el final de")
        print("   %LOCALAPPDATA%\\Jarvis\\jarvis.log")
    print("=" * 58 + "\n")
