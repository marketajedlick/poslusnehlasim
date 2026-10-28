"""Typ hlasování ze stena a výsledek bodu."""

from svejk.build.vote_logic import (
    classify_vote_motion,
    topic_proslo_from_votes,
    topic_vysledek,
    verdikt_odporuje,
    vote_motions_from_steno,
)


def _v(cislo, vysledek, pro=100, proti=10):
    return {"cislo": cislo, "vysledek": vysledek, "pro": pro, "proti": proti, "datum": "30.06.2026", "cas": f"10:{cislo:02d}"}


def test_classify_final_and_referral():
    assert classify_vote_motion(
        "návrh usnesení zní: Poslanecká sněmovna vyslovuje souhlas s vládním návrhem zákona", ""
    ) == "zaverecne"
    assert classify_vote_motion("", " … Konstatuji, že tento návrh byl přikázán k projednání výboru") == "prikazani"
    assert classify_vote_motion("vypořádáme se s návrhem na zamítnutí návrhu zákona", "") == "zamitnuti"
    assert classify_vote_motion("návrh na vrácení zákona garančnímu výboru", "") == "vraceni"
    assert classify_vote_motion("pozměňovací návrh pana poslance", "") == "pozmenovak"


def test_motions_from_steno_text():
    steno = [
        {"poradi": 1, "text": "Kdo souhlasí s tím, aby návrh byl přikázán výboru? Hlasování číslo 165, pro 95. Konstatuji, že tento návrh byl přikázán k projednání výboru."},
        {"poradi": 2, "text": "Hlasujeme o pozměňovacím návrhu. Hlasování číslo 166, pro 25, proti 63."},
    ]
    assert vote_motions_from_steno(steno) == {165: "prikazani", 166: "pozmenovak"}


def test_first_reading_referral_is_postup_not_rejection():
    group = [_v(164, "R", 27, 68), _v(165, "A", 95, 0), _v(166, "R", 25, 63), _v(167, "R", 22, 62)]
    motions = {164: "vraceni", 165: "prikazani", 166: "prikazani", 167: "prikazani"}
    assert topic_vysledek(group, motions) == "postup"
    assert verdikt_odporuje("zamiteno", "postup")
    assert not verdikt_odporuje("prvni_cteni", "postup")


def test_final_vote_decides_even_after_amendments():
    group = [_v(1, "A"), _v(2, "A"), _v(3, "R", 60, 108)]
    motions = {1: "pozmenovak", 2: "pozmenovak", 3: "zaverecne"}
    assert topic_vysledek(group, motions) == "zamitnuto"
    assert topic_proslo_from_votes(group, motions) is False
    # bez stena stará heuristika (prošel pozměňovák = „prošlo“)
    assert topic_proslo_from_votes(group) is True


def test_veto_override_last_final_wins():
    group = [_v(37, "R", 0, 108), _v(38, "A", 104, 45)]
    assert topic_vysledek(group, {37: "zaverecne", 38: "zaverecne"}) == "schvaleno"


def test_konstatovani_zaverecneho_hlasovani():
    assert classify_vote_motion("", ", pro 92 proti 40. Konstatuji, že s návrhem zákona byl vysloven souhlas.") == "zaverecne"
    assert classify_vote_motion("", ", pro 54. Konstatuji, že jsme návrh zákona ve znění schváleném Senátem nepřijali.") == "zaverecne"
    assert classify_vote_motion("", " a návrh usnesení nebyl schválen. A já konstatuju, že návrh zákona nebyl přijat.") == "zaverecne"
    # ukončení rozpravy po textu o jiném bodu není závěrečné hlasování
    pre = "Poslanecká sněmovna vyslovuje souhlas s návrhem zákona" + " x" * 300 + " hlasujeme o ukončení rozpravy."
    assert classify_vote_motion(pre, " Návrh byl přijat. Rozprava je ukončena.") == "jine"
