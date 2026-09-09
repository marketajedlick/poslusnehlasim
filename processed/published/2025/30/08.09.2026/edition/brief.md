# Brief vydání 08.09.2026

ISO: `2026-09-08` · Schůze: `2025-s30`

Cursor: přečti `.cursor/prompts/edition-draft.md` a doplň `facts/`.


## Doporučená témata (max 3 články)

### 1. `navrh-zakona-o-statnich-zamestnancich` — Návrh zákona o státních zaměstnancích
- skóre: 64, steno_slov: 2267, proti_max: 68, proslo: True

  1. [2025_30_00068] (zákon o státních zaměstnancích)
  2. [2025_30_00068] 2.Návrh zákona o právních poměrech státních zaměstnanců v ministerstvech a jiných správních úřadech (zákon o státních za
  3. [2025_30_00068] A prosím, aby se za navrhovatele k usnesení Senátu o zamítnutí tohoto návrhu zákona vyjádřil pan poslanec Radek Vondráče

### 2. `navrh-zakona-o-statnich-zamestnancich-souvisejic` — Návrh zákona o státních zaměstnancích - související
- skóre: 56, steno_slov: 6542, proti_max: 69, proslo: True

  1. [2025_30_00061] Hlasování číslo 29, bylo přihlášeno 179 poslanců, pro hlasovalo 101, proti 53 a já konstatuji, že pořad schůze byl schvá
  2. [2025_30_00061] Přistoupíme k projednávání prvního bodu, což je 186.Návrh časového harmonogramu projednávání vládního návrhu zákona o st
  3. [2025_30_00061] září 2026, jehož přílohou je i návrh usnesení Poslanecké sněmovny.

### 3. `navrh-casoveho-harmonogramu-projednavani-vladnih` — Návrh časového harmonogramu projednávání vládního návrhu zákona o stát
- skóre: 12, steno_slov: 588, proti_max: 0, proslo: True

  1. [2025_30_00064] Společná schůzka zpravodajů výborů, kde budou probrána jednotlivá usnesení výborů i oponentní zpráva, je plánována na 11
  2. [2025_30_00064] Druhé čtení – pokud vše půjde podle plánu a podle harmonogramu – by mělo proběhnout ve středu 25.
  3. [2025_30_00064] Návrh usnesení máte k dispozici, proto jej, pokud není námitek, nebudu číst.

## Stats dne

```json
{
  "pocet_hlas_zakon": 3,
  "proslo_vote": 3,
  "zamitnuto_vote": 0,
  "spor_o_porad": true,
  "calendar_isos": [
    "2026-09-08",
    "2026-09-09"
  ]
}
```

## Úkoly pro agenta

1. `facts/by_topic/<slug>.json`: nadpis, lead, pointa, mean, citace_text, publikovat
2. `facts/by_day/`: dnesni_ucet (2 řádky), zaver (že …), topic_slugs, steno_zdroje
3. `./run-svejk.sh edition link-phrases --schuze N --den D`
4. `./run-svejk.sh edition preview --schuze N --den D`
