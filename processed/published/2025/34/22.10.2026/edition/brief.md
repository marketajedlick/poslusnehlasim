# Brief vydání 22.10.2026

ISO: `2026-10-22` · Schůze: `2025-s34`

Cursor: přečti `.cursor/prompts/edition-draft.md` a doplň `facts/`.


## Doporučená témata (max 3 články)

### 1. `vl-n-z-o-statnim-rozpoctu-cr-na-rok-2027` — Vl.n.z. o státním rozpočtu ČR na rok 2027
- skóre: 69, steno_slov: 160409, proti_max: 95, proslo: True

  1. [2025_34_01240] 1.Vládní návrh zákona o státním rozpočtu České republiky na rok 2027/sněmovní tisk 324/ – prvé čtení Z pověření vlády ná
  2. [2025_34_01240] Prosím, ujmete se slova a připraví se následně také zpravodaj rozpočtového výboru, poslanec Vladimír Pikora.
  3. [2025_34_01240] Přečtu pořadí řečníků s přednostním právem, protože stejně se mě na to budete pořád ptát nebo dokola spoustu lidí.

### 2. `odpoved-na-pisemnou-interpelaci-e-olsakove-na-a-` — Odpověď na písemnou interpelaci E. Olšákové na A. Schillerovou
- skóre: 58, steno_slov: 235, proti_max: 71, proslo: False

  1. [2025_34_01508] (poslanec Berki reaguje ze sálu.)
  2. [2025_34_01508] (Jednání přerušeno v 10.59 hodin.) *** Neprošlo jazykovou korekturou, neautorizováno!
  3. [2025_34_01508] Ještě počkáme, já mezitím přečtu omluvy aspoň částečně: Adamec Ivan celý jednací den – osobní důvody, Bauer Jan celý jed

### 3. `odpoved-na-pisemnou-interpelaci-m-jurecky-na-a-b` — Odpověď na písemnou interpelaci M. Jurečky na A. Babiše
- skóre: 50, steno_slov: 246, proti_max: 14, proslo: True

  1. [2025_34_01482] V hlasování číslo 220 přihlášeno 110 poslanců, pro 34, proti 14.
  2. [2025_34_01482] Já se omlouvám, protože tohle je úplně první řízení, které je tady v tomto bodě, a nemám to zatím úplně uložené, nechám 
  3. [2025_34_01482] Takže rozprava ještě není ukončena a hlásí se do ní paní poslankyně Kovářová.

## Zvažovaná, ale vyřazená

- `odpoved-na-pisemnou-interpelaci-m-jurecky-na-i-b` — procedura / slabý steno signál (skóre 50)
- `novela-z-o-nekt-opatr-v-souv-s-ozbrojenym-konfli` — mimo top 3 pro den (skóre 22)

## Stats dne

```json
{
  "pocet_hlas_zakon": 2,
  "proslo_vote": 2,
  "zamitnuto_vote": 0,
  "spor_o_porad": true,
  "calendar_isos": [
    "2026-10-22",
    "2026-10-23"
  ]
}
```

## Úkoly pro agenta

1. `facts/by_topic/<slug>.json`: nadpis, lead, pointa, mean, citace_text, publikovat
2. `facts/by_day/`: dnesni_ucet (2 řádky), zaver (že …), topic_slugs, steno_zdroje
3. `./run-svejk.sh edition link-phrases --schuze N --den D`
4. `./run-svejk.sh edition preview --schuze N --den D`
