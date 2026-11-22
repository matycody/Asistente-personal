"""Pruebas de la búsqueda del navegador (sin Windows: se inyecta qué archivos existen)."""
import unittest
from unittest import mock

from jarvis import navegador

ENTORNO = {
    "PROGRAMFILES": r"C:\Program Files",
    "PROGRAMFILES(X86)": r"C:\Program Files (x86)",
    "LOCALAPPDATA": r"C:\Users\Matias\AppData\Local",
}
BRAVE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_USUARIO = r"C:\Users\Matias\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"


def solo(*instalados):
    return lambda ruta: ruta in instalados


class Buscar(unittest.TestCase):
    def ruta(self, nombre, existe):
        return navegador.ruta_de(nombre, existe=existe, entorno=ENTORNO, usar_registro=False)

    def test_lo_encuentra_en_program_files(self):
        self.assertEqual(self.ruta("brave", solo(BRAVE)), BRAVE)

    def test_lo_encuentra_instalado_para_el_usuario(self):
        self.assertEqual(self.ruta("brave", solo(BRAVE_USUARIO)), BRAVE_USUARIO)

    def test_si_no_esta_devuelve_nada(self):
        # esto es lo que pasaba antes y no se notaba: 'brave' no resolvía a nada
        self.assertIsNone(self.ruta("brave", solo()))

    def test_acepta_una_ruta_completa(self):
        otro = r"D:\Navegadores\raro.exe"
        self.assertEqual(self.ruta(otro, solo(otro)), otro)
        self.assertIsNone(self.ruta(otro, solo()))

    def test_navegador_desconocido(self):
        self.assertIsNone(self.ruta("netscape", solo()))
        self.assertIsNone(self.ruta("", solo()))

    def test_alias(self):
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.assertEqual(self.ruta("google chrome", solo(chrome)), chrome)


class Abrir(unittest.TestCase):
    def test_usa_modo_app_cuando_lo_soporta(self):
        with mock.patch.object(navegador, "ruta_de", return_value=BRAVE), \
             mock.patch.object(navegador.subprocess, "Popen") as popen:
            self.assertTrue(navegador.abrir("http://x/?t=1", "brave", modo_app=True))
        args = popen.call_args[0][0]
        self.assertEqual(args[0], BRAVE)
        self.assertEqual(args[1], "--app=http://x/?t=1")

    def test_sin_modo_app_pasa_la_url_sola(self):
        with mock.patch.object(navegador, "ruta_de", return_value=BRAVE), \
             mock.patch.object(navegador.subprocess, "Popen") as popen:
            navegador.abrir("http://x/", "brave", modo_app=False)
        self.assertEqual(popen.call_args[0][0][1], "http://x/")

    def test_si_no_esta_el_navegador_usa_el_predeterminado(self):
        import webbrowser
        with mock.patch.object(navegador, "ruta_de", return_value=None), \
             mock.patch.object(webbrowser, "open", return_value=True) as abrir:
            self.assertTrue(navegador.abrir("http://x/", "brave"))
        abrir.assert_called_once_with("http://x/")

    def test_si_falla_el_lanzamiento_cae_al_predeterminado(self):
        import webbrowser
        with mock.patch.object(navegador, "ruta_de", return_value=BRAVE), \
             mock.patch.object(navegador.subprocess, "Popen", side_effect=OSError("boom")), \
             mock.patch.object(webbrowser, "open", return_value=True) as abrir:
            self.assertTrue(navegador.abrir("http://x/", "brave"))
        abrir.assert_called_once()

    def test_devuelve_falso_si_no_se_pudo_abrir_nada(self):
        import webbrowser
        with mock.patch.object(navegador, "ruta_de", return_value=None), \
             mock.patch.object(webbrowser, "open", return_value=False):
            self.assertFalse(navegador.abrir("http://x/", "brave"))


if __name__ == "__main__":
    unittest.main()
