"""Lógica del asistente: palabra de activación, confirmaciones y ejecución."""
from __future__ import annotations

import logging
import time

from .actions import Executor
from .commands import Intent, norm, parse, strip_wake

log = logging.getLogger("jarvis")

NEEDS_CONFIRM = {"shutdown", "restart"}
YES = {"confirmo", "si", "dale", "hacelo", "confirmado", "ok", "aceptar"}
NO = {"no", "cancela", "cancelar", "cancelalo", "dejalo", "nada"}


class Assistant:
    def __init__(self, cfg: dict, executor: Executor, clock=time.monotonic, planner=None):
        self.cfg = cfg
        self.ex = executor
        self.clock = clock
        self.planner = planner          # opcional: modelo para órdenes libres
        self.awake_until = 0.0
        self.expect_command = False     # dijo solo "Jarvis" y espero la orden
        self.pending: tuple[Intent, float] | None = None

    def _extend(self) -> None:
        self.awake_until = self.clock() + self.cfg.get("followup_seconds", 6)

    def handle(self, transcript: str) -> list[str]:
        """Recibe lo que se escuchó y devuelve lo que Jarvis tiene que decir."""
        now = self.clock()
        heard_wake, rest = strip_wake(transcript)

        # 1) Confirmación pendiente (apagar/reiniciar)
        if self.pending and now < self.pending[1]:
            words = set(norm(transcript).split())
            intent = self.pending[0]
            if words & YES and not words & NO:
                self.pending = None
                return [self.ex.run(intent)]
            if words & NO:
                self.pending = None
                return ["Cancelado."]
        elif self.pending:
            self.pending = None

        # 2) ¿Me hablan a mí?
        in_window = now < self.awake_until
        if not heard_wake and not in_window:
            return []
        if heard_wake and not rest:
            self._extend()
            self.expect_command = True
            return ["Decime."]

        addressed = heard_wake or self.expect_command   # me hablan directamente
        self.expect_command = False
        intents = parse(rest, self.cfg)
        # Si las frases fijas no alcanzan, el modelo intenta entender la orden libre.
        # Solo cuando me hablan directo: en la ventana de seguimiento sería gastar CPU con ruido.
        if self.planner and addressed and (not intents or all(i.kind == "unknown_target" for i in intents)):
            planned = self.planner.plan(rest)
            if planned:
                intents = planned
        if not intents:
            # Sin palabra de activación (ventana de seguimiento) ignoramos el ruido en silencio
            return ["No entendí."] if addressed else []

        replies = []
        for it in intents:
            if it.kind in NEEDS_CONFIRM:
                self.pending = (it, now + 10)
                replies.append(f"¿Seguro que querés {it.label}? Decí confirmo.")
                break
            replies.append(self.ex.run(it))
        self._extend()
        return replies
