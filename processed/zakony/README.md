# Zákony — stránky `/zakony/{slug}/`

Jeden soubor `{slug}.json` = jedna stránka s celou cestou zákona. Obsah je ruční
(redakce), build (`export-pages`) ho jen doplní o odkazy a ověří citace.

Rozložení stránky: **vlevo opozice · uprostřed průběh a znění · vpravo vláda**
(na mobilu: průběh, opozice, vláda pod sebou).

## Pole

| Pole | Význam |
|------|--------|
| `slug` | URL (`/zakony/{slug}/`) |
| `publikovat` | `false` = stránka se negeneruje |
| `obdobi`, `tisk` | volební období (2025) a číslo sněmovního tisku → odkaz na psp.cz |
| `eyebrow`, `nazev`, `nazev_kratky`, `perex`, `meta` | hlavička, `nazev_kratky` je v drobečkové navigaci |
| `stav` | jedna věta „kde je zákon teď“ |
| `aktualizovano` | `D.M.YYYY`, jde i do sitemapy |
| `predkladatel`, `zpravodaj`, `garancni_vybor` | řádek metadat pod hlavičkou |
| `temata` | slugy témat z `facts/by_topic/` — pod těmi články ve vydání se objeví tlačítko „Celá cesta zákona →“ |
| `zneni` | box „Znění na stole“: `nadpis`, `text`, `body[]`, `zmeny` (co se oproti vládnímu návrhu změnilo) |
| `faze[]` | fáze cesty (viz níže), pořadí = pořadí na stránce |
| `vlada`, `opozice` | boční sloupce: `eyebrow`, `nadpis`, `strany[]`, `shrnuti`, `argumenty[{titulek,text}]`, `navrhy[]`, `citace[]`, `citace_nahore` (kolik citací je vidět bez rozbalení, výchozí 6) |
| `poznamka` | drobná poznámka pod průběhem |

### `faze[]`

```json
{"id": "1-cteni", "nazev": "První čtení", "kratce": "1. čtení",
 "stav": "hotovo|probiha|ceka|neprobehlo", "datum": "23.–24. 10. 2026",
 "schuze": 34, "text": "…", "vysledek": "zvýrazněný výsledek",
 "kroky": [{"datum": "", "cas": "19:46", "text": "…", "steno_id": "2025_34_01995",
            "dulezite": true,
            "hlasovani": {"cislo": 277, "co": "…", "kdo_navrhl": "…"},
            "hlasovani_skupina": [{"cislo": 289, "co": "…"}], "skupina_label": "…"}],
 "vydani": [{"schuze": 34, "datum_unl": "23.10.2026", "slug": "…", "label": "…"}]}
```

U `hlasovani` stačí `cislo` (+ `schuze` ve fázi nebo kroku) — pro/proti/čas a
odkaz na psp.cz se doplní z `raw/votes.jsonl`.

### `citace[]`

```json
{"steno_id": "2025_34_02001", "jmeno": "Martin Kupka", "strana": "ODS",
 "funkce": "", "citace": "doslovně ze stena", "kontext": "na co reagoval"}
```

`citace` musí být doslovný výňatek ze stenozáznamu daného `steno_id`; když
nesedí, build vypíše varování. Odkaz „stenozáznam ↗“ vede na psp.cz.
