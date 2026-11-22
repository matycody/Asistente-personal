"""Configuración de Jarvis.

Todo lo que quieras cambiar va en `config.json` (al lado de la carpeta `jarvis`).
Lo que pongas ahí se combina con esto: solo escribís lo que querés cambiar.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def data_dir() -> Path:
    """Carpeta donde Jarvis guarda log y pendientes."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jarvis"
    base.mkdir(parents=True, exist_ok=True)
    return base


def project_dir() -> Path:
    return Path(__file__).resolve().parent.parent


DEFAULT_CONFIG = {
    # Navegador para abrir páginas web ("" = el predeterminado de Windows)
    "browser": "brave",
    # Modelo de Whisper: tiny / base / small / medium (más grande = más preciso y más lento)
    "whisper_model": "small",
    # "auto" usa la placa de video si hay NVIDIA (mucho más rápido), si no la CPU
    "whisper_device": "auto",
    # Silencio (en segundos) que espera antes de dar la frase por terminada. Menos = más rápido.
    "silencio_final": 0.65,
    # Segundos que queda escuchando sin decir "Jarvis" después de un comando
    "followup_seconds": 6,
    # Cuánto más fuerte que el ruido de fondo tiene que ser tu voz. Subilo si se activa solo.
    "umbral_voz": 4.0,
    "hud": True,           # ventana con el estado
    "bandeja": True,       # ícono al lado del reloj
    "sonidos": True,       # pitido corto al activarse
    # Voz: "auto" usa Piper si está el modelo, si no la de Windows.
    # ritmo < 1 habla más rápido (Piper). velocidad = palabras por minuto (voz de Windows).
    "voz": {"motor": "auto", "modelo": "voces/es_MX-ald-medium.onnx",
            "genero": "masculina", "ritmo": 0.95, "velocidad": 185},
    # Órdenes libres con Ollama (https://ollama.com). Si no está instalado, se ignora sin problema.
    # keep_alive deja el modelo en memoria; contexto = cuántas vueltas recuerda.
    "llm": {"enabled": True, "model": "qwen2.5:3b", "url": "http://127.0.0.1:11434",
            "timeout": 25, "keep_alive": "30m", "num_predict": 160, "num_ctx": 2048,
            "contexto": 2, "precargar": True},
    # Para el clima del parte del día (Open-Meteo: gratis, sin clave, sin cuenta)
    "ubicacion": {"nombre": "Claypole", "lat": -34.80, "lon": -58.34,
                  "zona": "America/Argentina/Buenos_Aires"},
    "empleo": {
        "por_defecto": "programacion",
        # {q-} se reemplaza por la búsqueda con guiones, {q} por la búsqueda para parámetros
        "sitios": [
            "https://ar.computrabajo.com/trabajo-de-{q-}",
            "https://ar.indeed.com/q-{q-}-empleos.html",
            "https://ar.jooble.org/trabajo-{q-}",
            "https://www.linkedin.com/jobs/search/?keywords={q}",
        ],
        "perfiles": {
            "programacion": {"busqueda": "programador junior", "cv": ""},
            "electricidad": {"busqueda": "electricista", "cv": ""},
        },
    },
    "facultad": {"sitios": [], "carpetas": []},
    "apps": {
        "brave": "brave",
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "msedge",
        "firefox": "firefox",
        "explorador de archivos": "explorer",
        "explorador": "explorer",
        "calculadora": "calc",
        "bloc de notas": "notepad",
        "paint": "mspaint",
        "administrador de tareas": "taskmgr",
        "configuracion": "ms-settings:",
        "simbolo del sistema": "cmd",
        "cmd": "cmd",
        "powershell": "powershell",
        "terminal": "wt",
        "visual studio code": "code",
        "vscode": "code",
        "spotify": "spotify:",
        "discord": "discord:",
        "whatsapp": "whatsapp:",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
    },
    "folders": {
        "este equipo": "shell:MyComputerFolder",
        "mi pc": "shell:MyComputerFolder",
        "descargas": "~/Downloads",
        "documentos": "~/Documents",
        "escritorio": "~/Desktop",
        "imagenes": "~/Pictures",
        "fotos": "~/Pictures",
        "videos": "~/Videos",
        "musica": "~/Music",
        "papelera": "shell:RecycleBinFolder",
    },
    "sites": {
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "google": "https://www.google.com",
        "drive": "https://drive.google.com",
        "github": "https://github.com",
        "chatgpt": "https://chatgpt.com",
        "claude": "https://claude.ai",
        "whatsapp web": "https://web.whatsapp.com",
        "linkedin": "https://www.linkedin.com",
        "computrabajo": "https://ar.computrabajo.com",
        "indeed": "https://ar.indeed.com",
        "mercado libre": "https://www.mercadolibre.com.ar",
        "netflix": "https://www.netflix.com",
    },
}

# En estas secciones las claves son cosas que decís en voz alta: van en minúscula.
_SPOKEN = ("apps", "folders", "sites")


def _merge(base: dict, extra: dict, lower_keys: bool = False) -> dict:
    for key, value in extra.items():
        k = key.lower() if lower_keys else key
        if isinstance(value, dict) and isinstance(base.get(k), dict):
            _merge(base[k], value, lower_keys)
        else:
            base[k] = value
    return base


def load_config(path: str | os.PathLike | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # copia profunda
    path = Path(path) if path else project_dir() / "config.json"
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        for section, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(section), dict):
                _merge(cfg[section], value, lower_keys=section in _SPOKEN)
            else:
                cfg[section] = value
    return cfg
