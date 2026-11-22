"""Pruebas de la interfaz web: se levanta el servidor de verdad y se le habla por HTTP."""
import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from jarvis.webui import WebUI


class Web(unittest.TestCase):
    def setUp(self):
        self.pausado, self.parar = threading.Event(), threading.Event()
        self.recibidas = []
        self.ui = WebUI(self.pausado, self.parar, puerto=8899,
                        on_orden=self.recibidas.append)
        self.ui.iniciar()
        self.addCleanup(self.ui.servidor.server_close)
        self.addCleanup(self.ui.servidor.shutdown)
        self.base = f"http://127.0.0.1:{self.ui.puerto}"
        self.t = self.ui.token

    def get(self, ruta, timeout=4):
        return urllib.request.urlopen(self.base + ruta, timeout=timeout)

    def post(self, ruta, cuerpo=None):
        req = urllib.request.Request(
            self.base + ruta, method="POST",
            data=json.dumps(cuerpo or {}).encode(),
            headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=4)

    # ---------- servir la página ----------
    def test_sirve_la_pagina_con_token(self):
        r = self.get(f"/?t={self.t}")
        cuerpo = r.read().decode()
        self.assertEqual(r.status, 200)
        self.assertIn("J.A.R.V.I.S.", cuerpo)
        self.assertIn("<canvas id=\"onda\"", cuerpo)

    def test_sin_token_no_entra_nadie(self):
        for ruta in ("/", "/eventos", "/index.html"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.get(ruta)
            self.assertEqual(e.exception.code, 403, ruta)

    def test_token_equivocado_no_entra(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/?t=lo-invente")
        self.assertEqual(e.exception.code, 403)

    def test_no_se_puede_salir_de_la_carpeta_web(self):
        for ruta in ("/../config.py", "/../../etc/passwd", "/..%2fconfig.py"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.get(f"{ruta}?t={self.t}")
            self.assertIn(e.exception.code, (403, 404), ruta)

    # ---------- órdenes ----------
    def test_orden_llega_al_asistente(self):
        self.post(f"/orden?t={self.t}", {"texto": "abrí brave"})
        for _ in range(40):
            if self.recibidas:
                break
            time.sleep(0.05)
        self.assertEqual(self.recibidas, ["abrí brave"])

    def test_orden_sin_token_no_hace_nada(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/orden", {"texto": "apagá la pc"})
        time.sleep(0.2)
        self.assertEqual(self.recibidas, [])

    def test_pausa_y_salir(self):
        self.post(f"/pausa?t={self.t}")
        self.assertTrue(self.pausado.is_set())
        self.post(f"/pausa?t={self.t}")
        self.assertFalse(self.pausado.is_set())
        self.post(f"/salir?t={self.t}")
        self.assertTrue(self.parar.is_set())

    # ---------- eventos en vivo ----------
    def test_eventos_en_vivo(self):
        self.ui.status("escuchando")          # ya pasó: tiene que llegar igual al conectarse
        r = self.get(f"/eventos?t={self.t}", timeout=8)
        leidos = []

        def leer():
            try:
                for linea in r:
                    if linea.startswith(b"data: "):
                        leidos.append(json.loads(linea[6:].decode()))
                        if len(leidos) >= 3:
                            return
            except Exception:
                pass   # el hilo muere cuando se cierra la respuesta
        h = threading.Thread(target=leer, daemon=True)
        h.start()
        time.sleep(0.4)
        self.ui.heard("abrí brave")
        self.ui.said("Abriendo brave.")
        h.join(timeout=6)
        r.close()
        tipos = [e["tipo"] for e in leidos]
        self.assertIn("estado", tipos)
        self.assertIn("oido", tipos)
        self.assertIn("dijo", tipos)
        self.assertIn({"tipo": "oido", "dato": "abrí brave"}, leidos)

    def test_el_nivel_no_se_guarda_como_estado(self):
        self.ui.nivel(0.5)
        self.assertNotIn("nivel", self.ui.ultimo)

    def test_puerto_ocupado_busca_otro(self):
        otra = WebUI(threading.Event(), threading.Event(), puerto=self.ui.puerto)
        otra.iniciar()
        self.addCleanup(otra.servidor.server_close)
        self.addCleanup(otra.servidor.shutdown)
        self.assertNotEqual(otra.puerto, self.ui.puerto)


class Indice(unittest.TestCase):
    def setUp(self):
        from unittest import mock

        from jarvis import indice
        self.pausado, self.parar = threading.Event(), threading.Event()
        self.ui = WebUI(self.pausado, self.parar, puerto=8920)
        self.ui.iniciar()
        self.addCleanup(self.ui.servidor.server_close)
        self.addCleanup(self.ui.servidor.shutdown)
        parche = mock.patch.object(indice, "_cache", {
            "efootball": {"titulo": "eFootball 2024", "tipo": "steam", "destino": "1"},
            "efootball 2024": {"titulo": "eFootball 2024", "tipo": "steam", "destino": "1"},
            "brave": {"titulo": "Brave", "tipo": "lnk", "destino": "x"},
        })
        parche.start()
        self.addCleanup(parche.stop)

    def test_lista_sin_repetidos_y_ordenada(self):
        url = f"http://127.0.0.1:{self.ui.puerto}/indice?t={self.ui.token}"
        datos = json.loads(urllib.request.urlopen(url, timeout=4).read())
        self.assertEqual(datos, [{"titulo": "Brave", "tipo": "lnk"},
                                 {"titulo": "eFootball 2024", "tipo": "steam"}])

    def test_el_indice_tambien_pide_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{self.ui.puerto}/indice", timeout=4)
        self.assertEqual(e.exception.code, 403)


class Integracion(unittest.TestCase):
    """La interfaz conectada al asistente de verdad, como lo arma __main__."""

    def test_una_orden_escrita_recorre_todo_el_camino(self):
        import tempfile
        from pathlib import Path as P

        from jarvis.actions import Executor
        from jarvis.assistant import Assistant
        from jarvis.config import load_config
        from jarvis.tasks import Tasks

        cfg = load_config("/nonexistent.json")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tareas = Tasks(cfg)
        tareas.file = P(tmp.name) / "pendientes.json"
        ex = Executor(cfg, dry_run=True, tasks=tareas)
        asistente = Assistant(cfg, ex)

        pausado, parar = threading.Event(), threading.Event()
        ui = WebUI(pausado, parar, puerto=8910)
        ui.iniciar()
        self.addCleanup(ui.servidor.server_close)
        self.addCleanup(ui.servidor.shutdown)

        def procesar(texto):
            ui.heard(texto)
            for r in asistente.handle(texto):
                ui.said(r)
            ui.pendientes([i["texto"] for i in tareas._leer()])
        ui.on_orden = procesar

        base = f"http://127.0.0.1:{ui.puerto}"
        r = urllib.request.urlopen(f"{base}/eventos?t={ui.token}", timeout=8)
        leidos = []

        def leer():
            try:
                for linea in r:
                    if linea.startswith(b"data: "):
                        leidos.append(json.loads(linea[6:].decode()))
                        if len(leidos) >= 4:
                            return
            except Exception:
                pass
        h = threading.Thread(target=leer, daemon=True)
        h.start()
        time.sleep(0.3)
        req = urllib.request.Request(
            f"{base}/orden?t={ui.token}", method="POST",
            data=json.dumps({"texto": "jarvis anotá que probar la interfaz"}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=4)
        h.join(timeout=6)
        r.close()

        dijo = [e["dato"] for e in leidos if e["tipo"] == "dijo"]
        pend = [e["dato"] for e in leidos if e["tipo"] == "pendientes"]
        self.assertTrue(any("Anotado" in d for d in dijo), leidos)
        self.assertEqual(pend[-1], ["probar la interfaz"])
        self.assertEqual(ex.done, ["anotar probar la interfaz"])


if __name__ == "__main__":
    unittest.main()
