import unittest

from jarvis.actions import Executor
from jarvis.assistant import Assistant
from jarvis.commands import parse, strip_wake
from jarvis.config import load_config

CFG = load_config("/nonexistent.json")


def kinds(text):
    _, rest = strip_wake(text)
    return [(i.kind, i.arg) for i in parse(rest, CFG)]


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


class Flow(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.ex = Executor(CFG, dry_run=True)
        self.a = Assistant(CFG, self.ex, clock=lambda: self.t)

    def test_ignores_without_wake(self):
        self.assertEqual(self.a.handle("abrí brave"), [])
        self.assertEqual(self.ex.done, [])

    def test_wake_only_then_command(self):
        self.assertEqual(self.a.handle("Jarvis"), ["Decime."])
        self.t = 3
        self.a.handle("abrí brave")
        self.assertEqual(self.ex.done, ["abrir app brave"])

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



import json as _json
from jarvis.llm import OllamaPlanner


def fake(actions):
    def transport(url, payload, timeout):
        return {"message": {"content": _json.dumps({"actions": actions})}}
    return transport


def broken(url, payload, timeout):
    raise ConnectionError("ollama apagado")


class FreeCommands(unittest.TestCase):
    def make(self, transport):
        self.t = 0.0
        self.ex = Executor(CFG, dry_run=True)
        return Assistant(CFG, self.ex, clock=lambda: self.t,
                         planner=OllamaPlanner(CFG, transport=transport))

    def test_llm_used_when_rules_fail(self):
        a = self.make(fake([{"kind": "open", "name": "descargas"}, {"kind": "open", "name": "brave"}]))
        a.handle("jarvis llevame a lo que baje hoy y dejame navegar")
        self.assertEqual(self.ex.done, ["abrir carpeta " + __import__("os").path.expanduser("~/Downloads"),
                                        "abrir app brave"])

    def test_rules_take_priority(self):
        a = self.make(fake([{"kind": "open", "name": "calculadora"}]))
        a.handle("jarvis abrí brave")
        self.assertEqual(self.ex.done, ["abrir app brave"])

    def test_invalid_actions_are_dropped(self):
        a = self.make(fake([{"kind": "open", "name": "formatear disco"},
                            {"kind": "run", "cmd": "del /s *"},
                            {"kind": "system", "name": "rm_everything"}]))
        out = a.handle("jarvis hacé algo raro")
        self.assertEqual(out, ["No entendí."])
        self.assertEqual(self.ex.done, [])

    def test_say(self):
        a = self.make(fake([{"kind": "say", "text": "Son las diez."}]))
        self.assertEqual(a.handle("jarvis qué hora es"), ["Son las diez."])

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


if __name__ == "__main__":
    unittest.main()
