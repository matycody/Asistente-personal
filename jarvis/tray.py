"""Ícono al lado del reloj: pausar, mostrar la ventana o salir sin tocar la consola.

Necesita pystray y pillow. Si no están instalados, Jarvis funciona igual y esto
no se activa.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger("jarvis")


def _icono_imagen(color: str):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), outline=color, width=5)
    d.ellipse((24, 24, 40, 40), fill=color)
    return img


def iniciar(pausado: threading.Event, parar: threading.Event, hud=None):
    """Arranca el ícono en un hilo aparte. Devuelve el ícono o None."""
    try:
        import pystray
    except Exception as e:
        log.info("Sin ícono en la bandeja (%s). Jarvis funciona igual.", e)
        return None

    def repintar(icono):
        icono.icon = _icono_imagen("#6b8296" if pausado.is_set() else "#35d6ed")
        icono.title = "Jarvis — en pausa" if pausado.is_set() else "Jarvis — escuchando"

    def alternar(icono, _item=None):
        if hud:
            hud.alternar_pausa()
        else:
            pausado.clear() if pausado.is_set() else pausado.set()
        repintar(icono)

    def mostrar(icono, _item=None):
        if hud:
            hud.mostrar()

    def salir(icono, _item=None):
        parar.set()
        if hud:
            hud.close()
        icono.stop()

    try:
        menu = pystray.Menu(
            pystray.MenuItem(lambda _i: "Reanudar" if pausado.is_set() else "Pausar", alternar,
                             default=True),
            pystray.MenuItem("Mostrar ventana", mostrar, visible=bool(hud)),
            pystray.MenuItem("Salir", salir),
        )
        icono = pystray.Icon("jarvis", _icono_imagen("#35d6ed"), "Jarvis — escuchando", menu)
        threading.Thread(target=icono.run, daemon=True).start()
        return icono
    except Exception as e:
        log.info("No pude crear el ícono de la bandeja (%s).", e)
        return None
