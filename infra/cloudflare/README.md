# Bezpečnostní hlavičky (Cloudflare + GitHub Pages)

GitHub Pages na běžných stránkách neposílá HSTS, CSP ani `X-Frame-Options`. GitHubův vlastní 404 ano — proto sken vypadá, že web je „napůl zabezpečený“.

Řešení: **doménu přes Cloudflare proxy** (oranžový mráček) a hlavičky doplnit u edge.

## 1. DNS přes Cloudflare

1. Přidej zónu `poslusnehlasim.cz` do Cloudflare (Free stačí).
2. U registrátora přepni nameservery na Cloudflare.
3. V **DNS** nastav záznamy na GitHub Pages a zapni **Proxied** (oranžový mráček):

| Typ | Jméno | Hodnota |
|-----|-------|---------|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `marketajedlick.github.io` |

4. **SSL/TLS → Overview:** režim **Full (strict)** (GitHub má platný certifikát).
5. V GitHubu **Settings → Pages → Custom domain** nech `poslusnehlasim.cz` — ověření projde i přes proxy.

## 2. HSTS (doporučeno mimo Transform Rules)

**SSL/TLS → Edge Certificates → HTTP Strict Transport Security (HSTS):**

- Enable HSTS
- Max Age: 12 months
- Include subdomains: ano
- Preload: ano (až po ověření, že vše běží přes HTTPS)

## 3. Ostatní hlavičky — Transform Rule

**Rules → Transform Rules → Modify response header → Create rule**

| Pole | Hodnota |
|------|---------|
| Rule name | `Security headers` |
| When | `Hostname equals poslusnehlasim.cz` **OR** `Hostname equals www.poslusnehlasim.cz` |
| Then | **Set static** — pro každou hlavičku z [`headers.txt`](headers.txt) (bez řádků s `#`) |

Postup v UI: u každého řádku `Název: hodnota` přidej akci **Set static** → Header name / Value.

HSTS můžeš vynechat, pokud ho máš z kroku 2 (neduplikovat).

### CSP a web

Politika v `headers.txt` počítá s tím, co web reálně používá:

- inline skripty (listování stránek, cookies, odběr) → `'unsafe-inline'`
- Google Analytics po souhlasu → `googletagmanager.com`, `google-analytics.com`
- odběr → `poslusnehlasim-odebir.pages.dev`, `*.ecomailapp.cz`
- Stripe jen jako odkaz (žádný iframe) → není v `frame-src`

Nejdřív můžeš nasadit **Report-Only** variantu: v Transform Rule použij hlavičku `Content-Security-Policy-Report-Only` se stejnou hodnotou, sleduj konzoli prohlížeče, pak přepni na `Content-Security-Policy`.

## 4. Alternativa: `_headers` (jen Cloudflare Pages)

Soubor [`_headers`](_headers) platí **jen** když hlavní web hostuješ na **Cloudflare Pages**, ne na GitHub Pages. U GH Pages se `_headers` neaplikuje (zůstane jen jako soubor v repu).

## 5. Ověření

```bash
./scripts/check-security-headers.sh
# nebo konkrétní URL:
./scripts/check-security-headers.sh https://poslusnehlasim.cz/noviny/2025/
```

Očekávané hlavičky po nasazení: `strict-transport-security`, `content-security-policy`, `x-frame-options`, `x-content-type-options`, `referrer-policy`.

Skript akceptuje i `Content-Security-Policy-Report-Only` (varování, ne chyba). Po ověření v prohlížeči přepni na vynucující `Content-Security-Policy`.

## 6. security.txt

Export webu generuje `/.well-known/security.txt` (kontakt pro reporty zranitelností). Ověření:

```bash
curl -sS https://poslusnehlasim.cz/.well-known/security.txt
```

## 7. API odběru

Worker `poslusnehlasim-odebir.pages.dev` běží zvlášť na Cloudflare Pages — hlavičky z této zóny se na něj nevztahují. CORS řeší `ALLOWED_ORIGIN` ve [`workers/wrangler.toml`](../../workers/wrangler.toml). Worker sám posílá `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` a restriktivní CSP u JSON odpovědí.
