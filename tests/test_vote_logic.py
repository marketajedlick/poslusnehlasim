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


def _load_topic_proslo_from_vote_logic():
    vote_logic_path = Path(__file__).resolve().parents[1] / "svejk" / "build" / "vote_logic.py"
    spec = importlib.util.spec_from_file_location("svejk_vote_logic_for_tests", vote_logic_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.topic_proslo_from_votes


_verdikt = _load_verdikt_from_extract()
topic_proslo_from_votes = _load_topic_proslo_from_vote_logic()


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


if __name__ == "__main__":
    unittest.main()
