# Vygeneruj vydání podle briefu

Pracuješ na satirickém newsletteru **Poslušně hlásím**. Materiál je už připravený — tvůj úkol je **dopsat redakční texty**, ne vymýšlet fakta.

## Vstup

1. Načti `processed/{obdobi}-s{schuze}/editions/{YYYY-MM-DD}/brief.md` a `brief.json`.
2. Pravidla psaní: `.cursor/rules/poslusne-hlasim-pravidla.md` a `steno-zapisy.mdc`.
3. Celý checklist (co načíst, co dopíšeš ty vs. skript): `docs/edition-agent-checklist.md`.

**Prázdný brief (`recommended: []`):** témata jsou v `facts/by_day/*.json` → `topic_slugs` a v `facts/by_topic/*.json`. Projdi steno pro jednací den ručně (curiosity pass), brief nemusí mít menu.

## Co udělat

Pro každé **doporučené téma** v briefu uprav `facts/by_topic/<slug>.json`:

- `nadpis` — krátký, chytlavý, lidový
- `lead` — první odstavec (srozumitelný bez jednacího řádu)
- `pointa` — tělo sekce, glosa „Poslušně podotýkám…"
- `mean` — jedna suchá věta (Hlášení na velitelstvo)
- `citace_text` + `citace_autor` — nejlepší doslovná citace ze stena (z briefu)
- `publikovat: true`
- `fakty[]` — obohať o doslovné `citace`, `steno_id` z briefu; `link_phrase` doplní skript

V `facts/by_day/{YYYY-MM-DD}.json`:

- `dnesni_ucet` — **2 řádky** (`\n`), rovnoměrně
- `zaver` — jedna věta začínající „že …"
- `topic_slugs` — slugs z briefu
- `steno_zdroje: true`

## Po psaní (povinné)

```bash
./run-svejk.sh edition link-phrases --schuze N --den D.M.RRRR
./run-svejk.sh edition preview --schuze N --den D.M.RRRR
./run-svejk.sh edition review --schuze N --den D.M.RRRR
```

## Pravidla

- Citace **doslovně** ze stenoprotokolu — nikdy si nevymýšlej.
- Skóre dne jen u **zákonů**, ne procedury.
- Do `dnesni_ucet`, `zaver` a `vysledek` **nepiš schválení pořadu schůze** — i když šlo o maraton hlasování, výsledek procedury není pointa dne. Absurdní detaily z boje o pořad patří do sekce, ne do hlavního hlášení.
- **Debata o pořadu** (`debata-porad-*`, `spor_o_porad: true`): sekci piš ve dvou částech — **co se do pořadu / na program nedostalo** (vylistuj návrhy + shrnutí) a **co se do pořadu dostalo** (finální program + shrnutí). U pořadu **nepiš „padlo“** (to je váha zákona), piš **„nedostalo se na program“**. Detail §2a v `poslusne-hlasim-pravidla.md`.
- Žádné em/en pomlčky.
- Čísla v lead/pointa piš **slovně** (kromě skóre typu 97:51).
- Citát dne (`jazykolam`) nesmí být stejná věta jako citát v článku (`citace_text` ani `fakty[].citace`).
