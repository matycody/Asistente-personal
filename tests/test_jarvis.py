import json as _json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from jarvis.actions import Executor
from jarvis.assistant import Assistant
from jarvis.commands import parse, strip_wake
from jarvis.config import load_config
from jarvis.listener import es_alucinacion
from jarvis.llm import OllamaPlanner
from jarvis.tasks import Tasks

CFG = load_config("/nonexistent.json")
AHORA = datetime(2026, 11, 22, 9, 30)


def kinds(text):
    _, rest = strip_wake(text)
    return [(i.kind, i.arg) for i in parse(rest, CFG)]


def tasks_tmp(tmp: Path, http=None):
    t = Tasks(CFG, http=http or (lambda url, timeout=10: {}), now=lambda: AHORA)
    t.file = tmp / "pendientes.json"
    return t


# ---------------------------------------------------------------- parser
class Parser(unittest.TestCase):
    def test_open_brave(self):
        self.assertEqual(kinds("Jarvis, abrí Brave"), [("open_app", "brave")])

    def test_fuzzy_brave(self):
        self.assertEqual(kinds("jarvis abri brev")[0][0], "open_app")

    def test_explorer_and_drive(self):
        self.assertEqual(
            kinds("Jarvis, abrí el explorador de archivos y entrá al disco H"),
            [("open_app", "explorer"), ("open_path", "H:\\")],
        )

    def test_drive_spoken_letter(self):
        self.assertEqual(kinds("jarvis entra al disco hache"), [("open_path", "H:\\")])

    def test_site(self):
        self.assertEqual(kinds("jarvis abrí youtube")[0][0], "open_url")

    def test_search_does_not_split_on_y(self):
        self.assertEqual(kinds("jarvis busca recetas y postres"), [("search", "recetas y postres")])

    def test_youtube_search(self):
        self.assertEqual(kinds("jarvis buscá lofi en youtube")[0][0], "search_youtube")

    def test_system(self):
        self.assertEqual(kinds("jarvis subí el volumen")[0][0], "volume_up")
        self.assertEqual(kinds("jarvis bajá el volumen")[0][0], "volume_down")
        self.assertEqual(kinds("jarvis minimizá todo")[0][0], "show_desktop")
        self.assertEqual(kinds("jarvis cerrá esta ventana")[0][0], "close_window")

    def test_unknown(self):
        self.assertEqual(kinds("jarvis abrí zzzzzz")[0][0], "unknown_target")

    def test_chatter_is_not_a_command(self):
        self.assertEqual(kinds("hoy hace mucho calor"), [])


# ---------------------------------------------------------------- parser de tareas
class ParserTareas(unittest.TestCase):
    def test_brief(self):
        for frase in ["jarvis buenos días", "jarvis dame el parte del día",
                      "jarvis cómo viene el día", "jarvis qué tengo hoy"]:
            self.assertEqual(kinds(frase)[0][0], "brief", frase)

    def test_weather(self):
        self.assertEqual(kinds("jarvis cómo está el clima")[0][0], "weather")
        self.assertEqual(kinds("jarvis va a llover")[0][0], "weather")

    def test_time(self):
        self.assertEqual(kinds("jarvis qué hora es")[0][0], "time")
        self.assertEqual(kinds("jarvis qué día es hoy")[0][0], "time")

    def test_note_add(self):
        self.assertEqual(kinds("jarvis anotá que mañana tengo parcial"),
                         [("note_add", "manana tengo parcial")])
        self.assertEqual(kinds("jarvis recordame comprar cable")[0][0], "note_add")

    def test_note_list(self):
        self.assertEqual(kinds("jarvis qué tengo pendiente")[0][0], "note_list")
        self.assertEqual(kinds("jarvis leeme los pendientes")[0][0], "note_list")

    def test_note_done_and_clear(self):
        self.assertEqual(kinds("jarvis listo el dos"), [("note_done", "2")])
        self.assertEqual(kinds("jarvis marcá el 3"), [("note_done", "3")])
        self.assertEqual(kinds("jarvis borrá todos los pendientes")[0][0], "note_clear")

    def test_jobs(self):
        self.assertEqual(kinds("jarvis buscá empleo"), [("jobs", "")])
        self.assertEqual(kinds("jarvis buscame trabajo de electricidad"),
                         [("jobs", "electricidad")])

    def test_study(self):
        self.assertEqual(kinds("jarvis modo facultad")[0][0], "study")

    def test_pause(self):
        self.assertEqual(kinds("jarvis dejá de escuchar")[0][0], "pause_listening")
        self.assertEqual(kinds("jarvis ponete en pausa")[0][0], "pause_listening")

    def test_dejame_algo_no_es_pausa(self):
        self.assertNotIn("pause_listening", [k for k, _ in kinds("jarvis dejame navegar")])

    def test_search_still_wins_over_jobs(self):
        self.assertEqual(kinds("jarvis buscá recetas de milanesa"),
                         [("search", "recetas de milanesa")])


# ---------------------------------------------------------------- flujo
class Flow(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(Path(self.tmp.name)))
        self.a = Assistant(CFG, self.ex, clock=lambda: self.t)

    def test_ignores_without_wake(self):
        self.assertEqual(self.a.handle("abrí brave"), [])
        self.assertEqual(self.ex.done, [])

    def test_wake_only_then_command(self):
        self.assertEqual(self.a.handle("Jarvis"), ["Decime."])
        self.t = 3
        self.a.handle("abrí brave")
        self.assertEqual(self.ex.done, ["abrir app brave"])

    def test_on_wake_callback(self):
        veces = []
        a = Assistant(CFG, self.ex, clock=lambda: self.t, on_wake=lambda: veces.append(1))
        a.handle("jarvis abrí brave")
        a.handle("sin palabra de activación")
        self.assertEqual(len(veces), 1)

    def test_followup_window_expires(self):
        self.a.handle("jarvis abrí brave")
        self.t = 3
        self.a.handle("abrí calculadora")
        self.t = 30
        self.a.handle("abrí paint")
        self.assertEqual(self.ex.done, ["abrir app brave", "abrir app calc"])

    def test_shutdown_needs_confirmation(self):
        out = self.a.handle("jarvis apagá la pc")
        self.assertIn("confirmo", out[0])
        self.assertEqual(self.ex.done, [])
        self.t = 2
        self.a.handle("confirmo")
        self.assertEqual(self.ex.done, ["apagar"])

    def test_shutdown_cancel_and_timeout(self):
        self.a.handle("jarvis apagá la pc")
        self.t = 2
        self.assertEqual(self.a.handle("no"), ["Cancelado."])
        self.a.handle("jarvis reiniciá")
        self.t = 60
        self.a.handle("confirmo")
        self.assertEqual(self.ex.done, [])

    def test_note_clear_needs_confirmation(self):
        self.ex.tasks.anotar("algo")
        out = self.a.handle("jarvis borrá todos los pendientes")
        self.assertIn("confirmo", out[0])
        self.assertIn("algo", self.ex.tasks.pendientes())
        self.t = 2
        self.a.handle("dale")
        self.assertEqual(self.ex.tasks.pendientes(), "No tenés pendientes.")

    def test_pause_calls_back(self):
        pausas = []
        ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(Path(self.tmp.name)),
                      pausar=lambda: pausas.append(1))
        Assistant(CFG, ex, clock=lambda: self.t).handle("jarvis dejá de escuchar")
        self.assertEqual(len(pausas), 1)


# ---------------------------------------------------------------- tareas
class Tareas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_pendientes_ciclo_completo(self):
        t = tasks_tmp(self.dir)
        self.assertEqual(t.pendientes(), "No tenés pendientes.")
        t.anotar("comprar cable")
        t.anotar("entregar tp")
        self.assertIn("1. comprar cable", t.pendientes())
        self.assertIn("2. entregar tp", t.pendientes())
        self.assertIn("comprar cable", t.listo(1))
        self.assertIn("1. entregar tp", t.pendientes())
        self.assertIn("no tengo", t.listo(9).lower())
        t.borrar_pendientes()
        self.assertEqual(t.pendientes(), "No tenés pendientes.")

    def test_anotar_vacio(self):
        self.assertIn("qué querés", tasks_tmp(self.dir).anotar("   ").lower())

    def test_pendientes_persisten_en_disco(self):
        tasks_tmp(self.dir).anotar("algo")
        self.assertIn("algo", tasks_tmp(self.dir).pendientes())

    def test_clima(self):
        datos = {"current": {"temperature_2m": 23.4, "weather_code": 3},
                 "daily": {"temperature_2m_max": [28.1], "temperature_2m_min": [17.0],
                           "precipitation_probability_max": [60]}}
        t = tasks_tmp(self.dir, http=lambda url, timeout=10: datos)
        texto = t.clima()
        self.assertIn("Claypole", texto)
        self.assertIn("23 grados", texto)
        self.assertIn("nublado", texto)
        self.assertIn("paraguas", texto)

    def test_clima_sin_lluvia_no_menciona_paraguas(self):
        datos = {"current": {"temperature_2m": 25, "weather_code": 0},
                 "daily": {"temperature_2m_max": [30], "temperature_2m_min": [18],
                           "precipitation_probability_max": [5]}}
        t = tasks_tmp(self.dir, http=lambda url, timeout=10: datos)
        self.assertNotIn("paraguas", t.clima())

    def test_clima_sin_internet_no_rompe(self):
        def falla(url, timeout=10):
            raise OSError("sin red")
        self.assertIn("No pude", tasks_tmp(self.dir, http=falla).clima())

    def test_parte_del_dia(self):
        def falla(url, timeout=10):
            raise OSError("sin red")
        t = tasks_tmp(self.dir, http=falla)
        t.anotar("entregar tp")
        texto = t.parte()
        self.assertIn("Buen día", texto)
        self.assertIn("domingo 22 de noviembre", texto)
        self.assertIn("09:30", texto)
        self.assertIn("entregar tp", texto)

    def test_empleo_abre_las_busquedas(self):
        ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(self.dir))
        texto = ex.tasks.empleo("")
        urls = [d for d in ex.done if d.startswith("abrir web")]
        self.assertEqual(len(urls), 4)
        self.assertIn("abrir web https://ar.computrabajo.com/trabajo-de-programador-junior", urls)
        self.assertIn("abrir web https://ar.indeed.com/q-programador-junior-empleos.html", urls)
        self.assertIn("abrir web https://www.linkedin.com/jobs/search/?keywords=programador+junior", urls)
        self.assertIn("programacion", texto)

    def test_empleo_perfil_electricidad(self):
        ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(self.dir))
        ex.tasks.empleo("electricidad")
        self.assertTrue(any("trabajo-de-electricista" in d for d in ex.done))

    def test_empleo_perfil_con_tilde_o_parcial(self):
        ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(self.dir))
        ex.tasks.empleo("programacion")
        self.assertTrue(any("programador-junior" in d for d in ex.done))

    def test_facultad_sin_configurar(self):
        ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(self.dir))
        self.assertIn("config", ex.tasks.facultad())


# ---------------------------------------------------------------- escucha
class Escucha(unittest.TestCase):
    def test_descarta_alucinaciones(self):
        for frase in ["Subtítulos realizados por la comunidad de Amara.org",
                      "¡Gracias por ver el video!", "Música", "Suscríbete al canal",
                      "gracias gracias gracias", "", "   "]:
            self.assertTrue(es_alucinacion(frase), frase)

    def test_no_descarta_ordenes_reales(self):
        for frase in ["Jarvis, abrí Brave", "abrí el explorador y entrá al disco H",
                      "anotá que mañana tengo parcial", "Jarvis"]:
            self.assertFalse(es_alucinacion(frase), frase)


# ---------------------------------------------------------------- órdenes libres
def fake(actions):
    def transport(url, payload, timeout):
        return {"message": {"content": _json.dumps({"actions": actions})}}
    return transport


def broken(url, payload, timeout):
    raise ConnectionError("ollama apagado")


class FreeCommands(unittest.TestCase):
    def make(self, transport):
        self.t = 0.0
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ex = Executor(CFG, dry_run=True, tasks=tasks_tmp(Path(self.tmp.name)))
        return Assistant(CFG, self.ex, clock=lambda: self.t,
                         planner=OllamaPlanner(CFG, transport=transport))

    def test_llm_used_when_rules_fail(self):
        import os
        a = self.make(fake([{"kind": "open", "name": "descargas"}, {"kind": "open", "name": "brave"}]))
        a.handle("jarvis llevame a lo que baje hoy y dejame navegar")
        self.assertEqual(self.ex.done, ["abrir carpeta " + os.path.expanduser("~/Downloads"),
                                        "abrir app brave"])

    def test_rules_take_priority(self):
        a = self.make(fake([{"kind": "open", "name": "calculadora"}]))
        a.handle("jarvis abrí brave")
        self.assertEqual(self.ex.done, ["abrir app brave"])

    def test_invalid_actions_are_dropped(self):
        a = self.make(fake([{"kind": "open", "name": "formatear disco"},
                            {"kind": "run", "cmd": "del /s *"},
                            {"kind": "system", "name": "rm_everything"},
                            {"kind": "task", "name": "borrar_todo"}]))
        out = a.handle("jarvis hacé algo raro")
        self.assertEqual(out, ["No entendí."])
        self.assertEqual(self.ex.done, [])

    def test_say(self):
        a = self.make(fake([{"kind": "say", "text": "Un chiste corto."}]))
        self.assertEqual(a.handle("jarvis contame un chiste"), ["Un chiste corto."])

    def test_hora_se_responde_sin_modelo(self):
        llamadas = []

        def spy(url, payload, timeout):
            llamadas.append(1)
            return {"message": {"content": "{}"}}
        out = self.make(spy).handle("jarvis qué hora es")
        self.assertEqual(llamadas, [])
        self.assertIn("09:30", out[0])

    def test_task_and_note_from_llm(self):
        a = self.make(fake([{"kind": "note_add", "text": "llamar al taller"}]))
        a.handle("jarvis no te olvides de lo del taller")
        self.assertIn("llamar al taller", self.ex.tasks.pendientes())

    def test_jobs_from_llm(self):
        a = self.make(fake([{"kind": "jobs", "profile": "electricidad"}]))
        a.handle("jarvis mostrame laburos de electricista")
        self.assertTrue(any("trabajo-de-electricista" in d for d in self.ex.done))

    def test_note_clear_from_llm_still_confirms(self):
        a = self.make(fake([{"kind": "task", "name": "note_clear"}]))
        self.ex.tasks.anotar("algo")
        out = a.handle("jarvis limpiá toda la lista esa")
        self.assertIn("confirmo", out[0])
        self.assertIn("algo", self.ex.tasks.pendientes())

    def test_shutdown_from_llm_still_needs_confirmation(self):
        a = self.make(fake([{"kind": "system", "name": "shutdown"}]))
        out = a.handle("jarvis ya me voy a dormir, dejá todo")
        self.assertIn("confirmo", out[0])
        self.assertEqual(self.ex.done, [])

    def test_llm_down_falls_back(self):
        a = self.make(broken)
        self.assertEqual(a.handle("jarvis hacé algo raro"), ["No entendí."])

    def test_no_llm_on_followup_noise(self):
        a = self.make(fake([{"kind": "say", "text": "hola"}]))
        a.handle("jarvis abrí brave")
        self.t = 2
        self.assertEqual(a.handle("che pasame la sal"), [])

    def test_wake_then_free_command_uses_llm(self):
        a = self.make(fake([{"kind": "say", "text": "ok"}]))
        a.handle("jarvis")
        self.t = 2
        self.assertEqual(a.handle("contame algo"), ["ok"])

    def test_bare_action_object_is_accepted(self):
        def bare(url, payload, timeout):
            return {"message": {"content": _json.dumps({"kind": "say", "text": "Dale."})}}
        a = self.make(bare)
        self.assertEqual(a.handle("jarvis contame algo"), ["Dale."])

    def test_action_list_is_accepted(self):
        def lst(url, payload, timeout):
            return {"message": {"content": _json.dumps([{"kind": "open", "name": "brave"}])}}
        a = self.make(lst)
        a.handle("jarvis quiero navegar un rato")
        self.assertEqual(self.ex.done, ["abrir app brave"])

    def test_prompt_renders(self):
        seen = {}

        def spy(url, payload, timeout):
            seen["p"] = payload["messages"][0]["content"]
            return {"message": {"content": "{}"}}
        self.make(spy).handle("jarvis algo raro")
        self.assertIn("descargas", seen["p"])
        self.assertIn("brief", seen["p"])
        self.assertNotIn("{hora}", seen["p"])


# ---------------------------------------------------------------- ventana
class Ventana(unittest.TestCase):
    """La ventana necesita tkinter para dibujarse, pero la cola se puede probar sin pantalla."""

    def test_cola_y_pausa(self):
        import threading
        from jarvis.hud import Hud, NullUI

        pausado, parar = threading.Event(), threading.Event()
        hud = Hud(pausado, parar)
        hud.status("escuchando")
        hud.heard("abrí brave")
        hud.said("Abriendo brave.")
        eventos = [hud.q.get_nowait() for _ in range(3)]
        self.assertEqual(eventos, [("status", "escuchando"), ("heard", "abrí brave"),
                                   ("said", "Abriendo brave.")])

        hud.alternar_pausa()
        self.assertTrue(pausado.is_set())
        hud.alternar_pausa()
        self.assertFalse(pausado.is_set())
        hud.salir()
        self.assertTrue(parar.is_set())

        ui = NullUI()           # no debe romper nunca
        ui.status("x"); ui.heard("x"); ui.said("x"); ui.log("x"); ui.close()


# ---------------------------------------------------------------- voz
class Voz(unittest.TestCase):
    def test_elige_masculina_por_lo_que_dice_windows(self):
        from jarvis.voz import elegir_voz
        voces = [("Microsoft Helena", "es-ES", "Female"),
                 ("Microsoft Pablo", "es-ES", "Male"),
                 ("Microsoft David", "en-US", "Male")]
        self.assertEqual(elegir_voz(voces, "masculina"), "Microsoft Pablo")
        self.assertEqual(elegir_voz(voces, "femenina"), "Microsoft Helena")

    def test_prefiere_espanol_sobre_el_genero_correcto_en_ingles(self):
        from jarvis.voz import elegir_voz
        voces = [("Microsoft David", "en-US", "Male"),
                 ("Microsoft Helena", "es-ES", "Female")]
        self.assertEqual(elegir_voz(voces, "masculina"), "Microsoft Helena")

    def test_cuando_windows_no_informa_genero_usa_el_nombre(self):
        from jarvis.voz import elegir_voz
        voces = [("Microsoft Helena Desktop", "es-ES", "NotSet"),
                 ("Microsoft Jorge Desktop", "es-ES", "NotSet")]
        self.assertEqual(elegir_voz(voces, "masculina"), "Microsoft Jorge Desktop")

    def test_avisa_cuando_no_hay_del_genero_pedido(self):
        from jarvis.voz import elegir_voz, hay_del_genero
        # masculina en inglés no sirve: se va a usar una española femenina
        voces = [("Microsoft Sabina", "es-MX", "Female"),
                 ("Microsoft David", "en-US", "Male")]
        self.assertFalse(hay_del_genero(voces, "masculina"))
        self.assertEqual(elegir_voz(voces, "masculina"), "Microsoft Sabina")
        con_pablo = voces + [("Microsoft Pablo", "es-ES", "Male")]
        self.assertTrue(hay_del_genero(con_pablo, "masculina"))

    def test_sin_voces_devuelve_nada(self):
        from jarvis.voz import elegir_voz
        self.assertIsNone(elegir_voz([], "masculina"))

    def test_ritmo_sapi_se_mantiene_en_rango(self):
        from jarvis.voz import _ritmo_sapi
        self.assertEqual(_ritmo_sapi(200), 0)
        self.assertEqual(_ritmo_sapi(185), -1)
        self.assertTrue(-10 <= _ritmo_sapi(40) <= 10)
        self.assertTrue(-10 <= _ritmo_sapi(900) <= 10)

    def test_el_guion_de_powershell_escapa_las_comillas(self):
        from jarvis.voz import VozPowerShell
        guion = VozPowerShell.GUION.format(ritmo=0, seleccion="try{$s.SelectVoice('O''Brien')}catch{};")
        self.assertIn("O''Brien", guion)
        self.assertIn("FromBase64String", guion)
        self.assertNotIn("{ritmo}", guion)

    def test_si_no_hay_ningun_motor_lo_dice_y_no_rompe(self):
        from jarvis.speaker import Speaker
        hablante = Speaker({"voz": {"motor": "piper", "modelo": "voces/no-existe.onnx"}})
        for _ in range(50):
            if hablante.motor != "cargando":
                break
            import time as _t
            _t.sleep(0.02)
        self.assertEqual(hablante.motor, "ninguno")
        self.assertFalse(hablante.enabled)
        hablante.say("esto no debería romper nada")   # sigue andando sin voz

    def test_motor_apagado_cuando_no_se_pide_voz(self):
        from jarvis.speaker import Speaker
        self.assertEqual(Speaker({}, enabled=False).motor, "apagada")


# ---------------------------------------------------------------- velocidad
class Velocidad(unittest.TestCase):
    def test_payload_trae_keep_alive_y_tope(self):
        visto = {}

        def spy(url, payload, timeout):
            visto.update(payload)
            return {"message": {"content": "{}"}}
        OllamaPlanner(CFG, transport=spy).plan("algo")
        self.assertEqual(visto["keep_alive"], "30m")
        self.assertEqual(visto["options"]["num_predict"], 160)
        self.assertEqual(visto["options"]["temperature"], 0)

    def test_recuerda_las_ultimas_vueltas(self):
        vistos = []

        def spy(url, payload, timeout):
            vistos.append(payload["messages"])
            return {"message": {"content": _json.dumps(
                {"actions": [{"kind": "open", "name": "brave"}]})}}
        p = OllamaPlanner(CFG, transport=spy)
        p.plan("abrime el navegador")
        p.plan("y ahora cerralo")
        roles = [m["role"] for m in vistos[1]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertEqual(vistos[1][1]["content"], "abrime el navegador")

    def test_no_recuerda_si_no_entendio(self):
        def vacio(url, payload, timeout):
            return {"message": {"content": "{}"}}
        p = OllamaPlanner(CFG, transport=vacio)
        p.plan("una")
        p.plan("otra")
        self.assertEqual(len(p.historial), 0)

    def test_precalentar_no_rompe_sin_ollama(self):
        p = OllamaPlanner(CFG, transport=broken)
        p.precalentar()   # corre en segundo plano y solo debe anotar el aviso
        import time as _t
        _t.sleep(0.2)


# ---------------------------------------------------------------- configuración
class Config(unittest.TestCase):
    def test_merge_anidado_no_pisa_el_resto(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = Path(tmp.name) / "config.json"
        p.write_text(_json.dumps({
            "empleo": {"por_defecto": "electricidad"},
            "apps": {"LOGO Soft": "C:/logo.exe"},
            "ubicacion": {"nombre": "Temperley"},
        }), encoding="utf-8")
        cfg = load_config(p)
        self.assertEqual(cfg["empleo"]["por_defecto"], "electricidad")
        self.assertIn("programacion", cfg["empleo"]["perfiles"])      # no se perdió
        self.assertEqual(cfg["apps"]["logo soft"], "C:/logo.exe")     # clave en minúscula
        self.assertEqual(cfg["apps"]["brave"], "brave")               # las de fábrica siguen
        self.assertEqual(cfg["ubicacion"]["nombre"], "Temperley")
        self.assertEqual(cfg["ubicacion"]["zona"], "America/Argentina/Buenos_Aires")


if __name__ == "__main__":
    unittest.main()
