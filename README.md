# Poslušně hlásím

**poslusnehlasim.cz** · srozumitelný přehled ze Sněmovny

Poslušně hlásím je srozumitelný přehled z Poslanecké sněmovny: co se projednalo, co prošlo a proč na tom záleží. Statický web **[poslusnehlasim.cz](https://poslusnehlasim.cz)** vychází ze stenozáznamů a hlasování z PSP (UNL + Hlídač státu); texty v novinách redakce dolaďuje ručně v `processed/`.

## Struktura repozitáře

| Složka / soubor | Účel |
|-----------------|------|
| [`svejk/`](svejk/) | Build pipeline, šablony HTML, CSS, glosář, newsletter |
| [`psp/`](psp/) | Stahování a parsování dat ze sněmovny (UNL, Hlídač, steno) |
| [`processed/`](processed/) | Hotová vydání — raw → aligned → facts → out (viz [processed/README.md](processed/README.md)) |
| [`hl-2025ps/`](hl-2025ps/) | Seznam schůzí a hlasování z UNL (`hl2025s.unl`, `zmatecne.unl`) |
| [`workers/`](workers/) | Cloudflare Pages worker: odběr (Ecomail), korektury (Resend) |
| [`svejk.py`](svejk.py), [`run-svejk.sh`](run-svejk.sh) | CLI vstupní bod |
| [`.github/workflows/`](.github/workflows/) | CI — deploy webu, sync dat, kontrola nových dat |

**Negeneruje se do gitu:** `site/` (statický web z `export-pages`), `raw/steno.jsonl` (velké soubory — viz `processed/.gitignore`), lokální `secrets.env`.

## Rychlý start

**Požadavky:** Python 3.10+ (doporučeno 3.12), pip.

```bash
# virtuální prostředí (volitelné)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-svejk.txt

# tajemství pro Hlídač (volitelné, jen sync/fetch)
echo 'HLIDAC_TOKEN=…' > secrets.env

# náhled webu z hotových facts (bez stahování dat)
./run-svejk.sh export-pages --obdobi 2025 --out site --cname ""
python3 -m http.server -d site 8765
# → http://localhost:8765
```

Všechny příkazy spouštěj přes `./run-svejk.sh` — skript najde Python, načte `secrets.env` a deleguje na `svejk.py`.

## Pipeline (od dat k novinám)

```
UNL + Hlídač státu
       ↓  build / sync
processed/{obdobi}-s{N}/raw/     votes.jsonl, steno.jsonl
       ↓  align
processed/.../aligned/topics.json
       ↓  extract + ruční editace
processed/.../facts/by_topic/*.json, by_day/*.json
       ↓  compose
processed/.../out/noviny-dlouhe/*.md, *.html
       ↓  export-pages
site/noviny/2025/{schuze}/{den}.html  →  GitHub Pages
```

Jedna schůze = složka `processed/2025-s20/` (období + číslo schůze). URL na webu: `/noviny/2025/20/28.05.2026`.

### Typický den redaktora

```bash
# přehled dne: hlasy vs. glosa vs. návrh na web
./run-svejk.sh review --schuze 20 --den 28.5

# po úpravě facts přegenerovat vydání
./run-svejk.sh build --schuze 20 --only compose --den 28.5

# kontrola pojmů bez tooltipu
./run-svejk.sh glossary-audit --obdobi 2025 --export-only
```

Podrobnosti polí v `facts/`, pravidla textů a další příkazy: **[processed/README.md](processed/README.md)**.

Redakční playbook (sync → facts → audit → publish): **[processed/WORKFLOW.md](processed/WORKFLOW.md)**.

Editorial pravidla (satira, terminologie, formát článků): [`.cursor/rules/steno-zapisy.mdc`](.cursor/rules/steno-zapisy.mdc).

## Užitečné příkazy

| Příkaz | Co dělá |
|--------|---------|
| `./run-svejk.sh build --schuze N --obdobi 2025` | Celá pipeline pro jednu schůzi |
| `./run-svejk.sh compose-changed --obdobi 2025` | Compose jen schůzí se změněnými daty (po syncu) |
| `./run-svejk.sh sync --obdobi 2025 --check-only` | Kontrola, zda jsou na PSP nová data |
| `./run-svejk.sh timeline --schuze 20 --den 26.5` | Náhled vydání v terminálu |
| `./run-svejk.sh export-pages --obdobi 2025 --out site` | Statický web do `site/` |
| `./run-svejk.sh review --schuze 20 --audit` | Slabá témata bez dostatečné glosy |

Úplný seznam: `./run-svejk.sh --help`.

## CI a automatizace

| Workflow | Kdy | Účel |
|----------|-----|------|
| `pages.yml` | push na `main`, cron | Build + deploy GitHub Pages |
| `sync.yml` | cron, ručně | Stažení nových dat z Hlídače, commit do repa |
| `data-check.yml` | cron | Upozornění, že na PSP jsou data ještě nesyncnutá |
| `subscribe-worker.yml` | push | Deploy Cloudflare workeru pro odběr |
| `doi-sync.yml` | ručně | Šablona double opt-in e-mailu v Ecomailu |

Push na `main` s hotovými `facts/` typicky jen exportuje web (~1 min). Stahování sten z Hlídače běží v cronu nebo ručně přes `workflow_dispatch`.

## Kam dál

- **Redakce a facts** → [processed/README.md](processed/README.md)
- **Styl a pravidla psaní** → [.cursor/rules/steno-zapisy.mdc](.cursor/rules/steno-zapisy.mdc)
