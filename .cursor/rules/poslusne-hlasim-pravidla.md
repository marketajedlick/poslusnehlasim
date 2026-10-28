# Pravidla: Poslušně hlásím — generování ze steno záznamu

Tento soubor je návod pro AI agenta (Cursor), jak z `steno.jsonl` a `votes.jsonl`
vygenerovat texty do satirického newsletteru "Poslušně hlásím" ve stylu Švejka.
Cíl: kvalita na první pokus, bez toho, aby to člověk musel dohledávat a opravovat.

**Doplňky mimo tento soubor:**

| Téma | Soubor |
|---|---|
| Terminologie, glosář, skóre dne, typografie, `dnesni_ucet` / `zaver` | [`steno-zapisy.mdc`](./steno-zapisy.mdc) |
| Legislativní fáze, kvóra, heuristiky z rozpravy | [`legislativni-proces-kontext.md`](./legislativni-proces-kontext.md) |
| Debata o pořadu schůze (co nedostalo / co dostalo) | §2a níže |
| Curiosity pass (grep tipy, signály), sync, publish, finální průchod | [`processed/WORKFLOW.md`](../../processed/WORKFLOW.md) §2a, §4a, §9 |

**Mapování polí v `facts/by_topic/*.json`:**

| Účel | JSON pole | Export na webu |
|---|---|---|
| Titulek sekce | `nadpis` | `## …` |
| Úvodní odstavec | `lead` | první odstavec pod nadpisem |
| Citát (~60 slov) | `fakty[].citace` (+ volitelně `citace_text` / `citace_autor`) | blockquote |
| Tělo / glosa | `pointa` | pokračování sekce |
| Hlášení na velitelstvo | `mean` | `**Hlášení na velitelstvo:** …` |
| Odkaz na steno | `fakty[].steno_id`, `fakty[].link_phrase` | `<a class="steno-link">` |
| Vynechat z vydání | `publikovat: false` | sekce se neexportuje |
| Výsledek hlasování | `verdikt` | skóre dne, wording v textu |

Do `lead` **nepiš** refrén „Poslušně hlásím…". Piš srozumitelný reportážní úvod (kdo, co, kdy).
Compose doplní „Poslušně hlásím, že …" **jen u prvního článku dne**, pokud tam refrén ještě není.

---

## 0. Vstupní data

**steno.jsonl** — jeden řádek = jeden proslov. Pole:
`id, poradi, obdobi, schuze, datum, cele_jmeno, tema, text, pocet_slov, url, cislo_hlasovani`

**votes.jsonl** — jeden řádek = jedno hlasování. Pole:
`cislo, bod, datum, cas, nazev, vysledek, pro, proti, zdrzel, nehlasoval, pritomno, je_porad_schuze`

Pravidlo: pokud sekce zmiňuje výsledek hlasování (číslo, poměr pro/proti), musí se
dohledat ve `votes.jsonl` přes `bod` + `nazev` + `datum`, ne odhadovat ani přebírat
z paměti. Pokud se nedá jednoznačně spárovat, napiš to jako nejisté nebo to vynech.

---

## 1. Výběr tématu pro sekci

1. Seřaď `tema` podle počtu záznamů (`groupby tema, count`), abys viděl, co se
   v dané schůzi řešilo nejvíc.
2. Pro každé kandidátní téma najdi řádky obsahující klíčová slova, ne jen název
   tématu — lidé často mluví k věci i mimo formální `tema` (interpelace, faktické
   poznámky).
3. Přednost mají témata, kde je jasný **konflikt dvou lidí** (otázka/odpověď,
   napadení/obhajoba) nebo **absurdní detail** (číslo, citát, nepřítomnost),
   který nese sám o sobě.
4. Nikdy nevymýšlej jméno řečníka. Pokud si nejsi jistý, kdo co řekl, najdi to
   v `cele_jmeno` u konkrétního `id`, ne podle kontextu nebo paměti.

---

## 1b. Curiosity pass (povinné před psaním textů)

Pipeline z stena vytáhne návrhy (`review`, `fakty_z_steno_record`), ale **nevidí celý
kontext debaty**. Materiál pro noviny vzniká až průchodem celého `steno.jsonl` pro den.

**Curiosity** = cokoli, co by čtenáře mimo sněmovnu zastavilo: scéna v sále, absurdní
metafora, faktický rozpor, chyba předsedajícího, ostrá výměna, ironie délky projevu.

Postup (detail, grep tipy, tabulka signálů): [`WORKFLOW.md` §2a](../../processed/WORKFLOW.md).

Shrnutí:

1. Z `votes.jsonl` si vypiš body s `proti` > 0; ze stena témata s nejvíc `pocet_slov`.
2. U každého slugu v `facts/by_topic/` zkontroluj, co už je v `fakty[]`, a dohledej chybějící ve stenozáznamu.
3. Projdi steno **den po dni**, ne jen `steno_ids` u tématu. U silných záznamů ulož `id` → `steno_id`.
4. Zapiš do `fakty[]`: doslovná `citace`, stručný `text`, později `link_phrase`.
5. Témata bez curiosity nastav `publikovat: false`.

Pro každou sekce, která půjde do vydání, musíš mít:

- [ ] aspoň **2–3 doslovné citace** v `fakty[]`, každá s ověřeným `steno_id`
- [ ] aspoň **jeden kontrast** (rétorika vs. fakta, velká slova vs. prázdný sál, koalice vs. opozice)
- [ ] víš, **proč by to četl člověk mimo politiku**

Teprve potom piš `lead` a `pointa`.

---

## 2. Struktura jedné sekce

V `facts/by_topic/*.json` (export v `noviny-dlouhe/`):

```
nadpis: krátký titulek, 2–5 slov, konkrétní — ne generický vtip bez obsahu

lead: úvodní odstavec — kdo/co/kdy, srozumitelný bez jednacího řádu.
      Může mít víc odstavců nebo odrážky (<ul>), u silných debat klidně delší.
      Refrén „Poslušně hlásím" sem nepiš (viz úvod souboru).

fakty[]: citace ze stena + steno_id (+ link_phrase po napsání lead/pointa)

pointa: tělo sekce — protistrana, kontext, výsledek hlasování, glosa.
        Volitelně „Poslušně podotýkám/dodávám, že…" — max jednou na sekci.

mean: Hlášení na velitelstvo — první věta, co téma znamená pro občana; zbytek
      suchý úřední průběh. Výsledek jen slovně (schváleno/zamítnuto), ne skóre hlasů.
```

**Délka:** radši méně sekcí s hloubkou než přehled deseti řečníků. Krátká interpelace
cca 120–220 slov; silná debata (stavební zákon, maraton jednoho řečníka) může být
delší, pokud každý odstavec nese konkrétní fakt nebo citát.

---

## 2a. Debata o pořadu schůze (`debata-porad-*`, `spor_o_porad`)

Když den obsahuje maraton hlasování o programu (`spor_o_porad: true`, `je_porad_schuze`
ve `votes.jsonl`), sekce **nesmí být jen soupis hlasování ani počet kol**. Piš ji jako
dvě jasné části: **co se do pořadu nedostalo** a **co se do pořadu dostalo**.

### Odkud brát data

1. **`votes.jsonl`:** všechna hlasování s `je_porad_schuze: true` — návrhy na přidání,
   vyřazení nebo přeuspořádání bodů; u každého `vysledek` (A/N) a `nazev`.
2. **`steno.jsonl`:** debata u tématu „Debata o pořadu schůze" a projevy navázané na
   konkrétní hlasování (`cislo_hlasovani`). Hledej „zavetovala", „vyškrtla", „nepřijímá",
   „jako první bod", „nově navržené body".
3. **Schválený pořad:** poslední hlasování o pořadu s `vysledek: A`, nebo oznámení
   předsedajícího ve stenozáznamu po sérii hlasování.

### Co se do pořadu nedostalo

Vylistuj konkrétní návrhy, které někdo předložil a které **se do pořadu nedostaly**
(hlasování o zařazení bodu skončilo zamítnutím):

- u každého bodu: **kdo navrhoval**, **o co šlo lidsky** (ne číslo sněmovního tisku),
  **proč to chtěli** (jedna věta ze stena nebo z `nazev` hlasování přeložené do češtiny);
- **shrnutí:** jaký vzorec boje vypadá (sucho místo rozpočtových pravidel, sváteční
  prodeje místo dluhů, dlouhé titulky proti Motoristům…).

Do `fakty[]` ulož nejlepší citace k návrhům, které **se na program nedostaly**.

**Terminologie (důležité):** u hlasování o pořadu **nepiš „padlo“ / „prošlo“** jako u
zákonů. Zamítnutý návrh bodu **se nedostal na program** (nebo „do pořadu“). „Padlo“
patří jen k substantivním výsledkům dne (zákon, usnesení s věcným verdiktem), ne k
boji o to, o čem se bude mluvit. Stejně tak do skóre dne / tabule `prošlo:padlo`
pořad **nepočítej**.

### Co se do pořadu dostalo

Vylistuj body, které ve **schváleném pořadu** zůstaly nebo se na program dostaly:

- u každého: pořadí (pokud je známo), lidský popis předmětu, kdo to prosazoval;
- **shrnutí:** jak finální program dne vypadá, o čem se poslanci skutečně budou bavit.

Do `fakty[]` ulož citace k **schválenému** pořadu (veto nových bodů, potvrzení pořadí).

### Struktura textu

| Pole | Pořadí obsahu |
|---|---|
| `lead` | kontext (proč se o pořadu hlasovalo) → **co se nedostalo na program** (hlavní návrhy + shrnutí) → **co zůstalo** (finální program + shrnutí) |
| `pointa` | scény a citáty ze stena — nejdřív boj o body mimo program, pak potvrzení programu; chronologie ze stenozáznamu |
| `mean` | pořad určuje, o čem se ten den mluví; bez skóre hlasování |
| `fakty[]` | logicky rozdělené: body mimo program vs. schválený program; každý záznam s `steno_id` |

**Nepiš** „devět hlasování za dvě hodiny" ani jiný počet kol jako pointu dne. Počet
hlasování patří do `pocet_hlasovani` v JSON, ne do `lead`/`pointa`. Absurdní detail
(z déjà vu, trhací kalendář, dlouhý titulek bodu) patří do `pointa`, ne do `dnesni_ucet`
/ `zaver` (viz `steno-zapisy.mdc`).

**Příklad struktury `lead`:** „Večer šlo hlavně o to, co vůbec dostane na program.
Opozice chtěla sucho, sváteční prodeje a dlouhé titulky proti Motoristům — nic z toho
se na program nedostalo. Ve schváleném pořadu zůstala rozpočtová pravidla jako první bod a další
vládní návrhy, o kterých se má jednat druhý den."

---

## 3. Hlas a tón

- Ironie z kontrastu faktů, ne z moralizování. Necháš čtenáře dojít k závěru sám.
- Refrén „Poslušně hlásím / podotýkám / dodávám" — úsporně. Compose ho dá k prvnímu
  článku dne; v `pointa` max jednou na sekci.
- `lead`, `pointa`, `nadpis` piš **lidově a vtipně** — bez jednacího žargonu
  (`legislativní nouze`, `ve třetím čtení`, `personálka`). Detailní styl: `steno-zapisy.mdc`.
- `mean` (Hlášení na velitelstvo): první věta pro občana, zbytek suchý úřední zápis.
  Detailní styl: `steno-zapisy.mdc`, §4b.
- Žádná negativní paralelismus („Není to X. Je to Y."). Krátké odstavce. Věty různé délky.

---

## 4. Vysvětlování pojmů (zlidovění)

Než napíšeš sekci, zeptej se: pochopí to čtenář, který nesleduje denně
sněmovní žargon? Pokud je v textu pojem jako „dozorčí rada", „trafika",
„akciová společnost jako nezisková organizace" — vysvětli ho **jednou větou v textu
sekce** (`lead` nebo `pointa`), ne v poznámce pod čarou.

Nevysvětlené zkratky a instituce = čtenář ztrácí pointu. Humor funguje jen tehdy,
když čtenář rozumí, co je na situaci absurdní. Glosář pro tooltipy: `svejk/glossary.py`.

---

## 4b. Srozumitelnost pro laika (test „vyznal se v tom?")

Čtenář nesleduje sněmovnu denně. Text musí fungovat i pro něj.

**Úvod (`lead`):**

- Začni **předmětem**, ne procedurou. Špatně: „středa patřila stavebnímu zákonu ve třetím čtení". Dobře: „šlo o to, jak rychle v Česku dostanete stavební povolení".
- Fázi zákona přelož jednou větou, pokud je v textu nutná: „poslední hlasování před prezidentem", „poslanci ještě měnili detaily".
- U ministra, předkladatele nebo klíčové postavy uveď **funkci** při první zmínce, pokud není zřejmá z kontextu.

**Tělo (`pointa`):**

- Drž **chronologii** ze stenozáznamu. Citát a reakce na něj nesmí působit, že přišly dřív, než řečník promluvil.
- Kontrast (mlčení ministrů vs. dopis o diskusi) vysvětli jednou větou, ne jen naznač.

**Hlášení na velitelstvo (`mean`):**

- První věta: co téma **znamená pro občana** (co zákon nebo dávka dělá).
- Zbytek: suchý průběh dne, bez insider žargonu.

**Kontrola před odevzdáním:** přečti `lead` nahlas někomu, kdo politiku nesleduje. Když se musí ptát „a o co vlastně šlo?", přepiš úvod.

---

## 4c. Návaznost na historii tématu

Stejný zákon, interpelace nebo kauza se ve sněmovně vrací po dnech. Když jsme o tématu **už psali** v dřívějším vydání, navaz na to v `lead` nebo `pointa`.

**Nejdřív dohledej historii:**

- `grep` v `processed/2025-s*/facts/by_topic/` podle klíčových slov, slugu nebo názvu tisku
- starší články téhož dne v `topic_slugs` a v `processed/published/`
- fázi zákona z [`legislativni-proces-kontext.md`](./legislativni-proces-kontext.md)

**Jak navázat:**

- Jedna věta stačí: co minule padlo, kdo mluvil, co se změnilo (`v úterý to padlo v prvním kole`, `ministr tentokrát promluvil`, `opozice vrací stejný argument`).
- Pointa dne = **nový** detail ze stenozáznamu, ne opakování celého starého článku.
- Kontrast funguje nejlíp: stejný řečník jiná slova, stejná strana jiné hlasování, slib vs. realita.

**Co to není:**

- Nepiš meta poznámky o kalendáři (`noční rozpočty patří k úterku`, `Vločka skončila včera`). To je zakázáno v `steno-zapisy.mdc`.
- Nevymýšlej minulé dny. Navazuj jen na to, co je v `facts/`, `published/` nebo ve stenozáznamu téhož zákona.

**Příklad:** stavební zákon ve třetím čtení → v `lead` nebo `pointa` jednou zmínit, že minulá vláda zákon shodila, ANO pro něj hlasovalo dřív, ministr mlčel už celé kolo. Nový text = Kučerovo vyčítání, Havlíčkův první projev.

---

## 4a. Odkazy na steno (`link_phrase`)

Každá důležitá citace nebo tvrzení ve vydání má vlastní `steno_id` a `link_phrase`.

| Pole | Pravidlo |
|---|---|
| `steno_id` | přesně z `steno.jsonl` / `review` |
| `citace` | doslovně ze stena |
| `link_phrase` | **přesná podmnožina textu** v `lead` nebo `pointa` — compose podle ní vloží odkaz |

Postup: nejdřív napiš článek (`lead`, `pointa`), **pak** doplň `link_phrase` podle
hotového wordingu. Každé jiné místo ve stenozáznamu = jiné `steno_id`.

V `facts/by_day/YYYY-MM-DD.json` nastav `"steno_zdroje": true` a `topic_slugs`.

Plný řetězec článek → stránka Zdroje → PSP, kontrola před publikací:
[`WORKFLOW.md` §4a, §6, §9](../../processed/WORKFLOW.md).

---

## 5. Ověřování faktů — povinný checklist před odevzdáním

Pro každou sekci:

- [ ] Jméno řečníka odpovídá `cele_jmeno` u konkrétního `id` v steno.jsonl —
      nezaměnil jsem podobná jména (např. Šenda vs. Šmída, Šebestyán vs. Šmída)?
- [ ] Citát je doslovný výňatek z pole `text`, ne parafráze vydávaná za citát.
- [ ] Citát je kratší než ~60 slov. Delší myšlenku parafrázuj vlastními slovy.
- [ ] Číslo, procento nebo částka se dá dohledat v `text` nebo `votes.jsonl` —
      nevymyslel jsem si ho ani nezaokrouhlil bez poznámku.
- [ ] V redakčním textu (`lead`, `pointa`, `mean`, `link_phrase`, `dnesni_ucet`,
      `zaver`, `vysledek`) jsou **čísla slovně** (`sto dvacet tři`, ne `123`).
      Výjimky: skóre hlasování `97:51`, roky u data (`2026`, `2035`), strana
      `TOP 09`, označení návrhu (`A7`). **Číslice jen v `citace` / `citace_text`**
      (doslovně ze stena).
- [ ] Pokud sekce zmiňuje výsledek hlasování, je ověřený ve `votes.jsonl`
      (číslo hlasování, pro/proti/zdržel se), ne jen odhadnutý z tónu diskuse.
- [ ] Strana/klub u jména je uvedená jen tehdy, když je to ve zdroji jisté.
      Radši žádná strana než špatná.
- [ ] Kontext (kdo na koho reaguje, kdo je ministr, kdo předkladatel) sedí
      s `tema` a okolními řádky (`id - 2` až `id + 2`), ne jen s izolovanou
      větou.
- [ ] Důležité věty mají `link_phrase`, která sedí s textem po compose (§4a).
- [ ] V `dnesni_ucet`, `zaver` a `vysledek` není poznámka typu „patří k úterku“
      o věcech z jiného dne, které v článcích stejného vydání nejsou.
- [ ] `lead` projde testem „vyznal se v tom?" (§4b): předmět, role postav, chronologie citátů.
- [ ] Pokud jsme o stejném tématu už psali dřív (§4c), text na historii navazuje jednou větou.
- [ ] Citát dne (`jazykolam`) není stejná věta jako citát v článku (`citace_text` ani `fakty[].citace`).

Pokud checklist neprojde, sekci neodevzdávej — dohledej znovu nebo napiš,
co chybí.

---

## 5b. Čísla slovně (redakce vs. citace)

Compose při exportu přepisuje číslice v `lead`/`pointa`/`mean` (`svejk/cislo_slovy.py`),
ale **`link_phrase` musí sedět s wordingem v článku** — compose nejdřív přepíše text,
pak hledá frázi pro steno odkaz. Když napíšeš `123` místo `sto dvacet tři`, odkaz
nefunguje.

| Pole | Číslice? |
|------|----------|
| `citace`, `citace_text`, `fakty[].citace` | ano, doslovně ze stena |
| `lead`, `pointa`, `mean`, `link_phrase` | ne, piš slovně |
| `by_day` → `dnesni_ucet`, `zaver`, `vysledek` | ne, piš slovně |
| skóre dne (tabule „stav zápasu" v `by_day`) | ano, formát `X:Y` jen u zákonů |
| kalendářní rok (`2026`, `2035`) | ano, nech číslice |

Příklady: `devět hlasování`, `400 000 korun` → `čtyři sta tisíc korun`.
Ve větách článku nepiš `154:0`, `sto dvacet tři hlasů pro` ani `osmdesát pět pro,
dvě proti`. Piš „schválila", „zamítla", „prošlo bez odporu". Skóre hlasů patří
do `votes.jsonl` a `citace`, ne do `lead`/`pointa`/`mean`.

---

## 6. Co nedělat

- Nevymýšlet jméno, stranu ani přesné číslo, když to steno záznam neříká.
- Nepoužívat arabské číslice v `lead`/`pointa`/`link_phrase` (kromě kalendářního
  roku). Do `citace` patří doslovný tvar ze stena, i když má číslice. Nepoužívat
  skóre hlasování v těle článku (`154:0`, `X pro, Y proti`), jen verdikt.
- Necitovat víc než jednu delší pasáž za osobu na sekci (autorská práva + čtivost).
- Nepoužívat „CO TO ZNAMENÁ PRO VÁS" ani jiné publicistické vysvětlivky —
  místo toho `mean` (Hlášení na velitelstvo), psané suše a byrokraticky.
- Nepřidávat obecné moralizování na konci — humor stojí na faktech, ne na kázání.
- Neopakovat stejný detail ve dvou sekcích — najdi mu jednu přesnou sekci.
- Nepoužívat jedno `steno_id` pro všechny odkazy v sekci.

---

## 7. Pracovní postup pro nové vydání

1. Načti `steno.jsonl` a `votes.jsonl` pro danou schůzi.
2. `./run-svejk.sh review --schuze N --den D.M` a `--audit` — vyber dny a témata.
3. **Curiosity pass** (§1b): projdi steno pro den, obohať `fakty[]`.
4. **Historie tématu** (§4c): grep prior `facts/` a `published/`; navaz na dřívější fázi nebo článek.
5. Vytipuj 2–4 silné sekce (ne 5–7 slabých přehledů). U každé najdi rozsah `id`.
6. Zapiš `facts/by_topic/<slug>.json` (`nadpis`, `fakty[]`, `lead`, `pointa`, `mean`).
7. Doplň `link_phrase` podle hotového textu; v `facts/by_day/` nastav `steno_zdroje`.
8. Projdi checklist (§5).
9. `./run-svejk.sh build --only compose --den D.M` — lokální náhled.
10. **Finální průchod** celého vydání: [`WORKFLOW.md` §9](../../processed/WORKFLOW.md).
