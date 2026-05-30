# Nasazení poslusnehlasim.cz (GitHub Pages)

## Co je v gitu (minimum)

| Složka | Účel |
|--------|------|
| `svejk/`, `psp/`, `svejk.py`, `run-svejk.sh` | build + export statického webu |
| `processed/*/facts/`, `aligned/`, `raw/votes.jsonl` | hotová vydání novin (export-pages) |
| `hl-2025ps/hl2025s.unl`, `zmatecne.unl` | seznam schůzí / build z UNL |
| `.github/workflows/pages.yml` | CI build + deploy |

`site/` se negeneruje do gitu — vzniká v Actions. `raw/steno.jsonl` je lokálně velké → v `processed/.gitignore`.

## GitHub (jednorázově)

1. **Settings → Secrets → Actions:** `HLIDAC_TOKEN` (už máš) — cron stahuje nová stena a přegeneruje noviny.
2. **Settings → Pages → Build and deployment:** Source = **GitHub Actions** (ne „Deploy from branch“).
3. Mezitím web běží na `https://marketajedlick.github.io/poslusnehlasim/` (workflow má `SVEJK_BASE_PATH: /poslusnehlasim`).
4. Po zapnutí DNS na vlastní doménu v workflow změň `SVEJK_BASE_PATH` na `""` a `SVEJK_PAGES_CNAME` na `poslusnehlasim.cz`.

Push na `main` jen exportuje z `processed/facts` (~1 min). Stažení z Hlídače běží při **cron** nebo **workflow_dispatch**.

## Doména poslusnehlasim.cz

Po přepnutí DNS v workflow zapni `SVEJK_PAGES_CNAME: poslusnehlasim.cz` (soubor `site/CNAME`). U registrátora domény nastav **jednu** z variant (podle toho, co podporuješ):

### Varianta A — apex domény (`poslusnehlasim.cz`)

U většiny registrátorů (Wedos, Forpsi, …) **A záznamy** na GitHub Pages:

| Typ | Host | Hodnota |
|-----|------|---------|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |

Volitelně **AAAA** (IPv6): `2606:50c0:8000::153` … `::154` (viz [GitHub docs](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site#configuring-an-apex-domain)).

### Varianta B — jen www

| Typ | Host | Hodnota |
|-----|------|---------|
| CNAME | `www` | `marketajedlick.github.io` |

Pak v GitHub **Settings → Pages → Custom domain** zadej `www.poslusnehlasim.cz` a v exportu použij stejnou doménu (`SVEJK_PAGES_CNAME` / `--cname`).

### Po nastavení DNS

1. V repo **Settings → Pages → Custom domain:** `poslusnehlasim.cz` (pokud ještě není).
2. Zapni **Enforce HTTPS** (až DNS projde, obvykle do 24 h).
3. U apex domény může GitHub nabídnout i přesměrování `www` → apex — podle preference.

Lokální test exportu:

```bash
./run-svejk.sh export-pages --obdobi 2025 --out site
python3 -m http.server -d site 8765
```

## Newsletter (odběr + e-mail při novém vydání)

**E-maily odběratelů nejsou v gitu.** Ukládá je [Buttondown](https://buttondown.com) (double opt-in, GDPR). Web má jen formulář a RSS.

### Jednorázové nastavení

1. Založ účet na Buttondown, vyber username (např. `poslusnehlasim`).
2. V GitHub **Settings → Secrets → Actions** přidej:
   - `BUTTONDOWN_USERNAME` — stejný username (veřejný, jde do HTML formuláře)
   - `BUTTONDOWN_API_KEY` — z Buttondown → Settings → API (jen CI, nikdy do kódu)
3. Po dalším deployi se na konci každého vydání zobrazí blok **Odběr novinek**.

### Jak lidé dostanou e-mail

**Varianta A (doporučená): RSS automatizace**

1. Po exportu existuje `https://poslusnehlasim.cz/feed.xml`.
2. V Buttondown: **Automations → RSS-to-email** → URL feedu výše.
3. Při každém novém vydání na webu Buttondown pošle e-mail odběratelům (bez ruční práce).

**Varianta B: CI po deployi**

Workflow po `export-pages` spustí `newsletter-notify`, pokud je `BUTTONDOWN_API_KEY`. Stav posledního odeslání je v `processed/newsletter-state.json` (jen ID vydání, žádné e-maily).

```bash
# náhled bez odeslání
BUTTONDOWN_API_KEY=… ./run-svejk.sh newsletter-notify --obdobi 2025 --dry-run

# vynutit znovu (test)
./run-svejk.sh newsletter-notify --obdobi 2025 --force
```

Lokální export s formulářem:

```bash
export BUTTONDOWN_USERNAME=tvuj-username
export SVEJK_SITE_URL=https://poslusnehlasim.cz
./run-svejk.sh export-pages --obdobi 2025 --out site
```
