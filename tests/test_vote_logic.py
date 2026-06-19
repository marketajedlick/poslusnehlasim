import ast
import importlib.util
import unittest
from pathlib import Path


def _load_verdikt_from_extract():
    extract_path = Path(__file__).resolve().parents[1] / "svejk" / "build" / "extract.py"
    source = extract_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(extract_path))
    func_node = next(
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name == "_verdikt"
    )
    isolated_module = ast.Module(body=[func_node], type_ignores=[])
    ast.fix_missing_locations(isolated_module)
    namespace: dict[str, object] = {}
    exec(compile(isolated_module, filename=str(extract_path), mode="exec"), namespace)
    return namespace["_verdikt"]


def _load_vote_logic_helpers():
    vote_logic_path = Path(__file__).resolve().parents[1] / "svejk" / "build" / "vote_logic.py"
    spec = importlib.util.spec_from_file_location("svejk_vote_logic_for_tests", vote_logic_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.topic_proslo_from_votes, module.topic_proslo_druhe_cteni_ukonceno


_verdikt = _load_verdikt_from_extract()
topic_proslo_from_votes, topic_proslo_druhe_cteni_ukonceno = _load_vote_logic_helpers()


class VerdiktTests(unittest.TestCase):
    def test_verdikt_odlozeno_for_postponement_keyword(self) -> None:
        self.assertEqual(
            _verdikt(
                proslo=True,
                nazev="Návrh na odložení digitalizace dávek",
                vysvetleni="",
            ),
            "odlozeno",
        )

    def test_verdikt_schvaleno_when_passed_without_delay_signal(self) -> None:
        self.assertEqual(
            _verdikt(
                proslo=True,
                nazev="Návrh zákona o státních zaměstnancích",
                vysvetleni="",
            ),
            "schvaleno",
        )

    def test_verdikt_zamiteno_when_not_passed_without_delay_signal(self) -> None:
        self.assertEqual(
            _verdikt(
                proslo=False,
                nazev="Návrh zákona o státních zaměstnancích",
                vysvetleni="",
            ),
            "zamiteno",
        )


class TopicProsloFromVotesTests(unittest.TestCase):
    def test_returns_false_for_empty_group(self) -> None:
        self.assertFalse(topic_proslo_from_votes([]))

    def test_returns_true_for_decisive_acceptance(self) -> None:
        group = [
            {"datum": "01.01.2026", "cas": "10:00", "vysledek": "A", "pro": 102, "proti": 88}
        ]
        self.assertTrue(topic_proslo_from_votes(group))

    def test_returns_false_when_no_decisive_acceptance_exists(self) -> None:
        group = [
            {"datum": "01.01.2026", "cas": "10:00", "vysledek": "A", "pro": 90, "proti": 90},
            {"datum": "01.01.2026", "cas": "10:05", "vysledek": "R", "pro": 89, "proti": 91},
        ]
        self.assertFalse(topic_proslo_from_votes(group))

    def test_returns_false_for_marathon_interruptions_pattern(self) -> None:
        group = [{"datum": "01.01.2026", "cas": "10:00", "vysledek": "A", "pro": 101, "proti": 80}]
        for i in range(10):
            group.append(
                {
                    "datum": "01.01.2026",
                    "cas": f"10:{i + 1:02d}",
                    "vysledek": "R",
                    "pro": 80,
                    "proti": 101,
                }
            )
        self.assertFalse(topic_proslo_from_votes(group))


class TopicProsloSecondReadingTests(unittest.TestCase):
    def test_detects_second_reading_concluded_after_return_vote(self) -> None:
        texts = [
            "Návrh na vrácení zákona garančnímu výboru k novému projednání byl zamítnut.",
            "Končím tedy druhé čtení tohoto návrhu zákona.",
        ]
        self.assertTrue(topic_proslo_druhe_cteni_ukonceno(texts))

    def test_ignores_without_second_reading_closure(self) -> None:
        texts = ["Návrh na vrácení zákona garančnímu výboru k novému projednání byl zamítnut."]
        self.assertFalse(topic_proslo_druhe_cteni_ukonceno(texts))


def _load_spor_helpers():
    vote_logic_path = Path(__file__).resolve().parents[1] / "svejk" / "build" / "vote_logic.py"
    spec = importlib.util.spec_from_file_location("svejk_vote_logic_spor", vote_logic_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.spor_o_porad_schuze, module.debata_vysledek_radek


spor_o_porad_schuze, debata_vysledek_radek = _load_spor_helpers()


class SporOPoradTests(unittest.TestCase):
    def test_s23_porad_is_not_long_dispute(self) -> None:
        votes = [
            {"je_porad_schuze": True, "proti": 34, "cas": "15:04"},
            {"je_porad_schuze": True, "proti": 6, "cas": "15:04"},
        ]
        self.assertFalse(spor_o_porad_schuze(votes))

    def test_many_proti_on_porad_counts_as_dispute(self) -> None:
        votes = [{"je_porad_schuze": True, "proti": 45, "cas": "15:04"}]
        self.assertTrue(spor_o_porad_schuze(votes))

    def test_long_debate_without_porad_dispute(self) -> None:
        line = debata_vysledek_radek(
            {"dlouha_debata": True, "minuty": 283, "spor_o_porad": False}
        )
        self.assertIn("celé odpoledne", line)


if __name__ == "__main__":
    unittest.main()
