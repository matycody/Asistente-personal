"""Pantalla de Jarvis: una ventana chica que muestra qué está haciendo.

Usa tkinter, que ya viene con Python: no hace falta instalar nada.
La ventana corre en el hilo principal y la escucha en otro hilo; se comunican
por una cola, así que el audio nunca queda trabado por la interfaz.
"""
from __future__ import annotations

import queue
import threading
from datetime import datetime

BG = "#0b0f14"
PANEL = "#121821"
LINEA = "#1d2733"
TEXTO = "#cfe3ee"
TENUE = "#6b8296"
CIAN = "#35d6ed"
AMBAR = "#f0b429"
ROJO = "#ff6b6b"
VERDE = "#4ade80"

COLOR_ESTADO = {
    "escuchando": VERDE, "procesando": CIAN, "hablando": AMBAR,
    "en pausa": TENUE, "iniciando": TENUE, "error": ROJO,
}


class NullUI:
    """Cuando no hay ventana (modo texto o --sin-hud): no hace nada."""

    def status(self, estado: str) -> None: ...
    def heard(self, texto: str) -> None: ...
    def said(self, texto: str) -> None: ...
    def log(self, texto: str) -> None: ...
    def close(self) -> None: ...


class Hud:
    def __init__(self, pausado: threading.Event, parar: threading.Event, titulo: str = "J.A.R.V.I.S."):
        self.pausado = pausado
        self.parar = parar
        self.titulo = titulo
        self.q: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self.root = None
        self._tk = {}

    # ---------- API que usa el resto del programa (desde cualquier hilo) ----------
    def status(self, estado: str) -> None:
        self.q.put(("status", estado))

    def heard(self, texto: str) -> None:
        self.q.put(("heard", texto))

    def said(self, texto: str) -> None:
        self.q.put(("said", texto))

    def log(self, texto: str) -> None:
        self.q.put(("log", texto))

    def close(self) -> None:
        self.q.put(("close", ""))

    # ---------- ventana ----------
    def _construir(self):
        import tkinter as tk

        root = tk.Tk()
        self.root = root
        root.title(self.titulo)
        root.configure(bg=BG)
        root.geometry("540x430")
        root.minsize(420, 320)

        cab = tk.Frame(root, bg=BG)
        cab.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(cab, text=self.titulo, bg=BG, fg=CIAN,
                 font=("Consolas", 17, "bold")).pack(side="left")
        self._tk["punto"] = tk.Label(cab, text="●", bg=BG, fg=TENUE, font=("Segoe UI", 15))
        self._tk["punto"].pack(side="right", padx=(8, 0))
        self._tk["estado"] = tk.Label(cab, text="iniciando", bg=BG, fg=TENUE,
                                      font=("Segoe UI", 10))
        self._tk["estado"].pack(side="right")

        caja = tk.Frame(root, bg=PANEL, highlightbackground=LINEA, highlightthickness=1)
        caja.pack(fill="x", padx=18, pady=6)
        tk.Label(caja, text="TE ESCUCHÉ", bg=PANEL, fg=TENUE,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        self._tk["oido"] = tk.Label(caja, text="—", bg=PANEL, fg=TEXTO, wraplength=470,
                                    justify="left", font=("Segoe UI", 12))
        self._tk["oido"].pack(anchor="w", padx=12, pady=(2, 10))

        caja2 = tk.Frame(root, bg=PANEL, highlightbackground=LINEA, highlightthickness=1)
        caja2.pack(fill="both", expand=True, padx=18, pady=6)
        tk.Label(caja2, text="ACTIVIDAD", bg=PANEL, fg=TENUE,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self._tk["log"] = tk.Text(caja2, bg=PANEL, fg=TENUE, bd=0, highlightthickness=0,
                                  font=("Consolas", 9), wrap="word", state="disabled")
        self._tk["log"].pack(fill="both", expand=True, padx=12, pady=(0, 10))

        pie = tk.Frame(root, bg=BG)
        pie.pack(fill="x", padx=18, pady=(4, 16))
        self._tk["btn_pausa"] = tk.Button(
            pie, text="Pausar", command=self.alternar_pausa, bg=PANEL, fg=TEXTO,
            activebackground=LINEA, activeforeground=TEXTO, bd=0, padx=16, pady=6,
            font=("Segoe UI", 9), cursor="hand2")
        self._tk["btn_pausa"].pack(side="left")
        tk.Button(pie, text="Ocultar", command=self.ocultar, bg=PANEL, fg=TENUE,
                  activebackground=LINEA, activeforeground=TEXTO, bd=0, padx=16, pady=6,
                  font=("Segoe UI", 9), cursor="hand2").pack(side="left", padx=8)
        tk.Button(pie, text="Salir", command=self.salir, bg=PANEL, fg=ROJO,
                  activebackground=LINEA, activeforeground=ROJO, bd=0, padx=16, pady=6,
                  font=("Segoe UI", 9), cursor="hand2").pack(side="right")

        root.protocol("WM_DELETE_WINDOW", self.ocultar)
        root.after(100, self._vaciar_cola)
        return root

    # ---------- botones ----------
    def alternar_pausa(self) -> None:
        if self.pausado.is_set():
            self.pausado.clear()
            self.status("escuchando")
        else:
            self.pausado.set()
            self.status("en pausa")
        if "btn_pausa" in self._tk:
            self._tk["btn_pausa"].config(text="Reanudar" if self.pausado.is_set() else "Pausar")

    def ocultar(self) -> None:
        if self.root:
            self.root.withdraw()

    def mostrar(self) -> None:
        if self.root:
            self.root.deiconify()
            self.root.lift()

    def salir(self) -> None:
        self.parar.set()
        if self.root:
            self.root.quit()

    # ---------- bucle ----------
    def _escribir_log(self, texto: str) -> None:
        w = self._tk["log"]
        w.config(state="normal")
        w.insert("end", f"{datetime.now():%H:%M}  {texto}\n")
        lineas = int(w.index("end-1c").split(".")[0])
        if lineas > 60:
            w.delete("1.0", f"{lineas - 60}.0")
        w.see("end")
        w.config(state="disabled")

    def _vaciar_cola(self) -> None:
        try:
            while True:
                tipo, dato = self.q.get_nowait()
                if tipo == "status":
                    self._tk["estado"].config(text=dato)
                    self._tk["punto"].config(fg=COLOR_ESTADO.get(dato, TENUE))
                elif tipo == "heard":
                    self._tk["oido"].config(text=dato)
                    self._escribir_log(f"oí: {dato}")
                elif tipo == "said":
                    self._escribir_log(f"→ {dato}")
                elif tipo == "log":
                    self._escribir_log(dato)
                elif tipo == "close":
                    self.salir()
                    return
        except queue.Empty:
            pass
        if self.parar.is_set():
            self.salir()
            return
        self.root.after(100, self._vaciar_cola)

    def run(self) -> None:
        root = self._construir()
        try:
            root.mainloop()
        finally:
            self.parar.set()
