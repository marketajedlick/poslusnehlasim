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
3. Po prvním úspěšném workflow uvidíš URL typu `https://marketajedlick.github.io/poslusnehlasim/`; s vlastní doménou pak `https://poslusnehlasim.cz`.

## Doména poslusnehlasim.cz

Workflow při exportu vytvoří `site/CNAME` s obsahem `poslusnehlasim.cz`. U registrátora domény nastav **jednu** z variant (podle toho, co podporuješ):

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
