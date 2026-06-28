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
| `steno_id`, `link_phrase` | kotva na PSP u konkrétní věty |
| `mean` | jen když čtenář nepochopí co / proč / proč ho to zajímá |
| `pointa` | volitelně, satirický závěr sekce |
| `publikovat` | `false` = vynechat z vydání |

**Z praxe:**

- Kuriozita může být **v textu za citátem** (kurzívou), nemusí být rubrika „Kuriozita dne“.
- Zkratky (RIA, SZIF…) nahraď běžnou češtinou, nebo jednou větou v `mean`.
- Po úpravě facts vždy znovu `compose`.

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

Před publikací:

1. Každá citace → správná kotva ve stenoprotokolu (**ne všechny na jedno místo**).
2. Jména + **strany** ověř v datech (sdílená příjmení).
3. Scénické poznámky (kdo opustil sál, pořadí reakcí) ověř ve stenozáznamu.
4. Čísla (hlasy, délka projevu, `pocet_slov`) **spočítej z dat**.

---

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
| Struktura | méně témat, víc hloubky; pryč úřední přehledy řečníků |
| Hlasování | správný typ hlasování ve wordingu i ve skóre |
| Tabulka dne | krátké labely + mobil |
| Steno | unikátní kotvy, tooltipy celé |
| Styl | lead srozumitelný, `zaver` jednou větou |
| Publish | `hidden` → `approved` až po review |

---

## Rychlý workflow

```
sync → align → review (vyber dny/témata)
  → facts/by_topic (texty + citace + steno)
  → facts/by_day (skóre, závěr, labely tabule)
  → faktický audit (steno + votes)
  → compose → lokální náhled
  → publish-approved → push
  → newsletter-notify
```
