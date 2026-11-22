"""Encontrar y abrir el navegador de verdad.

Lanzarlo con `start brave` falla calladito cuando "brave" no está en el PATH: el
comando devuelve bien y no se abre nada. Por eso acá se busca el ejecutable
(registro de Windows y carpetas típicas) y se lo lanza directo, así se puede saber
si anduvo o no.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path, PureWindowsPath

log = logging.getLogger("jarvis")
IS_WIN = sys.platform == "win32"

# nombre que decís -> ejecutable
EJECUTABLES = {
    "brave": "brave.exe",
    "chrome": "chrome.exe", "google chrome": "chrome.exe",
    "edge": "msedge.exe", "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "opera": "opera.exe",
    "vivaldi": "vivaldi.exe",
}

# carpetas donde suelen instalarse, relativas a estas variables de entorno
CARPETAS = {
    "brave.exe": ["BraveSoftware/Brave-Browser/Application"],
    "chrome.exe": ["Google/Chrome/Application"],
    "msedge.exe": ["Microsoft/Edge/Application"],
    "firefox.exe": ["Mozilla Firefox"],
    "opera.exe": ["Opera", "Programs/Opera"],
    "vivaldi.exe": ["Vivaldi/Application"],
}
BASES = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA", "PROGRAMW6432")

# Los que aceptan --app= abren una ventana limpia, sin barra de direcciones
CON_MODO_APP = {"brave.exe", "chrome.exe", "msedge.exe", "vivaldi.exe", "opera.exe"}


def _del_registro(exe: str) -> str | None:
    """App Paths: ahí Windows anota dónde quedó instalado cada programa."""
    if not IS_WIN:
        return None
    import winreg
    rutas = [r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\" + exe,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\\" + exe]
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for ruta in rutas:
            try:
                with winreg.OpenKey(raiz, ruta) as k:
                    valor, _ = winreg.QueryValueEx(k, "")
                    valor = str(valor).strip('"')
                    if valor and Path(valor).is_file():
                        return valor
            except OSError:
                continue
    return None


def candidatos(exe: str, entorno: dict | None = None) -> list[str]:
    """Rutas donde podría estar, sin fijarse todavía si existen."""
    entorno = entorno if entorno is not None else os.environ
    salida = []
    for base in BASES:
        raiz = entorno.get(base)
        if not raiz:
            continue
        for sub in CARPETAS.get(exe, []):
            # PureWindowsPath y no Path: son rutas de Windows, se armen donde se armen
            salida.append(str(PureWindowsPath(raiz, *sub.split("/"), exe)))
    return salida


def ruta_de(nombre: str, existe=None, entorno: dict | None = None,
            usar_registro: bool = True) -> str | None:
    """Devuelve la ruta del navegador, o None si no está instalado.

    `existe`, `entorno` y `usar_registro` están para poder probarlo sin Windows.
    """
    if existe is None:
        existe = lambda ruta: Path(ruta).is_file()   # noqa: E731
    nombre = (nombre or "").strip()
    exe = EJECUTABLES.get(nombre.lower())
    if not exe:
        # te pasaste la ruta completa, o un ejecutable que no conozco
        if nombre.lower().endswith(".exe") and existe(nombre):
            return nombre
        return None
    if usar_registro:
        del_registro = _del_registro(exe)
        if del_registro:
            return del_registro
    for ruta in candidatos(exe, entorno):
        if existe(ruta):
            return ruta
    return None


def abrir(url: str, navegador: str = "", modo_app: bool = False) -> bool:
    """Abre la dirección. Devuelve True solo si realmente se lanzó algo."""
    ruta = ruta_de(navegador) if navegador else None
    if ruta:
        exe = PureWindowsPath(ruta).name.lower()
        args = [ruta]
        if modo_app and exe in CON_MODO_APP:
            args.append(f"--app={url}")
        else:
            args.append(url)
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            log.warning("No pude lanzar %s", ruta, exc_info=True)
    elif navegador:
        log.info("No encontré el navegador '%s'; uso el predeterminado.", navegador)
    # el predeterminado del sistema
    try:
        import webbrowser
        return bool(webbrowser.open(url))
    except Exception:
        log.warning("No pude abrir el navegador", exc_info=True)
        return False
