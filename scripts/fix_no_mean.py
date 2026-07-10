#!/usr/bin/env python3
"""Doplní chybějící mean (Hlášení na velitelstvo) u publikovaných témat."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svejk.paths import SchuzePaths
from svejk.review import review_topic

# (schuze, slug) → mean
MEANS: dict[tuple[int, str], str] = {
    (2, "nav-zasedaciho-poradku-poslancu-v-jedn-sale-ps"): (
        "Pořádek zasedání určuje, kdo kde sedí v jednacím sále Sněmovny. "
        "Běžného člověka to nijak nezasáhne."
    ),
    (2, "navrh-na-stanoveni-poctu-poslancu-ve-stalych-del"): (
        "Sněmovna stanovila počty poslanců ve stálých delegacích do zahraničních parlamentních sborů. "
        "Běžného člověka to nijak nezasáhne."
    ),
    (2, "zmeny-ve-slozeni-organu-ps"): (
        "Poslanci přesadili lidi ve výborech a dalších orgánech Sněmovny. "
        "Jde o personální změny, ne o zákon měnící práva občanů."
    ),
    (5, "navrh-na-odvolani-clenu-dr-sfdi"): (
        "Sněmovna hlasovala o odvolání členů dozorčí rady Státního fondu dopravní infrastruktury. "
        "Jde o personální obsazení fondu, který platí dopravní stavby."
    ),
    (5, "navrh-na-zmeny-ve-slozeni-organu-poslanecke-snem"): (
        "Formální hlasování o složení sněmovních výborů a komisí. "
        "Běžného člověka to nijak nezasáhne."
    ),
    (5, "navrh-na-zmeny-ve-slozeni-organu-poslanecke-snem-2"): (
        "Formální hlasování o složení sněmovních výborů a komisí. "
        "Běžného člověka to nijak nezasáhne."
    ),
    (10, "navrh-rozpoctu-sfa-na-rok-2026"): (
        "Sněmovna schvalovala rozpočet Státního fondu audiovize na rok 2026. "
        "Peníze jdou na podporu české kinematografie, televize a audiovize."
    ),
    (10, "navrh-rozpoctu-sfpi-na-rok-2026"): (
        "Sněmovna schvalovala rozpočet Státního fondu podpory investic na rok 2026. "
        "Fond platí stavební a bytové projekty podporované ze státních peněz."
    ),
    (10, "navrh-rozpoctu-szif-na-rok-2026"): (
        "Sněmovna schvalovala rozpočet Státního zemědělského intervenčního fondu na rok 2026. "
        "Peníze jdou hlavně na zemědělské dotace a podporu farmářů."
    ),
    (10, "novela-z-o-statnich-svatcich"): (
        "Návrh mění zákon o státních svátcích a dnech pracovního klidu. "
        "Týká se kalendáře volných dnů, zatím šlo o přikázání návrhu výboru."
    ),
    (10, "rozpocet-sfdi-na-rok-2026"): (
        "Sněmovna schvalovala rozpočet Státního fondu dopravní infrastruktury na rok 2026. "
        "Peníze jdou na silnice, mosty a další dopravní stavby."
    ),
    (14, "n-casoveho-harm-projednavani-vladniho-navrhu-st-"): (
        "Sněmovna rozhodovala o harmonogramu projednání státního závěrečného účtu za rok 2024. "
        "Určuje, kdy se o účetní uzávěrce státu bude mluvit a hlasovat."
    ),
    (14, "novela-z-o-statnich-svatcich"): (
        "Senát vrátil úpravy zákona o státních svátcích, Sněmovna je znovu projednává. "
        "Mění se kalendář státních svátků a pravidla pro dny pracovního klidu."
    ),
    (14, "posouzeni-podminek-pro-projednani-st-163-ve-zkra"): (
        "Sněmovna rozhodovala, jestli se zákon o cenách benzínu a nafty projedná ve zkráceném režimu. "
        "Návrh na zkrácení neprošel, debata potrvá déle."
    ),
    (14, "potvrzeni-trvani-stavu-legislativni-nouze"): (
        "Sněmovna potvrdila trvání legislativní nouze u zákona o cenách pohonných hmot. "
        "Stát tak může zákon projednat rychleji než standardní postup."
    ),
    (24, "navrh-na-stanoveni-vyse-odmen-clenum-kr-ta-cr-za"): (
        "Sněmovna schválila roční odměny členům kontrolní rady Technologické agentury, "
        "částky se pohybují zhruba mezi 60 a 105 tisíci korunami. Od roku 2027 to přejde pod vládu."
    ),
    (24, "navrh-na-zmeny-ve-slozeni-organu-poslanecke-snem"): (
        "Formální přesuny poslanců ve výborech a komisích Sněmovny. "
        "Běžného člověka to nijak nezasáhne."
    ),
    (24, "navrh-zakona-o-statnich-zamestnancich-souvisejic"): (
        "Související úpravy k zákonu o státních zaměstnancích, hlavně termíny účinnosti. "
        "Týká se úředníků ve státní správě, ne běžných občanů v běžném dni."
    ),
    (24, "novela-z-trestni-zakonik"): (
        "Sněmovna projednávala změny trestního zákoníku v prvním kole. "
        "Závěrečné hlasování neproběhlo, platí dál stávající pravidla."
    ),
    (24, "sml-cr-malta-o-zamezeni-dvojimu-zdaneni"): (
        "Sněmovna vyslovila souhlas s ratifikací smlouvy s Maltou o zamezení dvojího zdanění. "
        "Týká se lidí a firem s příjmy v obou zemích."
    ),
    (24, "sml-mezi-cr-a-kenskou-republikou-o-zamezeni-dvoj"): (
        "Smlouva s Keňou upravuje zdanění příjmů z obou zemí, aby stejné peníze nebyly zdaněny dvakrát. "
        "Relevantní hlavně pro podnikatele a lidi s příjmy v Africe."
    ),
    (24, "sml-mezi-cr-a-mongolskem-o-policejni-spolupraci"): (
        "Sněmovna schválila ratifikaci smlouvy s Mongolskem o policejní spolupráci. "
        "Umožní společné stíhání a vymáhání trestů mezi oběma zeměmi."
    ),
    (24, "sml-mezi-cr-a-slovenskou-republikou-o-policejni-"): (
        "Smlouva se Slovenskem rozšiřuje policejní spolupráci, hlavně vymáhání trestů a předávání osob "
        "mezi českou a slovenskou policií."
    ),
    (24, "sml-mezi-cr-a-srn-o-statnich-hranicich"): (
        "Smlouva s Německem upravuje průběh státní hranice na řece Nežárce. "
        "Dotkne se především obcí u jihočeské hranice."
    ),
    (24, "sml-mezi-cr-a-tanzanskou-repub-o-zamezeni-dvojim"): (
        "Smlouva s Tanzanií má zabránit dvojímu zdanění příjmů. "
        "Týká se občanů a firem s obchodními nebo pracovními vazbami v obou zemích."
    ),
    (24, "vl-n-z-kt-se-meni-nektere-z-v-oblasti-verejnych-"): (
        "Novela rozpočtových zákonů upravuje pravidla pro státní výdaje v souvislosti se schváleným rozpočtem. "
        "Týká se hlavně toho, kam a jak smí stát utrácet."
    ),
}


def main() -> int:
    fixed = 0
    missing: list[str] = []

    for sch in range(1, 25):
        paths = SchuzePaths.create(2025, sch)
        if not paths.facts_by_topic.is_dir():
            continue
        for fp in sorted(paths.facts_by_topic.glob("*.json")):
            fact = json.loads(fp.read_text(encoding="utf-8"))
            if not fact.get("publikovat"):
                continue
            tr = review_topic(paths, fact["slug"])
            if not tr or not any(i.code == "no_mean" for i in tr.issues):
                continue
            key = (sch, fact["slug"])
            mean = MEANS.get(key)
            if not mean:
                missing.append(f"s{sch}/{fact['slug']}")
                continue
            if (fact.get("mean") or "").strip() == mean:
                continue
            fact["mean"] = mean
            fp.write_text(json.dumps(fact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fixed += 1

    print(f"fixed: {fixed}")
    if missing:
        print("missing:", missing)
        return 1

    # verify
    left = 0
    for sch in range(1, 25):
        paths = SchuzePaths.create(2025, sch)
        if not paths.facts_by_topic.is_dir():
            continue
        for fp in paths.facts_by_topic.glob("*.json"):
            fact = json.loads(fp.read_text())
            if not fact.get("publikovat"):
                continue
            tr = review_topic(paths, fact["slug"])
            if tr and any(i.code == "no_mean" for i in tr.issues):
                left += 1
    print(f"remaining no_mean: {left}")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
