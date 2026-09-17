---
marp: true
theme: default
paginate: true
title: Poslušně hlásím
description: Jak z dat sněmovny vzniká deník, který pochopíte bez jednacího řádu
style: |
  section { font-size: 28px; }
  section.lead h1 { font-size: 2.2em; }
  blockquote { border-left: 4px solid #333; padding-left: 1em; font-style: italic; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  .tag { font-size: 0.75em; opacity: 0.7; letter-spacing: 0.05em; text-transform: uppercase; }
---

<!-- _class: lead -->

# Poslušně hlásím

### Deník sněmovny pro lidi, kteří na ni nemají osm hodin

**poslusnehlasim.cz**

Satirický. Faktický. Každá citace dohledatelná až na psp.cz.

---

## Začneme uznáním faktu

Poslanecká sněmovna **zveřejňuje všechno**.

Stenoprotokoly. Hlasování. Pořadí projevů. Kdo byl proti.

Problém není nedostatek dat.
Problém je, že **normální člověk z toho nic nepřečte**.

---

## Co vidí občan vs. co vidíme my

<div class="cols">

<div>

**Oficiální web**

> „Návrh zákona, kterým se mění zákon č. 13/1997 Sb., o pozemních komunikacích…"

47 řečníků. 317 minut jednání. Jedno hlasování s 68 proti.

</div>

<div>

**Poslušně hlásím**

> Známka zůstane na dva tisíce pět set sedmdesát.
> Vláda ji zamrazila. Opozice spočítala díru v rozpočtu.

5 minut čtení. 3 citace. Odkaz na každou větu ve stenoprotokolu.

</div>

</div>

---

## Jedna věta z debaty stačí

<blockquote>
„Chcete, aby dálniční známka v České republice stála 3 200 korun za tři roky?"
<br>— poslanec Bednárik, 14. 7. 2026
</blockquote>

Takhle vypadá **signál** v datech: spor, čísla, něco, co zastaví scroll.

Naše práce: najít ten signál mezi tisíci řádky stenoprotokolu
a **nedat k němu vymyšlenou pointu**.

---

## Co projekt vlastně je

**Pro veřejnost:** srozumitelný přehled jednoho dne ve sněmovně

**Pro vývojáře:** datová pipeline + statický web + redakční vrstva v gitu

**Společný jmenovatel:** open data sněmovny jsou surovina.
My mezi ně a čtenáře dáváme **editorial layer**, který respektuje fakta.

Jeden den jednání = jedno vydání. Jako díl seriálu, ne jako tiskovka.

---

## Proč to dává smysl oběma světům

| Veřejnost | Vývojáři |
|-----------|----------|
| Pochopím, o čem se hlasovalo | Zajímavý problém: nestrukturovaný text → produkt |
| Vtip je z reality, ne z fabulace | Žádná databáze, žádný Kubernetes |
| Můžu ověřit každou citaci | Git jako CMS, CI jako redakční sazba |
| Nepotřebuju sledovat politiku | AI v loopu, ale s tvrdými guardrails |

---

## Z čeho to stojí (zdarma, veřejně)

```
PSP (Poslanecká sněmovna)
    │
    ├── UNL soubory          hlasování: pro, proti, výsledek
    │
    └── Hlídač státu         stenoprotokoly: doslovné projevy
```

**Veřejnost:** stát už data platí, my je jen přeložíme do lidské řeštiny.

**Devs:** dva zdroje, dva formáty, jeden produkt. Parsování UNL + JSONL z API.

---

## Příběh jednoho dne (14. 7. 2026)

1. Ve sněmovně proběhne **5+ hodin** debaty o dálniční známce
2. Cron v noci stáhne nová hlasování a steno
3. Skript vybere 1 téma se skóre 69 (spor + 17 000 slov debaty)
4. Redakce / AI dopíše texty do JSON
5. Push na GitHub → za minutu je vydání live
6. Newsletter koncept čeká v Ecomailu

**Večer ve sněmovně. Ráno na webu.**

---

## Pipeline: od raw dat k novinám

```
stenoprotokol + hlasování
        ↓  fetch (automat)
   raw/*.jsonl
        ↓  align (automat)
   topics.json          „co patří k sobě"
        ↓  facts (člověk + AI)
   by_topic/*.json      „co z toho je příběh"
        ↓  compose (automat)
   noviny-dlouhe/*.html
        ↓  export-pages
   poslusnehlasim.cz
```

**Klíčová myšlenka pro devs:** automatizujeme všechno kromě toho,
co vyžaduje úsudek. A i ten usuzujeme strukturovaně.

---

## Git je naše redakce

Jedna schůze = jedna složka. Jedno vydání = pár JSON souborů.

```
processed/2025-s28/
  raw/votes.jsonl          ← co hlasovali
  raw/steno.jsonl          ← co říkali (stovky MB)
  facts/by_topic/*.json    ← co publikujeme
  facts/by_day/*.json      ← úvod dne, závěr, skóre
  out/noviny-dlouhe/*.html  ← hotový výstup
```

**Pro veřejnost:** každé vydání má historii, jde auditovat.

**Pro devs:** content as code. Diff review místo WYSIWYG pekla.

---

## Co je v tom JSON (bez programování)

Jeden článek = `facts/by_topic/zmrazena-dálniční-známka.json`:

- **nadpis** — „Zmrazená dálniční známka"
- **lead** — první odstavec, lidsky
- **fakty[]** — doslovné citace + odkaz do stenoprotokolu
- **pointa** — glosa, protistrany, ironie
- **mean** — jedna věta: co to znamená pro občana

Jeden den = **dnesni_ucet** (2 řádky) + **zaver** („že …")

---

## Curiosity pass: kde vzniká obsah

Skript vybere témata. **Příběh vzniká až průchodem stenem.**

Hledáme v závorkách a v datech:

- `(Potlesk)` / `(Hluk)` / „opouští sál"
- „Budu stručný" u projevu na 50 minut
- `proti > 0` u hlasování
- dva řečníci, stejné číslo, jiný výklad

**Pravidlo:** radši 2 silné debaty než přehled 40 řečníků.

Tohle zatím **plně neautomatizujeme**. A je to záměr.

---

## Důvěra: tři kliknutí k pravdě

```
Článek na webu
    ↓  klik na podtrženou větu
Stránka Zdroje (naše)
    ↓  doslovná citace + kontext
psp.cz (oficiální stenoprotokol)
```

Každá citace má `steno_id` a `link_phrase`.
Fráze v textu musí **slovně sedět**, jinak odkaz nevznikne.

**Veřejnost:** satira, ale s patičkou „dokázat si to".

**Devs:** nejjemnější část pipeline. Heuristika + ruční doladění.

---

## Vtip, který nejde automatizovat (a pár, které ano)

**Ručně / AI:**
- lead, pointa, výběr momentu z debaty
- curiosity pass, kontrast rétoriky a prázdného sálu

**Automat:**
- stažení dat, párování témat, sestavení HTML
- glosář (tooltip u „druhé kolo", „STAN", „veto")
- kontrola: compose **spadne na em pomlčce** — ano, záměrně

Editorial constraints jako linter. Politický humor jako code review.

---

## AI v loopu, ne místo redakce

```
edition brief     →  kostra + návrhy citací (skript)
Cursor / agent    →  doplní texty podle pravidel
link-phrases      →  doplní odkazy (poloviční úspěch)
review            →  audit jmen, stran, hlasování
publish gate      →  teprve pak na web
```

Jedna věta v chatu: **`edition draft schůze 29, 25.8`**

(Pozor: **datum ≠ číslo schůze** — 25. 8. 2026 je s29, 14. 7. je s28.)

Pravidla pro agenta: `.cursor/prompts/edition-draft.md` + `docs/edition-agent-checklist.md`.

**Vymyšlená citace = diskvalifikace.** Brief je menu, ne hotové noviny.

---

## Pro vývojáře: proč jsme zvolili nudná řešení

| Rozhodnutí | Proč |
|------------|------|
| Statický web (GitHub Pages) | Rychlý, levný, nebourá se |
| JSONL místo DB | Diffs, grep, jednoduchý ingest |
| Python + Jinja | Bez frameworku, bez magie |
| Publish gate v JSON | Nedoladěné vydání neuteče na web |
| Cloudflare worker jen pro odběr | Jediný runtime mimo Pages |
| Cron sync dat | Sněmovna jedná večer, my stahujeme v noci |

**Ne stavíme platformu.** Stavíme deník, který musí vycházet pravidelně.

---

## Co běží samo (a co ne)

**Automat (noc / push):**
- sync hlasování a stenoprotokolů
- export webu + deploy
- koncept newsletteru v Ecomailu

**Člověk (ráno):**
- výběr, co ten den stojí za článek
- psaní a faktický audit
- schválení publish gate

Typický push s hotovými `facts/`: **~1 minuta** do produkce.

---

## Produkt mimo web

**Newsletter** — stejný obsah, jiný kanál (Ecomail)

**Odběr** — double opt-in přes Cloudflare worker + Resend

**Korektury** — čtenář pošle opravu, chodí na redakci

**Švejkovský slovníček** — „druhé kolo" ≠ fotbalové finále

Demokratizace ≠ zjednodušení na nepravdu. Demokratizace = **přístupnost s důkazem**.

---

## Co si odnést

**Jste občan?**
Sněmovna mluví celý den. My vytáhneme 5 minut, co stojí za pochopení.
A u každé věty ukážeme, kde to leží ve stenoprotokolu.

**Jste vývojář?**
Open data + file-based pipeline + statický web + AI s guardrails
= produkt, který škáluje obsahově, ne infra.

**Společně:**
Veřejná data mají cenu až když je někdo **přeloží bez lži**.

---

<!-- _class: lead -->

# Děkuji

**Web:** poslusnehlasim.cz
**Repo:** github.com (Poslušně hlásím)
**Otázky?**

*Nejlepší demo: otevřete včerejší vydání a klikněte na citát.*
