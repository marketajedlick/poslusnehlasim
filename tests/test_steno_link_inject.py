"""Vkládání steno odkazů: žádné vnořené <a>, hranice slov, fráze s čísly."""

from svejk.build.day_content import _sanitize_citace_export, _sanitize_mean_export
from svejk.build.steno_sources import _speaker_clause, inject_steno_link


def test_no_nested_link_when_phrase_spans_existing_link():
    text = 'Bendl (ODS) chtěl <a class="steno-link" href="#x">dodání papírů</a> včas.'
    assert inject_steno_link(text, "Bendl (ODS) chtěl dodání papírů", "#b") == text


def test_word_boundary():
    out = inject_steno_link("Nezákonný zákon.", "zákon", "#a")
    assert out == 'Nezákonný <a class="steno-link" href="#a">zákon</a>.'


def test_truncated_phrase_expands_to_whole_word():
    out = inject_steno_link("Rakušanův návrh", "Rakušan", "#d")
    assert out == '<a class="steno-link" href="#d">Rakušanův</a> návrh'


def test_phrase_with_digits_matches_words_in_text():
    out = inject_steno_link("Prošlo, sto třicet devět pro.", "139 pro", "#c")
    assert '<a class="steno-link" href="#c">sto třicet devět pro</a>' in out


def test_speaker_clause_stops_at_tag():
    text = 'Bendl (ODS) chtěl <a class="steno-link" href="#x">dodání</a> papírů'
    clause = _speaker_clause("Jan Bendl", text)
    assert clause is None or "<" not in clause


def test_sanitizer_keeps_text_with_lone_lt():
    assert _sanitize_citace_export("pod <5 % a <strong>ministr</strong>") == (
        "pod &lt;5 % a <strong>ministr</strong>"
    )
    assert "script" not in _sanitize_mean_export("a <script>x</script>")


def test_party_label_before_punctuation():
    text = "Při hlasování chyběl Andrej Babiš (ANO), premiér, a Macinka."
    out = inject_steno_link(text, "chyběl Andrej Babiš, premiér, a", "#x")
    assert '<a class="steno-link" href="#x">chyběl Andrej Babiš (ANO), premiér, a</a>' in out


def test_link_metric_ignores_party_labels_and_dashes():
    from svejk.edition.metrics import _norm_citace, _norm_link_text

    assert _norm_link_text("Richterová (Piráti) kritizovala vládu.") == "richterová kritizovala vládu"
    assert _norm_citace("všechno – možná") == _norm_citace("všechno, možná")
