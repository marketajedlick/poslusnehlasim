import json
import importlib.util
import tempfile
import unittest
from pathlib import Path


_IO_PATH = Path(__file__).resolve().parents[1] / "svejk" / "build" / "io.py"
_IO_SPEC = importlib.util.spec_from_file_location("svejk_build_io_for_tests", _IO_PATH)
_IO_MODULE = importlib.util.module_from_spec(_IO_SPEC)
assert _IO_SPEC is not None and _IO_SPEC.loader is not None
_IO_SPEC.loader.exec_module(_IO_MODULE)
iter_jsonl = _IO_MODULE.iter_jsonl


class IterJsonlTests(unittest.TestCase):
    def test_missing_file_returns_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.jsonl"
            self.assertEqual(list(iter_jsonl(missing)), [])

    def test_empty_file_returns_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            self.assertEqual(list(iter_jsonl(path)), [])

    def test_normal_file_streams_rows_and_skips_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.jsonl"
            row1 = {"id": 1, "text": "a"}
            row2 = {"id": 2, "text": "b"}
            payload = (
                json.dumps(row1, ensure_ascii=False)
                + "\n\n"
                + json.dumps(row2, ensure_ascii=False)
                + "\n"
            )
            path.write_text(payload, encoding="utf-8")

            rows = list(iter_jsonl(path))
            self.assertEqual(rows, [row1, row2])


if __name__ == "__main__":
    unittest.main()
