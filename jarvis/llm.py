"""Órdenes libres con un modelo local (Ollama).

El modelo NO ejecuta nada: solo traduce lo que dijiste a acciones de una lista cerrada.
Cada acción se valida acá antes de llegar al Executor, así que aunque el modelo se
equivoque no puede abrir cualquier cosa ni correr comandos.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime

from .commands import Intent, norm, resolve_target
from .tasks import fecha_larga, hora_corta

log = logging.getLogger("jarvis")

SYSTEM_ACTIONS = {
    "volume_up", "volume_down", "mute", "play_pause", "media_next", "media_prev",
    "show_desktop", "close_window", "screenshot", "lock", "shutdown", "restart",
    "pause_listening",
}
# Tareas sin argumentos
TASK_ACTIONS = {"brief", "weather", "time", "note_list", "note_clear", "study"}

PROMPT = """Sos el traductor de órdenes de voz de un asistente de PC con Windows. El usuario habla en español rioplatense.
Respondé SOLO un JSON: {{"actions": [...]}} con a lo sumo 5 acciones, en el orden pedido. Acciones permitidas:
- {{"kind":"open","name":"<nombre>"}}  abrir una app, carpeta o sitio. Usá EXACTAMENTE uno de estos nombres:
  {names}
- {{"kind":"drive","letter":"H"}}  abrir un disco por su letra
- {{"kind":"search","query":"..."}}  buscar en Google
- {{"kind":"youtube_search","query":"..."}}  buscar en YouTube
- {{"kind":"system","name":"<uno de: {system}>"}}
- {{"kind":"task","name":"<uno de: {tasks}>"}}  brief = parte del día (fecha, clima y pendientes);
  weather = clima; time = hora y fecha; note_list = leer los pendientes; note_clear = borrar
  todos los pendientes; study = abrir las cosas de la facultad
- {{"kind":"note_add","text":"..."}}  anotar algo en los pendientes
- {{"kind":"jobs","profile":"programacion"|"electricidad"}}  abrir las búsquedas de empleo
- {{"kind":"say","text":"..."}}  responder con voz una pregunta simple (máx. 2 frases, sin listas)
Reglas: usá "system" SOLO si el usuario pide explícitamente volumen, pausa, silencio, bloquear, etc. Para ir a una carpeta o abrir algo, usá "open".
Si pide algo que no podés hacer con estas acciones, usá "say" explicando brevemente que no podés.
Ejemplos:
"llevame a lo que bajé hoy" -> {{"actions":[{{"kind":"open","name":"descargas"}}]}}
"abrime el correo" -> {{"actions":[{{"kind":"open","name":"gmail"}}]}}
"poneme música" -> {{"actions":[{{"kind":"open","name":"spotify"}}]}}
"cómo viene el día" -> {{"actions":[{{"kind":"task","name":"brief"}}]}}
"no te olvides que mañana tengo parcial" -> {{"actions":[{{"kind":"note_add","text":"mañana tengo parcial"}}]}}
"mostrame trabajos de electricista" -> {{"actions":[{{"kind":"jobs","profile":"electricidad"}}]}}
"qué hora es" -> {{"actions":[{{"kind":"say","text":"Son las {hora}."}}]}}
"qué día es hoy" -> {{"actions":[{{"kind":"say","text":"Hoy es {dia}."}}]}}
"abrí brave y buscá recetas" -> {{"actions":[{{"kind":"open","name":"brave"}},{{"kind":"search","query":"recetas"}}]}}
"""


def _default_transport(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class OllamaPlanner:
    def __init__(self, cfg: dict, transport=_default_transport):
        self.cfg = cfg
        self.opts = cfg.get("llm", {})
        self.transport = transport
        self._warned = False

    @property
    def enabled(self) -> bool:
        return bool(self.opts.get("enabled", True))

    def _names(self) -> str:
        keys = sorted({*self.cfg["apps"], *self.cfg["folders"], *self.cfg["sites"]})
        return ", ".join(keys)

    def plan(self, text: str) -> list[Intent]:
        if not self.enabled:
            return []
        now = datetime.now()
        payload = {
            "model": self.opts.get("model", "qwen2.5:3b"),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": PROMPT.format(
                    names=self._names(), system=", ".join(sorted(SYSTEM_ACTIONS)),
                    tasks=", ".join(sorted(TASK_ACTIONS)),
                    hora=hora_corta(now), dia=fecha_larga(now))},
                {"role": "user", "content": text},
            ],
        }
        try:
            reply = self.transport(self.opts.get("url", "http://127.0.0.1:11434"),
                                   payload, self.opts.get("timeout", 25))
            data = json.loads(reply["message"]["content"])
        except Exception as e:  # Ollama apagado, modelo no descargado, JSON roto...
            if not self._warned:
                log.warning("LLM no disponible (%s). Sigo solo con frases fijas.", e)
                self._warned = True
            return []
        log.info("LLM plan: %s", data)
        return self._validate(data)

    @staticmethod
    def _actions_of(data) -> list:
        """Los modelos chicos no siempre respetan el formato: aceptamos varias formas."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if isinstance(data.get("actions"), list):
                return data["actions"]
            if isinstance(data.get("action"), dict):
                return [data["action"]]
            if "kind" in data:
                return [data]
        return []

    def _validate(self, data) -> list[Intent]:
        actions = self._actions_of(data)
        if not actions:
            return []
        out: list[Intent] = []
        for a in actions[:5]:
            if not isinstance(a, dict):
                continue
            kind = a.get("kind")
            if kind == "open" and isinstance(a.get("name"), str):
                it = resolve_target(norm(a["name"]), self.cfg)
                if it.kind != "unknown_target":
                    out.append(it)
            elif kind == "drive" and isinstance(a.get("letter"), str):
                letter = a["letter"].strip()[:1].upper()
                if letter.isalpha():
                    out.append(Intent("open_path", f"{letter}:\\", label=f"disco {letter}"))
            elif kind in ("search", "youtube_search") and isinstance(a.get("query"), str):
                q = a["query"].strip()[:200]
                if q:
                    out.append(Intent("search" if kind == "search" else "search_youtube", q, label=q))
            elif kind == "system" and a.get("name") in SYSTEM_ACTIONS:
                label = {"shutdown": "apagar la PC", "restart": "reiniciar la PC"}.get(a["name"], a["name"])
                out.append(Intent(a["name"], label=label))
            elif kind == "task" and a.get("name") in TASK_ACTIONS:
                label = {"note_clear": "borrar todos los pendientes"}.get(a["name"], a["name"])
                out.append(Intent(a["name"], label=label))
            elif kind == "note_add" and isinstance(a.get("text"), str) and a["text"].strip():
                texto = a["text"].strip()[:300]
                out.append(Intent("note_add", texto, label=texto))
            elif kind == "jobs":
                perfil = a.get("profile") if isinstance(a.get("profile"), str) else ""
                out.append(Intent("jobs", perfil.strip()[:40], label="empleos"))
            elif kind == "say" and isinstance(a.get("text"), str) and a["text"].strip():
                out.append(Intent("say", a["text"].strip()[:300]))
        return out
