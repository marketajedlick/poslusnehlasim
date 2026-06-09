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

### E-mail při nových datech z PSP (pro tebe)

Dva workflow ti pošlou **GitHub notifikaci** (selhání jobu), pokud máš u repa zapnuté watch / e-mail u Actions:

| Workflow | Kdy | Co znamená selhání |
|----------|-----|-------------------|
| **Check new PSP data** (`data-check.yml`) | denně 05:30 a 21:30 CET (před sync) | Na PSP / Hlídači jsou nová data, která ještě nejsou lokálně |
| **Sync PSP data** (`sync.yml`) | po stažení a commitu | Sync právě stáhl nová data do repa — je třeba doplnit `facts` a `compose` |

Lokální kontrola bez zápisu:

```bash
HLIDAC_TOKEN=… ./run-svejk.sh sync --obdobi 2025 --check-only --fail-if-pending
```

V **GitHub → Settings → Notifications** zapni e-maily u „Actions“ a u tohoto repozitáře „Watch → All activity“ (nebo aspoň failures).

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

**E-maily odběratelů nejsou v gitu.** Ukládá je [Ecomail](https://ecomail.cz) (double opt-in, GDPR). Web má jen formulář a RSS.

### Jednorázové nastavení

1. Založ účet na Ecomailu a vytvoř seznam kontaktů pro odběr.
2. V Ecomailu: **Kontakty → (tvůj seznam) → Formuláře** — URL pro vlastní HTML formulář je už v kódu.
3. V GitHub **Settings → Secrets → Actions** přidej:
   - `ECOMAIL_API_KEY` — z Ecomail → Nastavení → Integrace → API (jen CI + worker, nikdy do kódu)
   - `ECOMAIL_FROM_EMAIL` — ověřená odesílací adresa pro kampaně z CI
   - `CLOUDFLARE_API_TOKEN` a `CLOUDFLARE_ACCOUNT_ID` — pro worker odběru (doporučeno, nové e-maily bez robotchecku)
   - `SVEJK_SUBSCRIBE_API_URL` — volitelně ručně, jinak ho CI doplní z `wrangler deploy`
4. Po dalším deployi se na konci každého vydání zobrazí blok **Odběr novinek**.

### Odběr z webu (Cloudflare Pages API)

Veřejný Ecomail formulář vyžaduje robotcheck — skryté odeslání kontakt neuloží. Proto odběr jde přes **Ecomail API** na Cloudflare Pages (`workers/subscribe.js`):

```bash
cd workers
cp subscribe.js public/_worker.js
npx wrangler@4 login
npx wrangler pages secret put ECOMAIL_API_KEY --project-name=poslusnehlasim-odebir
npx wrangler pages deploy public --project-name=poslusnehlasim-odebir --branch=main
```

(Pozor: `pip install wrangler` v conda je jiný balíček — vždy `npx wrangler@4`.)

Produkční URL: **`https://poslusnehlasim-odebir.pages.dev`** (volitelně v GitHub Secret `SVEJK_SUBSCRIBE_API_URL`).

> **Proč ne workers.dev?** Na některých účtech je Production URL zapnutá, ale HTTPS certifikát pro `*.workers.dev` nefunguje (curl: SSL handshake failure), zatímco HTTP ano. Pages má spolehlivé HTTPS — proto používáme `*.pages.dev`.

Ověření:

```bash
curl -I https://poslusnehlasim-odebir.pages.dev
# → HTTP/2 405 (ne SSL chyba)
```

CI nasazuje Pages projekt `poslusnehlasim-odebir` automaticky.

Bez workeru funguje režim **`custom`** (vlastní formulář + Ecomail XHR). Výchozí je **`custom`** — oranžový formulář ve stylu webu (XHR bez preflight, funguje v prohlížeči). **`widget`** = embed snippet z Ecomailu.

```bash
# výchozí: Ecomail widget (design z editoru v Ecomailu)
SVEJK_SUBSCRIBE_MODE=widget

# vlastní oranžový formulář ve stylu webu
SVEJK_SUBSCRIBE_MODE=custom
```

Cloudflare worker je volitelný (`SVEJK_SUBSCRIBE_MODE=worker` + secret `SVEJK_SUBSCRIBE_API_URL`).

**Double opt-in:** nový kontakt může být v Ecomailu nejdřív v sekci **Nepotvrzení** — musí kliknout na potvrzovací e-mail.

### Nastavení double opt-in a welcome v Ecomailu

Po deployi webu je k dispozici děkovná stránka **`https://poslusnehlasim.cz/potvrzeno/`** (exportuje se jako `potvrzeno/index.html`).

1. **Seznam kontaktů → Nastavení seznamu**
   - Zapni **Registrace s potvrzením e-mailu (double opt-in)**
   - Odesílatel: ověřená doména (`ECOMAIL_FROM_EMAIL`)
   - Šablona potvrzení musí obsahovat merge tag **`*|SUBCONFIRM|*`**
   - URL po potvrzení: **`https://poslusnehlasim.cz/potvrzeno/`**

2. **Potvrzovací e-mail** — šablona ve stejném stylu jako newsletter:

```bash
./run-svejk.sh newsletter-doi-template -o site/email
# nebo při každém deployi automaticky: site/email/doi.html
```

V Ecomailu: **Šablony → nová šablona** → vlož obsah `doi.html`. Merge tag **`*|SUBCONFIRM|*`** musí zůstat na tlačítku. Předmět: `Poslušně hlásím — potvrď odběr novinek`.

3. **Welcome automatizace** (po potvrzení DOI)
   - Automatizace → trigger **Přihlásí se do seznamu**
   - Frekvence: **pouze jednou** (doporučeno)
   - Worker už posílá `trigger_autoresponders: true` — automatizace se spustí sama
   - Otestuj na vlastním e-mailu v záložce Testování

4. **Kontrola cesty:** formulář → potvrzovací mail → klik → `/potvrzeno/` → welcome mail → kontakt v **Potvrzení** (ne Nepotvrzení)

5. **Success text na webu** — po nasazení DOI uprav v `subscribe.html` zprávu na „zkontroluj e-mail a potvrď odběr“ (zatím zůstává „e-mail je zapsán“).

### Jak lidé dostanou e-mail

**Varianta A (doporučená): automatizace v Ecomailu**

Nastav uvítací sérii nebo automatizaci na nové kontakty ze seznamu. Případně RSS trigger, pokud ho v Ecomailu používáš.

**Varianta B: CI po deployi**

Workflow po `export-pages` spustí `newsletter-notify`, pokud je `ECOMAIL_API_KEY`. Stav posledního odeslání je v `processed/newsletter-state.json` (jen ID vydání, žádné e-maily).

```bash
# náhled bez odeslání
ECOMAIL_API_KEY=… ECOMAIL_LIST_ID=… ECOMAIL_FROM_EMAIL=… \
  ./run-svejk.sh newsletter-notify --obdobi 2025 --dry-run

# vynutit znovu (test)
./run-svejk.sh newsletter-notify --obdobi 2025 --force
```

Lokální export s formulářem:

```bash
export ECOMAIL_FORM_ACTION='https://tvujucet.ecomailapp.cz/public/subscribe/…'
export SVEJK_SITE_URL=https://poslusnehlasim.cz
./run-svejk.sh export-pages --obdobi 2025 --out site
```
