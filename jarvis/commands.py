"""Convierte frases en español en intenciones (Intent). No ejecuta nada."""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass


@dataclass
class Intent:
    kind: str          # open_path, open_app, open_url, search, volume_up, ... unknown_target
    arg: str = ""
    raw: str = ""
    label: str = ""    # nombre lindo para responder ("Brave", "disco H")


WAKE_RE = re.compile(
    r"\b(?:jarvis|yarvis|jarvi|jarbis|yarbis|jarves|charvis|jarvys|harvis|yarvi)\b"
)

OPEN_VERBS = (
    "abri|abre|abrir|abrime|abrame|ejecuta|ejecutar|inicia|iniciar|lanza|lanzar|"
    "arranca|corre|prende|pone|poneme"
)
NAV_VERBS = (
    "entra|entrar|anda|andate|ir|ve|vamos|navega|navegar|mostrame|muestrame|muestra|"
    "metete|meteme"
)
ALL_VERBS = f"{OPEN_VERBS}|{NAV_VERBS}|busca|buscar|buscame|googlea|investiga|subi|sube|subir|baja|bajar|" \
            "cerra|cierra|cerrar|minimiza|bloquea|apaga|reinicia|silencia|mutea|pausa|reproduci|captura"

# Cómo se dicen las letras de disco
LETTER_NAMES = {"ce": "c", "de": "d", "efe": "f", "ge": "g", "hache": "h", "ache": "h",
                "jota": "j", "ka": "k", "ele": "l", "eme": "m"}

DRIVE_RE = re.compile(r"\b(?:disco|unidad|drive|particion)\s+(?:local\s+)?([a-z]{1,5})\b")

FILLER_RE = re.compile(r"\b(?:por favor|porfa|porfis|quiero que|podes|podrias|ahora|dale)\b")

NUMEROS = {"uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
           "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
           "primero": 1, "segundo": 2, "tercero": 3}


def _numero(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return NUMEROS.get(token)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9: ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_wake(text: str) -> tuple[bool, str]:
    """Devuelve (había palabra de activación, resto de la frase normalizado)."""
    n = norm(text)
    m = WAKE_RE.search(n)
    if not m:
        return False, n
    return True, (n[m.end():]).strip()


def split_commands(text: str) -> list[str]:
    """'abri el explorador y entra al disco h' -> dos comandos."""
    pattern = rf"\s+(?:(?:y\s+)?(?:luego|despues|ademas)|y)\s+(?=(?:{ALL_VERBS})\b)"
    parts = re.split(pattern, text)
    return [p.strip() for p in parts if p.strip()]


def _drive_letter(token: str) -> str | None:
    token = LETTER_NAMES.get(token, token)
    return token if len(token) == 1 and token.isalpha() else None


def _targets(cfg: dict) -> dict[str, tuple[str, str]]:
    table: dict[str, tuple[str, str]] = {}
    for key, val in cfg["sites"].items():
        table[norm(key)] = ("open_url", val)
    for key, val in cfg["folders"].items():
        table[norm(key)] = ("open_path", val)
    for key, val in cfg["apps"].items():
        table[norm(key)] = ("open_app", val)
    return table


def resolve_target(target: str, cfg: dict) -> Intent:
    t = re.sub(r"^(?:el|la|los|las|un|una|mi|me|carpeta|programa|aplicacion|app|pagina|sitio|de)\s+", "", target)
    t = re.sub(r"^(?:el|la|mi)\s+", "", t).strip()

    m = DRIVE_RE.search(t)
    if m:
        letter = _drive_letter(m.group(1))
        if letter:
            return Intent("open_path", f"{letter.upper()}:\\", label=f"disco {letter.upper()}")

    table = _targets(cfg)
    if t in table:
        kind, val = table[t]
        return Intent(kind, val, label=t)
    # coincidencia por palabra completa, probando primero los nombres más largos
    for key in sorted(table, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", t):
            kind, val = table[key]
            return Intent(kind, val, label=key)
    # tolerancia a errores del reconocimiento ("brev", "explorador de archivo")
    close = difflib.get_close_matches(t, list(table), n=1, cutoff=0.65)
    if close:
        kind, val = table[close[0]]
        return Intent(kind, val, label=close[0])
    return Intent("unknown_target", t, label=t)


def parse_one(segment: str, cfg: dict) -> Intent | None:
    s = FILLER_RE.sub(" ", segment)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None

    # ---- tareas (van antes que "buscar", porque "buscá empleo" no es una búsqueda web) ----
    if re.search(r"\b(?:buen dia|buenos dias|buenas tardes|buenas noches)\b", s) and len(s.split()) <= 4:
        return Intent("brief", raw=s, label="el parte del día")
    if re.search(r"\b(?:parte|resumen|reporte)\s+del\s+dia\b|\bcomo viene el dia\b|\bque tengo hoy\b", s):
        return Intent("brief", raw=s, label="el parte del día")
    if re.search(r"\bclima\b|\bque tiempo (?:hace|va a hacer)\b|\bva a llover\b|\btemperatura\b", s):
        return Intent("weather", raw=s, label="el clima")
    if re.match(r"^(?:que hora es|que hora|decime la hora|que dia es(?: hoy)?|que fecha es)$", s):
        return Intent("time", raw=s, label="la hora")

    m = re.match(r"^(?:anota|anotar|anotame|apunta|apuntame|recordame|agenda|agendame|"
                 r"agrega|agregar|sumale?|sumar)\s+(?:a\s+(?:los\s+)?pendientes\s+)?(?:que\s+)?(.+)$", s)
    if m:
        texto = re.sub(r"\s+a\s+(?:los\s+)?pendientes$", "", m.group(1)).strip()
        return Intent("note_add", texto, raw=s, label=texto)
    if re.search(r"\b(?:borra|borrar|limpia|limpiar|vacia|vaciar|elimina|eliminar)\b.*\b(?:todos los |los )?pendientes\b", s):
        return Intent("note_clear", raw=s, label="borrar todos los pendientes")
    m = re.match(r"^(?:listo|marca|marcame|marcar|borra|borrar|saca|sacar|termine|complete)\s+"
                 r"(?:el|la)?\s*(?:pendiente|punto|numero|item)?\s*(\w+)$", s)
    if m:
        n = _numero(m.group(1))
        if n:
            return Intent("note_done", str(n), raw=s, label=f"el pendiente {n}")
    if re.search(r"\bpendientes?\b", s) and re.search(
            r"^(?:que|cuales|cuantos|leeme|lee|decime|mostrame|mis|tengo)\b|^pendientes$", s):
        return Intent("note_list", raw=s, label="los pendientes")

    m = re.match(r"^(?:busca|buscar|buscame|conseguime|mostrame|abri|abrime|modo)\s+"
                 r"(?:me\s+)?(?:las?\s+)?(?:busquedas?\s+de\s+)?(?:empleos?|trabajos?)"
                 r"(?:\s+(?:de|para|en)\s+(.+))?$", s)
    if m:
        perfil = (m.group(1) or "").strip()
        return Intent("jobs", perfil, raw=s, label=f"empleos de {perfil}" if perfil else "empleos")
    if re.search(r"^(?:modo|abri|abrime|mostrame|entra a la?)\s+(?:la\s+)?(?:facu|facultad|universidad|cursada)$", s):
        return Intent("study", raw=s, label="la facultad")

    # Ojo: tiene que ser una orden explícita. "dejame navegar" NO es pedir silencio.
    if re.search(r"\b(?:deja de escuchar|dejame en paz|dejame tranquilo|pausate|"
                 r"ponete en pausa|silenciate|no me escuches|modo pausa)\b", s):
        return Intent("pause_listening", raw=s, label="dejar de escuchar")

    # ---- sistema ----
    if re.search(r"\bvolumen\b", s):
        if re.match(r"^(?:subi|sube|subir|aumenta|aumentar|mas)\b", s):
            return Intent("volume_up", raw=s, label="volumen arriba")
        if re.match(r"^(?:baja|bajar|reduce|reducir|menos)\b", s):
            return Intent("volume_down", raw=s, label="volumen abajo")
    if re.search(r"\b(?:silencio|mutea|mutear|silencia|silenciar|mute)\b", s) and len(s.split()) <= 4:
        return Intent("mute", raw=s, label="silencio")
    if re.match(r"^(?:pausa|pausar|play|reproduci|reanuda|continua)\b", s) and len(s.split()) <= 4:
        return Intent("play_pause", raw=s, label="play/pausa")
    if re.search(r"\b(?:siguiente|proxima)\b.*\b(?:cancion|tema)\b|^siguiente$", s):
        return Intent("media_next", raw=s, label="siguiente")
    if re.search(r"\b(?:cancion|tema)\s+anterior\b|^anterior$", s):
        return Intent("media_prev", raw=s, label="anterior")
    if re.search(r"\b(?:minimiza|minimizar|oculta|ocultar)\b.*\b(?:todo|ventanas)\b|\bmostra(?:me)? (?:el )?escritorio\b", s):
        return Intent("show_desktop", raw=s, label="escritorio")
    if re.match(r"^(?:cerra|cierra|cerrar)\b(?: (?:esto|esta|este|la|el|ventana|programa|aplicacion|actual))*$", s):
        return Intent("close_window", raw=s, label="ventana")
    if re.search(r"\b(?:bloquea|bloquear)\b", s):
        return Intent("lock", raw=s, label="bloqueo")
    if re.search(r"\b(?:apaga|apagar|apagame)\b", s):
        return Intent("shutdown", raw=s, label="apagar la PC")
    if re.search(r"\b(?:reinicia|reiniciar|reiniciame)\b", s):
        return Intent("restart", raw=s, label="reiniciar la PC")
    if re.search(r"captura de pantalla|screenshot|print screen", s):
        return Intent("screenshot", raw=s, label="captura")

    # ---- búsqueda ----
    m = re.match(r"^(?:busca|buscar|buscame|googlea|investiga)\s+(.+)$", s)
    if m:
        q = m.group(1)
        q = re.sub(r"^(?:en internet|en google)\s+", "", q)
        q = re.sub(r"\s+en google$", "", q)
        yt = re.match(r"^(.+?)\s+en youtube$", q)
        if yt:
            return Intent("search_youtube", yt.group(1), raw=s, label=yt.group(1))
        return Intent("search", q, raw=s, label=q)

    # ---- abrir / navegar ----
    m = re.match(rf"^(?:{NAV_VERBS})\s+(?:a la|al|a|en el|en la|en|hacia)\s+(.+)$", s)
    if not m:
        m = re.match(rf"^(?:{OPEN_VERBS})\s+(.+)$", s)
    if not m:
        m = re.match(rf"^(?:{NAV_VERBS})\s+(.+)$", s)
    if m:
        intent = resolve_target(m.group(1), cfg)
        intent.raw = s
        return intent
    return None


def parse(text: str, cfg: dict) -> list[Intent]:
    """Texto ya sin palabra de activación -> lista de intenciones."""
    intents = []
    for seg in split_commands(norm(text)):
        it = parse_one(seg, cfg)
        if it:
            intents.append(it)
    return intents
