# SPEC — SEO redesign poslusnehlasim.cz

**Verze:** 1.0 · 8. 7. 2026
**Cíl:** Web se má zobrazovat ve výsledcích Googlu na dotazy o dění ve sněmovně (dnes je neviditelný — dotaz „poslušně hlásím" ovládá film z roku 1957 a web nemá stránky, které by cílily na jiné dotazy).
**Strategie:** Neválčit o brand keyword s filmem. Vybudovat entitu „Poslušně hlásím = deník Poslanecké sněmovny" a rankovat na long-tail dotazy (poslanci, zákony, pojmy, „co se dělo ve sněmovně").

Položky označené ⚠️ OVĚŘIT vycházejí z externí analýzy webu — developer nechť potvrdí proti skutečnému stavu kódu.

---

## 1. Cílové dotazy (proč to celé děláme)

| Skupina dotazů | Příklad | Cílová stránka |
|---|---|---|
| Denní přehled | „co se dělo ve sněmovně", „sněmovna dnes" | Homepage / dnešní vydání |
| Poslanec + téma | „babiš interpelace", „richterová bydlení" | `/poslanec/{slug}/` |
| Zákon / téma | „zákon o obalech novela", „korespondenční volba hlasování" | `/tema/{slug}/` |
| Vysvětlení pojmu | „co je interpelace", „co je sněmovní tisk" | `/slovnicek/{slug}/` |
| Brand | „poslušně hlásím sněmovna" | Homepage (dlouhodobě) |

---

## 2. Cílová struktura webu

```
Homepage (/)                          ← stabilní landing, ne měnící se článek
├── Dnešní vydání (/vydani/2026-07-08/)
├── Archiv (/archiv/)
│   └── Vydání (/vydani/{YYYY-MM-DD}/)
│       └── Stenoreport (/vydani/{YYYY-MM-DD}/steno/)   ⚠️ OVĚŘIT dnešní podobu -steno.html
├── Poslanci (/poslanci/)
│   └── Detail (/poslanec/{slug}/)            např. /poslanec/andrej-babis/
├── Témata (/temata/)
│   └── Detail (/tema/{slug}/)                např. /tema/zakon-o-obalech/
├── Slovníček (/slovnicek/)
│   └── Pojem (/slovnicek/{slug}/)            např. /slovnicek/interpelace/
├── O webu (/o-webu/)
├── Podpora (/podpora/)
└── Pivo (/pivo/)
```

Pravidla URL:
- lowercase, pomlčky, bez diakritiky, bez `.html`, konzistentní trailing slash (doporučuji s lomítkem, a druhá varianta 301)
- žádné tečky v názvech souborů (dnešní `02.07.2026.html` ⚠️ OVĚŘIT)
- datum ve formátu ISO `YYYY-MM-DD` — řadí se, je jednoznačné, čitelné pro crawler i člověka

---

## 3. Redirect tabulka (301)

Všechny existující URL musí dostat 301 na nové. Vzor (⚠️ OVĚŘIT skutečné staré URL proti access logu / sitemap):

| Stará URL | Nová URL |
|---|---|
| `/noviny/{rok}/{schuze}/{DD.MM.YYYY}.html` | `/vydani/{YYYY-MM-DD}/` |
| `/noviny/{rok}/{schuze}/{DD.MM.YYYY}-steno.html` | `/vydani/{YYYY-MM-DD}/steno/` |
| `/archiv.html` | `/archiv/` |
| `/slovnicek.html` | `/slovnicek/` |
| `/o-webu.html` | `/o-webu/` |

Implementace: redirect mapa na úrovni serveru (nginx map / Cloudflare rules / `_redirects`), ne JS redirect. Po nasazení projít Search Console → Pages a zkontrolovat, že staré URL hlásí „Page with redirect".

---

## 4. Homepage (/)

Dnes: homepage = dnešní vydání, obsah se denně přepisuje, stejný text žije i na datované URL → duplicita a nestabilní relevance.

Nově:
- **H1 (stabilní):** `Poslušně hlásím — satirický deník Poslanecké sněmovny`
- Pod H1 jedna dvě věty o tom, co web je (obsahují slova *Poslanecká sněmovna, hlasování, poslanci, každý jednací den*).
- Dále plný obsah **dnešního vydání** (může být identický s /vydani/…), ale `<link rel="canonical">` homepage ukazuje **na sebe** (`https://poslusnehlasim.cz/`) a datovaná URL má canonical na sebe. Aby nevznikla duplicita, homepage zobrazuje vydání *bez* jeho vlastní H1 — titulek dne je H2.
  - Alternativa (jednodušší a SEO-čistší): homepage zobrazuje jen perex + první článek vydání a tlačítko „Číst celé vydání" → /vydani/…. Rozhodnutí nechávám na UX, obě varianty jsou přijatelné; nepřijatelné je současné 1:1 zdvojení.
- Sekce „Z archivu" — 5 posledních vydání jako textové odkazy s titulky (interní linky s anchor textem).
- Odkazy na /poslanci/, /temata/, /slovnicek/ v hlavní navigaci.

**Title:** `Poslušně hlásím — denní zpravodaj z Poslanecké sněmovny`
**Meta description:** `Satirický deník z Poslanecké sněmovny. Každý jednací den srozumitelně: o čem poslanci hlasovali, co zaznělo v rozpravě a co to znamená. Bez stenoprotokolové mlhy.`

---

## 5. Stránka vydání (/vydani/{YYYY-MM-DD}/)

- **H1:** `{Titulek dne}` — např. `Titulek na počkání`
- Hned pod H1 řádek: `Poslanecká sněmovna, {den v týdnu} {D. M. YYYY} · {n}. schůze` — dostane keyword + datum do prvních 100 slov.
- Každý článek vydání = `<article>` s `<h2>` a stabilním `id` anchorem (`#rada-ct`, `#zakon-o-obalech`) — umožní deep-linkování z entitních stránek.
- Jména poslanců a názvy témat v textu = interní odkazy na `/poslanec/…` a `/tema/…` (viz §8). Pojmy = odkazy na `/slovnicek/…` (ne modal — modal ponechat jako progressive enhancement přes JS, ale v HTML musí být `<a href>`).
- Patička vydání: `← předchozí vydání | další vydání →` (chronologické prolinkování, crawler projde celý archiv bez sitemap).

**Title šablona:** `Sněmovna {D. M. YYYY}: {Titulek dne} | Poslušně hlásím`
**Meta description šablona:** `{Perex dne, max 150 znaků}. Denní přehled z Poslanecké sněmovny — {D. M. YYYY}.`

---

## 6. Entitní stránky (fáze 2 — hlavní zdroj budoucího trafficu)

### /poslanec/{slug}/
Generovat automaticky z dat vydání (řečníci jsou tagovaní ⚠️ OVĚŘIT formát dat). Obsah stránky:
1. H1: `{Jméno Příjmení} ({strana}) v Poslušně hlásím`
2. Krátký strojový úvod: kolikrát zmíněn, v kolika vydáních, poslední zmínka.
3. Chronologický seznam zmínek: datum → titulek článku → 1–2 věty kontextu → odkaz na `/vydani/{date}/#anchor`.
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

- Rozpadnout současnou jednu stránku na samostatné URL per pojem.
- Struktura pojmu: H1 `Co je {pojem}?` → definice v 1. odstavci (40–60 slov, přímá odpověď — featured snippet formát) → satirický dovětek → „Kde se o tom psalo" (odkazy na vydání).
- /slovnicek/ zůstává jako index se všemi pojmy a kotvami.
- FAQPage/DefinedTerm schema viz §9.

**Title:** `Co je {pojem}? Sněmovní slovníček | Poslušně hlásím`

---

## 8. Interní prolinkování — pravidla pro generátor

1. První výskyt jména poslance v článku → odkaz na `/poslanec/{slug}/` (pokud stránka existuje).
2. První výskyt sledovaného tématu → odkaz na `/tema/{slug}/`.
3. Pojmy ze slovníčku → `<a href="/slovnicek/{slug}/">` (modal jako JS enhancement nad odkazem).
4. Žádná stránka bez alespoň jednoho příchozího interního odkazu (orphan check v buildu).
5. Anchor texty popisné — jméno/pojem, nikdy „zde" / „více".
6. Breadcrumbs na všech podstránkách: `Poslušně hlásím › Archiv › 8. 7. 2026` (+ BreadcrumbList schema).

---

## 9. Strukturovaná data (JSON-LD, do `<head>`)

Validovat v https://search.google.com/test/rich-results před nasazením.

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
Pole `sameAs` doplnit o sociální profily, jakmile existují (klíčové pro odlišení od filmu). `logo` URL ⚠️ OVĚŘIT.

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
  ]
}
```

### Pojem slovníčku — DefinedTerm + FAQPage
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
        "name": "Sněmovní slovníček Poslušně hlásím",
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

### Všechny podstránky — BreadcrumbList
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

- Zachovat kalendář jako UI, ale **pod něj doplnit chronologický textový seznam**: `8. 7. 2026, Titulek na počkání` (odkaz na vydání). **Hotovo** — sekce „Všechna vydání" na `/archiv.html` (Fáze 0.3, 9. 7. 2026).
- Při > ~100 vydáních stránkovat po měsících: `/archiv/2026-07/`.

---

## 11. Technické požadavky

| Položka | Požadavek |
|---|---|
| `sitemap.xml` | Generovat v buildu: homepage, všechna vydání, entitní stránky, slovníček, statické stránky. `<lastmod>` reálné. Odkaz v robots.txt. |
| `robots.txt` | Povolit vše relevantní, `Sitemap:` řádek. Nezakazovat /vydani/. |
| Canonical | Každá stránka self-canonical, absolutní URL, https, jednotný trailing slash. |
| 301 | Kompletní mapa dle §3, bez řetězení redirectů. |
| `llms.txt` | Krátký soubor v rootu: co web je, struktura sekcí, odkaz na archiv a slovníček. Pomáhá AI crawlerům (AI Overview, Perplexity) web správně zařadit. |
| OG/Twitter | Per-page og:title, og:description, og:image (dnes existuje ⚠️ OVĚŘIT úplnost na podstránkách). |
| `<html lang="cs">` | Zkontrolovat. |
| Výkon | Server-side render zachovat (funguje). Žádný content za JS. |
| Datum v HTML | `<time datetime="2026-07-08">` u vydání. |

---

## 12. Search Console — checklist po nasazení

1. Ověřit vlastnictví (DNS TXT), pokud ještě není.
2. Odeslat sitemap.xml.
3. URL Inspection → Request indexing pro homepage, /o-webu/, /slovnicek/, 3 poslední vydání.
4. Po 2 týdnech zkontrolovat Pages report: indexed vs. crawled-not-indexed; staré URL = „Page with redirect".
5. Sledovat Performance na dotazy obsahující „sněmovna" — baseline pro měření redesignu.

---

## 13. Fáze a akceptační kritéria

### Fáze 0 — bez redesignu (nasadit hned, ~dny)
- [ ] GSC ověřeno, sitemap odeslána *(Markéta, po deployi)*
- [x] Title/description šablony dle §4–5 (na stávajících URL) — *9. 7. 2026*
- [x] JSON-LD Organization + WebSite na homepage, NewsArticle na vydáních — *9. 7. 2026*
- [x] Archiv doplněn o textový seznam s titulky — *9. 7. 2026*

### Fáze 1 — restrukturalizace (~1–2 týdny)
- [ ] Nové URL schéma + kompletní 301 mapa
- [ ] Homepage jako stabilní landing dle §4
- [ ] Breadcrumbs + BreadcrumbList
- [ ] prev/next prolinkování vydání
- [ ] Slovníček jako samostatné stránky

### Fáze 2 — entitní stránky (~2–4 týdny)
- [ ] /poslanec/ generované z dat (práh ≥ 3 zmínky)
- [ ] /tema/ pro 10–20 kurátorovaných témat
- [ ] Interní linkování z textů vydání dle §8
- [ ] Orphan check v build pipeline

### Definice hotovo (celek)
- Rich Results Test bez chyb na všech typech stránek
- `site:poslusnehlasim.cz` v Googlu vrací homepage s novým title + podstránky
- Žádné 404 z původních URL (crawl přes Screaming Frog / sitecheck)

---

## 14. Mimo scope specifikace (ale nutné pro výsledek)

Off-page: zmínky a backlinky (LinkedIn, Hlídač státu / open-data komunita, novinářské newslettery) — bez externích signálů potrvá entitní odlišení od filmu Poslušně hlásím (1957) měsíce. Řeší Markéta, ne developer.
