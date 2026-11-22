"""Índice de todo lo que se puede abrir en esta PC.

Junta, en un solo lugar:
  · todo lo que aparece en el menú Inicio (programas de escritorio y de la Store)
  · los accesos directos del escritorio
  · los juegos de Steam, con su identificador para lanzarlos
  · los discos conectados, con su etiqueta
  · carpetas del sistema (papelera, descargas, panel de control…)

Se guarda en %LOCALAPPDATA%\\Jarvis\\indice.json y se rearma con:
    python -m jarvis --indexar
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

from .config import data_dir
from .texto import norm

log = logging.getLogger("jarvis")
IS_WIN = sys.platform == "win32"

# Entradas del menú Inicio que no sirven como orden de voz
BASURA = ("uninstall", "desinstalar", "readme", "leeme", "manual", "documentation",
          "documentacion", "ayuda de", "help", "licencia", "license", "sitio web",
          "website", "changelog", "release notes", "modify", "reparar", "repair")

CARPETAS_SISTEMA = {
    "papelera": "shell:RecycleBinFolder",
    "papelera de reciclaje": "shell:RecycleBinFolder",
    "este equipo": "shell:MyComputerFolder",
    "mi pc": "shell:MyComputerFolder",
    "panel de control": "shell:ControlPanelFolder",
    "impresoras": "shell:PrintersFolder",
    "programas instalados": "shell:AppsFolder",
    "inicio": "shell:Startup",
    "descargas": "shell:Downloads",
    "documentos": "shell:Personal",
    "escritorio": "shell:Desktop",
    "imagenes": "shell:My Pictures",
    "fotos": "shell:My Pictures",
    "videos": "shell:My Video",
    "musica": "shell:My Music",
}


# ---------------------------------------------------------------- claves
def claves(titulo: str) -> list[str]:
    """Varias formas de nombrar lo mismo: 'eFootball™ 2024' -> efootball 2024, efootball."""
    base = norm(titulo)
    if not base:
        return []
    salida = [base]
    # sin la parte después de un guion o dos puntos: "Brave - Navegador" -> "brave"
    # (se corta sobre el título original, porque norm() se come los guiones)
    corto = norm(re.split(r"\s+[-–—]\s+|:\s+", re.sub(r"[™®©]", "", titulo))[0])
    if corto and corto != base:
        salida.append(corto)
    # sin año ni número de versión al final: "efootball 2024" -> "efootball"
    sin_version = re.sub(r"\s+(?:v?\d[\d.]*|20\d\d)$", "", base).strip()
    if sin_version and sin_version not in salida and len(sin_version) >= 3:
        salida.append(sin_version)
    return salida


def _ps_json(script: str, timeout: int = 60):
    from .powershell import correr
    salida = correr(script, timeout=timeout).strip()
    if not salida:
        raise RuntimeError("sin salida")
    datos = json.loads(salida)
    return datos if isinstance(datos, list) else [datos]


# ---------------------------------------------------------------- fuentes
def apps_menu_inicio() -> dict[str, dict]:
    """Todo lo del menú Inicio, incluidas las apps de la Store."""
    if not IS_WIN:
        return {}
    salida = {}
    for app in _ps_json("Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"):
        nombre, appid = app.get("Name"), app.get("AppID")
        if not nombre or not appid:
            continue
        if any(b in nombre.lower() for b in BASURA):
            continue
        for k in claves(nombre):
            salida.setdefault(k, {"titulo": nombre, "tipo": "app", "destino": appid})
    return salida


def accesos_directos() -> dict[str, dict]:
    """Los .lnk del escritorio y del menú Inicio (por si alguno no sale en Get-StartApps)."""
    if not IS_WIN:
        return {}
    carpetas = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path.home() / "Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
        Path.home() / "OneDrive/Escritorio",
    ]
    salida = {}
    for carpeta in carpetas:
        if not carpeta.is_dir():
            continue
        try:
            for lnk in carpeta.rglob("*.lnk"):
                nombre = lnk.stem
                if any(b in nombre.lower() for b in BASURA):
                    continue
                for k in claves(nombre):
                    salida.setdefault(k, {"titulo": nombre, "tipo": "lnk",
                                          "destino": str(lnk)})
        except OSError:
            log.debug("No pude recorrer %s", carpeta, exc_info=True)
    return salida


def _carpeta_steam() -> Path | None:
    if not IS_WIN:
        return None
    import winreg
    for raiz, ruta, clave in [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]:
        try:
            with winreg.OpenKey(raiz, ruta) as k:
                valor, _ = winreg.QueryValueEx(k, clave)
                p = Path(valor)
                if p.is_dir():
                    return p
        except OSError:
            continue
    return None


def bibliotecas_steam(texto_vdf: str) -> list[str]:
    """Saca las carpetas de biblioteca de libraryfolders.vdf."""
    return [m.group(1).replace("\\\\", "\\")
            for m in re.finditer(r'"path"\s+"([^"]+)"', texto_vdf)]


def juego_de_manifiesto(texto_acf: str) -> tuple[str, str] | None:
    """(appid, nombre) de un appmanifest_*.acf de Steam."""
    appid = re.search(r'"appid"\s+"(\d+)"', texto_acf, re.I)
    nombre = re.search(r'"name"\s+"([^"]*)"', texto_acf, re.I)
    if not appid or not nombre or not nombre.group(1).strip():
        return None
    return appid.group(1), nombre.group(1).strip()


def juegos_steam() -> dict[str, dict]:
    """Los juegos instalados de Steam. Se lanzan con steam://rungameid/<id>."""
    raiz = _carpeta_steam()
    if not raiz:
        return {}
    carpetas = [raiz]
    vdf = raiz / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        try:
            for ruta in bibliotecas_steam(vdf.read_text(encoding="utf-8", errors="ignore")):
                p = Path(ruta)
                if p.is_dir() and p not in carpetas:
                    carpetas.append(p)
        except OSError:
            log.debug("No pude leer libraryfolders.vdf", exc_info=True)
    salida = {}
    for carpeta in carpetas:
        apps = carpeta / "steamapps"
        if not apps.is_dir():
            continue
        for acf in apps.glob("appmanifest_*.acf"):
            try:
                juego = juego_de_manifiesto(acf.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if not juego:
                continue
            appid, nombre = juego
            # Las herramientas de Steam no son juegos
            if nombre.lower().startswith(("steamworks", "steam linux", "proton")):
                continue
            for k in claves(nombre):
                salida[k] = {"titulo": nombre, "tipo": "steam", "destino": appid}
    return salida


def discos() -> dict[str, dict]:
    """Los discos conectados, por letra y por etiqueta."""
    if not IS_WIN:
        return {}
    import ctypes
    import string
    salida = {}
    try:
        mapa = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return {}
    for i, letra in enumerate(string.ascii_uppercase):
        if not (mapa >> i) & 1:
            continue
        raiz = f"{letra}:\\"
        etiqueta = ""
        try:
            buf = ctypes.create_unicode_buffer(261)
            if ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(raiz), buf, 261, None, None, None, None, 0):
                etiqueta = buf.value.strip()
        except Exception:
            pass
        titulo = f"disco {letra}" + (f" ({etiqueta})" if etiqueta else "")
        salida[f"disco {letra.lower()}"] = {"titulo": titulo, "tipo": "carpeta",
                                            "destino": raiz}
        if etiqueta:
            for k in claves(etiqueta):
                salida.setdefault(k, {"titulo": titulo, "tipo": "carpeta", "destino": raiz})
    return salida


def carpetas_sistema() -> dict[str, dict]:
    return {k: {"titulo": k, "tipo": "carpeta", "destino": v}
            for k, v in CARPETAS_SISTEMA.items()}


# ---------------------------------------------------------------- índice
def ruta_indice() -> Path:
    return data_dir() / "indice.json"


def escanear(avisar=lambda *_: None) -> dict[str, dict]:
    """Recorre todas las fuentes. Si una falla, sigue con las demás."""
    indice: dict[str, dict] = {}
    # el orden importa: lo de abajo pisa a lo de arriba
    for nombre, fuente in [("accesos directos", accesos_directos),
                           ("menú Inicio", apps_menu_inicio),
                           ("carpetas del sistema", carpetas_sistema),
                           ("discos", discos),
                           ("juegos de Steam", juegos_steam)]:
        try:
            encontrado = fuente()
            indice.update(encontrado)
            avisar(f"   {nombre}: {len(encontrado)}")
        except Exception as e:
            avisar(f"   {nombre}: falló ({str(e)[:90]})")
            log.debug("Falló la fuente %s", nombre, exc_info=True)
    return indice


_cache: dict[str, dict] | None = None


def cargar(recargar: bool = False) -> dict[str, dict]:
    global _cache
    if _cache is not None and not recargar:
        return _cache
    try:
        _cache = json.loads(ruta_indice().read_text(encoding="utf-8"))
    except Exception:
        _cache = {}
    return _cache


def guardar(indice: dict[str, dict]) -> None:
    global _cache
    ruta_indice().write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    _cache = indice


def reindexar(avisar=print) -> dict[str, dict]:
    avisar("Buscando todo lo que hay en la PC...")
    indice = escanear(avisar)
    guardar(indice)
    avisar(f"Listo: {len(indice)} cosas que Jarvis puede abrir.")
    return indice


def buscar(nombre: str) -> dict | None:
    """Busca algo por nombre: exacto, por palabras, o pareciéndose."""
    import difflib
    ind = cargar()
    if not ind:
        return None
    n = norm(nombre)
    if not n:
        return None
    if n in ind:
        return ind[n]
    # que la orden contenga la clave entera ("abrir el efootball" -> "efootball"),
    # quedándonos con la clave más larga, que es la más específica
    mejor, largo = None, 0
    for clave, dato in ind.items():
        if len(clave) > largo and re.search(rf"\b{re.escape(clave)}\b", n):
            mejor, largo = dato, len(clave)
    if mejor:
        return mejor
    # por último, parecido; con el índice lleno de nombres hay que ser exigente
    cerca = difflib.get_close_matches(n, list(ind), n=1, cutoff=0.86)
    return ind[cerca[0]] if cerca else None
