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

log = logging.getLogger("jarvis")

SYSTEM_ACTIONS = {
    "volume_up", "volume_down", "mute", "play_pause", "media_next", "media_prev",
    "show_desktop", "close_window", "screenshot", "lock", "shutdown", "restart",
}

PROMPT = """Sos el traductor de órdenes de voz de un asistente de PC con Windows. El usuario habla en español rioplatense.
Respondé SOLO un JSON: {{"actions": [...]}} con a lo sumo 5 acciones, en el orden pedido. Acciones permitidas:
- {{"kind":"open","name":"<nombre>"}}  abrir una app, carpeta o sitio. Usá EXACTAMENTE uno de estos nombres:
  {names}
- {{"kind":"drive","letter":"H"}}  abrir un disco por su letra
- {{"kind":"search","query":"..."}}  buscar en Google
- {{"kind":"youtube_search","query":"..."}}  buscar en YouTube
- {{"kind":"system","name":"<uno de: {system}>"}}
- {{"kind":"say","text":"..."}}  responder con voz una pregunta simple (máx. 2 frases, sin listas)
Si pide algo que no podés hacer con estas acciones, usá "say" explicando brevemente que no podés.
Ahora son las {now}.
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
        payload = {
            "model": self.opts.get("model", "qwen2.5:3b"),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": PROMPT.format(
                    names=self._names(), system=", ".join(sorted(SYSTEM_ACTIONS)),
                    now=datetime.now().strftime("%A %d/%m/%Y %H:%M"))},
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

    def _validate(self, data) -> list[Intent]:
        actions = data.get("actions") if isinstance(data, dict) else None
        if not isinstance(actions, list):
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
            elif kind == "say" and isinstance(a.get("text"), str) and a["text"].strip():
                out.append(Intent("say", a["text"].strip()[:300]))
        return out
