# Cloudflare Worker: odběr + korektury

Projekt `poslusnehlasim-odebir` na Cloudflare Pages.

| Endpoint | Metoda | Služba |
|----------|--------|--------|
| `/` | POST | Odběr novinek → Ecomail (zápis) + Resend (potvrzovací mail) |
| `/confirm` | GET | Potvrzení odběru (token z mailu) → Ecomail status 1 → redirect na web |
| `/corrections` | POST | Návrh korektury → Resend |

## Jak funguje double opt-in

1. Formulář na webu pošle e-mail na worker (`POST /`).
2. Worker zapíše kontakt do Ecomailu jako **nepotvrzený** (`status: 6`, `skip_confirmation: true`).
3. Worker načte HTML šablonu z Ecomailu (`conf_message` seznamu), nahradí `*|SUBCONFIRM|*` vlastním odkazem a pošle mail přes **Resend**.
4. Uživatel klikne na odkaz (`GET /confirm?token=…`).
5. Worker potvrdí odběr v Ecomailu (`status: 1`) a přesměruje na `/potvrzeno/`.

Šablona mailu se synchronizuje do Ecomailu příkazem `./run-svejk.sh newsletter-doi-sync --apply` (worker ji odtud čte).

## Secrets (Cloudflare Pages)

```bash
cd workers
npx wrangler pages secret put ECOMAIL_API_KEY --project-name=poslusnehlasim-odebir
npx wrangler pages secret put ECOMAIL_FROM_EMAIL --project-name=poslusnehlasim-odebir
npx wrangler pages secret put RESEND_API_KEY --project-name=poslusnehlasim-odebir
# volitelně, když má korektury jiný inbox než NOTIFY_EMAIL:
npx wrangler pages secret put CORRECTIONS_NOTIFY_EMAIL --project-name=poslusnehlasim-odebir
```

`RESEND_API_KEY` je **povinný** pro odběr novinek (potvrzovací mail).

V GitHub Actions: stejné názvy v **Repository secrets** (`RESEND_API_KEY` atd.).

## Resend: ověření domény

1. Účet na [resend.com](https://resend.com), API klíč s oprávněním **Sending access**.
2. **Domains → Add domain** → `poslusnehlasim.cz`.
3. V DNS (Cloudflare) přidej záznamy, které Resend ukáže (typicky SPF, DKIM, volitelně DMARC).
4. Po ověření nastav odesílatele, např. `svejk@poslusnehlasim.cz` (secret `ECOMAIL_FROM_EMAIL` nebo `RESEND_FROM_EMAIL`).

Korektury chodí na `CORRECTIONS_NOTIFY_EMAIL`, jinak na `NOTIFY_EMAIL`, jinak na `ECOMAIL_FROM_EMAIL`.

## Deploy

```bash
CLOUDFLARE_API_TOKEN=… CLOUDFLARE_ACCOUNT_ID=… \
ECOMAIL_API_KEY=… ECOMAIL_FROM_EMAIL=svejk@poslusnehlasim.cz \
RESEND_API_KEY=re_… \
./scripts/deploy-subscribe-worker.sh
```

URL workeru ulož do GitHub secret `SVEJK_SUBSCRIBE_API_URL` (např. `https://poslusnehlasim-odebir.pages.dev`).

## Test odběru

```bash
curl -sS -X POST "https://poslusnehlasim-odebir.pages.dev/" \
  -H "Content-Type: application/json" \
  -H "Origin: https://poslusnehlasim.cz" \
  -d '{"email":"tvuj@email.cz"}'
```

Očekávaná odpověď: `{"ok":true}`. Potvrzovací mail přijde z Resendu (ne z Ecomailu).

## Test korektury

```bash
curl -sS -X POST "https://poslusnehlasim-odebir.pages.dev/corrections" \
  -H "Content-Type: application/json" \
  -H "Origin: https://poslusnehlasim.cz" \
  -d '{
    "suggestion": "Testovací návrh korektury z curl.",
    "topic_slug": "test",
    "page_url": "https://poslusnehlasim.cz/noviny/2025/",
    "kind": "typo"
  }'
```

Očekávaná odpověď: `{"ok":true}`.
