"""Pruebas del índice de la PC. Lo que depende de Windows se prueba con datos de ejemplo."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import indice
from jarvis.commands import parse, strip_wake
from jarvis.config import load_config

CFG = load_config("/nonexistent.json")


def kinds(text):
    _, rest = strip_wake(text)
    return [(i.kind, i.arg, i.label) for i in parse(rest, CFG)]


class Claves(unittest.TestCase):
    def test_variantes_de_un_nombre(self):
        self.assertIn("efootball 2024", indice.claves("eFootball™ 2024"))
        self.assertIn("efootball", indice.claves("eFootball™ 2024"))
        self.assertIn("brave", indice.claves("Brave - Navegador web"))
        self.assertEqual(indice.claves("Steam")[0], "steam")

    def test_no_recorta_nombres_muy_cortos(self):
        self.assertEqual(indice.claves("FL 2024"), ["fl 2024"])   # 'fl' sería ambiguo

    def test_nombre_vacio(self):
        self.assertEqual(indice.claves("   "), [])


class Steam(unittest.TestCase):
    ACF = '''"AppState"
{
\t"appid"\t\t"1665460"
\t"Universe"\t\t"1"
\t"name"\t\t"eFootball 2024"
\t"StateFlags"\t\t"4"
}'''

    def test_lee_un_manifiesto(self):
        self.assertEqual(indice.juego_de_manifiesto(self.ACF), ("1665460", "eFootball 2024"))

    def test_manifiesto_incompleto(self):
        self.assertIsNone(indice.juego_de_manifiesto('"AppState" { "appid" "1" }'))
        self.assertIsNone(indice.juego_de_manifiesto('"AppState" { "appid" "1" "name" "" }'))

    def test_bibliotecas(self):
        vdf = '''"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"
\t}
\t"1"
\t{
\t\t"path"\t\t"D:\\\\SteamLibrary"
\t}
}'''
        self.assertEqual(indice.bibliotecas_steam(vdf),
                         ["C:\\Program Files (x86)\\Steam", "D:\\SteamLibrary"])


class Buscar(unittest.TestCase):
    EJEMPLO = {
        "efootball 2024": {"titulo": "eFootball 2024", "tipo": "steam", "destino": "1665460"},
        "efootball": {"titulo": "eFootball 2024", "tipo": "steam", "destino": "1665460"},
        "steam": {"titulo": "Steam", "tipo": "lnk", "destino": "C:\\steam.lnk"},
        "papelera de reciclaje": {"titulo": "papelera de reciclaje", "tipo": "carpeta",
                                  "destino": "shell:RecycleBinFolder"},
        "calculadora": {"titulo": "Calculadora", "tipo": "app",
                        "destino": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"},
        "disco h": {"titulo": "disco H (Juegos)", "tipo": "carpeta", "destino": "H:\\"},
    }

    def setUp(self):
        self.p = mock.patch.object(indice, "_cache", dict(self.EJEMPLO))
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_exacto(self):
        self.assertEqual(indice.buscar("steam")["tipo"], "lnk")

    def test_dentro_de_una_frase_gana_la_clave_mas_larga(self):
        self.assertEqual(indice.buscar("el efootball 2024")["destino"], "1665460")
        self.assertEqual(indice.buscar("efootball")["titulo"], "eFootball 2024")

    def test_parecido(self):
        self.assertIsNotNone(indice.buscar("calculadora"))
        self.assertIsNotNone(indice.buscar("papelera de recicraje"))

    def test_no_inventa_resultados(self):
        self.assertIsNone(indice.buscar("zzzz programa que no existe"))
        self.assertIsNone(indice.buscar(""))

    def test_una_palabra_suelta_no_arrastra_cualquier_cosa(self):
        # "disco" solo no debería devolver el disco H
        self.assertIsNone(indice.buscar("disco"))


class ConElParser(unittest.TestCase):
    """El índice se usa recién cuando la configuración no conoce el nombre."""

    def setUp(self):
        self.p = mock.patch.object(indice, "_cache", dict(Buscar.EJEMPLO))
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_abre_un_juego_de_steam(self):
        self.assertEqual(kinds("jarvis abrí el efootball"),
                         [("open_steam", "1665460", "eFootball 2024")])

    def test_el_nombre_al_final_tambien_vale(self):
        self.assertEqual(kinds("abrí el efootball, jarvis"),
                         [("open_steam", "1665460", "eFootball 2024")])

    def test_app_de_la_store(self):
        k, arg, _ = kinds("jarvis abrí la calculadora")[0]
        self.assertEqual(k, "open_app")        # la config gana: calc está en config.py
        self.assertEqual(arg, "calc")

    def test_papelera(self):
        k, arg, _ = kinds("jarvis abrí la papelera de reciclaje")[0]
        self.assertEqual((k, arg), ("open_path", "shell:RecycleBinFolder"))

    def test_lo_que_no_existe_sigue_siendo_desconocido(self):
        self.assertEqual(kinds("jarvis abrí zzzzzz")[0][0], "unknown_target")


class Archivo(unittest.TestCase):
    def test_guardar_y_cargar(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name) / "indice.json"
        with mock.patch.object(indice, "ruta_indice", return_value=ruta):
            indice.guardar({"brave": {"titulo": "Brave", "tipo": "lnk", "destino": "x"}})
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["brave"]["titulo"],
                             "Brave")
            self.assertEqual(indice.cargar(recargar=True)["brave"]["tipo"], "lnk")

    def test_sin_archivo_no_rompe(self):
        with mock.patch.object(indice, "ruta_indice", return_value=Path("/no/existe.json")):
            self.assertEqual(indice.cargar(recargar=True), {})

    def test_escanear_sigue_si_una_fuente_falla(self):
        avisos = []
        with mock.patch.object(indice, "apps_menu_inicio", side_effect=OSError("boom")), \
             mock.patch.object(indice, "juegos_steam", return_value={
                 "x": {"titulo": "X", "tipo": "steam", "destino": "1"}}), \
             mock.patch.object(indice, "accesos_directos", return_value={}), \
             mock.patch.object(indice, "discos", return_value={}):
            resultado = indice.escanear(avisos.append)
        self.assertIn("x", resultado)                      # lo demás se indexó igual
        self.assertTrue(any("falló" in a for a in avisos))
        self.assertIn("papelera", resultado)               # las del sistema siempre están


class Codificacion(unittest.TestCase):
    """Windows no siempre devuelve UTF-8: un acento no puede tirar abajo el escaneo."""

    def test_decodifica_cualquier_cosa(self):
        from jarvis.powershell import decodificar
        self.assertEqual(decodificar("Aplicación ñ".encode("utf-8")), "Aplicación ñ")
        self.assertEqual(decodificar("Aplicación".encode("cp1252")), "Aplicación")
        self.assertEqual(decodificar("\ufeffHola".encode("utf-16-le")), "Hola")
        self.assertEqual(decodificar(b""), "")

    def test_un_byte_invalido_no_levanta_excepcion(self):
        from jarvis.powershell import decodificar
        # esto es lo que rompía: 0xff suelto en medio de la salida
        self.assertIn("Name", decodificar(b'[\r\n  {"Name":\xff"X"}'))

    def test_el_prefijo_pide_utf8(self):
        from jarvis.powershell import PREFIJO
        self.assertIn("OutputEncoding", PREFIJO)
        self.assertIn("UTF8", PREFIJO)


if __name__ == "__main__":
    unittest.main()
