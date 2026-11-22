"""Configuración por defecto de Jarvis.

Para agregar tus propias apps, carpetas o sitios editá `config.json` (al lado de
la carpeta `jarvis`). Lo que pongas ahí se suma a esto y pisa lo que se llame igual.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    # Navegador para abrir páginas web ("" = el predeterminado de Windows)
    "browser": "brave",
    # Modelo de Whisper: tiny / base / small / medium (más grande = más preciso y más lento)
    "whisper_model": "small",
    # Segundos que queda escuchando sin decir "Jarvis" después de un comando
    "followup_seconds": 6,
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
        "computrabajo": "https://www.computrabajo.com.ar",
        "zonajobs": "https://www.zonajobs.com.ar",
        "bumeran": "https://www.bumeran.com.ar",
        "mercado libre": "https://www.mercadolibre.com.ar",
        "netflix": "https://www.netflix.com",
    },
}


def load_config(path: str | os.PathLike | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # copia profunda
    path = Path(path) if path else Path(__file__).resolve().parent.parent / "config.json"
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update({k.lower(): v for k, v in value.items()})
            else:
                cfg[key] = value
    return cfg
