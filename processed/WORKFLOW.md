# Workflow: zpracování schůze

Playbook pro redakci jedné schůze od stažení dat po newsletter.  
Styl a terminologie textů: [`.cursor/rules/steno-zapisy.mdc`](../.cursor/rules/steno-zapisy.mdc).  
Technické detaily polí a příkazů: [processed/README.md](README.md).

## Cíl

- Jedna schůze = složka `processed/{obdobi}-s{N}/` (např. `2025-s23/`).
- Jeden **den** jednání = jedno vydání (`facts/by_day/` + `out/noviny-dlouhe/`).
- Cíl není přepsat celou schůzi, ale vybrat **odchylky** (spory, absurdní detaily, kontrast rétoriky a dat) a napsat k nim satirické, ale **fakticky přesné** texty.

---

## 1. Příprava dat

```bash
./run-svejk.sh sync --obdobi 2025 --schuze N --check-only
./run-svejk.sh build --schuze N --obdobi 2025 --only fetch
./run-svejk.sh build --schuze N --only align
```

**Kontrola:** v `raw/votes.jsonl` a `raw/steno.jsonl` jsou dny, které chceš zpracovat. Bez stena jde rychleji, ale bez citací a scénických poznámek to nemá smysl.

---

## 2. Výběr dnů a témat

Projdi každý den (`review`, raw data). **Nepublikuj** všechno.

| Signál | Co z toho udělat |
|--------|------------------|
| vysoký `pocet_slov` | hlavní článek nebo sekce |
| `proti` > 0 | reálný spor, stojí za článek |
| scénické poznámky v `(závorkách)` | nejlepší gagy |
| `pritomno` výrazně pod 200 | „velká slova k prázdným lavicím“ |
| opakované jednomyslné hlasování | spíš jedna věta ve skóre, ne celý článek |
| `je_porad_schuze: true` | ignoruj (rozjezd, ověřovatelé) |

```bash
./run-svejk.sh review --schuze N --den D.M
./run-svejk.sh review --schuze N --audit
./run-svejk.sh review --schuze N --slug nazev-tematu
```

Rozhodni: kolik **sekcí/článků** ten den bude (typicky 1–3 podle témat, ne podle počtu hlasování).

---

## 2a. Průzkum stena a obohacení `facts`

`align` a `extract` ti dají kostru. **Materiál pro noviny ale vzniká až průchodem stenem** — hledáním **curiosity**, momentů, které zaujmou lidi mimo sněmovnu. Vzor: schůze **s23** (11. 6. 2026), kde z jednoho dne stavebního zákona vyšly tři sekce (Turek, Kovářová, hlasování), ne přehled čtyřiceti řečníků.

**Curiosity** = cokoli, co by čtenář bez jednacího řádu zastavilo: scéna v sále, absurdní metafora, faktický rozpor, lidská chyba předsedajícího, ostrá výměna, ironie délky projevu. Pipeline z stena vytáhne návrhy (`review`, `fakty_z_steno_record`), ale **automat nevidí kontext debaty** — curiosity dohledáváš ručně v celém `steno.jsonl` pro daný den.

### Curiosity pass (procházka stenem)

Pro každý den, který jde do vydání:

1. **Z mapy dne:** z `votes.jsonl` si vypiš body s `proti` > 0 a témata s nejvíc `pocet_slov` ve stenozáznamu. To jsou kotvy, kde curiosity hledat jako první.
2. **Projdi `facts/by_topic/`** pro schůzi (nebo témata z `review --audit`). U každého slugu si přečti, co už je v `fakty[]`, `lead`, `mean`. Co chybí, dohledáš ve stenozáznamu.
3. **Projdi steno den po dni** — ne jen `steno_ids` u tématu:
   ```bash
   ./run-svejk.sh review --schuze N --den D.M
   ./run-svejk.sh review --schuze N --slug nazev-tematu
   ```
   V `raw/steno.jsonl` filtruj podle `datum`, jména řečníka, klíčových slov z názvu bodu / hlasování. U každého silného záznamu si ulož `id` (→ `steno_id`).
4. **Zapiš curiosity do `fakty[]`:** doslovná `citace`, stručný `text` pro redakci, později `link_phrase` (§4a). Scény označ v hlavě jako `[scéna]` (pipeline je také dává jako `kind: scene`).
5. **Vyhoď nebo `publikovat: false`** témata, která mají jen úřední přehled bez curiosity.

**Co pipeline už bere jako curiosity** (viz `svejk/build/steno_text.py`): scénické poznámky v závorkách, „budu stručný“ u dlouhého projevu, věty s čísly a dopadem na občana. **Co musíš dohledat ty:** protichůdná tvrzení dvou řečníků, kontroverze mimo klíčová slova zákona, chyby předsedajícího, gesta mimo závorky, souvislosti napříč body (stejný den, jiné téma).

### Co dělat (shrnutí)

1. Curiosity pass podle kroků výše.
2. Obohať `fakty[]` o konkrétní citace, scény a protichůdná tvrzení.
3. Teprve potom piš `lead` a skládej sekce.

### Co ve stenozáznamu hledat (signály pro laika)

| V stenozáznamu | Proč to lidi zajímá | Příklad ze s23 |
|----------------|---------------------|----------------|
| `(Potlesk)`, `(Hluk)`, gesta, „opouští sál“ | co se v sále reálně dělo | Turek odešel při reakci Svárovské, Piráti tleskali |
| vysoký `pocet_slov` + „budu stručný“ | ironie délky | Kovářová přes padesát minut |
| absurdní přirovnání, čísla, metafora | citátelný moment | „zelený bitcoin“, větrníky foukají 20 % času |
| faktická vsuvka vs. rétorika | kontext navíc | mandát europoslance vs. „opustil EP kvůli parodii“ |
| předsedající / strany se pletou | lidská chyba | Okamura přiřadil Turka k SPD |
| ostrá výměna napříč kluby | spor, ne procedura | Svárovská vs. Turek o akceleračních zónách |
| kontroverzní tvrzení koalice vs. opozice | proč se hádají | Nigérie, Doing Business, hygienické limity |
| rozpor v datech mezi řečníky | historický kvíz | různé čísla o délce řízení, větru, dotacích |
| prázdný sál / chybějící klíčová postava | kontrast velkých slov | (u s22 tentýž den: premiér mimo sál) |

**Grep tipy (curiosity ve stenozáznamu)** v `processed/2025-s{N}/raw/steno.jsonl` (nebo po `datum` filtruj):

- `(Potlesk|Hluk|Smích|Gest|úsměv|opouští|pardon|omlouv|transparent)`
- `budu stručn` — pak zkontroluj `pocet_slov` (ironie délky)
- `"pocet_slov": [3-9][0-9]{2,}` nebo řazení podle délky projevu u daného `datum`
- jména z hlasování s `proti` > 0 — celý jejich projev, ne jen první věta z `review`
- stejné klíčové slovo u dvou řečníků (čísla, země, „developer“, „dotace“) — hledáš rozpor
- `neautorizováno` u krátkého záznamu = přeskoč; u dlouhého = možná chybí přepis, ne curiosity

### Co obvykle neobohacovat

- předčítání paragrafů a formalit
- dlouhé technické pasáže bez sporu (EET, RIA, transpozice), pokud nejsou jádrem dne
- seznam deseti řečníků po sobě — radši **2–3 silné linie** s citacemi
- procedura sama o sobě (`je_porad_schuze`), ledaže je z ní absurdní příběh (s24: boj o pořad)

### Jak poznat, že máš dost materiálu

Pro každou sekci, která půjde do vydání:

- [ ] aspoň **2–3 doslovné citace** v `fakty[]`, každá s ověřeným `steno_id`
- [ ] aspoň **jeden kontrast** (rétorika vs. fakta, velká slova vs. prázdný sál, koalice vs. opozice)
- [ ] víš, **proč by to četl člověk mimo politiku** (bydlení, peníze, absurdita, spor o moc)
- [ ] `mean` jen tam, kde bez vysvětlení nepochopíš **co se hlasovalo nebo proč to bolí**

Teprve potom piš `lead`, skládej sekce a doplň `link_phrase` (§4, §4a).

---

## 3. Struktura vydání

**Jeden den = jeden soubor novin**, uvnitř několik sekcí (`## Nadpis`).

Doporučená kostra:

1. **`dnesni_ucet`** (2 řádky, `\n`, rovnoměrně) — co ten den bylo, lidově
2. **Hlavní témata** — každé = `facts/by_topic/<slug>.json` → jedna sekce
3. **Skóre / výsledek dne** — z `facts/by_day/`
4. **`zaver`** — jedna věta začínající „že …“

**Rozdělení:** radši 2–3 silné debaty + hlasování, ne jeden dlouhý přehled deseti řečníků. Vedlejší projevy patří do sekce jen když posilují pointu.

---

## 4. Psaní `facts/by_topic`

| Pole | Účel |
|------|------|
| `nadpis` | krátký titulek (bez úřednického žargonu) |
| `lead` | první odstavec pod nadpisem, srozumitelný bez jednacího řádu |
| `fakty`, `citace` | 1–3 věty, **doslovně ze stena** |
| `steno_id`, `link_phrase` | viz sekce 4a (odkazy na steno → PSP) |
| `mean` | jen když čtenář nepochopí co / proč / proč ho to zajímá |
| `pointa` | volitelně, satirický závěr sekce |
| `publikovat` | `false` = vynechat z vydání |

**Z praxe:**

- Kuriozita může být **v textu za citátem** (kurzívou), nemusí být rubrika „Kuriozita dne“.
- Zkratky (RIA, SZIF…) nahraď běžnou češtinou, nebo jednou větou v `mean`.
- Po úpravě facts vždy znovu `compose`.

---

## 4a. Odkazy na steno a PSP (dvoustupňově)

Čtenář nejdřív klikne ve **článku** na konkrétní větu. Dostane se na **naši stránku se zdroji** (stenoprotokol + citace). Odtud může jít na **oficiální PSP**.

```
článek  →  stránka Zdroje (steno)  →  psp.cz (celý projev)
   ↑              ↑                        ↑
 link_phrase   citace + kontext         psp_url
```

Příklad z s23: ve větě „podle něj fouká jen dvacet procent času“ je odkaz na  
`/noviny/2025/23/11.06.2026-steno.html#steno-2025_23_00028-p2`,  
pod citátem pak tlačítko „Celý projev na psp.cz“.

### Krok 1: Najdi pasáž ve stenozáznamu

```bash
./run-svejk.sh review --schuze N --slug nazev-tematu
# nebo grep v raw/steno.jsonl podle jména řečníka / klíčových slov
```

Záznam má `id` ve tvaru `2025_23_00028` (období_schůze_pořadí). To je `steno_id`.

### Krok 2: Doplň položku do `fakty[]` v `facts/by_topic/<slug>.json`

U každé citované věty nebo tvrzení, které chceš prolinkovat:

```json
{
  "text": "Krátký popis pro review (nemusí být doslovný).",
  "source": "steno",
  "steno_id": "2025_23_00028",
  "citace": "Doslovný úryvek ze stenoprotokolu, bez úprav.",
  "link_phrase": "podle něj fouká jen dvacet procent času"
}
```

| Pole | Pravidlo |
|------|----------|
| `steno_id` | přesně z `steno.jsonl` / `review`; jiný projev = jiné id |
| `citace` | doslovně ze stena, ověř diakritiku a interpunkci |
| `link_phrase` | **přesná podmnožina textu v článku** (lead nebo tělo sekce), podle které compose najde místo pro odkaz |

`link_phrase` musí **slovně sedět** s tím, co je v `lead` / běžném textu sekce. Compose hledá frázi v textu a obalí ji `<a class="steno-link">`. Když fráze v článku není, odkaz se nevloží (nebo skončí na špatném místě).

**Tipy z praxe (s23):**

- Piš nejdřív článek, pak doplň `link_phrase` podle hotového wordingu, ne naopak.
- U citátu v uvozovkách stačí prolinkovat klíčovou část věty, celou citaci ne.
- Každé **jiné místo ve stenozáznamu** = jiné `steno_id` (Turek v projevu `00028`, faktická poznámka `00040`, Jurečka `00054`).
- Scénické vsuvky (`kind: "scene"`) taky mohou mít vlastní `steno_id` a `link_phrase` (např. „omylem přiřadil ke své SPD“).
- **Nepoužívej jedno `steno_id` pro všechny odkazy** — typická chyba před publikací.

### Krok 3: Zapni stránku se zdroji pro den

V `facts/by_day/YYYY-MM-DD.json`:

```json
"steno_zdroje": true,
"topic_slugs": ["debata-turek-stavebni-zakon", "debata-kovarova-stavebni-zakon", "..."]
```

Bez `"steno_zdroje": true` se nevygeneruje `-steno.html` a odkazy z článku nevzniknou.

### Krok 4: Compose a kontrola

```bash
./run-svejk.sh build --schuze N --only compose --den D.M
```

**V lokálním náhledu ověř:**

1. **Článek** — u důležitých vět jsou klikací `steno-link` (ne všechny stejná kotva).
2. **Stránka Zdroje** (`…/DD.MM.RRRR-steno.html`) — u každé pasáže:
   - „Přesně z článku“ (=`link_phrase`)
   - doslovná citace ze stena
   - odkaz **Celý projev na psp.cz**
3. **PSP** — odkaz vede na správného řečníka a pořadí projevu.

PSP URL se skládají při compose (cache v `aligned/psp_url_cache.json`). Na produkci musí fungovat i bez lokálního `steno.jsonl` (CI používá `steno_refs.json`).

### Kdy stačí jen hlasování

U hlasování bez projevu stačí `source: "votes"` a kotva z `votes.jsonl` (compose to řeší jinak). Pro citace řečníků vždy `source: "steno"` + `steno_id`.

---

## 5. Hlasování a skóre dne (`facts/by_day`)

Nejdřív pochop, **o čem se hlasovalo**. Ne každé „zamítnuto“ = pád zákona.

Typické pasti:

- **Návrh na vrácení do výboru** ≠ zamítnutí novely
- **Druhé kolo** ≠ finální schválení zákona
- Skóre dne: jen **zákony** (`substantivní`), ne výbory, volby funkcí, pořad schůze

V `by_day/YYYY-MM-DD.json`:

- `board_proslo_label` / `board_zamitnuto_label` — **krátké popisky** + čísla (např. „věcných změn“ / „vrácení padlo“)
- `zaver` — „že …“
- odrážky ve „Výsledku dne“ musí **sedět k tabulce**

Po úpravě: `compose` a kontrola na mobilu (popisky tabule se nesmí usekávat).

---

## 6. Steno odkazy (povinná kontrola)

Před publikací projdi **celý řetězec** článek → zdroje → PSP:

1. **Každá důležitá citace** má vlastní `steno_id` a `link_phrase`, která sedí s textem v článku.
2. **Ne všechny odkazy na jedno místo** — klikni postupně každý `steno-link` ve vydání.
3. Na stránce **Zdroje** sedí citace se stenem; tlačítko PSP otevře správný projev.
4. Jména + **strany** ověř v datech (sdílená příjmení).
5. Scénické poznámky (kdo opustil sál, pořadí reakcí) ověř ve stenozáznamu.
6. Čísla (hlasy, délka projevu, `pocet_slov`) **spočítej z dat**.

Chybějící odkaz = chybí nebo nesedí `link_phrase`, špatné `steno_id`, nebo `steno_zdroje: false`. Oprav v `facts/`, znovu `compose`.

## 7. Faktický audit (před schválením)

- [ ] Výklad hlasování = `votes.jsonl` (co přesně padlo / prošlo)
- [ ] Strany u jmen sedí
- [ ] Citace doslovné
- [ ] `dnesni_ucet` a `zaver` neprotiřečí tělu článku
- [ ] Skóre dne = publikované články podle `verdikt` (`schvaleno` / `zamiteno` / `odlozeno`)
- [ ] `./run-svejk.sh glossary-audit --obdobi 2025 --export-only`
- [ ] Žádné em/en pomlčky (compose na ně spadne)

---

## 8. Sestavení a náhled

```bash
./run-svejk.sh build --schuze N --only compose --den D.M
./run-svejk.sh export-pages --obdobi 2025 --out site --cname ""
python3 -m http.server -d site 8765
```

URL náhledu: `http://127.0.0.1:8765/noviny/2025/N/DD.MM.RRRR.html`

**Publish gate** (`processed/publish-approved.json`):

- nové vydání nejdřív do `hidden` (nebo mimo `approved`)
- po review přesuň klíč `2025/N/DD.MM.RRRR` do `approved`
- teprve pak push na `main` (deploy webu)

---

## 9. Newsletter

```bash
./run-svejk.sh newsletter-notify --obdobi 2025 --schuze N --force
```

Před odesláním v Ecomailu:

- tabulka skóre na mobilu
- nadpisy v e-mailu
- **nový koncept** (`--force`), ne starý draft v UI

---

## 10. Finální checklist (typicky až na konci)

| Oblast | Co kontrolovat |
|--------|------------------|
| Materiál | curiosity pass hotový; každá sekce má citace, kontrast a důvod pro laika (§2a) |
| Struktura | méně témat, víc hloubky; pryč úřední přehledy řečníků |
| Hlasování | správný typ hlasování ve wordingu i ve skóre |
| Tabulka dne | krátké labely + mobil |
| Steno | unikátní kotvy, `link_phrase` sedí s textem, PSP link funguje |
| Styl | lead srozumitelný, `zaver` jednou větou |
| Publish | `hidden` → `approved` až po review |

---

## Rychlý workflow

```
sync → align → review (vyber dny/témata)
  → curiosity pass ve stenozáznamu: obohať facts o citace, spory, scény (§2a)
  → facts/by_topic (lead + texty + steno_id + link_phrase)
  → facts/by_day (skóre, zaver, steno_zdroje: true)
  → compose → kontrola steno-link → stránka Zdroje → PSP
  → faktický audit (steno + votes)
  → lokální náhled
  → publish-approved → push
  → newsletter-notify
```
