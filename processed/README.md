# Processed schůze (file-based build)

Jedna schůze = složka `{obdobi}-s{cislo}/`, např. `2025-s20/`.

```bash
# celé období — všechny schůze 1–20 (dlouhé: steno z Hlídače)
HLIDAC_TOKEN=… ./run-svejk.sh build --obdobi 2025 --vsechny-schuze

# jen stáhnout suroviny (UNL + steno), bez novin
HLIDAC_TOKEN=… ./run-svejk.sh build --obdobi 2025 --vsechny-schuze --only fetch

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

- `raw/votes.jsonl` — hlasování z UNL
- `raw/steno.jsonl` — stenozáznamy z Hlídače
- `aligned/topics.json` — párování témat
- `facts/by_topic/*.json` — fakta k bodům (ručně editovatelná)
- `facts/by_day/*.json` — index dnů
- `out/noviny-dlouhe/*.md` — hotové noviny (markdown)
- `out/noviny-dlouhe/*.html` — stejný obsah ve designu varianta C (letterpress)

Proměnná `SVEJK_PROCESSED_DIR` přepíše výchozí `processed/` v kořeni projektu.

Web: `GET /noviny/{obdobi}/{schuze}/{den}` — např. `/noviny/2025/19/15.05.2026`

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
V repo Settings → Pages → Source: **GitHub Actions**. Secret: `HLIDAC_TOKEN` (volitelné — build dat).

Vlastní doména: soubor `site/CNAME` (`poslusnehlasim.cz`), DNS u registrátora → GitHub Pages.
