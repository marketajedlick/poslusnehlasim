# SPEC — SEO redesign poslusnehlasim.cz

**Verze:** 1.3 · 10. 7. 2026  
**Cíl:** Web se má zobrazovat ve výsledcích Googlu na dotazy o dění ve sněmovně (dnes je neviditelný — dotaz „poslušně hlásím" ovládá film z roku 1957 a web nemá stránky, které by cílily na jiné dotazy).  
**Strategie:** Neválčit o brand keyword s filmem. Vybudovat entitu „Poslušně hlásím = deník Poslanecké sněmovny" a rankovat na long-tail dotazy (poslanci, zákony, pojmy, „co se dělo ve sněmovně").

**Stav implementace (10. 7. 2026):** Detailní plán a checklist v [`seo-redesign-plan.md`](seo-redesign-plan.md).

| Oblast | Stav |
|---|---|
| Title/meta, JSON-LD, archiv textový seznam | ✅ Fáze 0 (9. 7. 2026) |
| Nové URL `/vydani/{ISO}/`, `/archiv/`, meta-refresh ze starých cest | ✅ Fáze 1.1 (10. 7. 2026) |
| Homepage stabilní landing (H1/H2, úvod, „Z archivu") | ✅ Fáze 1.2 (10. 7. 2026) |
| HTTP 301 redirecty | ⏳ zatím meta-refresh (rozhodnutí); Cloudflare později |
| Breadcrumbs | ✅ Fáze 1.3 (10. 7. 2026) |
| Prev/next vydání (pager + patička) | ✅ Fáze 1.4 (10. 7. 2026) |
| Slovníček per-pojem (`/slovnicek/{slug}/`) | ✅ Fáze 1.5 (10. 7. 2026) |
| Article anchory (`#slug` deep-linky) | ✅ Fáze 1.6 (10. 7. 2026) |
| `/poslanec/`, `/tema/`, interní prolinkování poslanců/témat | ⏳ Fáze 2 |
| GSC, sitemap odeslání, Rich Results Test | ⏳ Markéta, po deployi |

Položky označené ⚠️ OVĚŘIT vycházejí z externí analýzy webu — u hotových částí jsou potvrzeny v kódu (viz plán).

---

## 1. Cílové dotazy (proč to celé děláme)

| Skupina dotazů | Příklad | Cílová stránka |
|---|---|---|
| Denní přehled | „co se dělo ve sněmovně", „sněmovna dnes" | Homepage / dnešní vydání |
| Poslanec + téma | „babiš interpelace", „richterová bydlení" | `/poslanec/{slug}/` |
| Zákon / téma | „zákon o obalech novela", „korespondenční volba hlasování" | `/tema/{slug}/` |
| Vysvětlení pojmu | „co je interpelace", „co je sněmovní tisk" | `/slovnicek/{slug}/` ✅ |
| Brand | „poslušně hlásím sněmovna" | Homepage (dlouhodobě) |

---

## 2. Cílová struktura webu

```
Homepage (/)                          ← stabilní landing ✅ (1.2), bez breadcrumbs
├── Dnešní vydání (/vydani/2026-07-08/)   ✅ (1.1)
├── Archiv (/archiv/)                   ✅ (1.1) + breadcrumbs (1.3)
│   └── Vydání (/vydani/{YYYY-MM-DD}/)  ✅ + breadcrumbs (1.3)
│       ├── Stenoreport (/vydani/…/steno/)        ✅ + breadcrumbs (1.3)
│       ├── Smlouvy, řečníci, vyznamenání         ✅ + breadcrumbs (1.3)
│       └── Články (#topic-slug)                  ✅ (1.6)
├── Poslanci (/poslanci/)               ⏳ Fáze 2
│   └── Detail (/poslanec/{slug}/)
├── Témata (/temata/)                   ⏳ Fáze 2
│   └── Detail (/tema/{slug}/)
├── Slovníček (/slovnicek/)             ✅ index (1.1) + breadcrumbs (1.3)
│   └── Pojem (/slovnicek/{slug}/)      ✅ (1.5) + breadcrumbs
├── O webu (/o-webu/)
├── Podpora (/podpora/)
└── Pivo (/pivo/)
```

Pravidla URL:
- lowercase, pomlčky, bez diakritiky, bez `.html`, konzistentní trailing slash ✅
- žádné tečky v názvech souborů ✅ (staré `02.07.2026.html` přesměrovány meta-refreshem)
- datum ve formátu ISO `YYYY-MM-DD` ✅

---

## 3. Redirect tabulka (301)

Všechny existující URL musí vést na nové. **Implementováno (1.1):** meta-refresh stuby ze starých cest při exportu ([`export_pages.py`](../svejk/build/export_pages.py)). HTTP 301 zatím ne (rozhodnutí), doplnit přes Cloudflare Bulk Redirect Rules.

| Stará URL | Nová URL | Stav |
|---|---|---|
| `/noviny/{rok}/{schuze}/{DD.MM.YYYY}.html` | `/vydani/{YYYY-MM-DD}/` | ✅ meta-refresh |
| `/noviny/{rok}/{schuze}/{DD.MM.YYYY}-steno.html` | `/vydani/{YYYY-MM-DD}/steno/` | ✅ meta-refresh |
| `/archiv.html` | `/archiv/` | ✅ meta-refresh |
| `/slovnicek.html` | `/slovnicek/` | ✅ meta-refresh |
| `/o-webu.html` | `/o-webu/` | ✅ meta-refresh |

Po nasazení projít Search Console → Pages a zkontrolovat, že staré URL hlásí „Page with redirect" (u meta-refresh může trvat déle než u 301).

---

## 4. Homepage (/)

**Dříve:** homepage = dnešní vydání, obsah se denně přepisuje, stejný text žije i na datované URL → duplicita a nestabilní relevance.

**Implementováno (1.2, 10. 7. 2026):**
- **H1 (stabilní):** `Poslušně hlásím, satirický deník Poslanecké sněmovny` ([`homepage-landing.html`](../svejk/templates/homepage-landing.html))
- Pod H1 úvodní odstavec s klíčovými slovy (Poslanecká sněmovna, hlasování, poslanci, každý jednací den)
- Plný obsah dnešního vydání na `/`; titulek dne je **H2**; canonical homepage na sebe (`https://poslusnehlasim.cz/`)
- Sekce **„Z archivu"** — 5 předchozích vydání jako textové odkazy ([`homepage-archive.html`](../svejk/templates/homepage-archive.html))
- Masthead „Poslušně hlásím!" je dekorace (`<p>`), ne H1

**Zbývá:** odkazy na `/poslanci/`, `/temata/` v hlavní navigaci (až Fáze 2).

**Title:** `Poslušně hlásím, denní zpravodaj z Poslanecké sněmovny` ✅  
**Meta description:** viz níže ✅

---

## 5. Stránka vydání (/vydani/{YYYY-MM-DD}/)

**Implementováno (1.1–1.4, 1.6):**
- **H1:** `{Titulek dne}` ([`edition-day-headline.html`](../svejk/templates/edition-day-headline.html))
- Pod H1 řádek: `Poslanecká sněmovna, {den} {D. M. YYYY} · {n}. schůze` s `<time datetime="YYYY-MM-DD">` ✅
- **Breadcrumbs:** `Poslušně hlásím › Archiv vydání › 8. 7. 2026` + BreadcrumbList JSON-LD ✅ (1.3)
- **Title** a **meta description** dle šablon níže ✅
- **Patička vydání prev/next** — pager v hlavičce i patičce (`← 1. 7. | 3. 7. →`), kanonické `/vydani/` URL ✅ (1.4)
- **Article anchory:** každý článek má `id` = slug tématu (`#novela-z-o-obalech`), citace `#slug-citace` ✅ (1.6)
- **JSON-LD `hasPart`:** fragment URL na každý článek ✅ (1.6)

**Zbývá:**
- Jména poslanců / témata jako interní odkazy na entity stránky — Fáze 2
- Pojmy slovníčku v textu → odkazy na `/slovnicek/{slug}/` ✅ (1.5)

**Title šablona:** `Sněmovna {D. M. YYYY}: {Titulek dne} | Poslušně hlásím` ✅  
**Meta description šablona:** `{Perex dne}. Denní přehled z Poslanecké sněmovny, {D. M. YYYY}.` ✅

**Příklad deep-linku:** `https://poslusnehlasim.cz/vydani/2026-07-02/#novela-z-o-obalech`

---

## 6. Entitní stránky (fáze 2 — hlavní zdroj budoucího trafficu)

### /poslanec/{slug}/
Generovat automaticky z dat vydání (řečníci jsou tagovaní ⚠️ OVĚŘIT formát dat). Obsah stránky:
1. H1: `{Jméno Příjmení} ({strana}) v Poslušně hlásím`
2. Krátký strojový úvod: kolikrát zmíněn, v kolika vydáních, poslední zmínka.
3. Chronologický seznam zmínek: datum → titulek článku → 1–2 věty kontextu → odkaz na `/vydani/{date}/#{anchor_id}` (anchor z 1.6).
4. Interní odkazy na související témata.

**Title:** `{Jméno Příjmení} — vystoupení a hlasování ve sněmovně | Poslušně hlásím`

Publikovat stránku jen pokud má poslanec ≥ 3 zmínky (thin content by uškodil). Ostatní nechat bez stránky, jméno v textu bez odkazu.

### /tema/{slug}/
Stejný princip pro zákony a kauzy (zákon o obalech, korespondenční volba, Rada ČT…). Témata kurátorovat ručně nebo poloautomaticky — začít 10–20 nejsilnějšími.

**Title:** `{Název tématu} ve sněmovně — vývoj a hlasování | Poslušně hlásím`

### Index stránky /poslanci/ a /temata/
Abecední/řazený seznam s počtem zmínek. Zajišťují, že žádná entitní stránka není orphan.

---

## 7. Slovníček (/slovnicek/ + /slovnicek/{slug}/)

**Implementováno (1.1, 1.3, 1.5):**
- Index na `/slovnicek/` ✅, FAQPage JSON-LD na indexu ✅ (0.2), breadcrumbs ✅ (1.3)
- Samostatná stránka pro každý pojem ze `SLOVNIČEK`: `/slovnicek/{slug}/` ✅
- Šablona [`slovnicek-pojem.html`](../svejk/templates/slovnicek-pojem.html): H1 `Co je {pojem}?` → definice → „Kde se o tom psalo" (index zmínek z vydání)
- DefinedTerm + FAQPage JSON-LD na stránce pojmu (`slovnicek_term_json_ld()`)
- Index [`slovnicek-stranka.html`](../svejk/templates/slovnicek-stranka.html): odkazy na per-pojem URL (ne kotvy)
- Pojmy v textech vydání → `<a href="/slovnicek/{slug}/">` ([`glossary_markup.py`](../svejk/build/glossary_markup.py)); modal jako JS enhancement

**Title (nasazeno):** `Co je {pojem}? Švejkov slovníček | Poslušně hlásím`  
*(Spec původně „Sněmovní slovníček" — v kódu značka Švejkův slovníček.)*

---

## 8. Interní prolinkování — pravidla pro generátor

1. První výskyt jména poslance v článku → odkaz na `/poslanec/{slug}/` (pokud stránka existuje). ⏳ Fáze 2
2. První výskyt sledovaného tématu → odkaz na `/tema/{slug}/`. ⏳ Fáze 2
3. Pojmy ze slovníčku → `<a href="/slovnicek/{slug}/">` (modal jako JS enhancement nad odkazem). ✅ *1.5*
4. Žádná stránka bez alespoň jednoho příchozího interního odkazu (orphan check v buildu). ⏳ Fáze 2
5. Anchor texty popisné — jméno/pojem, nikdy „zde" / „více".
6. Breadcrumbs na všech podstránkách: `Poslušně hlásím › Archiv › 8. 7. 2026` (+ BreadcrumbList schema). ✅ *1.3*
7. Deep-link na článek ve vydání: `/vydani/{ISO}/#{topic-slug}`. ✅ *1.6*

---

## 9. Strukturovaná data (JSON-LD, do `<head>`)

Validovat v https://search.google.com/test/rich-results před nasazením.

**Stav:** Organization + WebSite na homepage ✅, NewsArticle na vydáních ✅ (0.2, `hasPart` s fragmenty ✅ 1.6). BreadcrumbList na podstránkách ✅ (1.3). DefinedTerm + FAQ na pojmech slovníčku ✅ (1.5).

### Homepage — Organization + WebSite (@graph)
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://poslusnehlasim.cz/#org",
      "name": "Poslušně hlásím",
      "url": "https://poslusnehlasim.cz/",
      "logo": "https://poslusnehlasim.cz/assets/logo.png",
      "description": "Satirický denní zpravodaj z jednání Poslanecké sněmovny Parlamentu ČR. Srozumitelné shrnutí rozprav a hlasování za každý jednací den.",
      "sameAs": []
    },
    {
      "@type": "WebSite",
      "@id": "https://poslusnehlasim.cz/#website",
      "name": "Poslušně hlásím — deník Poslanecké sněmovny",
      "url": "https://poslusnehlasim.cz/",
      "publisher": { "@id": "https://poslusnehlasim.cz/#org" },
      "inLanguage": "cs"
    }
  ]
}
```
Pole `sameAs` doplnit o sociální profily, jakmile existují (klíčové pro odlišení od filmu). `logo` v kódu: `/static/apple-touch-icon.png` (odchylka od spec `/assets/logo.png`).

### Stránka vydání — NewsArticle
```json
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "{Titulek dne}",
  "datePublished": "{YYYY-MM-DD}T{HH:MM}:00+02:00",
  "dateModified": "{YYYY-MM-DD}T{HH:MM}:00+02:00",
  "inLanguage": "cs",
  "image": ["{OG obrázek vydání}"],
  "author": { "@type": "Organization", "@id": "https://poslusnehlasim.cz/#org" },
  "publisher": { "@id": "https://poslusnehlasim.cz/#org" },
  "mainEntityOfPage": "https://poslusnehlasim.cz/vydani/{YYYY-MM-DD}/",
  "about": [
    { "@type": "Thing", "name": "Poslanecká sněmovna Parlamentu České republiky" }
  ],
  "hasPart": [
    {
      "@type": "NewsArticle",
      "headline": "{Nadpis článku}",
      "articleBody": "{Perex + mean}",
      "position": 1,
      "@id": "https://poslusnehlasim.cz/vydani/{YYYY-MM-DD}/#{topic-slug}",
      "url": "https://poslusnehlasim.cz/vydani/{YYYY-MM-DD}/#{topic-slug}"
    }
  ]
}
```

### Pojem slovníčku — DefinedTerm + FAQPage ✅ (1.5)
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "DefinedTerm",
      "name": "{Pojem}",
      "description": "{Definice, první odstavec stránky}",
      "inDefinedTermSet": {
        "@type": "DefinedTermSet",
        "name": "Švejkov slovníček",
        "url": "https://poslusnehlasim.cz/slovnicek/"
      }
    },
    {
      "@type": "FAQPage",
      "mainEntity": [{
        "@type": "Question",
        "name": "Co je {pojem}?",
        "acceptedAnswer": { "@type": "Answer", "text": "{Definice}" }
      }]
    }
  ]
}
```

### Všechny podstránky — BreadcrumbList ✅ (1.3, 1.5)

Implementováno v [`breadcrumbs.html`](../svejk/templates/breadcrumbs.html) a `breadcrumb_json_ld()` v [`seo.py`](../svejk/build/seo.py). Vzor:
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Poslušně hlásím", "item": "https://poslusnehlasim.cz/" },
    { "@type": "ListItem", "position": 2, "name": "Archiv", "item": "https://poslusnehlasim.cz/archiv/" },
    { "@type": "ListItem", "position": 3, "name": "{Titulek dne}" }
  ]
}
```

Schema musí odpovídat viditelnému obsahu stránky — nemarkupovat nic, co na stránce není.

---

## 10. Archiv (/archiv/)

- Zachovat kalendář jako UI, ale **pod něj doplnit chronologický textový seznam**: `8. 7. 2026, Titulek na počkání` (odkaz na vydání). **Hotovo** — sekce „Všechna vydání" na `/archiv/` (Fáze 0.3); kanonická URL `/archiv/` od 1.1; breadcrumbs od 1.3.
- Při > ~100 vydáních stránkovat po měsících: `/archiv/2026-07/`.

---

## 11. Technické požadavky

| Položka | Požadavek | Stav |
|---|---|---|
| `sitemap.xml` | Generovat v buildu: homepage, všechna vydání, slovníček (index + pojmy), statické stránky | ✅ (1.1 + 1.5); entity až Fáze 2 |
| `robots.txt` | Povolit vše relevantní, `Sitemap:` řádek | ✅ |
| Canonical | Každá stránka self-canonical, absolutní URL, https, trailing slash | ✅ |
| 301 | Kompletní mapa dle §3 | ⏳ meta-refresh (1.1); HTTP 301 později |
| `llms.txt` | Krátký soubor v rootu | ✅ |
| OG/Twitter | Per-page og:title, og:description, og:image | ✅ na vydáních a homepage |
| `<html lang="cs">` | Zkontrolovat | ✅ |
| Výkon | Server-side render, žádný content za JS | ✅ |
| Datum v HTML | `<time datetime="2026-07-08">` u vydání | ✅ (1.2) |
| Breadcrumbs | UI + BreadcrumbList JSON-LD na podstránkách | ✅ (1.3, 1.5) |
| Article fragmenty | Stabilní `#slug` anchory + `hasPart` URL | ✅ (1.6) |

---

## 12. Search Console — checklist po nasazení

1. Ověřit vlastnictví (DNS TXT), pokud ještě není.
2. Odeslat sitemap.xml.
3. URL Inspection → Request indexing pro homepage, /o-webu/, /slovnicek/, 2–3 pojmy slovníčku (např. `/slovnicek/obstrukce/`), 3 poslední vydání.
4. Po 2 týdnech zkontrolovat Pages report: indexed vs. crawled-not-indexed; staré URL = „Page with redirect".
5. Sledovat Performance na dotazy obsahující „sněmovna" — baseline pro měření redesignu.
6. Rich Results Test: DefinedTerm/FAQ na stránce pojmu, NewsArticle `hasPart` na vydání.

---

## 13. Fáze a akceptační kritéria

### Fáze 0 — bez redesignu (~dny)
- [ ] GSC ověřeno, sitemap odeslána *(Markéta, po deployi)*
- [x] Title/description šablony dle §4–5 — *9. 7. 2026*
- [x] JSON-LD Organization + WebSite na homepage, NewsArticle na vydáních — *9. 7. 2026*
- [x] Archiv doplněn o textový seznam s titulky — *9. 7. 2026*

### Fáze 1 — restrukturalizace — hotovo *10. 7. 2026*
- [x] Nové URL schéma — *1.1* (meta-refresh místo HTTP 301, viz rozhodnutí)
- [x] Homepage jako stabilní landing dle §4 — *1.2*
- [x] Breadcrumbs + BreadcrumbList — *1.3*
- [x] prev/next prolinkování vydání — *1.4*
- [x] Slovníček jako samostatné stránky — *1.5*
- [x] Article anchory (`DenItem.anchor_id`) pro deep-linky — *1.6*

### Fáze 2 — entitní stránky (~2–4 týdny)
- [ ] /poslanec/ generované z dat (práh ≥ 3 zmínky)
- [ ] /tema/ pro 10–20 kurátorovaných témat
- [ ] Interní linkování z textů vydání dle §8 (poslanci, témata)
- [ ] Orphan check v build pipeline

### Definice hotovo (celek)
- Rich Results Test bez chyb na všech typech stránek
- `site:poslusnehlasim.cz` v Googlu vrací homepage s novým title + podstránky
- Žádné 404 z původních URL (crawl přes Screaming Frog / sitecheck)

---

## 14. Mimo scope specifikace (ale nutné pro výsledek)

Off-page: zmínky a backlinky (LinkedIn, Hlídač státu / open-data komunita, novinářské newslettery) — bez externích signálů potrvá entitní odlišení od filmu Poslušně hlásím (1957) měsíce. Řeší Markéta, ne developer.
