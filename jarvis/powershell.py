"""Correr PowerShell sin que la codificación rompa nada.

Windows devuelve la salida en la codificación de la consola, que no siempre es UTF-8:
puede ser cp1252, o UTF-16 con BOM. Si se le fuerza UTF-8 a ciegas, un solo acento
tira todo abajo con un UnicodeDecodeError. Por eso acá se lee en bytes y se prueba
cada codificación hasta que una entra.
"""
from __future__ import annotations

import subprocess
import sys

IS_WIN = sys.platform == "win32"
SIN_VENTANA = 0x08000000 if IS_WIN else 0   # CREATE_NO_WINDOW

# Le pedimos a PowerShell que escriba en UTF-8; igual después decodificamos con red.
PREFIJO = ("$ErrorActionPreference='Stop';"
           "try{[Console]::OutputEncoding=[System.Text.Encoding]::UTF8}catch{};")


def decodificar(datos: bytes) -> str:
    """Bytes de PowerShell -> texto, pase lo que pase."""
    if not datos:
        return ""
    if datos.startswith(b"\xff\xfe"):
        return datos[2:].decode("utf-16-le", errors="replace")
    if datos.startswith(b"\xfe\xff"):
        return datos[2:].decode("utf-16-be", errors="replace")
    for codificacion in ("utf-8", "cp1252", "latin-1"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


def correr(script: str, entrada: str | None = None, timeout: int = 25,
           con_prefijo: bool = True) -> str:
    """Ejecuta un script y devuelve su salida. Levanta RuntimeError si falla."""
    if not IS_WIN:
        raise RuntimeError("PowerShell es solo de Windows")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         (PREFIJO + script) if con_prefijo else script],
        input=entrada.encode("utf-8") if entrada is not None else None,
        capture_output=True, timeout=timeout, creationflags=SIN_VENTANA)
    if r.returncode != 0:
        raise RuntimeError(decodificar(r.stderr).strip()[:300] or "powershell falló")
    return decodificar(r.stdout)
