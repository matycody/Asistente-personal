"""Tareas de Jarvis: parte del día, clima, pendientes, empleo y facultad.

El clima sale de Open-Meteo, que es gratis y no pide clave ni cuenta.
Los pendientes se guardan en un archivo tuyo, en %LOCALAPPDATA%\\Jarvis.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime

from .config import data_dir

log = logging.getLogger("jarvis")

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Códigos de Open-Meteo (WMO) agrupados en algo que se pueda decir en voz alta
CIELO = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "con niebla", 48: "con niebla", 51: "con llovizna", 53: "con llovizna",
    55: "con llovizna fuerte", 56: "con llovizna helada", 57: "con llovizna helada",
    61: "con lluvia leve", 63: "con lluvia", 65: "con lluvia fuerte",
    66: "con lluvia helada", 67: "con lluvia helada", 71: "con nieve", 73: "con nieve",
    75: "con mucha nieve", 77: "con granizo", 80: "con chaparrones",
    81: "con chaparrones", 82: "con chaparrones fuertes", 85: "con nevadas",
    86: "con nevadas", 95: "con tormenta", 96: "con tormenta y granizo",
    99: "con tormenta y granizo",
}


def fecha_larga(now: datetime) -> str:
    return f"{DIAS[now.weekday()]} {now.day} de {MESES[now.month - 1]}"


def hora_corta(now: datetime) -> str:
    return now.strftime("%H:%M")


def saludo(now: datetime) -> str:
    h = now.hour
    if h < 6:
        return "Buenas noches"
    if h < 13:
        return "Buen día"
    if h < 20:
        return "Buenas tardes"
    return "Buenas noches"


def _http_json(url: str, timeout: float = 10) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class Tasks:
    """Las tareas. `opener` es el Executor, que sabe abrir webs y carpetas."""

    def __init__(self, cfg: dict, opener=None, http=_http_json, now=datetime.now):
        self.cfg = cfg
        self.opener = opener
        self.http = http
        self.now = now
        self.file = data_dir() / "pendientes.json"

    # ---------- clima ----------
    def clima(self) -> str:
        u = self.cfg["ubicacion"]
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={u['lat']}&longitude={u['lon']}"
            "&current=temperature_2m,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&timezone={urllib.parse.quote(u['zona'])}&forecast_days=1"
        )
        try:
            d = self.http(url)
            cur, day = d["current"], d["daily"]
            cielo = CIELO.get(int(cur["weather_code"]), "")
            partes = [f"En {u['nombre']} hay {round(cur['temperature_2m'])} grados"]
            if cielo:
                partes.append(cielo)
            texto = ", ".join(partes) + "."
            lluvia = day["precipitation_probability_max"][0]
            texto += (f" Máxima {round(day['temperature_2m_max'][0])},"
                      f" mínima {round(day['temperature_2m_min'][0])}.")
            if lluvia is not None and lluvia >= 30:
                texto += f" {round(lluvia)} por ciento de probabilidad de lluvia, llevá paraguas."
            return texto
        except Exception as e:
            log.warning("No pude traer el clima: %s", e)
            return "No pude traer el clima."

    # ---------- pendientes ----------
    def _leer(self) -> list[dict]:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _guardar(self, items: list[dict]) -> None:
        self.file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def anotar(self, texto: str) -> str:
        texto = texto.strip()
        if not texto:
            return "¿Qué querés que anote?"
        items = self._leer()
        items.append({"texto": texto, "fecha": self.now().isoformat(timespec="minutes")})
        self._guardar(items)
        return f"Anotado: {texto}."

    def pendientes(self, prefijo: str = "") -> str:
        items = self._leer()
        if not items:
            return "No tenés pendientes."
        partes = [f"{i}. {it['texto']}" for i, it in enumerate(items[:10], 1)]
        cabeza = prefijo or (f"Tenés {len(items)} pendiente." if len(items) == 1
                             else f"Tenés {len(items)} pendientes.")
        return cabeza + " " + " ".join(partes)

    def listo(self, numero: int) -> str:
        items = self._leer()
        if not 1 <= numero <= len(items):
            return f"No tengo un pendiente número {numero}."
        hecho = items.pop(numero - 1)
        self._guardar(items)
        return f"Listo: {hecho['texto']}."

    def borrar_pendientes(self) -> str:
        self._guardar([])
        return "Borré todos los pendientes."

    # ---------- parte del día ----------
    def parte(self) -> str:
        now = self.now()
        texto = f"{saludo(now)}. Hoy es {fecha_larga(now)}, son las {hora_corta(now)}. "
        texto += self.clima() + " "
        items = self._leer()
        if not items:
            texto += "No tenés pendientes anotados."
        else:
            texto += self.pendientes()
        return texto

    # ---------- empleo ----------
    def empleo(self, perfil: str = "") -> str:
        cfg = self.cfg["empleo"]
        perfiles = cfg["perfiles"]
        nombre = perfil.strip().lower() or cfg["por_defecto"]
        if nombre not in perfiles:
            # "programación" -> "programacion", o la primera que empiece igual
            nombre = next((k for k in perfiles if k.startswith(nombre[:5])), cfg["por_defecto"])
        datos = perfiles[nombre]
        # {q} = para parámetros (?keywords=programador+junior)
        # {q-} = para rutas con guiones (/trabajo-de-programador-junior)
        q = urllib.parse.quote_plus(datos["busqueda"])
        q_guiones = urllib.parse.quote(datos["busqueda"].strip().replace(" ", "-"))
        abiertos = 0
        for plantilla in cfg["sitios"]:
            url = plantilla.replace("{q-}", q_guiones).replace("{q}", q)
            if self.opener and self.opener.open_url(url):
                abiertos += 1
        if datos.get("cv") and self.opener:
            self.opener.open_file(datos["cv"])
        if not abiertos:
            return "No pude abrir las búsquedas de empleo."
        return f"Abrí {abiertos} búsquedas de {nombre}: {datos['busqueda']}."

    # ---------- facultad ----------
    def facultad(self) -> str:
        cfg = self.cfg["facultad"]
        if not cfg["sitios"] and not cfg["carpetas"]:
            return "Todavía no cargaste nada de la facultad en config punto json."
        n = 0
        for url in cfg["sitios"]:
            if self.opener and self.opener.open_url(url):
                n += 1
        for carpeta in cfg["carpetas"]:
            if self.opener and self.opener.open_folder(carpeta):
                n += 1
        return f"Abrí {n} cosas de la facultad." if n else "No pude abrir nada de la facultad."
