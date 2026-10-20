# Brief vydání 14.10.2026

ISO: `2026-10-14` · Schůze: `2025-s34`

Cursor: přečti `.cursor/prompts/edition-draft.md` a doplň `facts/`.


## Doporučená témata (max 3 články)

### 1. `novela-z-o-latkach-ktere-poskozuji-ozonovou-vrst` — Novela z. o látkách, které poškozují ozonovou vrstvu - EU
- skóre: 69, steno_slov: 1785, proti_max: 91, proslo: True

  1. [2025_34_00227] (oprava chyby v psaní)
  2. [2025_34_00227] IV“ nahrazuje textem „čl.VI“ (oprava chyby v psaní) Za třetí v části první čl.
  3. [2025_34_00227] 2 prováděcího nařízení Komise (EU) 2025/1893“, to jest doplňují se číslo článku „2“ a číslo nařízení „1893“ A za šesté v

### 2. `novela-z-o-vyrobcich-s-ukoncenou-zivotnosti-eu` — Novela z. o výrobcích s ukončenou životností - EU
- skóre: 69, steno_slov: 6790, proti_max: 100, proslo: True

  1. [2025_34_00165] (Ministr Červený: Ano.)
  2. [2025_34_00165] Pozměňovací návrhy jsou uvedeny ve sněmovním tisku 58/2, který byl doručen dne 23.
  3. [2025_34_00165] 143.Vládní návrh zákona, kterým se mění zákon č.

### 3. `novela-z-obcansky-soudni-rad-eu` — Novela z. - občanský soudní řád - EU
- skóre: 69, steno_slov: 2737, proti_max: 75, proslo: True

  1. [2025_34_00404] (Krátká prodleva.)
  2. [2025_34_00404] 82/1998 Sb., o odpovědnosti za škodu způsobenou při výkonu veřejné moci rozhodnutím nebo nesprávným úředním postupem, ve
  3. [2025_34_00404] 549/1991 Sb., o soudních poplatcích, ve znění pozdějších předpisů, a zákon č.

## Zvažovaná, ale vyřazená

- `novela-z-o-ochrane-spotrebitele-eu` — mimo top 3 pro den (skóre 63)
- `navrh-na-zmeny-ve-slozeni-organu-poslanecke-snem` — mimo top 3 pro den (skóre 60)
- `navrh-na-jmenovani-clenu-kontrolni-rady-grantove` — mimo top 3 pro den (skóre 58)
- `vl-n-z-o-nekterych-povinn-souvisejicich-s-opravo` — mimo top 3 pro den (skóre 54)
- `navrh-na-jmenovani-clena-kontrolni-rady-technolo` — mimo top 3 pro den (skóre 50)
- `navrh-na-volbu-clena-dozorci-rady-vinarskeho-fon` — procedura / slabý steno signál (skóre 50)
- `navrh-na-volbu-clenu-rady-ceskeho-rozhlasu` — procedura / slabý steno signál (skóre 50)
- `vl-n-z-o-urc-provozoven-za-ucel-shrom-dukazu-v-t` — mimo top 3 pro den (skóre 48)

## Stats dne

```json
{
  "pocet_hlas_zakon": 7,
  "proslo_vote": 7,
  "zamitnuto_vote": 0,
  "spor_o_porad": true,
  "calendar_isos": [
    "2026-10-14",
    "2026-10-15"
  ]
}
```

## Úkoly pro agenta

1. `facts/by_topic/<slug>.json`: nadpis, lead, pointa, mean, citace_text, publikovat
2. `facts/by_day/`: dnesni_ucet (2 řádky), zaver (že …), topic_slugs, steno_zdroje
3. `./run-svejk.sh edition link-phrases --schuze N --den D`
4. `./run-svejk.sh edition preview --schuze N --den D`
