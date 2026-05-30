"""Novinove shrnuti schuze ve stylu Svejka, rozsireny text z casove osy."""

from __future__ import annotations

import re
import random
from datetime import datetime

from svejk.mix import compose_template, pick_slot, re_sub_space
from svejk.obcansky import glosa_pro_obcana
from svejk.timeline import BlokDne, DenSchuze, SchuzeCasovaOsa

HLAVICKA_LISTU = "Poslušně hlásím z Poslanecké sněmovny"


def _new_state() -> dict:
    return {"poslusne": False, "used": set(), "seq": 0, "salt": random.randint(0, 2**31)}


def _glosuj_fakt(vysv: str, core: str, *, zamitnuto: bool, state: dict, seed: str) -> str:
    nazev = core.removeprefix("Hlasovali o:").strip() if core.startswith("Hlasovali o:") else core
    obcansky = glosa_pro_obcana(nazev, vysv, proslo=not zamitnuto)
    if obcansky:
        return obcansky

    if zamitnuto:
        return "Návrh neprošel, pro vás se zatím nic nemění."
    return ""


def _pridej_glosu(text: str, gloss: str) -> str:
    if not gloss:
        return text
    if gloss.lower()[:50] in text.lower():
        return text
    return re_sub_space(f"{text} {gloss}")


def _podobne(a: str, b: str) -> bool:
    words = {w[:5] for w in re.findall(r"\w{4,}", a.lower())}
    return len(words & {w[:5] for w in re.findall(r"\w{4,}", b.lower())}) >= 2


def _law_kategorie(blok: BlokDne) -> str:
    t = (blok.nazev + " " + blok.svejk + " " + blok.vysvetleni).lower()
    if "interpelac" in t:
        return "interpelace"
    if any(k in t for k in ("dosadili", "výbor", "personál", "volbu", "jmenování", "komis", " rady ", "volba ", "volby ")):
        return "personalka"
    return "substantivni"


def _core_text(blok: BlokDne) -> str:
    core = re.sub(r"\s*Tentokrát ne.*", "", blok.svejk).strip()
    core = re.sub(r"^Poslušně hlásím,?\s*", "", core)
    if core:
        core = core[0].upper() + core[1:]
    return core


def _zamitnuto(blok: BlokDne) -> bool:
    if blok.typ == "law":
        return not blok.proslo
    return "smetli ze stolu" in blok.svejk or "Tentokrát ne" in blok.svejk


def _zkrat_nazev(nazev: str) -> str:
    n = nazev.strip()
    for prefix in ("Vl.n.z., ", "Vl. n. z. , ", "Novela z. o ", "Návrh na "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    if len(n) > 55:
        n = n[:52] + "…"
    return n[0].lower() + n[1:] if n else "bod programu"


def _fakticke_law(blok: BlokDne) -> str:
    cas = _cas_rozsah(blok)
    nazev = _zkrat_nazev(blok.nazev)
    if blok.pocet_hlasovani > 1:
        cast = f"{blok.pocet_hlasovani}× hlasovali o {nazev}"
        if blok.pocet_zamitnuto:
            cast += f" ({blok.pocet_zamitnuto}× zamítnuto, {blok.pocet_prijato}× přijato)"
    else:
        cast = f"hlasovali o {nazev}"
    vysledek = "Prošlo." if blok.proslo else "Neprošlo."
    return f"{cas} {cast}. {vysledek}"


def _sloucit_law_run(bloky: list[BlokDne], start: int) -> tuple[list, int]:
    first = bloky[start]
    kat = _law_kategorie(first)
    if kat == "substantivni":
        return [("law", first)], start + 1

    group = [first]
    j = start + 1
    while j < len(bloky) and bloky[j].typ == "law" and _law_kategorie(bloky[j]) == kat:
        group.append(bloky[j])
        j += 1

    if len(group) == 1:
        return [("law", first)], j

    return [("law_group", kat, group)], j


def _preprocess_bloky(bloky: list[BlokDne]) -> list:
    out: list = []
    i = 0
    while i < len(bloky):
        b = bloky[i]
        if b.typ == "law":
            chunk, i = _sloucit_law_run(bloky, i)
            out.extend(chunk)
        else:
            out.append((b.typ, b))
            i += 1
    return out


def _hodiny_int(text: str) -> int:
    m = re.search(r"(\d+)\s*hodin", text)
    return int(m.group(1)) if m else 0


def _datum_cesky(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    mesice = [
        "ledna", "února", "března", "dubna", "května", "června",
        "července", "srpna", "září", "října", "listopadu", "prosince",
    ]
    return f"{d.day}. {mesice[d.month - 1]} {d.year}"


def _cas_rozsah(blok: BlokDne) -> str:
    if blok.cas_do and blok.cas_do != blok.cas_od:
        return f"Mezi {blok.cas_od} a {blok.cas_do}"
    return f"Ve {blok.cas_od}"


def _prekryv(debate: BlokDne, porad: BlokDne) -> bool:
    return debate.cas_od == porad.cas_od or (
        debate.cas_do and porad.cas_od <= debate.cas_do
    )


def _debate_hint(blok: BlokDne, *, state: dict, seed: str) -> str:
    m = re.search(r"Opozice chtěla\s+(.+?)\.\s", blok.svejk)
    if not m:
        return ""
    return compose_template(
        "{hint}",
        ("hint",),
        seed=f"{seed}|hint",
        state=state,
        temata=m.group(1).strip(),
    )


def _porad_cisla(blok: BlokDne) -> tuple[int, int, int] | None:
    if blok.pocet_hlasovani:
        return blok.pocet_hlasovani, blok.pocet_zamitnuto, blok.pocet_prijato
    svejk = blok.svejk
    m = re.search(r"(\d+)\s*hlasování.*?(\d+)×\s*ne", svejk)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(1)) - int(m.group(2))
    m = re.search(r"(\d+)×\s*ne,\s*(\d+)×\s*jo", svejk)
    if m:
        zamitnuto, prijato = int(m.group(1)), int(m.group(2))
        return zamitnuto + prijato, zamitnuto, prijato
    return None


def _odstavec_start(blok: BlokDne, den: str, datum: str, *, state: dict) -> str:
    seed = f"start|{datum}|{blok.cas_od}"
    if int(blok.cas_od[:2]) >= 12:
        return compose_template(
            "Jednání pokračovalo {datum}, od {cas}. {start_b}. {start_c}",
            ("start_b", "start_c"),
            seed=seed + "|pm",
            state=state,
            cas=blok.cas_od,
            datum=datum,
        )
    if hash(seed) % 3 == 0:
        return compose_template(
            "{den} {cas}, sněmovna znovu usedla. {start_b}. {start_c}",
            ("start_b", "start_c"),
            seed=seed + "|den",
            state=state,
            cas=blok.cas_od,
            den=den.capitalize(),
        )
    return compose_template(
        "{start_a} v {cas}, {start_b}. {start_c}",
        ("start_a", "start_b", "start_c"),
        seed=seed,
        state=state,
        cas=blok.cas_od,
    )


def _odstavec_debate_porad(debate: BlokDne, porad: BlokDne, *, state: dict) -> str:
    hod = "několik"
    m = re.search(r"(\d+)\s*hodin", debate.svejk)
    if m:
        hod = m.group(1)
    cas = _cas_rozsah(debate)
    seed = f"dp|{cas}|{hod}"
    hint = _debate_hint(debate, state=state, seed=seed)
    pm = _porad_cisla(porad)

    if pm:
        celkem, zamitnuto, prijato = pm
        vata = ""
        if _hodiny_int(debate.svejk) >= 3:
            vata = pick_slot("vata_debata", seed=seed + "|vd", state=state)
        elif zamitnuto > celkem // 2:
            vata = pick_slot("vata_porad", seed=seed + "|vp", state=state)
        tail = ""
        if zamitnuto > 0:
            tail = pick_slot("porad_tail", seed=seed + "|t", state=state)
        elif celkem == 1:
            tail = " Pořad prošel bez potíží."
        porad_fakt = f" {celkem}× hlasování o pořadu ({zamitnuto}× zamítnuto, {prijato}× přijato)."
        if celkem == 1 and zamitnuto == 0:
            porad_fakt = " Pořad schůze schválen."
        return compose_template(
            "{dp_open}{vata} {dp_stat}{hint}{porad_fakt}{tail}{porad_cizi}",
            ("dp_open", "dp_stat", "porad_cizi"),
            seed=seed,
            state=state,
            cas=cas,
            hod=hod,
            celkem=celkem,
            zamitnuto=zamitnuto,
            vata=vata,
            hint=hint,
            porad_fakt=porad_fakt,
            tail=tail,
        )

    return compose_template(
        "{deb_open}{vata_debata}{deb_stat}{hint}{porad_cizi}",
        ("deb_open", "vata_debata", "deb_stat", "porad_cizi"),
        seed=seed + "|solo",
        state=state,
        cas=cas,
        hod=hod,
        hint=hint,
    )


def _odstavec_debate(blok: BlokDne, *, state: dict) -> str:
    hod = "několik"
    m = re.search(r"(\d+)\s*hodin", blok.svejk)
    if m:
        hod = m.group(1)
    cas = _cas_rozsah(blok)
    seed = f"deb|{cas}|{hod}"
    hint = _debate_hint(blok, state=state, seed=seed)
    text = compose_template(
        "{deb_open}{vata_debata}{deb_stat}{hint}{porad_cizi}",
        ("deb_open", "vata_debata", "deb_stat", "porad_cizi"),
        seed=seed,
        state=state,
        cas=cas,
        hod=hod,
        hint=hint,
    )
    if "hlasování o:" in blok.vysvetleni:
        nazev = blok.vysvetleni.split("hlasování o:", 1)[1].strip().rstrip(".")
        gloss = glosa_pro_obcana(nazev, proslo=True, nahled=True)
        text = _pridej_glosu(text, gloss)
    return text


def _odstavec_porad(blok: BlokDne, *, state: dict) -> str:
    cas = _cas_rozsah(blok)
    pm = _porad_cisla(blok)
    seed = f"porad|{cas}"
    if pm:
        celkem, zamitnuto, prijato = pm
        if celkem == 1 and zamitnuto == 0:
            base = f"{cas} schválili pořad schůze."
        else:
            base = (
                f"{cas} {celkem}× hlasovali o pořadu dne "
                f"({zamitnuto}× zamítnuto, {prijato}× přijato)."
            )
        vata = ""
        if zamitnuto > celkem // 2:
            vata = pick_slot("vata_porad", seed=seed + "|vb", state=state)
        elif celkem <= 8 and zamitnuto > 0:
            vata = pick_slot("vata_porad_kratka", seed=seed + "|vk", state=state)
        return re_sub_space(base + vata)
    return f"{cas} proběhla hádka o pořad dne."


def _odstavec_law(blok: BlokDne, *, state: dict, law_idx: int) -> str:
    zamitnuto = _zamitnuto(blok)
    seed = f"law|{blok.cas_od}|{law_idx}"
    fakt = _fakticke_law(blok)
    gloss = _glosuj_fakt(
        blok.vysvetleni,
        blok.nazev or _core_text(blok),
        zamitnuto=zamitnuto,
        state=state,
        seed=seed,
    )

    extra = ""
    if zamitnuto:
        extra = pick_slot("zamitnuto", seed=seed + "|z", state=state)
    elif law_idx == 0:
        extra = pick_slot("law_cizi", seed=seed + "|c", state=state)

    parts = [fakt]
    if gloss:
        parts.append(gloss)
    if extra:
        parts.append(extra.lstrip())
    return re_sub_space(" ".join(parts))


def _odstavec_law_group(kat: str, group: list[BlokDne], *, state: dict) -> str:
    od = group[0].cas_od
    do = group[-1].cas_do or group[-1].cas_od
    cas = f"Mezi {od} a {do}" if od != do else f"Ve {od}"
    pocet = sum(b.pocet_hlasovani for b in group)
    zamitnuto = sum(b.pocet_zamitnuto for b in group)
    seed = f"lg|{kat}|{cas}|{pocet}"

    if kat == "personalka":
        nazvy = []
        for b in group:
            c = _core_text(b)
            if c.startswith("Hlasovali o:"):
                n = c.removeprefix("Hlasovali o:").strip()
                for sep in (" - ", ", ", ","):
                    n = n.split(sep)[0]
                nazvy.append(n[:45])
            elif "Dozimetr" in c:
                nazvy.append("Dozimetr")
            else:
                nazvy.append(c.split(".")[0][:40])
        ukazka = ", ".join(dict.fromkeys(nazvy[:4]))
        if len(nazvy) > 4:
            ukazka += f" a další ({pocet} celkem)"
        return compose_template(
            "{personalka}",
            ("personalka",),
            seed=seed,
            state=state,
            cas=cas,
            pocet=pocet,
            ukazka=ukazka,
        )

    if kat == "interpelace":
        zam_txt = f" {zamitnuto}× to zamítli." if zamitnuto else " Většinou to protlačili."
        return compose_template(
            "{interpelace}",
            ("interpelace",),
            seed=seed,
            state=state,
            cas=cas,
            pocet=pocet,
            zamitnuto=zam_txt,
        )

    return compose_template(
        "{generic_law}",
        ("generic_law",),
        seed=seed,
        state=state,
        cas=cas,
        pocet=pocet,
    )


def _odstavec_end(blok: BlokDne, *, state: dict) -> str:
    seed = f"end|{blok.cas_od}"
    if "kadeti" in blok.svejk or "chyběla" in blok.svejk:
        extra = pick_slot("end_odchod", seed=seed + "|o", state=state)
    else:
        extra = pick_slot("end_extra", seed=seed + "|e", state=state)

    if not state.get("poslusne"):
        state["poslusne"] = True
        return compose_template(
            "{end_poslusne}",
            ("end_poslusne",),
            seed=seed + "|p",
            state=state,
            cas=blok.cas_od,
            extra=extra,
        )

    return compose_template(
        "{end_main}",
        ("end_main",),
        seed=seed,
        state=state,
        cas=blok.cas_od,
        extra=extra,
    )


def _perex_dne(day: DenSchuze) -> str:
    shr = day.shrnuti.replace("Ve zkratce:", "Shrnutí dne:")
    shr = shr.replace(" Tomu se skoro nechce věřit.", "")
    return f"*{day.den.capitalize()} {day.datum}*, {shr}"


def _iter_odstavce(bloky: list[BlokDne], state: dict):
    items = _preprocess_bloky(bloky)
    law_idx = 0
    i = 0
    while i < len(items):
        typ = items[i][0]
        if typ == "start":
            yield ("start", items[i][1])
            i += 1
        elif typ == "debate":
            if i + 1 < len(items) and items[i + 1][0] == "porad":
                debate, porad = items[i][1], items[i + 1][1]
                if _prekryv(debate, porad):
                    yield _odstavec_debate_porad(debate, porad, state=state)
                    i += 2
                    continue
            yield _odstavec_debate(items[i][1], state=state)
            i += 1
        elif typ == "porad":
            yield _odstavec_porad(items[i][1], state=state)
            i += 1
        elif typ == "law":
            yield _odstavec_law(items[i][1], state=state, law_idx=law_idx)
            law_idx += 1
            i += 1
        elif typ == "law_group":
            yield _odstavec_law_group(items[i][1], items[i][2], state=state)
            i += 1
        elif typ == "end":
            yield _odstavec_end(items[i][1], state=state)
            i += 1
        else:
            i += 1


def render_den_noviny(day: DenSchuze, *, state: dict | None = None) -> str:
    datum = _datum_cesky(day.datum)
    if state is None:
        state = _new_state()
    lines = [
        f"## {day.den.capitalize()}, den ve sněmovně",
        "",
        _perex_dne(day),
        "",
    ]
    for item in _iter_odstavce(day.bloky, state):
        if isinstance(item, tuple) and item[0] == "start":
            lines.append(_odstavec_start(item[1], day.den, datum, state=state))
        else:
            lines.append(item)
        lines.append("")
    return "\n".join(lines).strip()


def render_schuze_noviny(osa: SchuzeCasovaOsa) -> str:
    if not osa.dny:
        return ""

    od = _datum_cesky(osa.dny[0].datum)
    do = _datum_cesky(osa.dny[-1].datum)
    rozsah = od if len(osa.dny) == 1 else f"{od}, {do}"

    state = _new_state()
    intro = compose_template(
        "{intro_a} {intro_b}{intro_c}",
        ("intro_a", "intro_b", "intro_c"),
        seed=f"article|{osa.cislo}|{osa.obdobi}",
        state=state,
    )
    lines = [
        f"# Schůze {osa.cislo}/{osa.obdobi}: Poslanecká sněmovna glosuje",
        "",
        f"*Švejkovo shrnutí jednání ({rozsah})*",
        "",
        intro,
        "",
    ]

    for i, day in enumerate(osa.dny):
        if i > 0:
            lines.append("---")
            lines.append("")
        lines.append(render_den_noviny(day, state=state))
        lines.append("")

    return "\n".join(lines).strip()


def _prvni_veta(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^Poslušně hlásím,?\s*", "", t, flags=re.I)
    m = re.match(r"^([^.!?]+[.!?])", t)
    if m:
        return m.group(1).strip()
    return t[:120] + ("…" if len(t) > 120 else "")


def _capitalize(s: str) -> str:
    s = s.strip()
    return s[0].upper() + s[1:] if s else s


def _nadpis_zakonu(nazev: str) -> str:
    n = _zkrat_nazev(nazev)
    return _capitalize(n)


def _meta_radek(blok: BlokDne) -> str:
    if blok.cas_do and blok.cas_do != blok.cas_od:
        cas = f"{blok.cas_od}-{blok.cas_do}"
    else:
        cas = blok.cas_od
    cast = ""
    if blok.pocet_hlasovani > 1:
        cast = f"{blok.pocet_hlasovani}× hlasování"
        if blok.pocet_zamitnuto:
            cast += f" ({blok.pocet_zamitnuto}× zamítnuto)"
    elif blok.typ == "law":
        cast = "1× hlasování"
    vysledek = ""
    if blok.typ == "law":
        vysledek = "prošlo" if blok.proslo else "neprošlo"
    parts = [p for p in (cas, cast, vysledek) if p]
    return " · ".join(parts)


def _headline_z_bloku(blok: BlokDne) -> str:
    """Krátký titulek, z názvu zákona, ne celá glosa."""
    return _nadpis_zakonu(blok.nazev)


def _kratka_zprava_start(blok: BlokDne, datum: str, *, state: dict) -> str:
    return pick_slot(
        "start_kratka",
        seed=f"sk|{datum}|{blok.cas_od}",
        state=state,
        cas=blok.cas_od,
    )


def _kratka_zprava_porad(blok: BlokDne) -> str:
    pm = _porad_cisla(blok)
    cas = blok.cas_od
    if pm and pm[0] > 1:
        celkem, zamitnuto, _ = pm
        return f"{cas} Pořad dne, {celkem}× hlasování, {zamitnuto}× zamítnuto."
    return f"{cas} Pořad schůze schválen."


def _kratka_zprava_end(blok: BlokDne) -> str:
    extra = ""
    if "polovina" in blok.svejk.lower() or "chyběla" in blok.svejk.lower():
        extra = " V sále sotva polovina."
    return f"{blok.cas_od} Konec jednání.{extra}"


def _kratka_debate_porad(debate: BlokDne, porad: BlokDne) -> str:
    hod = "několik"
    m = re.search(r"(\d+)\s*hodin", debate.svejk)
    if m:
        hod = m.group(1)
    pm = _porad_cisla(porad)
    cas = debate.cas_od
    if pm:
        celkem, zamitnuto, _ = pm
        return f"{cas} {hod} h debaty o pořadu, pak {celkem}× hlasování ({zamitnuto}× zamítnuto)."
    return f"{cas} Hodiny debaty o pořadu dne."


def _telo_zakona(blok: BlokDne) -> str:
    gloss = glosa_pro_obcana(blok.nazev, blok.vysvetleni, proslo=blok.proslo)
    if gloss:
        vety = re.split(r"(?<=[.!?])\s+", gloss.strip())
        vety = [_prvni_veta(v) for v in vety if v.strip()]
        if vety:
            text = vety[0] if len(vety) == 1 else f"{vety[0]} {vety[1]}"
            return _capitalize(text)
    if blok.proslo:
        return "Prošlo, podrobnosti v názvu návrhu."
    return "Neprošlo, pro vás se zatím nic nemění."


def _stories_z_items(items: list) -> list[tuple[BlokDne, str]]:
    stories: list[tuple[BlokDne, str]] = []
    for typ, *rest in items:
        if typ == "law":
            blok = rest[0]
            if _law_kategorie(blok) == "substantivni":
                stories.append((blok, _headline_z_bloku(blok)))
    return stories


def _nadpis_dne_pro_den(
    day: DenSchuze,
    stories: list[tuple[BlokDne, str]],
    *,
    state: dict,
) -> str:
    prosle = [b for b, _ in stories if b.proslo]
    if len(prosle) >= 2:
        return pick_slot(
            "headline_dne_dva",
            seed=f"hd|{day.datum}",
            state=state,
            a=_nadpis_zakonu(prosle[0].nazev),
            b=_nadpis_zakonu(prosle[1].nazev),
        )
    if len(prosle) == 1:
        return pick_slot(
            "headline_dne_jeden",
            seed=f"hd|{day.datum}",
            state=state,
            a=_nadpis_zakonu(prosle[0].nazev),
        )
    shr = day.shrnuti.replace("Ve zkratce:", "").strip()
    if stories:
        return shr or stories[0][1]
    return shr or pick_slot("headline_dne_prazdny", seed=f"hd|{day.datum}", state=state)


def _sekce_nadpis_law(blok: BlokDne) -> str:
    return _headline_z_bloku(blok)


def _sekce_nadpis_law_group(kat: str) -> str:
    if kat == "interpelace":
        return "Interpelace"
    if kat == "personalka":
        return "Personálka"
    return "Hlasování"


def render_den_noviny_dlouhe(day: DenSchuze, *, state: dict | None = None) -> str:
    """Krátký hospodský přehled, lidské titulky, bez technického hlášení."""
    from svejk.listy import render_den_listy

    return render_den_listy(day, state=state)


def render_schuze_noviny_dlouhe(osa: SchuzeCasovaOsa) -> str:
    from svejk.listy import render_schuze_listy

    return render_schuze_listy(osa)


def render_den_noviny_kratke(day: DenSchuze, *, state: dict | None = None) -> str:
    if state is None:
        state = _new_state()
    datum = _datum_cesky(day.datum)
    items = _preprocess_bloky(day.bloky)

    stories: list[tuple[BlokDne, str]] = []
    kratke: list[str] = []
    i = 0

    while i < len(items):
        typ = items[i][0]
        if typ == "start":
            kratke.append(_kratka_zprava_start(items[i][1], day.datum, state=state))
            i += 1
        elif typ == "debate":
            if i + 1 < len(items) and items[i + 1][0] == "porad":
                debate, porad = items[i][1], items[i + 1][1]
                if _prekryv(debate, porad):
                    kratke.append(_kratka_debate_porad(debate, porad))
                    i += 2
                    continue
            hod = "několik"
            m = re.search(r"(\d+)\s*hodin", items[i][1].svejk)
            if m:
                hod = m.group(1)
            kratke.append(f"{items[i][1].cas_od} Debata bez hlasování ({hod} h).")
            i += 1
        elif typ == "porad":
            kratke.append(_kratka_zprava_porad(items[i][1]))
            i += 1
        elif typ == "law":
            blok = items[i][1]
            if _law_kategorie(blok) == "substantivni":
                stories.append((blok, _headline_z_bloku(blok)))
            else:
                kratke.append(
                    f"{blok.cas_od} {_headline_z_bloku(blok)} ({'prošlo' if blok.proslo else 'neprošlo'})."
                )
            i += 1
        elif typ == "law_group":
            kat, group = items[i][1], items[i][2]
            od = group[0].cas_od
            pocet = sum(b.pocet_hlasovani for b in group)
            if kat == "interpelace":
                kratke.append(f"{od} {pocet}× interpelace, ministr odpovídal.")
            else:
                kratke.append(f"{od} Personálka, {pocet}× hlasování o funkcích.")
            i += 1
        elif typ == "end":
            kratke.append(_kratka_zprava_end(items[i][1]))
            i += 1
        else:
            i += 1

    nadpis_dne = _nadpis_dne_pro_den(day, stories, state=state)

    lines = [
        f"# {HLAVICKA_LISTU} · {day.den} {datum}",
        "",
        f"## {nadpis_dne}",
        "",
    ]

    for blok, headline in stories:
        lines.append(f"### {headline}")
        lines.append(f"*{_meta_radek(blok)}*")
        lines.append("")
        lines.append(_telo_zakona(blok))
        lines.append("")

    if kratke:
        lines.append("**Krátké zprávy**")
        lines.append("")
        for z in kratke:
            lines.append(f"- {z}")
        lines.append("")

    return "\n".join(lines).strip()


def render_schuze_noviny_kratke(osa: SchuzeCasovaOsa) -> str:
    if not osa.dny:
        return ""
    state = _new_state()
    lines = [
        f"# Schůze {osa.cislo}/{osa.obdobi}, {HLAVICKA_LISTU}",
        "",
    ]
    for i, day in enumerate(osa.dny):
        if i > 0:
            lines.append("---")
            lines.append("")
        lines.append(render_den_noviny_kratke(day, state=state))
        lines.append("")
    return "\n".join(lines).strip()
