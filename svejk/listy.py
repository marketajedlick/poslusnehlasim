"""Krátký hospodský formát, Poslušně hlásím z poslanecké sněmovny."""

from __future__ import annotations

import re
import unicodedata

from svejk.build.vote_logic import debata_vysledek_radek
from svejk.cislo_slovy import po_hlasovanich_cap
from svejk.mix import SLOTS, _hash_seed, pick_slot, re_sub_space
from svejk.noviny import HLAVICKA_LISTU, _datum_cesky, _law_kategorie, _new_state, _zkrat_nazev
from svejk.obcansky import GENERIC_GLOSA_MARKERS, glosa_pro_obcana, ma_glosu
from svejk.timeline import BlokDne, DenSchuze, SchuzeCasovaOsa, _cas_minuty

# klíčová slova v názvu zákona → slug pro pravidla
LIDSKY_NADPIS: list[tuple[tuple[str, ...], str]] = [
    (("státní sociální podpo", "statni socialni podpo"), ""),
    (("sociálních služb", "socialnich sluzb"), ""),
    (("životním a existenčním minimu", "životní minimum"), ""),
    (("dávce státní sociální pomoci", "dávka státní sociální pomoc"), ""),
    (("státním rozpočtu", "státní rozpočet", "rozpočtu čr"), ""),
    (("veřejných rozpočt", "rozpočtových pravidel"), ""),
    (("pojistn", "osvč", "živnost"), ""),
    (("stavebn",), ""),
    (("penzijního spoření", "penzijním spoření", "doplňkovém penz", "doplňkového penz"), ""),
    (("penz", "penzijn"), ""),
    (("investičních společnostech", "investiční společnost"), ""),
    (("rostlinolékařské péči", "rostlinolékař"), ""),
    (("důvěry vládě", "důvěru vládě"), ""),
    (("nedůvěry vládě", "nedůvěru vládě"), ""),
    (("in vitro", "zkumavk", "diagnostick"), ""),
    (("silničním provozu", "silniční provoz"), ""),
    (("všeobecné zdravotní", "zdravotní pojišťov", "vzp"), ""),
    (("léčiv", "léků", "lieciv"), ""),
    (("pokut", "přestupk"), ""),
]

# titulky = stručný výsledek (ne název tématu)
NADPIS_VYSLEDEK: dict[str, dict[str, str]] = {
    "statni_socialni_podpo": {
        "odlozili": "Dávky počkají",
        "schvalili": "Dávky se mění",
        "zamitli": "Dávky zůstávají po staru",
    },
    "socialnich_sluzb": {
        "schvalili": "Úřad práce zůstává na svém místě",
        "zamitli": "Úřad práce se nemění",
    },
    "zivotnim_a_existencnim_minim": {
        "schvalili": "Chudoba má novou hranici",
        "zamitli": "Hranice chudoby zůstává",
    },
    "davce_statni_socialni_pomoci": {
        "schvalili": "Pomoc v nouzi se mění",
        "zamitli": "Pomoc v nouzi zůstává",
    },
    "statnim_rozpoctu": {
        "schvalili": "Stát ví, kolik smí utratit",
        "zamitli": "Rozpočet musí počkat",
    },
    "verejnych_rozpoct": {
        "schvalili": "Pravidla výdajů prošla",
        "zamitli": "Limity výdajů zůstávají",
    },
    "pojistn": {
        "schvalili": "Živnostníci ušetří na odvodech",
        "zamitli": "Odvody pro živnostníky zůstávají",
    },
    "stavebn": {
        "schvalili": "Stavba půjde snáz, když bůh dá",
        "zamitli": "Stavba si počká",
    },
    "penzijniho_sporeni": {
        "schvalili": "Spoření na důchod se mění",
        "zamitli": "Penzijní spoření zůstává po staru",
    },
    "penz": {
        "schvalili": "Důchody se mění",
        "zamitli": "Důchody zůstávají",
    },
    "duvery_vlade": {
        "schvalili": "Vláda má zelenou",
        "zamitli": "Vláda důvěru nedostala",
    },
    "neduvery_vlade": {
        "schvalili": "Vláda padla",
        "zamitli": "Vláda zůstává",
    },
    "investicnich_spolecnostech": {
        "schvalili": "Investice mají přísnější dohled",
        "zamitli": "Fondy zůstávají po staru",
    },
    "rostlinolekarske_peci": {
        "schvalili": "Postřiky mají nová pravidla",
        "zamitli": "Postřiky zůstávají po staru",
    },
    "in_vitro": {
        "schvalili": "Zkumavky budou pod dohledem",
        "zamitli": "Zkumavky zůstávají bez nových pravidel",
    },
    "silnicnim_provozu": {
        "schvalili": "Řidiči to pocítí jen málo",
        "zamitli": "Silnice si počkají",
    },
    "vseobecne_zdravotni": {
        "schvalili": "Ve vedení pojišťovny se něco změní",
        "zamitli": "Pojišťovna zůstává při starém",
    },
}

ZAKAZANE_VETY = (
    "× hlasovali",
    "× zamítnuto",
    "× přijato",
    "prošlo.",
    "neprošlo.",
    "typický sněmovní tempo",
    "plné obsazení",
    "obsahový vrchol",
    "exemplárně",
    "definitivně",
    "konsternace",
    "poslušně hlásím",
    "běžného člověka se netýká",
    "občana se to netýká přímo",
    "spíš televize",
    "personálka",
    "prostě to ještě chvíli potrvá",
    "než to sjednotí",
    "občané",
    "klienti systému",
    "příjemci dávky",
    "dotčení občané",
)

# metaforické pointy, nepoužívat
NEKREATIVNI_POINTA = (
    "stěhovací krabice",
    "ve skladu",
    "pod stůl",
    "schovaly",
    "klíče od",
    "zapomněl klíče",
    "počítače se schovaly",
)

URADNICKY_NA_LIDSKY: tuple[tuple[str, str], ...] = (
    (r"\bagenda\b", "program jednání"),
    (r"\badministrativ", "papírování"),
    (r"\bimplementac", "zavedení"),
    (r"\bsystémov", "nový"),
    (r"\bpříslušn", "správný"),
    (r"\blegislativn", ""),
    (r"\btranspozic", "úprava kvůli EU"),
    (r"\bdigitalizac\w*", "přechod na počítače"),
    (r"\bsystém\b", "počítače"),
    (r"\bstátní sociální podpo\w*", "dávky"),
    (r"\btechnická novela\b", "úprava"),
    (r"\bdiagnostiku v zkumavce\b", "testy ve zkumavkách"),
)

LEGISLATIVNI_SLOVA = (
    "novela",
    "digitalizac",
    "systém",
    "agenda",
    "implementac",
    "legislativ",
    "transpozic",
    "reforma",
    "papírová úprava",
)

MAX_SLOV = 320
_PREKRYV_PRAG = 0.38


def _nadpis_fallback(blok: BlokDne, verdikt: str) -> str:
    n = blok.nazev.lower()
    if re.search(r"\blék", n) or re.search(r"\bliec", n) or "léčiv" in n:
        return "Léky budou levnější" if blok.proslo else "Léky zůstávají stejně drahé"
    if "pokut" in n or "přestupk" in n:
        return "Pokuty se nemění" if not blok.proslo else "Pokuty se mění"
    if verdikt == "odlozili":
        return "Platí to až později"
    if blok.proslo:
        return "Prošlo to"
    return "Zůstává po staru"


def _nadpis_bodu(blok: BlokDne) -> str:
    """Titulek = co z toho vypadlo, ne jak se zákon jmenuje."""
    key = _topic_key(blok.nazev)
    verdikt = _verdikt_bloku(blok)
    pravidla = NADPIS_VYSLEDEK.get(key)
    if pravidla:
        if verdikt in pravidla:
            return pravidla[verdikt]
        if blok.proslo and "schvalili" in pravidla:
            return pravidla["schvalili"]
        if not blok.proslo and "zamitli" in pravidla:
            return pravidla["zamitli"]
    return _nadpis_fallback(blok, verdikt)


def _lidsky_nadpis(nazev: str) -> str:
    """Zpětná kompatibilita, pro interní odkazy použij _nadpis_bodu(blok)."""
    t = nazev.lower()
    for klicova, _ in LIDSKY_NADPIS:
        if any(k in t for k in klicova):
            return _topic_key(nazev).replace("_", " ")
    zkr = _zkrat_nazev(nazev)
    if len(zkr) > 45:
        zkr = zkr[:42] + "…"
    return zkr[0].upper() + zkr[1:] if zkr else "Další bod"


def _ascii_slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    ascii_text = norm.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")[:28]


def _topic_key(nazev: str) -> str:
    t = nazev.lower()
    for klicova, _ in LIDSKY_NADPIS:
        if any(k in t for k in klicova):
            return _ascii_slug(klicova[0])
    return "obecne"


def _slova(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"\w{4,}", text.lower())}


def _prekryvaji(a: str, b: str, prag: float = _PREKRYV_PRAG) -> bool:
    wa, wb = _slova(a), _slova(b)
    if not wa or not wb:
        return False
    spolecna = len(wa & wb)
    return spolecna / min(len(wa), len(wb)) >= prag


def _veta_je_zakazana(veta: str) -> bool:
    low = veta.lower()
    if any(z in low for z in ZAKAZANE_VETY):
        return True
    if any(
        u in low
        for u in (
            "agenda", "administrativ", "implementac", "legislativní návrh",
            "příslušný orgán", "systémové změny",
        )
    ):
        return True
    return False


def _cistit_uradnictinu(veta: str) -> str:
    v = veta
    for pattern, repl in URADNICKY_NA_LIDSKY:
        v = re.sub(pattern, repl, v, flags=re.I)
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"\s+([,.])", r"\1", v)
    return v


def _skore_legislativy(veta: str) -> int:
    low = veta.lower()
    return sum(-3 for w in LEGISLATIVNI_SLOVA if w in low)


def _veta_je_pouze_uradni(veta: str) -> bool:
    """Úřednická věta bez osobního dopadu, do „Co to znamená pro vás?“ nepatří."""
    if _skore_osloveni(veta) > 0:
        return False
    if any(
        w in veta.lower()
        for w in ("u vás", "u tebe", "doma", "chodíte", "dostanete", "nemusíte", "ušetří")
    ):
        return False
    return _skore_legislativy(veta) <= -3


def _humanizovat_lead(lead: str) -> str:
    """Legislativní jádro → vysvětlení u piva (význam beze změny)."""
    v = lead
    v = re.sub(
        r"posun digitalizace dávek[^.]*",
        "spuštění nových dávek",
        v,
        flags=re.I,
    )
    v = re.sub(r"úřady nestihly systém", "úřady nestihly připravit počítače", v, flags=re.I)
    v = re.sub(r"\bNovela prošla\b", "Návrh prošel", v, flags=re.I)
    v = re.sub(r"\bnovela prošla\b", "návrh prošel", v, flags=re.I)
    v = re.sub(r"\bZměna prošla\b", "Návrh prošel", v, flags=re.I)
    v = re.sub(r"\bzměna prošla\b", "návrh prošel", v, flags=re.I)
    v = re.sub(
        r"poslanci odložili změnu -",
        "poslanci změnu odložili -",
        v,
        flags=re.I,
    )
    return _cistit_uradnictinu(v)


def _uprav_vetu(veta: str) -> str:
    v = _cistit_uradnictinu(veta.strip())
    for prefix in ("jde o to, ", "šlo o to, ", "jde o ", "šlo o "):
        if v.lower().startswith(prefix):
            v = v[len(prefix):].strip()
            break
    v = re.sub(
        r"^Kdo teď chodí",
        "Pokud chodíte",
        v,
        flags=re.I,
    )
    v = re.sub(
        r"^Kdo (teď )?pobírá",
        "Pokud pobíráte",
        v,
        flags=re.I,
    )
    v = re.sub(
        r"^Když zařizujete",
        "Když zařizujete",
        v,
        flags=re.I,
    )
    v = re.sub(
        r"^Kam budete chodit",
        "Pořád půjdete",
        v,
        flags=re.I,
    )
    v = re.sub(r"\bnemusí se zatím bát\b", "nemusíte se zatím bát", v, flags=re.I)
    v = re.sub(r"\bmusí se zatím bát\b", "musíte se zatím bát", v, flags=re.I)
    v = re.sub(r"\bže by se mu\b", "že by se vám", v, flags=re.I)
    v = re.sub(
        r",?\s*ne na jiný úřad,?\s*jak chtěli\.?",
        ".",
        v,
        flags=re.I,
    )
    v = re.sub(
        r"([a-záčďéěíňóřšťúůýž])\s+A\s+([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ])",
        r"\1. \2",
        v,
    )
    v = re.sub(r",?\s*jak chtěli\.?", ".", v, flags=re.I)
    v = re.sub(r"\bobčané\b", "lidé", v, flags=re.I)
    v = re.sub(r"\bKlienti\b", "Lidé", v)
    v = re.sub(r"^A\s+", "", v)
    return v[0].upper() + v[1:] if v else v


def _skore_osloveni(veta: str) -> int:
    """Vyšší = přímé oslovení čtenáře."""
    low = veta.lower()
    if re.match(r"^(pokud|když|jestli)\s", low):
        return 4
    if re.search(
        r"\b(chodíte|půjdete|pobíráte|zařizujete|máte|dostanete|nemusíte)\b",
        low,
    ):
        return 3
    if any(w in low for w in ("občan", "klient", "příjemc", "dotčen")):
        return -3
    return 0


ABSTRAKTNI_MARKERY = (
    "stát chtěl",
    "byl připraven",
    "papírování jinam",
    "šlo o to, jestli návrh projde",
    "změna, která se dotkne",
    "změna prošla",
    "změna prošly",
    "jen části lidí",
    "šlo rychle",
    "stihl snídani",
    "stihl noviny",
    "dočetli tento text",
    "bylo svižné",
    "formálně",
    "jde o to, ",
    "tam, kde to znáte",
    "už zavírali",
    "nic stěhovat nebude",
)

# věty, které bez zdroje přisuzují konkrétní průběh
NEPRESNE_MARKERY = (
    "hlasovali o přesunu",
    "z úřadu práce jinam",
    "chtěli měnit",
    "měl dostat",
)

KONKRETNI_MARKERY = (
    "poslanci",
    "příspěvk",
    "péči",
    "úřad práce",
    "dávky",
    "software",
    "hendikep",
    "rodiče",
    "pivo",
    "utopenec",
    "výčepní",
    "živnost",
    "korun",
    "pacient",
    "předpis",
    "návrh",
    "hlasovali",
)


def _skore_konkrétnosti(veta: str) -> int:
    """Vyšší = konkrétnější; nevymyšlené detaily."""
    low = veta.lower()
    score = 0
    for a in ABSTRAKTNI_MARKERY + NEPRESNE_MARKERY:
        if a in low:
            score -= 4
    for k in KONKRETNI_MARKERY:
        if k in low:
            score += 2
    n = len(veta.split())
    if n >= 14:
        score += 2
    elif n >= 10:
        score += 1
    if re.search(r"\d", veta):
        score += 1
    return score


def _skore_vety_celkem(veta: str) -> int:
    return (
        _skore_osloveni(veta) * 10
        + _skore_konkrétnosti(veta)
        + _skore_legislativy(veta)
    )


def _pick_slot_konkrétní(
    name: str,
    *,
    seed: str,
    state: dict,
    min_skore: int = -99,
    **fixed: str,
) -> str:
    """Ze slotu vybere nejkonkrétnější variantu (deterministicky podle seed)."""
    pool = SLOTS.get(name, ())
    used: set[str] = state.setdefault("used", set())
    kandidati: list[tuple[int, str]] = []
    for raw in pool:
        if not str(raw).strip():
            continue
        try:
            text = re_sub_space(str(raw).format(**fixed))
        except (KeyError, ValueError):
            text = re_sub_space(str(raw))
        if not text:
            continue
        sk = _skore_konkrétnosti(text)
        if sk < min_skore:
            continue
        kandidati.append((sk, text))
    if not kandidati:
        return pick_slot(name, seed=seed, state=state, **fixed)
    kandidati.sort(
        key=lambda p: (-p[0], _hash_seed(seed, p[1])),
    )
    for _, text in kandidati:
        if text not in used:
            used.add(text)
            return text
    text = kandidati[0][1]
    used.add(text)
    return text


def _rozdelit_vety(text: str) -> list[str]:
    text = re.sub(r"^Poslušně hlásím,?\s*", "", text.strip(), flags=re.I)
    vety = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for v in vety:
        v = v.strip()
        if not v or _veta_je_zakazana(v):
            continue
        out.append(_uprav_vetu(v))
    return out


def _zdrojovy_text(blok: BlokDne) -> str:
    return f"{blok.nazev} {blok.svejk} {blok.vysvetleni or ''}"


def _ocisti_svejk_jadro(svejk: str) -> str:
    s = re.sub(r"^Poslušně hlásím,?\s*", "", svejk.strip(), flags=re.I)
    s = re.sub(r"\s*Tentokrát ne[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*Po \d+× hlasování nakonec prošlo\.?\s*", "", s, flags=re.I)
    return s.strip().rstrip(".")


def _rok_z_textu(text: str) -> str:
    m = re.search(r"20\d{2}", text)
    return m.group(0) if m else ""


KDO_KLIC = (
    "týká se", "pokud ", "chodíte", "půjdete", "lidé", "kdo ", "důchod", "živnost",
    "staví", "řidič", "pacient", "zaměstnan", "investuj", "spoří", "farmář",
    "nemocnic", "úřad práce", "každého", "občan", "investor",
)
DOPAD_KLIC = (
    "dostan", "platí", "změn", "zůstá", "ušetř", "kles", "zvýš", "nemusí", "bude",
    "projev", "od ledna", "vrátí", "upraví", "zkrátí", "prodlouž", "hlásit", "říct",
    "korun", "čeká", "termín", "sjednot", "dohled", "pokrač", "neschvál", "pravidl",
)

# odhad dopadu, bez konkrétních dat z návrhu nepoužívat
ODHAD_DOPADU = (
    "může zkrátit",
    "může prodloužit",
    "může urychlit",
    "může zpomalit",
    "může se dotknout",
    "úprava může",
    "pravděpodobně",
    "nejspíš",
    "podle znění návrhu",
    "podle toho, co",
    "když změna projde",
    "může zkrátit nebo prodloužit",
)

# měřitelný nebo popsaný fakt, ne spekulace
KONKRETNI_DOPAD = (
    "od ledna",
    "k 1.",
    "klesne z",
    "klesne na",
    "zvýší",
    "ušetří",
    "zůstává",
    "pokračuje podle",
    "neschválila",
    "neschválil",
    "vrátí",
    "musí hlásit",
    "musí říct",
    "musí nemocnicím",
    "hrozí nedostatek",
    "schválili, že",
    "sjednotili pravidla",
)

# lidský předmět schválení, ne zkrácený název zákona
PREDMET_LIDSKY: dict[str, str] = {
    "pojistn": "zálohách na sociálním pojištění pro živnostníky",
    "penzijniho_sporeni": "doplňkovém penzijním spoření",
    "stavebn": "stavebním zákoně",
    "investicnich_spolecnostech": "dohledu nad investičními fondy a společnostmi",
    "in_vitro": "hlášení nedostatku zkumavek v nemocnicích",
}

ZAKAZANE_LEAD_KONCE = (
    "hlasovali o „",
    "návrh prošel",
    "změna prošla",
    "řešili „",
    "schválili „",
    "zamítli „",
    "odložili „",
)


def _predmet_z_nazvu(nazev: str) -> str:
    """Významová část názvu zákona, ne celý legislativní titulek."""
    key = _topic_key(nazev)
    if key in PREDMET_LIDSKY:
        return PREDMET_LIDSKY[key]

    t = nazev.strip()
    vzory = (
        r"^návrh zákona,?\s*kterým se (?:mění|doplňuje|upravuje)\s+",
        r"^návrh zákona o\s+",
        r"^novela zákona o\s+",
        r"^novela\s+z\.?\s*o\s+",
        r"^novela o\s+",
        r"^zákon,?\s*kterým se (?:mění|doplňuje)\s+",
        r"^vl\.?\s*n\.?\s*z\.?\s*[--]?\s*",
        r"^vl\.?\s*n\.?\s*z\.?\s+o\s+",
        r"^změna\s+z\.?\s*",
        r"^změna\s+zákona\s+",
    )
    for _ in range(4):
        pred = t
        for pat in vzory:
            t = re.sub(pat, "", t, flags=re.I).strip(" .---")
        t = re.sub(r"\(změna\s+z\.[^)]+\)", "", t, flags=re.I).strip(" .---")
        if t == pred:
            break
    t = re.sub(r"\s*[--]\s*eu\s*$", "", t, flags=re.I).strip(" .---")
    if len(t) > 70:
        t = _zkrat_nazev(t)
    if re.match(r"^(novela|změna)\s+z\.?", t, re.I):
        return ""
    return t[0].lower() + t[1:] if t else ""


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


def _lead_je_vyrizeny(lead: str) -> bool:
    low = lead.lower()
    if re.search(r"\bzměna\s+z\.?\b", low):
        return False
    if re.search(r"\bnovela\s+z\.?\b", low):
        return False
    if any(z in low for z in ZAKAZANE_LEAD_KONCE):
        return False
    if "hlasovali o" in low and "nakonec schválili" not in low:
        return False
    if re.search(r"schválili změny (v|ve) ", low):
        return True
    if re.search(r"schválili, že ", low):
        return True
    if re.search(r"(zamítli změny|odložili|posunuli|vyjádřili|nestihl)", low):
        return True
    if re.search(r"řešili, jestli ", low):
        return True
    return len(lead.split()) >= 10


def _veta_je_odhad_dopadu(veta: str) -> bool:
    low = veta.lower()
    if any(p in low for p in ODHAD_DOPADU):
        return True
    if re.search(r"\bmůže\b", low) and not re.search(
        r"může (policie|vláda|utratit|vládnout|stíhat)",
        low,
    ):
        return True
    return False


def _veta_ma_konkretni_dopad(veta: str) -> bool:
    if _veta_je_odhad_dopadu(veta):
        return False
    low = veta.lower()
    if re.search(r"\d", veta):
        return True
    return any(m in low for m in KONKRETNI_DOPAD)


def _text_ma_konkretni_dopad(text: str) -> bool:
    vety = _rozdelit_vety(text)
    return any(_veta_ma_konkretni_dopad(v) for v in vety)


def _text_ma_koho(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in KDO_KLIC)


def _dopad_je_publikovatelny(text: str) -> bool:
    """Koho musí být vždy; dopad jen pokud je konkrétní, jinak jen koho a konec."""
    if not text or len(text.split()) < 6:
        return False
    if not _text_ma_koho(text):
        return False
    if any(_veta_je_odhad_dopadu(v) for v in _rozdelit_vety(text)):
        return False
    if re.fullmatch(r"penze[.!\s]*", text.lower().strip()):
        return False
    return True


def _priorita_bodu(dopad: str) -> int:
    """2 = konkrétní dopad, 1 = jen koho, 0 = nepublikovat."""
    if not _dopad_je_publikovatelny(dopad):
        return 0
    return 2 if _text_ma_konkretni_dopad(dopad) else 1


def _format_koho_veta(veta: str) -> str:
    v = veta.strip()
    low = v.lower()
    if low.startswith("týká se "):
        zbytek = v[8:].strip()
        if zbytek:
            return f"Koho se to týká? {zbytek[0].upper()}{zbytek[1:]}"
    if low.startswith("týká se"):
        zbytek = v[7:].strip(" ,")
        if zbytek:
            return f"Koho se to týká? {zbytek[0].upper()}{zbytek[1:]}"
    return v


def _bod_je_publikovatelny(blok: BlokDne, lead: str, dopad: str) -> bool:
    if not ma_glosu(blok.nazev, blok.vysvetleni, proslo=blok.proslo):
        return False
    gloss = glosa_pro_obcana(blok.nazev, blok.vysvetleni, proslo=blok.proslo)
    if _glosa_je_nedostatecna(gloss):
        return False
    if any(_veta_je_odhad_dopadu(v) for v in _rozdelit_vety(gloss)):
        return False
    if not _lead_je_vyrizeny(lead):
        return False
    if not _dopad_je_publikovatelny(dopad):
        return False
    return True


def _verdikt_bloku(blok: BlokDne) -> str:
    """schválili / zamítli / odložili / hlasovali / řešili, podle dat, ne synonyma."""
    t = _zdrojovy_text(blok).lower()
    if any(
        w in t
        for w in (
            "posun digitalizace",
            "úřady nestihly",
            "nestihly systém",
            "nestihly připravit",
        )
    ):
        return "odlozili"
    if blok.pocet_hlasovani > 0:
        return "schvalili" if blok.proslo else "zamitli"
    return "resili"


def _lead_schvaleni(blok: BlokDne, *, poslusne: str, jadro: str) -> str:
    predmet = _predmet_z_nazvu(blok.nazev)
    if predmet and len(predmet) > 6:
        return f"{poslusne}poslanci schválili změny v {predmet}."
    if jadro and re.match(r"^(schválili|schvalili)\b", jadro, re.I):
        return f"{poslusne}poslanci {jadro[0].lower()}{jadro[1:]}."
    if jadro and len(jadro.split()) >= 6:
        return f"{poslusne}poslanci schválili změnu, {jadro[0].lower()}{jadro[1:]}."
    return ""


def _lead_zamiteni(blok: BlokDne, *, poslusne: str) -> str:
    predmet = _predmet_z_nazvu(blok.nazev)
    if predmet:
        return f"{poslusne}poslanci zamítli změny v {predmet}."
    return ""


def _lead_z_faktů(blok: BlokDne, *, use_poslusne: bool, state: dict) -> str:
    key = _topic_key(blok.nazev)
    jadro = _ocisti_svejk_jadro(blok.svejk)
    verdikt = _verdikt_bloku(blok)
    poslusne = ""

    if use_poslusne and state.get("poslusne_count", 0) < 1:
        poslusne = "Poslušně hlásím, že "
        state["poslusne_count"] = state.get("poslusne_count", 0) + 1

    if key == "statni_socialni_podpo":
        kdy = ""
        if re.search(r"1\.\s*7\.\s*2026", blok.svejk):
            kdy = " k 1. červenci"
        if "nestihl" in _zdrojovy_text(blok).lower():
            lead = (
                f"{poslusne}stát chtěl spustit nové dávky{kdy}, "
                "ale úřady na to ještě nemají připravené počítače, poslanci to posunuli."
            )
        elif jadro:
            lead = (
                f"{poslusne}stát byl připraven měnit dávky dřív, než software, "
                "který je má spočítat, poslanci změnu odložili."
            )
        else:
            lead = f"{poslusne}poslanci odložili změny dávek."
        return _humanizovat_lead(lead.strip())

    if key == "socialnich_sluzb":
        lead = (
            "Poslanci řešili, jestli se příspěvky na péči přesunou na jiný úřad."
        )
        if blok.proslo:
            rok = _rok_z_textu(blok.svejk)
            if rok:
                lead += f" Přesun na jiný úřad se odkládá až na rok {rok}."
        else:
            lead += " Nakonec neprošla."
        return _humanizovat_lead(lead)

    if "důvěr" in blok.nazev.lower() and "nedůvěr" not in blok.nazev.lower():
        if blok.proslo:
            return f"{poslusne}poslanci vyjádřili vládě důvěru.".strip().capitalize()
        return f"{poslusne}návrh na vyslovení nedůvěry neprošel.".strip().capitalize()

    if "nedůvěr" in blok.nazev.lower():
        if blok.proslo:
            return f"{poslusne}poslanci vyslovili vládě nedůvěru.".strip().capitalize()
        return f"{poslusne}návrh na nedůvěru vládě neprošel.".strip().capitalize()

    if "zkumavk" in blok.nazev.lower() or "diagnostick" in blok.nazev.lower():
        lead = (
            "Poslanci schválili, že výrobci musí nemocnicím hlásit, "
            "když dojdou zkumavky na odběry."
        )
        if poslusne:
            lead = f"{poslusne}{lead[0].lower()}{lead[1:]}"
        return _humanizovat_lead(lead.strip())

    if verdikt == "schvalili":
        lead = _lead_schvaleni(blok, poslusne="", jadro=jadro)
        if lead and blok.pocet_zamitnuto > 0 and blok.pocet_hlasovani > 1:
            lead = (
                f"{po_hlasovanich_cap(blok.pocet_hlasovani)} "
                f"{lead[0].lower()}{lead[1:]}"
            )
        if lead and poslusne:
            lead = f"{poslusne}{lead[0].lower()}{lead[1:]}"
    elif verdikt == "zamitli":
        lead = _lead_zamiteni(blok, poslusne="")
    elif verdikt == "odlozili":
        predmet = _predmet_z_nazvu(blok.nazev)
        if "nestihl" in _zdrojovy_text(blok).lower() and predmet:
            lead = f"poslanci odložili změny v {predmet}."
        elif jadro:
            lead = f"poslanci odložili změnu, {jadro[0].lower()}{jadro[1:]}."
        else:
            lead = ""
    else:
        lead = ""

    if not lead:
        return ""
    if poslusne and not lead.lower().startswith("poslušně"):
        lead = f"{poslusne}{lead[0].lower()}{lead[1:]}"
    return _humanizovat_lead(lead.strip().capitalize())


def _veta_konfliktu_s_leadem(veta: str, lead: str) -> bool:
    if _prekryvaji(veta, lead, prag=0.72):
        return True
    ll, lv = lead.lower(), veta.lower()
    if any(k in ll for k in ("software", "počítač", "digitaliz")):
        if any(k in lv for k in ("počítač", "nestihl", "připravit", "software", "sjednotí")):
            return True
    if "stěhovat" in ll or "přesunout" in ll or "přesun" in ll:
        if "zatím pořád" in lv or "pořád půjdete" in lv:
            return False
        if "přesun" in lv and "odkládá" in lv and len(lv) < 55:
            return True
    return False


def _lead_veta(blok: BlokDne, *, state: dict, use_poslusne: bool) -> str:
    return _lead_z_faktů(blok, use_poslusne=use_poslusne, state=state)


def _co_to_znamena(blok: BlokDne, lead: str) -> str:
    gloss = glosa_pro_obcana(blok.nazev, blok.vysvetleni, proslo=blok.proslo)
    if _glosa_je_nedostatecna(gloss):
        return ""

    vety = _rozdelit_vety(gloss)
    if not vety:
        return ""

    razeni = sorted(vety, key=_skore_vety_celkem, reverse=True)
    koho_vety = [v for v in razeni if any(k in v.lower() for k in KDO_KLIC)]
    dopad_vety = [
        v
        for v in razeni
        if any(k in v.lower() for k in DOPAD_KLIC) and v not in koho_vety
    ] or [v for v in razeni if any(k in v.lower() for k in DOPAD_KLIC)]

    def _bere_vetu(v: str, chosen: list[str]) -> bool:
        if _veta_je_odhad_dopadu(v) or _veta_je_pouze_uradni(v) or _veta_konfliktu_s_leadem(v, lead):
            return False
        if v in chosen:
            return False
        if chosen and _prekryvaji(v, chosen[-1], prag=0.55):
            return False
        return True

    konkretni_vety = [v for v in razeni if _veta_ma_konkretni_dopad(v)]
    dopad_vety = [
        v
        for v in konkretni_vety
        if any(k in v.lower() for k in DOPAD_KLIC) and v not in koho_vety
    ] or [v for v in konkretni_vety if v not in koho_vety]

    chosen: list[str] = []
    for pool in (koho_vety, dopad_vety):
        for v in pool:
            if _bere_vetu(v, chosen):
                chosen.append(v)
                break

    if not chosen:
        for v in razeni:
            if _bere_vetu(v, chosen) and _text_ma_koho(v):
                chosen.append(v)
                break

    if not chosen:
        return ""

    if len(chosen) == 1 or not any(_veta_ma_konkretni_dopad(v) for v in chosen[1:]):
        return _format_koho_veta(chosen[0])

    koho = chosen[0]
    dopad_v = next((v for v in chosen[1:] if _veta_ma_konkretni_dopad(v)), "")
    if not dopad_v:
        return _format_koho_veta(koho)
    text = f"{_format_koho_veta(koho)} {dopad_v}"
    if not _dopad_je_publikovatelny(text):
        return _format_koho_veta(koho)
    return text


def _pointa_je_uvěřitelna(text: str) -> bool:
    low = text.lower()
    return not any(p in low for p in NEKREATIVNI_POINTA)


def _pointa_jednou(blok: BlokDne, lead: str, dopad: str, *, state: dict) -> str:
    """Nejvýše jedna pointa za den, jen uvěřitelná, navázaná na realitu."""
    if state.get("pointa_pouzita"):
        return ""
    key = _topic_key(blok.nazev)
    slot = f"listy_pointa_{key}"
    from svejk.mix import SLOTS

    if slot not in SLOTS:
        slot = "listy_pointa_obecne"
    text = pick_slot(slot, seed=f"pt|{blok.nazev}", state=state)
    if (
        not text
        or not _pointa_je_uvěřitelna(text)
        or _prekryvaji(text, lead)
        or _prekryvaji(text, dopad)
    ):
        return ""
    state["pointa_pouzita"] = True
    return text


def _substantivni_zakony(day: DenSchuze) -> list[BlokDne]:
    return [
        b
        for b in day.bloky
        if b.typ == "law" and _law_kategorie(b) == "substantivni"
    ]


def _statistika_dne(day: DenSchuze) -> dict:
    bloky = day.bloky
    zakony = [b for b in bloky if b.typ == "law"]
    pocet_hlas = sum(b.pocet_hlasovani for b in bloky if b.pocet_hlasovani)
    pocet_zamitnuto = sum(b.pocet_zamitnuto for b in zakony)
    pocet_proslo = sum(1 for b in zakony if b.proslo)
    start = bloky[0].cas_od if bloky else ""
    end_b = next((b for b in reversed(bloky) if b.typ == "end"), None)
    end_cas = end_b.cas_od if end_b else (bloky[-1].cas_od if bloky else "")
    minuty = 0
    if start and end_cas:
        minuty = max(0, _cas_minuty(end_cas) - _cas_minuty(start))
    dlouha_debata = any(
        "hodin" in b.svejk and _hodiny_debaty(b.svejk) >= 2
        for b in bloky
        if b.typ in ("debate", "porad")
    )
    return {
        "pocet_hlas": pocet_hlas or len(zakony),
        "minuty": minuty,
        "end_cas": end_cas,
        "proslo": pocet_proslo,
        "zamitnuto": pocet_zamitnuto,
        "dlouha_debata": dlouha_debata,
    }


def _hodiny_debaty(svejk: str) -> int:
    m = re.search(r"(\d+)\s*hodin", svejk)
    return int(m.group(1)) if m else 0


def _dnesni_ucet(stats: dict, *, state: dict) -> str:
    p, m, k = stats["pocet_hlas"], stats["minuty"], stats["end_cas"]
    if k:
        return f"{p} hlasování, {m} minut v sále,\na v {k} bylo po všem."
    return f"{p} hlasování,\n{m} minut v sále."


def _shrnuti_radka(stats: dict, *, state: dict) -> str:
    """Faktické shrnutí dne, bez opakování titulků z článku."""
    if stats["proslo"] and stats["minuty"] and stats["minuty"] < 120:
        p = stats["proslo"]
        if p == 1:
            return "schválili jednu změnu a šlo se domů"
        return f"schválili {p} změny a šlo se domů"
    if stats["end_cas"] and stats["minuty"] < 90:
        return _pick_slot_konkrétní(
            "listy_vysledek_konec",
            seed=f"vk|{stats['end_cas']}|{stats['minuty']}",
            state=state,
            min_skore=0,
            konec=stats["end_cas"],
        )
    if stats["dlouha_debata"] and stats["proslo"]:
        return "hlavně pár zákonů prošlo až po dlouhém dohadování o pořadu"
    if stats["dlouha_debata"] and not stats["proslo"] and not stats["zamitnuto"]:
        return "žádný zákon se nehlasoval"
    if stats["proslo"]:
        return "hlavně pár změn prošlo, zbytek ne"
    return "víc návrhů padlo než prošlo"


def _zamitnuto_vysledek_radek(n: int) -> str:
    if n == 1:
        return f"* {n} návrh neprošel"
    if 2 <= n <= 4:
        return f"* {n} návrhy neprošly"
    return f"* {n} návrhů neprošlo"


def _vysledek_dne(
    day: DenSchuze,
    zakony: list[BlokDne],
    stats: dict,
    *,
    state: dict,
) -> list[str]:
    lines = [
        f"* {stats['proslo']} {'věc' if stats['proslo'] == 1 else 'věci'} schválili",
        _zamitnuto_vysledek_radek(stats["zamitnuto"]),
    ]
    lines.append(debata_vysledek_radek(stats))
    lines.append(f"* {_shrnuti_radka(stats, state=state)}")
    return lines


_ZAVER_PIVO_UTOPENCE = (
    "že dneska to byla tak krátká schůze, že kdyby si člověk odskočil na jedno "
    "pivo a utopence, přišel by už na závěrečnou."
)


def _zaverecna_veta(stats: dict, *, state: dict) -> str:
    kratky_den = stats["minuty"] < 120
    if kratky_den:
        text = _ZAVER_PIVO_UTOPENCE
    else:
        text = _pick_slot_konkrétní(
            "listy_zaver_dlouhy",
            seed=f"zv|{stats['minuty']}|{stats['end_cas']}",
            state=state,
            min_skore=0,
            minuty=stats["minuty"],
        )
    if not text.lower().startswith("poslušně"):
        text = f"Poslušně hlásím, {text[0].lower()}{text[1:]}"
    return text


def _pocet_slov(text: str) -> int:
    return len(text.split())


def render_den_listy(day: DenSchuze, *, state: dict | None = None) -> str:
    if state is None:
        state = _new_state()
    state["poslusne_count"] = 0
    state["pointa_pouzita"] = False

    datum = _datum_cesky(day.datum)
    den_cap = day.den.capitalize()
    stats = _statistika_dne(day)
    zakony = _substantivni_zakony(day)

    lines = [
        f"# {HLAVICKA_LISTU}",
        "",
        f"**{den_cap} {datum}**",
        "",
        f"**Dnešní účet:** {_dnesni_ucet(stats, state=state)}",
        "",
    ]

    kandidati: list[tuple[int, BlokDne, str, str]] = []
    for blok in zakony:
        lead = _lead_veta(blok, state=state, use_poslusne=False)
        dopad = _co_to_znamena(blok, lead)
        if not lead or not _bod_je_publikovatelny(blok, lead, dopad):
            continue
        kandidati.append((_priorita_bodu(dopad), blok, lead, dopad))

    kandidati.sort(key=lambda x: (-x[0], -x[1].pocet_hlasovani))

    prvni_publikovany = True
    for _, blok, lead, dopad in kandidati:
        poslusne_pred = state.get("poslusne_count", 0)
        if prvni_publikovany:
            lead = _lead_veta(blok, state=state, use_poslusne=True)
        nadpis = _nadpis_bodu(blok)
        prvni_publikovany = False

        lines.append(f"## {nadpis}")
        lines.append("")
        lines.append(lead)
        lines.append("")
        lines.append("### Co to znamená pro vás?")
        lines.append("")
        lines.append(dopad)

        lines.append("")

    lines.append("## Výsledek dne")
    lines.append("")
    for radek in _vysledek_dne(day, zakony, stats, state=state):
        lines.append(radek)
    lines.append("")
    lines.append(f"**{_zaverecna_veta(stats, state=state)}**")

    return "\n".join(lines).strip()


def render_schuze_listy(osa: SchuzeCasovaOsa) -> str:
    if not osa.dny:
        return ""
    state = _new_state()
    parts = [f"# Schůze {osa.cislo}/{osa.obdobi}, {HLAVICKA_LISTU}", ""]
    for i, day in enumerate(osa.dny):
        if i > 0:
            parts.extend(["---", ""])
        parts.append(render_den_listy(day, state=state))
        parts.append("")
    return "\n".join(parts).strip()
