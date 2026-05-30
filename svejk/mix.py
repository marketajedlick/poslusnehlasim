"""Kombinatoricky generator svejkovskych frazi, tisice variant bez API."""

from __future__ import annotations

import hashlib
import random
from typing import Any

SLOTS: dict[str, tuple[str, ...]] = {
    # start dne
    "start_a": (
        "No tak se zase sešli",
        "Poslanci zase usedli",
        "Sněmovna znovu otevřela dveře",
        "Jednání pokračovalo",
        "Schůze odstartovala",
        "V sále zase hučelo",
        "Další den, další tlačítka",
        "Ranní klokání zaznělo",
        "Formálně zahájeno",
        "Program schůze na stole",
    ),
    "start_b": (
        "Pěkně na pohodu",
        "V klidu, kam spěchat",
        "Bez zbytečného spěchu",
        "Jako by jim nikdo nic neplatil",
        "V tempu, které u nich znamená celý den",
        "S typickou nonchalance",
        "Bez zvláštního nadšení",
        "S klidem veterána z kasáren",
        "V režimu pomalého startu",
        "S pocitem, že večer bude zase pozdě",
    ),
    "start_c": (
        "Program schválen, první zázrak dne.",
        "Pořad prošel. Organizace zvládnuta.",
        "Organizace bez potíží, podezřele klidný začátek.",
        "Schválili program. Samotné rozcvičení demokracie jim jde.",
        "První úspěch dne. Často i poslední.",
        "Exemplárně klidné ráno, na sněmovní poměry.",
        "Kasární disciplína, co se týče papírování.",
        "Definitivně zahájeno. Optimisticky.",
        "Odhad: do večera to zase skřípne.",
        "Pak ale přijde realita, a ta bývá jiná.",
    ),
    # uvod clanku
    "intro_a": (
        "Poslušně hlásím, následující text shrnuje",
        "Co následuje, je glosa z",
        "Níže je přehled podle",
        "Tento text vznikl z",
        "Shrnutí staví na",
        "Glosa vychází z",
    ),
    "intro_b": (
        "co se ve sněmovně skutečně dělo, ne z projevů, ale z hlasování.",
        "hlasovacích dat, ne z řečí u mikrofonu.",
        "tlačítek, ne slibů. Čísla nelžou.",
        "UNL záznamů. Projevy někdy ano, tlačítka spíš ne.",
        "faktických hlasování. Kdo čte jen projevy, ten nechápe nic.",
        "dat ze sněmovny. Statistiky jsou tvrdší než rétorika.",
    ),
    "intro_c": (
        " Tomu se nechce věřit, ale je to tak.",
        " I když se tomu nechce věřit.",
        " Kdo by to čekal, kromě pravidelných diváků.",
        " Standardní provoz demokracie.",
        "",
    ),
    # debata / porad, uvod
    "dp_open": (
        "{cas} se sněmovna zasekla na pořadu dne.",
        "{cas} celý blok visel na jednom: co vlastně projednávat.",
        "{cas} opozice s koalicí mlátili do stolu o program.",
        "{cas} místo zákonů zase pořad dne.",
        "{cas} formální maraton o tom, co bude na programu.",
        "{cas} procedurální kolotoč na celé dopoledne.",
        "{cas} hlasování o hlasování, meta-demokracie.",
        "{cas} program dne na programu dne.",
        "{cas} tlačítka místo obsahu.",
        "{cas} zaseknutí na pořadu, klasika.",
    ),
    "dp_stat": (
        "Za {hod} hodin mluvili víc než rozhodovali, pak {celkem}× hlasovali, *o čem* budou mluvit. {zamitnuto}× ne.",
        "{hod} hodin debaty, {celkem}× hlasování o pořadu, {zamitnuto}× zamítnuto.",
        "{hod} hodin bez výsledku, pak {celkem}× hlasování, {zamitnuto}× ne.",
        "Formálně {hod} hodin, pak {celkem}× tlačítek, {zamitnuto}× zamítnuto.",
        "Celých {hod} hodin řečí, {celkem}× hlasování, {zamitnuto}× ne.",
        "{hod} hodin mluvili, {celkem}× rozhodovali o pořadu, {zamitnuto}× zamítli.",
    ),
    "deb_open": (
        "{cas} poslanci mluvili a nehlasovali.",
        "{cas} debata bez výsledku.",
        "{cas} sněmovna v režimu rozhlasového pořadu.",
        "{cas} mluvili, mluvili, mluvili.",
        "{cas} hodiny řečí, nula rozhodnutí.",
        "{cas} konference bez závěrů.",
    ),
    "deb_stat": (
        " Celých {hod} hodin, a žádné rozhodnutí.",
        " {hod} hodin bez hlasování.",
        " {hod} hodin, nic nepadlo.",
        " {hod} hodin produktivity blíží se nule.",
    ),
    # vaty
    "vata_debata": (
        " Tomu se skoro nechce věřit, ale celé hodiny mluvili, a nehlasovali.",
        " Ano, doopravdy: hodiny řečí a nula rozhodnutí.",
        " Sněmovna v režimu rozhlasového pořadu. Jen bez moderátora.",
        " Hodiny řečí, nula produktivity.",
        " Mluvili jako na akademické konferenci, jen bez závěrů.",
        " Celý blok bez jediného rozhodnutí.",
        " Čistá konsternace.",
        " Absolutní nula produktivity, jak se říká v odborné literatuře.",
    ),
    "vata_porad": (
        " Opozice program blokovala. Samozřejmě.",
        " Koalice ho zase protlačila. Kdo by čekal jiný scénář.",
        " Hlasování o tom, *o čem* se bude hlasovat.",
        " Blokování jako sportovní disciplína.",
        " Formální ping-pong mezi koalicí a opozicí.",
        " Demokracie v akci, pomalu.",
    ),
    "vata_porad_kratka": (
        " Krátká hádka o pořadu.",
        " Rychlé hlasování, na sněmovní poměry rekord.",
        " Pár tlačítek a program hotový.",
    ),
    "porad_open": (
        "{cas} zase hádka o pořad.",
        "{cas} program dne na programu dne.",
        "{cas} tlačítka místo zákonů.",
        "{cas} kolotoč procedur.",
        "{cas} formální maraton.",
        "{cas} procedurální cvičení.",
    ),
    "porad_stat": (
        " {celkem}× hlasovali, {zamitnuto}× zamítli, opozice blokovala, koalice protlačila.",
        " {celkem}× hlasování, {zamitnuto}× ne.",
        " {celkem}× hlasovali o pořadu, {zamitnuto}× zamítli.",
        " {celkem}× tlačítek, {zamitnuto}× zamítnuto.",
    ),
    "porad_tail": (
        " Koalice program protlačila.",
        " Opozice blokovala, koalice vyhrála.",
        " Program nakonec prošel. Kdo by čekal.",
        " Formálně hotovo, obsahově teprve začíná.",
        " Standardní den ve sněmovně.",
        " Koalice neuhnula. Opozice protestovala.",
    ),
    "porad_cizi": (
        " Přidávání bodů trvalo celé odpoledne.",
        " Formální maraton v plné parádě.",
        " Ukázka demokracie v nejistém tempu.",
        " Procedurální cvičení na celý den.",
        " U nás v kasárnách by se o tom dohodli rychleji.",
    ),
    "hint": (
        " Opozice chtěla protáhnout {temata}. Koalice řekla ne, běžné.",
        " Opozice tlačila na {temata}. Koalice neuhnula.",
        " {temata}, to chtěla opozice. Koalice jinak.",
        " Hlavní téma sporu: {temata}. Výsledek? Koalice.",
        " Opozice prosazovala {temata}. Nepovedlo se.",
        " Spor o {temata}. Koalice držela linii.",
    ),
    # law
    "law_uvod": (
        "Ve {cas} konečně něco padlo, ne jen další hádka o pořadu.",
        "V {cas} další kolo hlasování.",
        "Krátce po {cas} padlo další rozhodnutí.",
        "Po {cas} zase tlačítka, demokracie v praxi.",
        "V {cas} přišlo na řadu další hlasování.",
        "Od {cas} poslanci hlasovali znovu.",
        "Kolem {cas} konečně hlasování o obsahu.",
        "V {cas} obsah místo procedury.",
        "Po {cas} přestali mluvit a začali tlačit.",
        "Ve {cas} další bod, tentokrát skutečný.",
        "V {cas} konečně zákon, ne pořad.",
        "Po {cas} rozhodnutí, které něco znamená.",
    ),
    "law_poslusne": (
        "Poslušně hlásím, ve {cas} konečně hlasovali o něčem, co není jen pořad dne.",
        "Poslušně hlásím, v {cas} konečně padlo rozhodnutí o obsahu.",
        "Poslušně hlásím, ve {cas} hlasovali o zákonu, ne o pořadu.",
        "Poslušně hlásím, v {cas} konečně obsah místo procedury.",
    ),
    "schvaleno": (
        " Prošlo to. Ano, doopravdy.",
        " Schváleno. Odvážné tempo.",
        " Konečně něco padlo.",
        " Přijato. Zázrak dne.",
        " Prošlo. Statistika se lehce zlepšila.",
        " Definitivně schváleno.",
    ),
    "zamitnuto": (
        " Zamítnuto. Překvapení nula.",
        " Neprošlo. Kdo by to čekal.",
        " Tentokrát ne. Příště možná zase ne.",
        " Zamítnuto. Další kolo dohadů.",
        " Ne. Opozice spokojená, koalice méně.",
        " Smetli to ze stolu. Standard.",
    ),
    "law_cizi": (
        " Typický sněmovní tempo.",
        " Faktum pro občana, jak se patří.",
        " Obsahový vrchol dne, relativně.",
        " Konečně něco pro občana.",
    ),
    # skupiny hlasovani
    "interpelace": (
        "{cas} {pocet}× hlasovali o interpelacích, ministr odpovídal, poslancům nestačilo.{zamitnuto}",
        "{cas} interpelace: {pocet}× hlasování.{zamitnuto} Ministr mluvil, opozice nebyla spokojená.",
        "{cas} {pocet}× se ptali ministrů, hlasovalo se, jestli odpovědi stačily.{zamitnuto}",
        "{cas} {pocet}× interpelace. Ministr odpovídal, sál nebyl spokojený.{zamitnuto}",
    ),
    "personalka": (
        "{cas} personálka ve velkém, {pocet} hlasování o funkcích. Třeba {ukazka}.",
        "{cas} dosazování do výborů: {pocet}× hlasování. {ukazka}.",
        "{cas} {pocet}× volili a jmenovali. {ukazka}.",
        "{cas} {pocet}× hlasování o obsazení postů. {ukazka}.",
    ),
    "generic_law": (
        "{cas} {pocet}× technické body, občana přímo netankují.",
        "{cas} procedurální hlasování, {pocet}×. Suché, ale nutné.",
        "{cas} {pocet}× technické body. Poslanci se baví.",
    ),
    # konec
    "end_main": (
        "Kolem {cas} poslanci schůzi ukončili a rozešli se domů.{extra}",
        "Ve {cas} to zabalili.{extra}",
        "Schůze skončila kolem {cas}.{extra}",
        "V {cas} poslední tlačítko, a domů.{extra}",
        "Poslušně hlásím, kolem {cas} šli domů.{extra}",
        "V {cas} zhaslo světlo v sále.{extra}",
    ),
    "end_poslusne": (
        "Poslušně hlásím, kolem {cas} to zabalili, den odpracován.{extra}",
        "Poslušně hlásím, ve {cas} končí jednání.{extra}",
    ),
    "end_extra": (
        " Den odpracován.",
        " Zítra zase stejný scénář.",
        " Schůze uzavřena.",
        " Hotovo.",
        " Odpočinek až zítra.",
        "",
    ),
    "end_odchod": (
        " Polovina poslanců už dávno chyběla.",
        " V sále zůstala sotva polovina.",
        " Odcházeli postupně, jak kadeti po večerce.",
        " Plné obsazení u nich spíš volný pojem.",
    ),
    # temata, glosy
    "stavebni_ne": (
        "Stavební zákon zůstává v dalším kole dohadů. Kdo staví, ať je trpělivý.",
        "Stavební novela zase neprošla, stavebníci si zvyknou čekat.",
        "Stavební zákon visí ve vzduchu. Permice taky někdy.",
        "Hlasovalo se o stavebním zákonu, tentokrát bez výsledku.",
        "Stavebníci musejí počkat. Sněmovna taky.",
    ),
    "stavebni_ano": (
        "Stavební novela prošla. Stavební úřady se těší.",
        "Hlasovalo se o stavebním zákonu, pro každého, kdo stavěl nebo boural.",
        "Stavební zákon schválen, jasnější pravidla na obzoru.",
    ),
    "penze": (
        "Nejdřív penze ne, pak penze jo, typická sněmovní logika.",
        "Penze: zamítnuto, pak schváleno. Konzistentní jako počasí.",
        "Hlasování o penzích, pendlování mezi ano a ne.",
        "Penze prošly až napodruhé. U nás v kasárnách by to bylo rychlejší.",
    ),
    # noviny, krátké nadpisy
    "headline_dne_dva": (
        "{a}, a {b}",
        "{a}. Navíc {b}.",
        "Hlavně {a}, pak {b}.",
        "{a}, k tomu {b}.",
    ),
    "headline_dne_jeden": (
        "{a}, zbytek procedura.",
        "Den patřil tématu: {a}.",
        "{a}. Jinak klidnější den.",
    ),
    "headline_dne_prazdny": (
        "Procedura, procedura a domů.",
        "Den bez velkých zákonů, poslanci si oddechli.",
        "Mluvili o pořadu, zákonů málo.",
        "Formální den, obsah přijde jindy.",
    ),
    "start_kratka": (
        "{cas} Zahájení jednání.",
        "{cas} Sněmovna zasedla.",
        "{cas} Další den, další kladívko.",
        "{cas} Formální start.",
    ),
    # listy, hospodský formát
    "listy_ucet": (
        "{pocet} hlasování, {minuty} minut v sále a v {konec} bylo po všem.",
        "{pocet} hlasování za {minuty} minut, v {konec} bylo po jednání.",
    ),
    "listy_zaver": (
        "že dneska to byla tak krátká schůze, že kdyby si člověk odskočil na jedno pivo a utopence, přišel by už na závěrečnou.",
        "že než by výčepní stihl natočit druhé pivo, v sále už bylo po jednání.",
    ),
    "listy_zaver_dlouhy": (
        "že poslanci jednali tak dlouho, že v hospodě byste mezitím stihli utopence, klobásu i jedno kolo navíc.",
        "že kdybyste po zahájení šli na jedno pivo, vrátili byste se až na večerní závěrečnou, a to v sále.",
        "že schůze trvala déle než večerní menu v hospodě, od utopence po poslední kolo.",
    ),
    # leady se skládají v listy.py ze zdrojových dat (svejk, hlasování)
    "listy_lead_statni_socialni_podpo": (),
    "listy_lead_socialnich_sluzb": (),
    "listy_lead_obecne": (),
    "listy_pointa_socialnich_sluzb": (
        "Úředníci si tak můžou nechat cedulky na dveřích, stěhování se odkládá.",
    ),
    "listy_pointa_obecne": (
        "",
    ),
    "listy_vysledek_konec": (
        "v {konec} skončilo jednání",
        "jednání skončilo v {konec}",
        "poslední hlasování bylo v {konec}",
    ),
}


def _hash_seed(*parts: str) -> int:
    blob = "|".join(str(p) for p in parts).encode()
    return int(hashlib.md5(blob).hexdigest()[:12], 16)


def compose(
    slot_names: tuple[str, ...],
    *,
    seed: str,
    state: dict[str, Any],
    optional: tuple[str, ...] = (),
    p_optional: float = 0.65,
    **fixed: str,
) -> str:
    """Slozi vetu z nahodne zvolenych slotu. Seed + pokus zajisti variabilitu a bez opakovani."""
    seq = state.setdefault("seq", 0)
    state["seq"] = seq + 1
    used: set[str] = state.setdefault("used", set())

    for attempt in range(48):
        rng = random.Random(_hash_seed(seed, str(seq), str(attempt)))
        parts: dict[str, str] = dict(fixed)
        for name in slot_names:
            pool = SLOTS[name]
            parts[name] = rng.choice(pool)
        for name in optional:
            if rng.random() < p_optional:
                parts[name] = rng.choice(SLOTS[name])
            else:
                parts[name] = ""
        try:
            text = "".join(parts[n] for n in slot_names if n in parts and parts[n])
            if not text:
                text = " ".join(parts[n] for n in slot_names if n in parts)
        except KeyError:
            continue
        # jednoduche formatovani {cas} atd.
        try:
            text = text.format(**{k: v for k, v in parts.items() if k not in slot_names})
        except (KeyError, ValueError):
            try:
                text = text.format(**fixed)
            except (KeyError, ValueError):
                pass
        text = re_sub_space(text)
        if text and text not in used:
            used.add(text)
            return text

    # fallback, posledni pokus bez deduplikace
    rng = random.Random(_hash_seed(seed, "fb"))
    parts = {n: rng.choice(SLOTS[n]) for n in slot_names}
    parts.update(fixed)
    for name in optional:
        parts[name] = rng.choice(SLOTS[name]) if rng.random() < p_optional else ""
    text = "".join(parts.get(n, "") for n in slot_names)
    try:
        text = text.format(**fixed)
    except (KeyError, ValueError):
        pass
    return re_sub_space(text)


def compose_template(
    template: str,
    slot_names: tuple[str, ...],
    *,
    seed: str,
    state: dict[str, Any],
    **fixed: str,
) -> str:
    """Slozi vetu podle sablony s {slot} placeholdery."""
    seq = state.setdefault("seq", 0)
    state["seq"] = seq + 1
    used: set[str] = state.setdefault("used", set())
    salt = str(state.get("salt", ""))

    for attempt in range(48):
        rng = random.Random(_hash_seed(salt, seed, template, str(seq), str(attempt)))
        parts: dict[str, str] = {k: str(v) for k, v in fixed.items()}
        for name in slot_names:
            raw = rng.choice(SLOTS[name])
            try:
                parts[name] = raw.format(**parts)
            except (KeyError, ValueError, IndexError):
                parts[name] = raw
        try:
            text = template.format(**parts)
        except KeyError:
            continue
        text = re_sub_space(text)
        if text and text not in used:
            used.add(text)
            return text

    rng = random.Random(_hash_seed(salt, seed, "fb"))
    parts = {k: str(v) for k, v in fixed.items()}
    for name in slot_names:
        raw = rng.choice(SLOTS[name])
        try:
            parts[name] = raw.format(**parts)
        except (KeyError, ValueError, IndexError):
            parts[name] = raw
    try:
        return re_sub_space(template.format(**parts))
    except KeyError:
        return re_sub_space(template.format(**{k: str(v) for k, v in fixed.items()}))


def pick_slot(name: str, *, seed: str, state: dict[str, Any], **fixed: str) -> str:
    """Jedna fráze ze slotu, bez opakovani v ramci clanku."""
    return compose_template(f"{{{name}}}", (name,), seed=seed, state=state, **fixed)


def re_sub_space(text: str) -> str:
    import re
    text = re.sub(r"\.([^\s\d])", r". \1", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()
