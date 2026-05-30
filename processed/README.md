# Processed schůze (file-based build)

## Doladění textů (raw → export)

Pipeline: **raw** (`votes.jsonl`, volitelně `steno.jsonl`) → **aligned** (`topics.json`) → **facts** (`by_topic/*.json`, ručně) → **compose** → **export-pages**.

```bash
# přehled jednoho dne: UNL hlasy vs. glosa vs. co jde na web
./run-svejk.sh review --schuze 20 --den 28.5

# jedno téma do hloubky
./run-svejk.sh review --schuze 20 --slug novela-z-stavebni-zakon

# všechna slabá témata schůze
./run-svejk.sh review --schuze 20 --audit

# po úpravě facts přegenerovat noviny + lokální náhled
./run-svejk.sh build --schuze 20 --only compose --den 28.5
./run-svejk.sh export-pages --obdobi 2025 --out site --cname ""
python3 -m http.server -d site 8765
```

Co typicky upravovat v `facts/by_topic/<slug>.json`:

| pole | účel |
|------|------|
| `nadpis` | titulek v novinách (krátký, chytlavý) |
| `lead` | volitelně, švejkovská glosa pod nadpisem (jinak listy) |
| `pointa` | volitelně, pointa hned za glossou (jinak z `tema_vysvetleni` / listy) |
| `mean` | volitelně, věcné „Co to znamená“ (jinak občanská glosa / `koho`+`fakty`) |
| `koho` | kontrola v `review`; na web přes `mean` |
| `fakty` | 1-3 věty pro `review` / lead ze stena |
| `publikovat` | `false` = vynechat z vydání |

V `facts/by_day/YYYY-MM-DD.json` volitelně `"zaver": "…"`, vlastní závěr (jinak vtipný závěr z `listy` / `mix.py`, např. utopence u dlouhé schůze).

**Články:** pod nadpisem švejkovská glosa + pointa; **Co to znamená** jen věcné vysvětlení (bez vtipu). U mnoha hlasování přesnější kotva z hlasování.

**Pomlčky:** ve výstupech nepoužívej em pomlčku (`—`) ani en pomlčku (`–`); místo toho čárka nebo ASCII `-`. Compose při nálezu dlouhé pomlčky spadne.

`review` ukáže návrhy vět ze stena a náhled závěru dne.

Jedna schůze = složka `{obdobi}-s{cislo}/`, např. `2025-s20/`.

```bash
# celé období, všechny schůze 1-20 (dlouhé: steno z Hlídače)
HLIDAC_TOKEN=… ./run-svejk.sh build --obdobi 2025 --vsechny-schuze

# jen stáhnout suroviny (UNL + steno), bez novin
HLIDAC_TOKEN=… ./run-svejk.sh build --obdobi 2025 --vsechny-schuze --only fetch

# po HTTP 429 (Too Many Requests), znovu stejný příkaz; steno.jsonl se **nesmaže**, pokračuje od posledního pořadí
# pomalejší API: HLIDAC_RATE_LIMIT_S=1.5 HLIDAC_TOKEN=… ./run-svejk.sh build --schuze 20 --only fetch

# pokračovat po přerušení (přeskočí schůze s hotovým fetch)
HLIDAC_TOKEN=… ./run-svejk.sh build --obdobi 2025 --vsechny-schuze --only fetch --preskocit-hotove

# jedna schůze
HLIDAC_TOKEN=… ./run-svejk.sh build --schuze 20 --obdobi 2025

# bez stena (rychlé, jen glosy)
./run-svejk.sh build --schuze 20 --skip-steno

# jen přegenerovat noviny z facts/
./run-svejk.sh build --schuze 20 --only compose

# čtení hotového výstupu
./run-svejk.sh timeline --schuze 20 --den 26.5 --format noviny-dlouhe
```

Struktura:

- `raw/votes.jsonl`, hlasování z UNL
- `raw/steno.jsonl`, stenozáznamy z Hlídače
- `aligned/topics.json`, párování témat
- `facts/by_topic/*.json`, fakta k bodům (ručně editovatelná)
- `facts/by_day/*.json`, index dnů
- `out/noviny-dlouhe/*.md`, hotové noviny (markdown)
- `out/noviny-dlouhe/*.html`, stejný obsah ve designu varianta C (letterpress)

Proměnná `SVEJK_PROCESSED_DIR` přepíše výchozí `processed/` v kořeni projektu.

Web: `GET /noviny/{obdobi}/{schuze}/{den}`, např. `/noviny/2025/19/15.05.2026`

Krátká URL `/noviny/2025/15.05.2026` přesměruje na schůzi (u duplicitního data vybere novější schůzi).

V HTML dole: šipky ←/→ mezi vydáními **chronologicky přes celé období** (všechny schůze za sebou). Listnutí stránky funguje přes web server (fetch bez reloadu); u `file://` je klasický přechod.

Po `--vsechny-schuze` vznikne souhrn `processed/2025-obdobi-build.json` a složky
`processed/2025-s1/`, `2025-s2/`, … `2025-s20/`.

## GitHub Pages

Statický web pro **poslusnehlasim.cz**:

```bash
./run-svejk.sh export-pages --obdobi 2025 --out site
```

Výstup: `site/index.html`, `site/noviny/2025/{schuze}/{den}.html`, `site/static/`.

Deploy: GitHub Actions workflow `.github/workflows/pages.yml` (push na `main` + cron).
V repo Settings → Pages → Source: **GitHub Actions**. Secret: `HLIDAC_TOKEN` (volitelné, build dat).

Vlastní doména: soubor `site/CNAME` (`poslusnehlasim.cz`), DNS u registrátora → GitHub Pages.
