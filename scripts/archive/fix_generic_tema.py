#!/usr/bin/env python3
"""Přepíše obecné tema_vysvetleni v aligned/topics.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svejk.obcansky import GLOSY, GENERIC_GLOSA_MARKERS, TEMA_PRAVIDLA, glosa_pro_obcana, tema_z_nazvu
from svejk.paths import SchuzePaths

# (schuze, slug) → ruční text, když automatika selže
MANUAL: dict[tuple[int, str], str] = {
    (2, "navrh-na-stanoveni-poctu-poslancu-ve-stalych-del"): (
        "Sněmovna stanovila, kolik poslanců má jednotlivé stálé delegace "
        "v meziparlamentních orgánech. Běžného člověka to nijak nezasáhne."
    ),
    (5, "navrh-na-odvolani-clenu-dr-sfdi"): (
        "Sněmovna hlasovala o odvolání členů dozorčí rady Státního fondu "
        "dopravní infrastruktury. Jde o personální obsazení fondu, ne o silnice hned zítra."
    ),
    (10, "novela-z-o-statnich-svatcich"): (
        "Návrh mění zákon o státních svátcích a dnech pracovního klidu. "
        "Týká se kalendáře volných dnů a toho, které dny jsou státní svátky."
    ),
    (14, "novela-z-o-statnich-svatcich"): (
        "Senát vrátil úpravy zákona o státních svátcích, Sněmovna je znovu projednává. "
        "Mění se kalendář státních svátků a pravidla pro dny pracovního klidu."
    ),
    (14, "posouzeni-podminek-pro-projednani-st-163-ve-zkra"): (
        "Sněmovna rozhodla, jestli se zákon o cenách benzínu projedná ve zkráceném režimu. "
        "Kratší debata znamená rychlejší hlasování."
    ),
    (14, "potvrzeni-trvani-stavu-legislativni-nouze"): (
        "Sněmovna potvrdila legislativní nouzi u zákona o cenách pohonných hmot. "
        "Stát tak může zákon projednat rychleji než obvykle."
    ),
    (24, "navrh-na-stanoveni-vyse-odmen-clenum-kr-ta-cr-za"): (
        "Sněmovna schválila roční odměny členům kontrolní rady Technologické agentury, "
        "částky se pohybují zhruba mezi 60 a 105 tisíci korunami."
    ),
    (24, "novela-z-trestni-zakonik"): (
        "Sněmovna projednávala změny trestního zákoníku. Úpravy se týkají pravidel trestných činů a sankcí."
    ),
    (24, "sml-cr-malta-o-zamezeni-dvojimu-zdaneni"): (
        "Smlouva s Maltou má zabránit dvojímu zdanění stejných příjmů. "
        "Týká se lidí a firem s příjmy v obou zemích."
    ),
    (24, "sml-mezi-cr-a-kenskou-republikou-o-zamezeni-dvoj"): (
        "Smlouva s Keňou upravuje zdanění příjmů z obou zemí, aby neplatil občan daně dvakrát za totéž."
    ),
    (24, "sml-mezi-cr-a-mongolskem-o-policejni-spolupraci"): (
        "Smlouva s Mongolskem umožní české a mongolské policii spolupracovat při stíhání a vymáhání trestů."
    ),
    (24, "sml-mezi-cr-a-slovenskou-republikou-o-policejni-"): (
        "Smlouva se Slovenskem rozšiřuje policejní spolupráci, hlavně vymáhání trestů a předávání osob."
    ),
    (24, "sml-mezi-cr-a-srn-o-statnich-hranicich"): (
        "Smlouva s Německem upravuje průběh státní hranice na řece Nežárce. "
        "Týká se především obcí u jihočeské hranice."
    ),
    (24, "sml-mezi-cr-a-tanzanskou-repub-o-zamezeni-dvojim"): (
        "Smlouva s Tanzanií má zabránit dvojímu zdanění příjmů občanů a firem působících v obou zemích."
    ),
}


def _glosa_je_nedostatecna(gloss: str) -> bool:
    if not gloss or len(gloss.strip()) < 45:
        return True
    low = gloss.lower()
    if any(m in low for m in GENERIC_GLOSA_MARKERS):
        return True
    if "-" in gloss[:90]:
        label = gloss.split("-", 1)[0].strip()
        if len(label.split()) <= 3 and len(gloss.split()) < 22:
            return True
    return False


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[0].strip()


def _clean_koho(s: str) -> str:
    s = re.sub(r"^Koho se to týká\?\s*", "", s.strip())
    s = re.sub(r"^Občana se to netýká[,\.]?\s*", "", s, flags=re.I)
    return s.strip()


def _ok(text: str) -> bool:
    t = (text or "").strip()
    return len(t) >= 45 and not _glosa_je_nedostatecna(t)


def _human_nazev(nazev: str) -> str:
    n = (nazev or "").strip()
    n = re.sub(r"^(Novela|Návrh|Náv\.|N\.|Sml\.|Vl\.n\.z\.|Vl\. n\. z\.)\s+", "", n, flags=re.I)
    n = re.sub(r"^z\.\s+", "", n, flags=re.I)
    return n[0].lower() + n[1:] if n else ""


def _pick(*cands: str) -> str | None:
    seen: set[str] = set()
    for c in cands:
        for variant in (c, _first_sentence(c)):
            v = variant.strip()
            if not v or v in seen:
                continue
            seen.add(v)
            if _ok(v):
                return v
    return None


def _from_glosy(nazev: str, *, proslo: bool) -> str | None:
    t = nazev.lower()
    best: str | None = None
    best_len = 0
    for klicova, text_ok, text_ne in GLOSY:
        for k in klicova:
            if k in t and len(k) > best_len:
                best = text_ok if proslo else text_ne
                best_len = len(k)
    return _pick(best or "")


def _from_tema_pravidla(nazev: str) -> str | None:
    t = nazev.lower()
    for klicova, _svejk, vysvetleni in TEMA_PRAVIDLA:
        if any(k in t for k in klicova):
            picked = _pick(vysvetleni)
            if picked:
                return picked
    return None


def propose_from_fact(fact: dict, sch: int) -> str | None:
    slug = fact["slug"]
    manual = MANUAL.get((sch, slug))
    if manual:
        return _pick(manual)

    nazev = fact.get("nazev", "")
    cands: list[str] = []

    for key in ("mean", "lead"):
        raw = (fact.get(key) or "").strip()
        if raw:
            cands.append(_first_sentence(raw.split("\n")[0]))

    for k in fact.get("koho") or []:
        ck = _clean_koho(k)
        if ck:
            cands.append(ck)

    pl = (fact.get("predmet_lidsky") or "").strip()
    if pl:
        cands.append(f"Sněmovna hlasovala o {pl}.")

    gloss = glosa_pro_obcana(nazev, "", proslo=fact.get("proslo", True))
    if gloss:
        cands.extend([gloss, _first_sentence(gloss)])

    cands.append(_from_glosy(nazev, proslo=fact.get("proslo", True)) or "")
    cands.append(_from_tema_pravidla(nazev) or "")

    _, tz = tema_z_nazvu(nazev)
    if tz:
        cands.append(tz)

    for fak in fact.get("fakty") or []:
        txt = (fak.get("text") or "").strip()
        if txt and len(txt.split()) >= 8 and fak.get("kind") != "scene":
            cands.append(_first_sentence(txt))

    return _pick(*cands) or (manual if manual else None)


def propose_from_topic(topic: dict, sch: int, fact: dict | None) -> str | None:
    if fact:
        picked = propose_from_fact(fact, sch)
        if picked:
            return picked

    slug = topic.get("slug", "")
    manual = MANUAL.get((sch, slug))
    if manual:
        return _pick(manual)

    nazev = topic.get("nazev", "") or ""
    proslo = topic.get("proslo", True)
    kategorie = topic.get("kategorie", "")
    short = _human_nazev(nazev)
    low = nazev.lower()

    picked = _pick(
        glosa_pro_obcana(nazev, "", proslo=proslo) or "",
        _from_glosy(nazev, proslo=proslo) or "",
        _from_tema_pravidla(nazev) or "",
        tema_z_nazvu(nazev)[1],
    )
    if picked:
        return picked

    if kategorie == "personalka" or any(
        k in low
        for k in (
            "volbu členů",
            "volba členů",
            "jmenování",
            "odvolání členů",
            "zřízení sk",
            "zřízení stálé",
            "potvrzení předsed",
            "ochránce práv",
        )
    ):
        return _pick(f"Sněmovna řešila personální obsazení: {short}. Běžného člověka to nijak nezasáhne.")

    if any(k in low for k in (" - eu", " eu", "evropsk", "souladu s předpisy", "ekodesign", "digitalní ekonom")):
        return _pick(
            f"Sněmovna projednávala změnu zákona kvůli pravidlům Evropské unie. Téma: {short}."
        )

    if "rozpočet" in low or "rozpoct" in low:
        return _pick(f"Sněmovna schvalovala rozpočet státního fondu na rok 2026. Téma: {short}.")

    if "sml." in low or low.startswith("sml "):
        return _pick(f"Sněmovna ratifikovala mezinárodní smlouvu. Téma: {short}.")

    if "usnesení" in low or kategorie == "usneseni":
        return _pick(f"Sněmovna hlasovala o politickém usnesení. Téma: {short}.")

    if short and len(short) >= 25:
        return _pick(f"Sněmovna hlasovala o návrhu týkajícím se {short}.")

    return None


def main() -> int:
    fixed = 0
    still_bad: list[str] = []

    for sch in range(1, 25):
        paths = SchuzePaths.create(2025, sch)
        if not paths.topics_json.is_file():
            continue

        topics_data = json.loads(paths.topics_json.read_text(encoding="utf-8"))
        topics = topics_data.get("topics") or []
        changed = False

        for topic in topics:
            slug = topic.get("slug")
            if not slug:
                continue
            old = topic.get("tema_vysvetleni") or ""
            if not _glosa_je_nedostatecna(old):
                continue

            fact_path = paths.facts_by_topic / f"{slug}.json"
            fact = json.loads(fact_path.read_text(encoding="utf-8")) if fact_path.is_file() else None

            new_vysv = propose_from_topic(topic, sch, fact)
            if not new_vysv or not _ok(new_vysv):
                still_bad.append(f"s{sch}/{slug}: {new_vysv!r}")
                continue
            if old == new_vysv:
                continue

            topic["tema_vysvetleni"] = new_vysv
            changed = True
            fixed += 1

        if changed:
            paths.topics_json.write_text(
                json.dumps(topics_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    print(f"fixed: {fixed}")
    if still_bad:
        print("still_bad:")
        for line in still_bad:
            print(" ", line)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
