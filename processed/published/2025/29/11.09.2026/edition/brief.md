# Brief vydání 11.09.2026

ISO: `2026-09-11` · Schůze: `2025-s29`

Cursor: přečti `.cursor/prompts/edition-draft.md` a doplň `facts/`.


## Doporučená témata (max 3 články)

### 1. `novela-z-o-spotrebitelskem-uveru` — Novela z. o spotřebitelském úvěru
- skóre: 69, steno_slov: 15499, proti_max: 110, proslo: True

  1. [2025_29_00304] (Odpověď ministryně mimo mikrofon.)
  2. [2025_29_00304] Pozměňovací návrhy jsou uvedeny ve sněmovním tisku 145/3, který byl doručen 26.
  3. [2025_29_00304] 257/2016 Sb., o spotřebitelském úvěru, ve znění pozdějších předpisů, a další související zákony/sněmovní tisk 145/ – tře

### 2. `vl-n-z-o-ekodesignu-vyrobku-eu` — Vl. n. z. o ekodesignu výrobků - EU
- skóre: 69, steno_slov: 1652, proti_max: 1, proslo: True

  1. [2025_29_00434] (zákon o ekodesignu výrobků)
  2. [2025_29_00434] 5.Vládní návrh zákona o ekodesignu výrobků a o výkonu státní správy v oblasti ekodesignu výrobků a o změně souvisejících
  3. [2025_29_00434] Návrh na zamítnutí ani pozměňovací návrhy nebyly ve druhém čtení předneseny.

### 3. `vl-n-z-o-vstupu-a-pobytu-cizincu` — Vl. n. z. o vstupu a pobytu cizinců
- skóre: 69, steno_slov: 1875, proti_max: 69, proslo: True

  1. [2025_29_00400] (cizinecký zákon)
  2. [2025_29_00400] 2.Vládní návrh zákona o vstupu a pobytu cizinců (cizinecký zákon)/sněmovní tisk 144/ – třetí čtení Prosím, aby místo u s
  3. [2025_29_00400] Pozměňovací návrhy byly uvedeny ve sněmovním tisku 144/2, který byl doručen dne 25.

## Zvažovaná, ale vyřazená

- `novela-z-o-duchodovem-pojisteni` — mimo top 3 pro den (skóre 60)
- `n-z-kterym-se-meni-nektere-zakony-na-useku-vnitr` — mimo top 3 pro den (skóre 54)

## Stats dne

```json
{
  "pocet_hlas_zakon": 5,
  "proslo_vote": 5,
  "zamitnuto_vote": 0,
  "spor_o_porad": true,
  "calendar_isos": [
    "2026-09-11",
    "2026-09-12"
  ]
}
```

## Úkoly pro agenta

1. `facts/by_topic/<slug>.json`: nadpis, lead, pointa, mean, citace_text, publikovat
2. `facts/by_day/`: dnesni_ucet (2 řádky), zaver (že …), topic_slugs, steno_zdroje
3. `./run-svejk.sh edition link-phrases --schuze N --den D`
4. `./run-svejk.sh edition preview --schuze N --den D`
