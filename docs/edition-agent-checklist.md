# Edition workflow: co agent dělá po promptu

Referenční checklist pro prompt typu:

> doplň `facts/` podle briefu pro schůzi 29, 25.8

**Poznámka k číslům schůzí:** datum ≠ číslo schůze. Např. **25. 8. 2026 = schůze 29** (`processed/2025-s29/`), **14. 7. 2026 = schůze 28** (`processed/2025-s28/`).

Definice workflow: `processed/WORKFLOW.md` (§ Rychlý workflow edition), `.cursor/prompts/edition-draft.md`.

---

## Celý řetězec

```
sync / fetch / align
  → edition brief --schuze N --den DD.MM.RRRR   (skript: kostra + brief)
  → Cursor: doplň facts/                         (agent: redakční texty)
  → edition link-phrases → preview → review
  → edition approve → publish
```

---

## 1. Co musí být hotové před promptem

Skript `./run-svejk.sh edition brief --schuze N --den DD.MM.RRRR` (`svejk/edition/brief.py`):

1. Načte `raw/votes.jsonl` a `raw/steno.jsonl`
2. Pokud je potřeba, spustí `align` → `aligned/topics.json`
3. Ohodnotí témata (spor, prázdný sál, scény, délka stena, zákony vs. procedura)
4. Vybere **max 3 témata** do `recommended`
5. Zapíše **kostru** do:
   - `facts/by_topic/<slug>.json`
   - `facts/by_day/YYYY-MM-DD.json` (`topic_slugs`, `stats`, `steno_zdroje: true`)
6. Vygeneruje brief:
   - `editions/YYYY-MM-DD/brief.md` + `brief.json`
   - `editions/YYYY-MM-DD/edition.json` (stav `draft`)

### Normální den vs. prázdný brief

**Normální den** (např. s28, 14. 7.): `brief.json` → `recommended[]` s tématy, skóre, signály, předvybranými citacemi.

**Prázdný brief** (např. s29, 25. 8.): `recommended: []`, protože `aligned/topics.json` má téma na **jiný kalendářní den** (26. 8.), zatímco jednací den 25. 8. je debata o pořadu + veto. Kostra v `facts/` pak vznikla ručně nebo z `review`, ne z automatického výběru briefu.

**Agent musí:** i bez `recommended[]` načíst existující `facts/by_topic/*.json` a `topic_slugs` v `by_day/`, projít steno pro jednací den, doplnit texty.

---

## 2. Co agent načte po promptu

### Instrukce (Cursor rules + prompt)

| Zdroj | K čemu |
|-------|--------|
| `.cursor/prompts/edition-draft.md` | checklist polí |
| `.cursor/rules/edition-draft.mdc` | trigger edition workflow |
| `.cursor/rules/steno-zapisy.mdc` | styl, skóre, terminologie |
| `.cursor/rules/poslusne-hlasim-pravidla.md` | sekce, curiosity pass, pořad |
| `.cursor/rules/schuzni-workflow.mdc` | pořadí kroků, časté chyby |

### Data pro konkrétní den

| Soubor | K čemu |
|--------|--------|
| `editions/YYYY-MM-DD/brief.md` | lidský přehled (může být prázdný v doporučených tématech) |
| `editions/YYYY-MM-DD/brief.json` | `recommended`, `rejected`, `day_stats` |
| `facts/by_topic/*.json` | kostra + cíl úprav |
| `facts/by_day/YYYY-MM-DD.json` | den jako celek |
| `raw/votes.jsonl` | hlasování, `proti`, typ hlasování |
| `raw/steno.jsonl` nebo `aligned/steno_refs.json` | citace, curiosity pass |
| `aligned/topics.json` | témata ↔ hlasování ↔ steno_ids |
| `editions/YYYY-MM-DD/edition.json` | stav, feedback |

Volitelně: `./run-svejk.sh review --schuze N --den DD.MM.RRRR`

---

## 3. Co dopíše agent vs. co dodá skript

### `facts/by_topic/<slug>.json`

**Ze skriptu (kostra):** `slug`, `nazev`, `datum`, `verdikt`, `predmet_lidsky`, `koho`, `fakty[]` s návrhy citací + `steno_id`, `publikovat`, `priorita`, `signaly`, metadata hlasování.

**Agent dopíše:** `nadpis`, `lead`, `pointa`, `mean`, `citace_text` + `citace_autor`, obohacení `fakty[]` (curiosity pass), případně `link_phrase`.

**Nepíše z hlavy:** citace, jména, čísla hlasů — vždy ze stena / votes.

### `facts/by_day/YYYY-MM-DD.json`

**Ze skriptu:** `topic_slugs`, `stats`, `steno_zdroje: true`

**Agent dopíše:** `dnesni_ucet` (2 řádky, `\n`), `zaver` (začíná „že …"), volitelně `vysledek`, `jazykolam`, `slovnicek`

---

## 4. Curiosity pass (brief to neudělá)

Brief vytáhne max ~4 návrhy citací na téma. Pipeline **nevidí celý kontext debaty**.

Agent projde stenozáznam pro jednací den:

- body s `proti` > 0 ve votes
- scény `(Potlesk)`, `(Hluk)`, „opouští sál"
- absurdní metafory, rozpory mezi řečníky
- u debaty o pořadu: co **nedostalo** do programu vs. co **zůstalo**

Detail: `poslusne-hlasim-pravidla.md` §1b, `WORKFLOW.md` §2a.

---

## 5. Po psaní (terminál)

```bash
./run-svejk.sh edition link-phrases --schuze N --den DD.MM.RRRR
./run-svejk.sh edition preview --schuze N --den DD.MM.RRRR
# volitelně: --serve (server nad site/ včetně /static/)
./run-svejk.sh edition review --schuze N --den DD.MM.RRRR
```

- **link-phrases** — doplní `link_phrase` podle hotového textu
- **preview** — compose + kopie do `site/preview/` + sync `site/static/` (Švejk, CSS)
- **review** — odkazy, strany u jmen, citace ve stenozáznamu

Typický stav před finálem: link_phrase coverage < 100 %, „slabá témata“ v review.

---

## 6. Ochrana ruční práce

`merge_topic_skeleton` / `merge_day_skeleton` chrání hotové `lead`, `pointa`, `mean`, `dnesni_ucet`, `zaver`. Opakovaný `edition brief` je nepřepíše.

---

## Jedna věta

Prompt = **přečti brief + pravidla, vezmi kostru v `facts/`, ověř ve stenozáznamu a votes, doplň redakční texty, navrhni link-phrases / review.**

Brief je **menu a předvybrané citace**, ne hotové noviny. Noviny vzniknou až po curiosity passu a compose.

## Trigger v chatu

```
edition draft schůze 29, 25.8
```

nebo:

```
doplň facts/ podle briefu pro schůzi 29, 25.8
```
