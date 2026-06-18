"""Sněmovní pojmy: krátká vysvětlení pro tooltipy v HTML.

Pořadí: delší fráze nahoře, aby se neshodily s kratšími prefixy.
"""

from __future__ import annotations

import re
import unicodedata

GLOSSARY: tuple[tuple[str, str], ...] = (
    # --- vyznamenání 4. 6. 2026 (s20) ---
    (
        "Třiadvacet návrhů ale spadlo pod stůl",
        "Tyto návrhy na vyznamenání 4. 6. 2026 neprošly: Luboš Dobrovský, Karel I., Michael Žantovský, "
        "Radim Passer, Naděžda Vlašín Johanisová, Lucie Bášová, Kristýna Cejnarová, Daniel Herman, "
        "Libuše Jarcovjáková, Milan Kňažko, Martin Kroupa, Mikuláš Kroupa, Miroslav Kundrata, "
        "Eva Lehotská, Ladislav Miko, Jesica Miňovská, Václav Moravec, Ondřej Novotný, Martin Ondráček, "
        "Zdislava Pokorná, Jiří Šlégr, Daniel Vávra a Vojtěch Filsák.",
    ),
    (
        "Luboš Dobrovský",
        "Novinář; návrh na vyznamenání 4. 6. 2026 neprošel (91:13), chyběly tři hlasy na většinu přítomných.",
    ),
    (
        "Vojtěch Filsák",
        "Návrh na vyznamenání 4. 6. 2026 neprošel (92:16); chyběl jediný hlas na většinu přítomných.",
    ),
    (
        "Václav Moravec",
        "Moderátor a novinář; návrh na vyznamenání 4. 6. 2026 neprošel (82:67).",
    ),
    (
        "Daniel Vávra",
        "Herní vývojář; návrh na vyznamenání 4. 6. 2026 neprošel (85:33).",
    ),
    # --- Rada ČT 5. 6. 2026 (s20) ---
    (
        "jeho vlastní výroky o novinářkách",
        "Talíř (STAN) 5. 6. 2026 v debatě citoval soudem nařízenou omluvu Luboše Xavera Veselého "
        "za výrok na adresu novinářky Johany Hovorkové: „je to zrůda, svině, hnát svinským krokem.“",
    ),
    (
        "výroky o novinářkách",
        "Soudem nařízená omluva za výrok Veselého o novinářce Johany Hovorkové: "
        "„je to zrůda, svině, hnát svinským krokem.“ Opozice to 5. 6. 2026 před volbou do Rady ČT předčítala.",
    ),
    # --- kontext konkrétních schůzí (delší fráze první) ---
    (
        "koaliční změna stavebního zákona",
        "Poslanecký návrh (tisk 67) od Babiše, Havlíčka a koalice: má zrychlit a zjednodušit "
        "povolování domů, hal a silnic. Měl nahradit novelu Fialovy vlády z roku 2021, "
        "koalice ho chtěla projít zkráceně.",
    ),
    (
        "rychlost nesmí ztratit právní jistotu",
        "Kučera (TOP 09): zrychlení staveb je správný cíl, ale nesmí rozbít "
        "pravidla tak, aby stavebník ani úřad nevěděli, co platí.",
    ),
    (
        "Bartošovu digitalizaci",
        "Mrázová (ANO) kritizovala digitalizaci stavebního řízení za ministra Bartoše (Piráti): "
        "úřady podle ní neměly funkční systém a povolování se nezrychlilo.",
    ),
    (
        "deset hlasování o usneseních ke jmenování ministrů",
        "16. 1. 2026: nejdřív se hlasovalo o pořadí, pak o devíti usneseních. Prošlo jen usnesení "
        "Šťastného (Motoristé), že prezident ať jmenuje ministry. Osm ostatních padlo: Jakob "
        "(rozpočtová odpovědnost), Zuna (dvakrát vůči ministrům), Langšádlová (klima a Ukrajina), "
        "Dvořák (nový ministr životního prostředí), Jurečka (proti Turkovi), Pospíšil "
        "(kompetenční žaloba).",
    ),
    (
        "deset hlasování o obsazení vlády",
        "16. 1. 2026: nejdřív se hlasovalo o pořadí, pak o devíti usneseních. Prošlo jen usnesení "
        "Šťastného (Motoristé), že prezident ať jmenuje ministry. Osm ostatních padlo: Jakob "
        "(rozpočtová odpovědnost), Zuna (dvakrát vůči ministrům), Langšádlová (klima a Ukrajina), "
        "Dvořák (nový ministr životního prostředí), Jurečka (proti Turkovi), Pospíšil "
        "(kompetenční žaloba).",
    ),
    (
        "koalice obsazování postů pustila dál",
        "16. 1. 2026: osm opozičních usnesení chtělo zbrzdit jmenování ministrů, většinou padlo "
        "101:82 až 101:83. Koalice schválila jen návrh Šťastného (Motoristé), že prezident má "
        "jmenovat ministry, a personální kolotoč pokračoval k odpoledním volbám do orgánů sněmovny.",
    ),
    (
        "rozdíl zisků VZP a ostatních pojišťoven",
        "Vojtěch 28. 1. 2026: navrhovaných 7,9 miliardy prý odpovídá rozdílu zisků za zaměstnance. "
        "VZP zhruba 10,5 miliardy, zaměstnanecké pojišťovny asi 2,6. Opozice to vnímá jako neférový "
        "přesun ve prospěch konkurence.",
    ),
    (
        "ubere z důchodu tisíc šest set padesát dva korun",
        "Jurečkův protiargument z debaty 16. 1. 2026: nižší zálohy na sociálním pojištění "
        "znamenají nižší odvody na důchod. Koalice mluví o úspoře 715 Kč měsíčně u záloh; "
        "Jurečka počítá, že v penzi by OSVČ přišla zhruba o 1 652 Kč měsíčně. Schillerová "
        "v projevu tuto cenu nezmínila.",
    ),
    (
        "nechal počkat, až v sále sedí víc ministrů",
        "Pirát Václav Pláteník měl 14. 1. po obědě domluvit projev proti vládě, který "
        "před polední pauzou přerušili uprostřed věty. Předsedající Barták (Motoristé) "
        "ho před pokračováním nechal chvíli počkat, až v sále sedí víc ministrů. "
        "Šlo o spor, jestli má vláda sedět v sále při debatě o důvěře. Richterová "
        "chtěla pauzu, dokud se nevrátí Babiš; Králíček (Motoristé) to označil za "
        "pirátskou obstrukci.",
    ),
    (
        "azbestu v Milovicích",
        "Kauza z vojenského areálu Milovice a Mladá: při demolicích a sanaci údajně skončil "
        "eternit rozdrcený ve stavební sutí v lese místo na bezpečné skládce. Policie "
        "obvinila mj. středočeského radního za ANO Bezděka z úmyslného zamoření lesů "
        "azbestem. Znalec spočítal škodu na životním prostředí 2,2 miliardy Kč; na "
        "zhruba 22 hektarech našli 88 tun kontaminované suti. Richterová to 14. 1. "
        "v debatě o důvěře připomněla jako příklad kauz hnutí ANO.",
    ),
    (
        "kauzách",
        "Ve středeční debatě o důvěře 14. 1. opozice (hlavně Richterová) vyjmenovávala "
        "konkrétní skandály kolem lidí z ANO: hejtman Krkoška (odsouzený za organizovanou "
        "zločineckou skupinu), primátor Charvát (vazba kvůli zakázkám města), kauza "
        "Stoka v Brně (exradní Švachula 9,5 roku), Faltýnkův diář se zakázkami, vazby "
        "senátorky Mračkové na Dozimetr a azbest v Milovicích. Nešlo o hlasování, "
        "šlo o útok na důvěryhodnost kabinetu, který o důvěru žádal.",
    ),
    (
        "dva opoziční návrhy ho chtěly shodit",
        "Před závěrečným hlasováním (č. 8) padly dva návrhy. Havránek (ODS) chtěl "
        "schválit základní parametry rozpočtu a poslat kapitoly do výborů (67:105). "
        "Svobodová (Piráti) chtěla doplnit 14 miliard na dostupné bydlení (39:35, "
        "80 zdrželých). Pak prošlo usnesení rozpočtového výboru 105:64.",
    ),
    (
        "stokrát opakovanou lží",
        "Stanjura 26. 11. při rozpočtu 2026: ANO celé dopoledne tvrdilo, že země "
        "není v kondici. On to označil za opakovanou lež a chtěl ukázat srovnání "
        "z hodnocení všech členských států Evropské komise (17. 11. 2025). "
        "Schillerová předtím útočila na rozpočet Fialovy vlády a srovnávala schodek "
        "376 miliard z roku 2021 s dnešními čísly.",
    ),
    (
        "ze čtvrté třídy",
        "Richterová Kolovratníkovi: „Doufám, že jsme se nedostali do čtvrté třídy "
        "základní školy, aby se tady běžně komolila lidem jména. To doufám, že byl "
        "opravdu omyl.“",
    ),
    (
        "oslovil Hřibkem",
        "Kolovratník záměrně řekl Hřibek místo Hřib, jako by mluvil o někom "
        "méně vážně, pak se s úsměvem opravil. Ve stenoprotokolu je u toho "
        "poznámka (Se smíchem.), šlo o vědomou demisi, ne o překlep.",
    ),
    (
        "Hřibkem",
        "Zdrobnělina, ne překlep. Kolovratník ji použil úmyslně, jako by mluvil "
        "o někom méně vážně, pak se s úsměvem opravil na správné jméno. Ve "
        "stenoprotokolu je u toho poznámka (Se smíchem.).",
    ),
    (
        "Hřibek",
        "Zdrobnělina, ne překlep. Kolovratník ji použil úmyslně, jako by mluvil o "
        "někom méně vážně, pak se s úsměvem „opravil“ na správné jméno. Ve "
        "stenoprotokolu je u toho poznámka (Se smíchem.), šlo o vědomou demisi, "
        "ne o omyl.",
    ),
    (
        "kde je férovost",
        "Kolovratník připomněl minulé období: Piráti 4 poslanci, přesto "
        "Richterová místopředsedkyně Sněmovny; SPD 20 poslanců a ve vedení "
        "Sněmovny nebylo. Ptá se, kde je férovost. Jenže mluvil o vedení "
        "Sněmovny, zatímco debata šla o výborech.",
    ),
    (
        "čtyři poslance a místopředsedkyni",
        "Totéž číslo jinak: Kolovratník připomněl, že Piráti měli jen 4 "
        "poslance, ale Richterová seděla ve vedení Sněmovny. SPD mělo 20 "
        "poslanců a ve vedení Sněmovny nebylo.",
    ),
    (
        "deset ku deseti",
        "Jediný výbor, kde koalice a opozice měly na papíře stejný počet míst "
        "(10+10). Richterová v tom viděla výjimku, koalice to přepsala na "
        "22 členů a získala většinu.",
    ),
    (
        "dvě různé volby",
        "Hřib: místopředsedkyně Sněmovny volí celé plénum podle koaliční "
        "dohody (Piráti se STAN měli 800 000 voličů). Předsedu výboru volí "
        "členové výboru. Kolovratník podle něj plete obě věci dohromady.",
    ),
    (
        "dvě různé funkce",
        "Totéž: vedení Sněmovny a vedení výboru jsou dvě různé volby. "
        "Místopředsedkyni volí plénum, předsedu výboru volí členové výboru.",
    ),
    (
        "vedení výborů",
        "Richterová: třicet let platilo, že strany vedou výbory podle počtu "
        "poslanců z voleb. Předseda svolává jednání a navrhuje program, "
        "proto na tom záleží.",
    ),
    # --- volby a vedení sněmovny ---
    (
        "mandátový a imunitní výbor",
        "Sněmovní rozhodčí: řeší střety zájmů, disciplinární prohřešky nebo vydání poslance policii.",
    ),
    (
        "tajné hlasování",
        "Poslanci hlasují anonymně na papírových lístcích v urně, ne tlačítkem na kartě.",
    ),
    (
        "tajnou volbu",
        "Poslanci hlasují anonymně na papírových lístcích v urně, ne tlačítkem na kartě.",
    ),
    (
        "tajné volby",
        "Poslanci hlasují anonymně na papírových lístcích v urně, ne tlačítkem na kartě.",
    ),
    (
        "tajná volba",
        "Poslanci hlasují anonymně na papírových lístcích v urně, ne tlačítkem na kartě.",
    ),
    (
        "volební komise",
        "Skupina poslanců, která organizuje a kontroluje všechny volby uvnitř Sněmovny.",
    ),
    (
        "místopředsedkyně sněmovny",
        "Zástupce předsedy. Řídí schůze, když předseda není přítomen.",
    ),
    (
        "místopředsedou sněmovny",
        "Zástupce předsedy. Řídí schůze, když předseda není přítomen.",
    ),
    (
        "místopředseda sněmovny",
        "Zástupce předsedy. Řídí schůze, když předseda není přítomen.",
    ),
    (
        "místopředsedů",
        "Zastupují předsedu sněmovny při řízení schůze.",
    ),
    (
        "místopředsedkyně",
        "Zastupuje předsedu sněmovny při řízení schůze.",
    ),
    (
        "místopředsedy",
        "Zastupují předsedu sněmovny při řízení schůze.",
    ),
    (
        "místopředseda",
        "Zastupuje předsedu sněmovny při řízení schůze.",
    ),
    (
        "ustavující schůze",
        "První schůze po volbách: volí se vedení, výbory a termíny. Zákony se zatím neprojednávají.",
    ),
    (
        "ověřovatelé",
        "Poslanečtí „kontroloři zápisu“. Hlídají, že schůze proběhla podle pravidel.",
    ),
    (
        "ověřovatelů",
        "Poslanečtí „kontroloři zápisu“. Hlídají, že schůze proběhla podle pravidel.",
    ),
    (
        "ověřovatelkami",
        "Poslanečtí „kontroloři zápisu“. Hlídají, že schůze proběhla podle pravidel.",
    ),
    (
        "ověřovatele",
        "Poslanečtí „kontroloři zápisu“. Hlídají, že schůze proběhla podle pravidel.",
    ),
    (
        "ověřovatel",
        "Poslanečtí „kontroloři zápisu“. Hlídají, že schůze proběhla podle pravidel.",
    ),
    # --- projednávání zákonů ---
    (
        "stanovisko vlády",
        "Oficiální názor kabinetu k návrhu zákona. Poslanci ho dostanou jako samostatný "
        "sněmovní tisk, obvykle s číslem /1.",
    ),
    (
        "vládní návrh",
        "Zákon, který do sněmovny posílá vláda (ne poslanci ani Senát). Má prioritu v pořadu "
        "a často jde rychleji než opoziční návrhy.",
    ),
    (
        "senátní návrh",
        "Zákon, který do sněmovny posílá Senát. Sněmovna ho může schválit, upravit nebo zamítnout.",
    ),
    (
        "zpravodajky",
        "Poslanci z výboru, kteří sněmovně vysvětlují návrh zákona a doporučují, jak hlasovat.",
    ),
    (
        "zpravodajka",
        "Poslanec z výboru, který sněmovně vysvětluje návrh zákona a doporučuje, jak hlasovat.",
    ),
    (
        "zpravodajce",
        "Poslanec z výboru, který sněmovně vysvětluje návrh zákona a doporučuje, jak hlasovat.",
    ),
    (
        "zpravodajů",
        "Poslanci u stolu u pultu: vysvětlují návrh zákona a odpovídají na dotazy před hlasováním.",
    ),
    (
        "zpravodaj",
        "Poslanec z výboru, který sněmovně vysvětluje návrh zákona a doporučuje, jak hlasovat.",
    ),
    (
        "obecnou rozpravu",
        "Fáze debaty, kdy poslanci mluví k celému návrhu obecně, ne k jednotlivým paragrafům.",
    ),
    (
        "obecné rozpravě",
        "Fáze debaty, kdy poslanci mluví k celému návrhu obecně, ne k jednotlivým paragrafům.",
    ),
    (
        "obecné rozpravy",
        "Fáze debaty, kdy poslanci mluví k celému návrhu obecně, ne k jednotlivým paragrafům.",
    ),
    (
        "obecná rozprava",
        "Fáze debaty, kdy poslanci mluví k celému návrhu obecně, ne k jednotlivým paragrafům.",
    ),
    (
        "podrobnou rozpravu",
        "Fáze debaty, kdy se čtou a projednávají konkrétní paragrafy zákona nebo usnesení.",
    ),
    (
        "podrobné rozpravě",
        "Fáze debaty, kdy se čtou a projednávají konkrétní paragrafy zákona nebo usnesení.",
    ),
    (
        "podrobné rozpravy",
        "Fáze debaty, kdy se čtou a projednávají konkrétní paragrafy zákona nebo usnesení.",
    ),
    (
        "podrobná rozprava",
        "Fáze debaty, kdy se čtou a projednávají konkrétní paragrafy zákona nebo usnesení.",
    ),
    (
        "nominační zákon",
        "Zákon o tom, kdo může sedět ve statutárních orgánech firem se státním podílem "
        "(353/2019 Sb.). Vláda jmenovala lidi do dozorů a rad státních podniků.",
    ),
    (
        "kuponovou debabišizaci",
        "Návrh prodat akcie Agrofertu občanům přes poukázky, aby premiér neměl firmu ve střetu zájmů.",
    ),
    (
        "zagongoval",
        "Předsedající zazvonil gongem a svolává poslance k hlasování (nebo ukončuje rozpravu).",
    ),
    (
        "zrychlené projednávání",
        "Mimořádný režim, kdy se zákon projednává rychleji než obvykle, kratší lhůty na připomínky "
        "a méně času pro opozici.",
    ),
    (
        "zkrácené řízení",
        "Mimořádný režim, kdy se zákon projednává rychleji než obvykle.",
    ),
    (
        "zkráceném režimu",
        "Zákon projde rychleji: kratší lhůty na připomínky a méně času pro opozici.",
    ),
    (
        "zkráceném jednání",
        "Zákon projde rychleji: kratší lhůty na připomínky a méně času pro opozici.",
    ),
    (
        "zkrácené jednání",
        "Zákon projde rychleji: kratší lhůty na připomínky a méně času pro opozici.",
    ),
    (
        "zkrácené projednávání",
        "Zákon projde rychleji: kratší lhůty na připomínky a méně času pro opozici.",
    ),
    (
        "legislativní nouze",
        "Výjimečný stav, kdy předseda sněmovny zkrátí lhůty natolik, že zákon může projít velmi rychle.",
    ),
    (
        "legislativní nouzi",
        "Výjimečný stav, kdy předseda sněmovny zkrátí lhůty natolik, že zákon může projít velmi rychle.",
    ),
    (
        "pozměňovací návrhy",
        "Pokus poslanců přepsat kus zákona, než se o něm definitivně hlasuje.",
    ),
    (
        "pozměňovací návrh",
        "Pokus poslance přepsat kus zákona, než se o něm definitivně hlasuje.",
    ),
    (
        "procedurálními návrhy",
        "Hlasuje se o tom, kdy, jak a jestli se vůbec bude jednat. Ne o obsahu zákona.",
    ),
    (
        "procedurální návrhy",
        "Hlasuje se o tom, kdy, jak a jestli se vůbec bude jednat. Ne o obsahu zákona.",
    ),
    (
        "procedurálním návrhem",
        "Hlasuje se o tom, kdy, jak a jestli se vůbec bude jednat. Ne o obsahu zákona.",
    ),
    (
        "procedurální návrh",
        "Hlasuje se o tom, kdy, jak a jestli se vůbec bude jednat. Ne o obsahu zákona.",
    ),
    (
        "přerušení schůze",
        "Poslanci si dali pauzu a slíbili, že se k tomu jednou vrátí.",
    ),
    (
        "přerušení jednání",
        "Poslanci si dali pauzu a slíbili, že se k tomu jednou vrátí.",
    ),
    (
        "přerušení bodu",
        "Poslanci si dali pauzu u konkrétního bodu programu a slíbili, že se k němu vrátí.",
    ),
    (
        "schůze přerušena",
        "Poslanci si dali pauzu a slíbili, že se k tomu jednou vrátí.",
    ),
    (
        "vrácen senátem",
        "Senátoři si zákon přečetli a poslali ho zpátky s poznámkou „zkuste to ještě jednou“.",
    ),
    (
        "senátem vrácen",
        "Senátoři si zákon přečetli a poslali ho zpátky s poznámkou „zkuste to ještě jednou“.",
    ),
    (
        "vrátil senát",
        "Senátoři si zákon přečetli a poslali ho zpátky s poznámkou „zkuste to ještě jednou“.",
    ),
    (
        "třetím čtení",
        "Finální hlasování o zákonu, pak může jít k prezidentovi k podpisu.",
    ),
    (
        "třetí čtení",
        "Finální hlasování o zákonu, pak může jít k prezidentovi k podpisu.",
    ),
    (
        "druhém čtení",
        "Poslanci navrhují změny a úpravy zákona, hlasuje se o konkrétních paragrafech.",
    ),
    (
        "druhé čtení",
        "Poslanci navrhují změny a úpravy zákona, hlasuje se o konkrétních paragrafech.",
    ),
    (
        "prvém čtení",
        "Ještě zákon neschválí. Jen rozhodne, jestli se jím Sněmovna bude dál zabývat.",
    ),
    (
        "prvé čtení",
        "Ještě zákon neschválí. Jen rozhodne, jestli se jím Sněmovna bude dál zabývat.",
    ),
    (
        "prvním čtení",
        "Ještě zákon neschválí. Jen rozhodne, jestli se jím Sněmovna bude dál zabývat.",
    ),
    (
        "první čtení",
        "Ještě zákon neschválí. Jen rozhodne, jestli se jím Sněmovna bude dál zabývat.",
    ),
    (
        "sněmovního tisku",
        "Oficiální číslo návrhu zákona ve sněmovně. Každý tisk má svůj program projednávání.",
    ),
    (
        "sněmovní tisku",
        "Oficiální číslo návrhu zákona ve sněmovně. Každý tisk má svůj program projednávání.",
    ),
    (
        "sněmovní tisk",
        "Oficiální číslo návrhu zákona ve sněmovně. Každý tisk má svůj program projednávání.",
    ),
    (
        "kuponová debabišizace",
        "Návrh prodat akcie Agrofertu občanům přes poukázky, aby premiér neměl firmu ve střetu zájmů.",
    ),
    (
        "online zákonodárství",
        "Projekt digitalizace zákonů. Cílem je, aby se připravovaly a zveřejňovaly elektronicky.",
    ),
    (
        "eLegislativa",
        "Elektronický systém pro tvorbu a projednávání zákonů. Má sjednotit práci úřadů a sněmovny.",
    ),
    # --- kola hlasování (rozpočet, volby) ---
    (
        "druhém kole",
        "Druhé projednání ve sněmovně: u zákonu fáze konkrétních úprav, u rozpočtu další fáze, "
        "u voleb funkcí druhý pokus.",
    ),
    (
        "druhé kolo",
        "Druhé projednání ve sněmovně: u zákonu fáze konkrétních úprav, u rozpočtu další fáze, "
        "u voleb funkcí druhý pokus.",
    ),
    (
        "prvním kole",
        "První projednání ve sněmovně: u zákonu rozhoduje, jestli se návrhem budou dál zabývat, "
        "u rozpočtu schvalují obrysy, u voleb první pokus.",
    ),
    (
        "první kolo",
        "První projednání ve sněmovně: u zákonu rozhoduje, jestli se návrhem budou dál zabývat, "
        "u rozpočtu schvalují obrysy, u voleb první pokus.",
    ),
    (
        "závěrečné hlasování",
        "Poslední hlasování o zákonu ve sněmovně (třetí čtení), pak může jít k prezidentovi k podpisu.",
    ),
    (
        "finální hlasování",
        "Poslední hlasování o zákonu ve sněmovně (třetí čtení), pak může jít k prezidentovi k podpisu.",
    ),
    # --- politické instituce a procedury ---
    (
        "vyšetřovací komise",
        "Sněmovní tým, který má prošetřit konkrétní kauzu; poslanci v něm mají zvláštní pravomoci.",
    ),
    (
        "Nejvyšší kontrolní úřad",
        "Nezávislý kontrolor státu: zjišťuje, jak úřady a firmy nakládají s veřejnými penězi.",
    ),
    (
        "mimořádnou schůzi",
        "Schůze mimo pravidelný kalendář, svolaná kvůli konkrétnímu tématu, třeba střetu zájmů premiéra.",
    ),
    (
        "mimořádné schůze",
        "Schůze mimo pravidelný kalendář, svolaná kvůli konkrétnímu tématu, třeba střetu zájmů premiéra.",
    ),
    (
        "mimořádná schůze",
        "Schůze mimo pravidelný kalendář, svolaná kvůli konkrétnímu tématu, třeba střetu zájmů premiéra.",
    ),
    (
        "státní závěrečný účet",
        "Roční bilance státu: kolik utratil, jak sedí s rozpočtem a jestli účetnictví souhlasí.",
    ),
    (
        "závěrečný účet",
        "Roční bilance státu: kolik utratil a jestli čísla sedí s rozpočtem.",
    ),
    (
        "poměrným zastoupením",
        "Počet míst ve výborech podle toho, kolik poslanců (a voličů) každá strana ve volbách získala.",
    ),
    (
        "poměrného zastoupení",
        "Počet míst ve výborech podle toho, kolik poslanců (a voličů) každá strana ve volbách získala.",
    ),
    (
        "poměrné zastoupení",
        "Počet míst ve výborech podle toho, kolik poslanců (a voličů) každá strana ve volbách získala.",
    ),
    (
        "imunitní výbor",
        "Sněmovní rozhodčí: řeší střety zájmů, disciplinární prohřešky nebo vydání poslance policii.",
    ),
    (
        "mandátový výbor",
        "Sněmovní rozhodčí: řeší střety zájmů, disciplinární prohřešky nebo vydání poslance policii.",
    ),
    (
        "Všeobecná pojišťovna",
        "Největší zdravotní pojišťovna v Česku. Stát v ní hraje roli, politici řeší její řízení a finance.",
    ),
    (
        "existenční minimum",
        "Nejnižší hranice příjmu pro výpočet některých sociálních dávek.",
    ),
    (
        "životní minimum",
        "Základní částka pro výpočet dávek, tedy kolik stát považuje za minimum k životu.",
    ),
    (
        "pořadu schůze",
        "Seznam bodů, o kterých se daný den ve sněmovně mluví a hlasuje.",
    ),
    (
        "pořad schůze",
        "Seznam bodů, o kterých se daný den ve sněmovně mluví a hlasuje.",
    ),
    (
        "střetu zájmů",
        "Situace, kdy politik rozhoduje o věcech, které se ho nebo jeho firmu osobně týkají.",
    ),
    (
        "střet zájmů",
        "Politik rozhoduje o věcech, které se ho nebo jeho firmu osobně týkají; zákon vyžaduje vyloučení nebo vysvětlení.",
    ),
    (
        "interpelacím",
        "Čas vyhrazený na otázky poslanců ministrům a premiérovi.",
    ),
    (
        "interpelací",
        "Čas vyhrazený na otázky poslanců ministrům a premiérovi.",
    ),
    (
        "interpelacemi",
        "Čas vyhrazený na otázky poslanců ministrům a premiérovi.",
    ),
    (
        "interpelacích",
        "Čas vyhrazený na otázky poslanců ministrům a premiérovi.",
    ),
    (
        "interpelace",
        "Část jednání, kdy poslanci pokládají otázky členům vlády.",
    ),
    (
        "ústavní zákon",
        "Zákon na nejvyšší úrovni; ke schválení potřebuje většinu poslanců a souhlas Senátu.",
    ),
    (
        "polistopadový kartel",
        "Babišův termín pro zavedené strany a elity po roce 1989, které podle něj koordinovaně proti němu stojí.",
    ),
    (
        "polistopadovým kartelem",
        "Babišův termín pro zavedené strany a elity po roce 1989, které podle něj koordinovaně proti němu stojí.",
    ),
    (
        "tři tisíce šest set toastů",
        "Babiš tvrdil, že Agrofert dodal 3600 toastů uprchlíkům z Ukrajiny na hlavním nádraží v roce 2022.",
    ),
    (
        "Okamurův novoroční projev",
        "Video předsedy sněmovny ze 1. ledna 2026: odmítl posílat zbraně Ukrajině a řekl, že za peníze důchodců nelze kupovat zbraně „k udržování nesmyslné války“.",
    ),
    (
        "videa se Zunou",
        "Bartoš připomněl klipy z minulé sněmovny: předseda klubu SPD Fiala s generálem Zunou točil ponižující videa poté, co Zuna řekl, že pomoc Ukrajině je nutná a Rusko je agresor. Ministr Šťastný (SPD) pak musel na tiskovce mlčet.",
    ),
    (
        "sudetoněmecký landsmanšaft",
        "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení.",
    ),
    (
        "Sudetoněmeckého landsmanšaftu",
        "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení.",
    ),
    (
        "Sudetoněmecký landsmanšaft",
        "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení.",
    ),
    (
        "landsmanšaft",
        "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení.",
    ),
    (
        "landsmanšaftu",
        "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení.",
    ),
    (
        "Benešových dekretů",
        "Poválečné dekrety prezidenta Beneše, které mimo jiné řešily majetek a postavení Němců "
        "a Maďarů po válce.",
    ),
    (
        "Benešovy dekrety",
        "Poválečné dekrety prezidenta Beneše, které mimo jiné řešily majetek a postavení Němců "
        "a Maďarů po válce.",
    ),
    (
        "koncesionářských poplatků",
        "Roční poplatek za televizi a rozhlas. Vláda a sněmovna o něm často debatují při rozpočtu "
        "a při volbách do rady České televize.",
    ),
    (
        "koncesionářské poplatky",
        "Roční poplatek za televizi a rozhlas. Vláda a sněmovna o něm často debatují při rozpočtu "
        "a při volbách do rady České televize.",
    ),
    (
        "volbě rady ČT",
        "Hlasování o tom, kdo bude sedět v radě České televize a dohlížet na její fungování.",
    ),
    (
        "volba rady ČT",
        "Hlasování o tom, kdo bude sedět v radě České televize a dohlížet na její fungování.",
    ),
    (
        "Rada ČT",
        "Skupina lidí, která dohlíží na Českou televizi a vybírá její vedení.",
    ),
    (
        "rady ČT",
        "Skupina lidí, která dohlíží na Českou televizi a vybírá její vedení.",
    ),
    (
        "přebytků VZP",
        "Peníze, které VZP vydělala navíc. Politici je často chtějí přerozdělit mezi zdravotní "
        "pojišťovny nebo použít na jiné účely.",
    ),
    (
        "rezervy VZP",
        "Peníze, které VZP naspořila navíc. Politici o nich často debatují při přerozdělování "
        "mezi pojišťovnami.",
    ),
    (
        "důchodový třetí pilíř",
        "Dobrovolné penzijní spoření, do kterého si lidé ukládají peníze na důchod vedle státního.",
    ),
    (
        "třetí pilíř",
        "Dobrovolné penzijní spoření, do kterého si lidé ukládají peníze na důchod.",
    ),
    (
        "digitalizace dávek",
        "Převod žádostí a administrativy sociálních dávek do online systému.",
    ),
    (
        "digitalizaci dávek",
        "Převod žádostí a administrativy sociálních dávek do online systému.",
    ),
    (
        "minimální sociální záloha",
        "Nejnižší povinná částka, kterou OSVČ odvádí na sociální pojištění.",
    ),
    (
        "minimální sociální zálohy",
        "Nejnižší povinná částka, kterou OSVČ odvádí na sociální pojištění.",
    ),
    (
        "veřejnoprávních médií",
        "Česká televize a Český rozhlas.",
    ),
    (
        "veřejnoprávní média",
        "Česká televize a Český rozhlas.",
    ),
    (
        "Úřadu práce",
        "Úřad, který vyplácí dávky v nezaměstnanosti, příspěvky na bydlení a další sociální pomoc.",
    ),
    (
        "Úřad práce",
        "Úřad, který vyplácí dávky v nezaměstnanosti, příspěvky na bydlení a další sociální pomoc.",
    ),
    (
        "superdávka",
        "Plán spojit několik sociálních dávek do jednoho systému s jednou žádostí. "
        "Nejde o novou dávku navíc, ale o sjednocení stávajících.",
    ),
    (
        "superdávky",
        "Plán spojit několik sociálních dávek do jednoho systému s jednou žádostí. "
        "Nejde o novou dávku navíc, ale o sjednocení stávajících.",
    ),
    (
        "Čapí hnízdo",
        "Dlouholetá kauza kolem evropské dotace na farmu spojenou s Andrejem Babišem. "
        "Soud řeší, zda byly splněny podmínky pro získání dotace.",
    ),
    (
        "obstrukcemi",
        "Zdržování jednání dlouhými projevy nebo procedurálními návrhy.",
    ),
    (
        "obstrukce",
        "Zdržování jednání dlouhými projevy nebo procedurálními návrhy.",
    ),
    (
        "obstrukcí",
        "Zdržování jednání dlouhými projevy nebo procedurálními návrhy.",
    ),
    (
        "obstrukci",
        "Zdržování jednání dlouhými projevy nebo procedurálními návrhy.",
    ),
    (
        "jednacího řádu",
        "Pravidla hry pro poslance. Určuje, kdo, kdy a jak dlouho smí mluvit.",
    ),
    (
        "jednacím řádem",
        "Pravidla hry pro poslance. Určuje, kdo, kdy a jak dlouho smí mluvit.",
    ),
    (
        "jednacím řádu",
        "Pravidla hry pro poslance. Určuje, kdo, kdy a jak dlouho smí mluvit.",
    ),
    (
        "jednací řád",
        "Pravidla hry pro poslance. Určuje, kdo, kdy a jak dlouho smí mluvit.",
    ),
    (
        "transpozicí",
        "Převedení evropských pravidel do českých zákonů.",
    ),
    (
        "transpozice",
        "Převedení evropských pravidel do českých zákonů.",
    ),
    (
        "transpozici",
        "Převedení evropských pravidel do českých zákonů.",
    ),
    (
        "schodku",
        "Rozdíl mezi tím, co stát vybral, a tím, co utratil navíc.",
    ),
    (
        "schodek",
        "Rozdíl mezi tím, co stát vybral, a tím, co utratil navíc.",
    ),
    (
        "schodkem",
        "Rozdíl mezi tím, co stát vybral, a tím, co utratil navíc.",
    ),
    (
        "fiskálními pravidly",
        "Pravidla, která mají státu připomínat, že kreditka není bezedná.",
    ),
    (
        "fiskální pravidla",
        "Pravidla, která mají státu připomínat, že kreditka není bezedná.",
    ),
    (
        "fiskálních pravidel",
        "Pravidla, která mají státu připomínat, že kreditka není bezedná.",
    ),
    (
        "fiskální limity",
        "Pravidla, která mají státu připomínat, že kreditka není bezedná.",
    ),
    (
        "rozpočtových brzdách",
        "Zákon, který říká: když stát utrácí moc rychle, měl by aspoň občas šlápnout na brzdu.",
    ),
    (
        "rozpočtové brzdy",
        "Zákon, který říká: když stát utrácí moc rychle, měl by aspoň občas šlápnout na brzdu.",
    ),
    (
        "rozpočtových brzd",
        "Zákon, který říká: když stát utrácí moc rychle, měl by aspoň občas šlápnout na brzdu.",
    ),
    (
        "rozpočtového pravidla",
        "Zákon určující, jak může stát plánovat a utrácet peníze.",
    ),
    (
        "rozpočtové pravidlo",
        "Zákon určující, jak může stát plánovat a utrácet peníze.",
    ),
    (
        "harmonizací s evropským právem",
        "Přepisování českých pravidel tak, aby si v Bruselu nemuseli dělat poznámky.",
    ),
    (
        "harmonizace s evropským",
        "Přepisování českých pravidel tak, aby si v Bruselu nemuseli dělat poznámky.",
    ),
    (
        "poslaneckých klubů",
        "Skupiny poslanců jedné strany ve sněmovně.",
    ),
    (
        "poslanecký klub",
        "Skupina poslanců jedné strany ve sněmovně.",
    ),
    (
        "poslanecké kluby",
        "Skupiny poslanců jedné strany ve sněmovně.",
    ),
    (
        "ve výborech",
        "Menší pracovní skupiny poslanců, kde se zákony řeší podrobněji než v hlavním sále.",
    ),
    (
        "do výborů",
        "Zákony se posílají do menších pracovních skupin poslanců, kde se řeší podrobněji než v sále.",
    ),
    (
        "výborů",
        "Menší pracovní skupiny poslanců, kde se zákony řeší podrobněji než v hlavním sále.",
    ),
    (
        "výbory",
        "Menší pracovní skupiny poslanců, kde se zákony řeší podrobněji než v hlavním sále.",
    ),
    (
        "výborem",
        "Menší pracovní skupina poslanců, kde se zákony řeší podrobněji než v hlavním sále.",
    ),
    (
        "výboru",
        "Menší pracovní skupina poslanců, kde se zákony řeší podrobněji než v hlavním sále.",
    ),
    (
        "výbor",
        "Menší pracovní skupina poslanců, kde se zákony řeší podrobněji než v hlavním sále.",
    ),
    (
        "kvorum",
        "Minimální počet poslanců v sále, bez kterého se oficiálně hlasovat nemůže.",
    ),
    (
        "imunitu poslance",
        "Ochrana poslance před trestním stíháním bez souhlasu sněmovny.",
    ),
    (
        "imunita poslance",
        "Ochrana poslance před trestním stíháním bez souhlasu sněmovny.",
    ),
    (
        "imunitu",
        "Ochrana poslance před trestním stíháním bez souhlasu sněmovny.",
    ),
    (
        "imunita",
        "Ochrana poslance před trestním stíháním bez souhlasu sněmovny.",
    ),
    (
        "nařízení Evropské unie",
        "Pravidlo, které platí přímo ve všech členských státech Evropské unie.",
    ),
    (
        "nařízení EU",
        "Pravidlo, které platí přímo ve všech členských státech Evropské unie.",
    ),
    (
        "v demisi",
        "Vláda po pádu nebo po volbách jen spravuje stát a nemá plné pravomoci, dokud nová nesloží slib.",
    ),
    (
        "nedůvěře",
        "Poslanci mohou vyslovit nedůvěru vládě. Projde-li návrh, kabinet musí odstoupit.",
    ),
    (
        "nedůvěru",
        "Poslanci hlasují o tom, zda vláda ztratila důvěru. Projde-li návrh, kabinet padá.",
    ),
    (
        "nedůvěra",
        "Hlasování, při kterém poslanci rozhodnou, zda vláda ztratila důvěru a má odstoupit.",
    ),
    (
        "usneseních",
        "Politická rozhodnutí sněmovny: doporučení, výzvy nebo schválení postupu. Nejde o zákony.",
    ),
    (
        "usnesením",
        "Politické rozhodnutí sněmovny: doporučení, výzva nebo schválení postupu. Není to zákon.",
    ),
    (
        "usnesení",
        "Politické rozhodnutí sněmovny: doporučení, výzva nebo schválení postupu. Není to zákon.",
    ),
    (
        "transparenty",
        "Plakáty v jednacím sále. Poslanci jimi vyjadřují názor; nesmí zakrývat řečníka u pultu.",
    ),
    (
        "transparentem",
        "Plakát v jednacím sále. Poslanci jím vyjadřují názor; nesmí zakrývat řečníka u pultu.",
    ),
    (
        "transparent",
        "Plakát v jednacím sále. Poslanci jím vyjadřují názor; nesmí zakrývat řečníka u pultu.",
    ),
    (
        "gongem",
        "Zvukovým znamením, kterým předsedající ukončí rozpravu a svolá poslance k hlasování.",
    ),
    (
        "gongu",
        "Zvukové znamení, kterým předsedající ukončí rozpravu a svolá poslance k hlasování.",
    ),
    (
        "gong",
        "Zvukové znamení, kterým předsedající ukončí rozpravu a svolá poslance k hlasování.",
    ),
    (
        "Dozimetr",
        "Korupční kauza spojená s pražským dopravním podnikem, kterou vyšetřuje policie.",
    ),
    (
        "dozimetr",
        "Korupční kauza spojená s pražským dopravním podnikem, kterou vyšetřuje policie.",
    ),
    (
        "Agrofertu",
        "Jeden z největších českých holdingů. Babiš ho převedl do svěřenských fondů; spor je, zda na něj má stále vliv.",
    ),
    (
        "agrofertu",
        "Jeden z největších českých holdingů. Babiš ho převedl do svěřenských fondů; spor je, zda na něj má stále vliv.",
    ),
    (
        "Agrofert",
        "Jeden z největších českých holdingů. Babiš ho převedl do svěřenských fondů; spor je, zda na něj má stále vliv.",
    ),
    (
        "svěřenských fondů",
        "Právní schránka, kam Babiš převedl Agrofert. Spor je, zda na firmu pořád reálně vliv má.",
    ),
    (
        "svěřenské fondy",
        "Právní schránka, kam Babiš převedl Agrofert. Spor je, zda na firmu pořád reálně vliv má.",
    ),
    (
        "babišismu",
        "Kupkovo označení pro styl vládnutí: stát slouží tomu, kdo sedí u moci, místo občanům.",
    ),
    (
        "babišismus",
        "Kupkovo označení pro styl vládnutí: stát slouží tomu, kdo sedí u moci, místo občanům.",
    ),
    (
        "nález Ústavního soudu",
        "Rozhodnutí nejvyššího soudního orgánu pro ústavu. V únoru 2020 řešil mimo jiné střet zájmů Andreje Babiše.",
    ),
    (
        "Ústavního soudu",
        "Nejvyšší soudní autorita pro ústavu. V roce 2020 řešil mimo jiné otázky střetu zájmů Andreje Babiše.",
    ),
    (
        "Ústavní soud",
        "Nejvyšší soudní autorita pro ústavu. V roce 2020 řešil mimo jiné otázky střetu zájmů Andreje Babiše.",
    ),
    (
        "kupónovou privatizaci",
        "Privatizace státního majetku v 90. letech pomocí kupónových knížek.",
    ),
    (
        "kupónová privatizace",
        "Privatizace státního majetku v 90. letech pomocí kupónových knížek.",
    ),
    (
        "správní rady VZP",
        "Skupina lidí, která rozhoduje o fungování VZP.",
    ),
    (
        "správní rada VZP",
        "Skupina lidí, která rozhoduje o fungování VZP.",
    ),
    (
        "elektronická sbírka zákonů",
        "Oficiální místo, kde se zveřejňují schválené zákony. Má být plně digitální, systém ale pořád není hotový.",
    ),
    (
        "sbírce zákonů",
        "Oficiální místo, kde se zveřejňují schválené zákony.",
    ),
    (
        "Sbírka zákonů",
        "Oficiální místo, kde se zveřejňují schválené zákony.",
    ),
    (
        "legislativní proces",
        "Cesta zákona od návrhu až po podpis prezidenta.",
    ),
    (
        "služební zákon",
        "Pravidla pro fungování státních úředníků.",
    ),
    (
        "stenoprotokolu",
        "Doslovný přepis všeho, co ve Sněmovně zazní.",
    ),
    (
        "stenoprotokol",
        "Doslovný přepis všeho, co ve Sněmovně zazní.",
    ),
    (
        "organizační výbor",
        "Skupina, která plánuje program schůzí.",
    ),
    (
        "EET",
        "Elektronická evidence tržeb. Každá účtenka hlásila státu, kolik kdo utržil.",
    ),
    (
        "elektronická evidence tržeb",
        "Každá účtenka hlásila státu, kolik kdo utržil. Mladší generace už často netuší, o co šlo.",
    ),
    (
        "stavebního zákona",
        "Pravidla pro povolování staveb. Koalice ho chce zrychlit, opozice varuje před oslabením obcí a úřadů.",
    ),
    (
        "stavební zákon",
        "Pravidla pro povolování staveb. Koalice ho chce zrychlit, opozice varuje před oslabením obcí a úřadů.",
    ),
    (
        "stavební řízení",
        "Úřední koloběh kolem povolení stavby. Debata je o tom, jak ho zkrátit, aniž se rozbije právní jistota.",
    ),
    (
        "stavebních úřadů",
        "Obecní nebo krajské úřady, které rozhodují o stavebních povoleních. Zákon je chce sloučit a zdigitalizovat.",
    ),
    (
        "stavební úřad",
        "Obecní nebo krajský úřad, který rozhoduje o stavebním povolení. Zákon je chce sloučit a zdigitalizovat.",
    ),
    (
        "digitalizaci stavebního řízení",
        "Přesun stavebního úřadu do online systému. Koalice slibuje rychlejší povolení, kritici pochybují, že to funguje.",
    ),
    (
        "digitalizace stavebního řízení",
        "Přesun stavebního úřadu do online systému. Koalice slibuje rychlejší povolení, kritici pochybují, že to funguje.",
    ),
    (
        "městských architektů",
        "Úředníci obcí, kteří dohlížejí na vzhled a soulad staveb s územním plánem.",
    ),
    (
        "městský architekt",
        "Úředník obce, který dohlíží na vzhled a soulad staveb s územním plánem.",
    ),
    (
        "územního plánu",
        "Dokument obce, který určuje, kde a co se smí stavět.",
    ),
    (
        "územní plán",
        "Dokument obce, který určuje, kde a co se smí stavět.",
    ),
    (
        "lex developer",
        "Přezdívka kritiků stavebního zákona: podle nich nahrává velkým developerům.",
    ),
    (
        "příspěvku na mobilitu",
        "Peníze pro lidi se zdravotním omezením na dopravu a cestování.",
    ),
    (
        "příspěvek na mobilitu",
        "Peníze pro lidi se zdravotním omezením na dopravu a cestování.",
    ),
    (
        "sociálním pojištění",
        "Odchozí peníze zaměstnanců a živnostníků na důchody, nemocenskou a podporu v nezaměstnanosti.",
    ),
    (
        "sociální pojištění",
        "Odchozí peníze zaměstnanců a živnostníků na důchody, nemocenskou a podporu v nezaměstnanosti.",
    ),
    (
        "minimální záloha",
        "Nejmenší měsíční částka, kterou musí živnostník odvést na sociální pojištění.",
    ),
    (
        "penzijního spoření",
        "Dobrovolné odkládání peněz na důchod vedle státní penze.",
    ),
    (
        "penzijní spoření",
        "Dobrovolné odkládání peněz na důchod vedle státní penze.",
    ),
    (
        "investičních fond",
        "Společnosti, které spravují peníze investorů, třeba z penzijního spoření.",
    ),
    (
        "investiční fondy",
        "Společnosti, které spravují peníze investorů, třeba z penzijního spoření.",
    ),
    (
        "investiční společnost",
        "Firma, která spravuje peníze investorů podle pravidel zákona.",
    ),
    (
        "státní vyznamenání",
        "Medaile a vyznamenání, která uděluje prezident nebo sněmovna za mimořádné zásluhy.",
    ),
    (
        "kontaktní místo obce",
        "Obecní úřad nebo pobočka, kam občan chodí vyřizovat formalitky místo na radnici.",
    ),
    (
        "podpoře bydlení",
        "Státní pomoc s nájmem nebo hypotékou pro lidi, kteří si sami nemohou bydlení dovolit.",
    ),
    (
        "podpora bydlení",
        "Státní pomoc s nájmem nebo hypotékou pro lidi, kteří si sami nemohou bydlení dovolit.",
    ),
    (
        "osob se zdravotním postižením",
        "Lidé s dlouhodobým zdravotním omezením; v zákoně se často zkracuje na OZP.",
    ),
    (
        "OZP",
        "Osoba se zdravotním postižením.",
    ),
    (
        "(KDU-ČSL)",
        "Křesťanská a demokratická unie, Československá lidová strana.",
    ),
    (
        "(TOP 09)",
        "TOP 09, strana, která se profiluje jako liberálně konzervativní.",
    ),
    (
        "(Piráti)",
        "Česká pirátská strana.",
    ),
    (
        "Motoristů",
        "Motoristé sobě, strana Petra Macinky, která se profiluje jako hnutí za práva řidičů.",
    ),
    (
        "Motoristé",
        "Motoristé sobě, strana Petra Macinky, která se profiluje jako hnutí za práva řidičů.",
    ),
    (
        "(Motoristé)",
        "Motoristé sobě, strana Petra Macinky, která se profiluje jako hnutí za práva řidičů.",
    ),
    (
        "(SPD)",
        "Svoboda a přímá demokracie, strana Tomia Okamury.",
    ),
    (
        "(STAN)",
        "Starostové a nezávislí.",
    ),
    (
        "(ODS)",
        "Občanská demokratická strana.",
    ),
    (
        "(ANO)",
        "Hnutí ANO 2011, strana Andreje Babiše.",
    ),
    (
        "hnutí STAN",
        "Starostové a nezávislí.",
    ),
    (
        "NKÚ",
        "Nejvyšší kontrolní úřad. Kontroluje, jak stát hospodaří s veřejnými penězi.",
    ),
    (
        "VZP",
        "Největší česká zdravotní pojišťovna.",
    ),
    (
        "SFŽP",
        "Státní fond životního prostředí. Platí například čistírny, zateplování nebo projekty proti suchu.",
    ),
    # --- zkratky a specifické pojmy ---
    (
        "návrh z grémia",
        "Návrh pořadu schůze, na kterém se předem domluvili předsedové poslaneckých klubů.",
    ),
    (
        "dohody grémia",
        "Dohoda předsedů klubů o pořadu, přestávce nebo průběhu schůze.",
    ),
    (
        "dohoda z grémia",
        "Dohoda předsedů klubů o pořadu, přestávce nebo průběhu schůze.",
    ),
    (
        "z grémia",
        "Podle dohody předsedů poslaneckých klubů na jejich společném jednání.",
    ),
    (
        "grémia",
        "Jednání předsedů poslaneckých klubů, kde se domlouvají pořad schůze a procedura.",
    ),
    (
        "grémiu",
        "Jednání předsedů poslaneckých klubů, kde se domlouvají pořad schůze a procedura.",
    ),
    (
        "grémium",
        "Jednání předsedů poslaneckých klubů, kde se domlouvají pořad schůze, přestávky a hlasování.",
    ),
    (
        "kuloáru",
        "Chodba vedle jednacího sálu, kam poslanci chodí domlouvat se mimo mikrofon.",
    ),
    (
        "kuloár",
        "Chodba vedle jednacího sálu, kam poslanci chodí domlouvat se mimo mikrofon.",
    ),
    (
        "QR kódy",
        "Čtvercový kód na volebním lístku: nevidomý volič ho načte telefonem a pozná, komu hlasuje.",
    ),
    (
        "QR kódů",
        "Čtvercový kód na volebním lístku: nevidomý volič ho načte telefonem a pozná, komu hlasuje.",
    ),
    (
        "QR kódem",
        "Čtvercový kód na volebním lístku: nevidomý volič ho načte telefonem a pozná, komu hlasuje.",
    ),
    (
        "QR kód",
        "Čtvercový kód na volebním lístku: nevidomý volič ho načte telefonem a pozná, komu hlasuje.",
    ),
    (
        "OSVČ",
        "Osoba samostatně výdělečně činná, tedy živnostník nebo freelancer. Sociální a zdravotní pojištění si platí sám.",
    ),
    (
        "DPP",
        "Dopravní podnik hlavního města Prahy, pražská městská doprava. V kauze Dozimetr jde o jeho zakázky.",
    ),
    (
        "Senátu",
        "Horní komora parlamentu. Může zákon vrátit k přepracování nebo ho zamítnout.",
    ),
    (
        "Senátem",
        "Horní komora parlamentu. Může zákon vrátit k přepracování nebo ho zamítnout.",
    ),
    (
        "senátu",
        "Horní komora parlamentu. Může zákon vrátit k přepracování nebo ho zamítnout.",
    ),
    (
        "Senát",
        "Horní komora parlamentu. Může zákon vrátit k přepracování nebo ho zamítnout.",
    ),
    (
        "senát",
        "Horní komora parlamentu. Může zákon vrátit k přepracování nebo ho zamítnout.",
    ),
    (
        "plénu",
        "Plná sněmovna, tedy všech 200 poslanců v jednacím sále, ne jen výbor.",
    ),
    (
        "plénum",
        "Plná sněmovna, tedy všech 200 poslanců v jednacím sále, ne jen výbor.",
    ),
    (
        "ústava",
        "Základní zákon státu. Změny vyžadují vysokou politickou shodu ve sněmovně i senátu.",
    ),
    (
        "Ústava",
        "Základní zákon státu. Změny vyžadují vysokou politickou shodu ve sněmovně i senátu.",
    ),
)

# Švejkův slovník: box pod článkem (kanonický název, klíč pro vyhledání v textu).
SLOVNIK_BOX: tuple[tuple[str, str], ...] = (
    ("Rozpočtové brzdy", "rozpočtových brzd"),
    ("Fiskální pravidla", "fiskální pravidl"),
    ("Schodek", "schodek"),
    ("Pozměňovací návrh", "pozměňovací návrh"),
    ("První čtení", "první čtení"),
    ("Druhé čtení", "druhé čtení"),
    ("Třetí čtení", "třetí čtení"),
    ("Procedurální návrh", "procedurální návrh"),
    ("Přerušení schůze", "přerušení"),
    ("Senát vrátil zákon", "vrácen senátem"),
    ("Usnesení", "usnesení"),
    ("Kvorum", "kvorum"),
    ("Výbor", "výbor"),
    ("EET", "EET"),
    ("Lex developer", "lex developer"),
    ("Rada ČT", "Rada ČT"),
    ("Landsmanšaft", "landsmanšaft"),
    ("Harmonizace s EU", "harmonizac"),
    ("Příspěvek na mobilitu", "příspěvek na mobilitu"),
    ("OZP", "OZP"),
    ("Minimální záloha", "minimální záloha"),
    ("Penzijní spoření", "penzijní spoření"),
    ("Investiční fondy", "investiční fond"),
    ("Podpora bydlení", "podpoře bydlení"),
    ("Státní vyznamenání", "státní vyznamenání"),
    ("Úřad práce", "Úřad práce"),
    ("Mimořádná schůze", "mimořádn"),
)

def slovnicek_anchor(question: str) -> str:
    """URL kotva z otázky ve slovníčku (např. „Co je obstrukce?“ → obstrukce)."""
    text = question.strip()
    for prefix in ("Co jsou ", "Co je ", "Co je to "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.rstrip("?").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


# Švejkův slovníček: panel vpravo na webu (otázka → odpověď).
SLOVNIČEK: tuple[tuple[str, str], ...] = (
    ("Co je pozměňovací návrh?", "Chvíle, kdy někdo řekne: „Já bych to napsal trochu jinak.“"),
    ("Co je první čtení?", "Rozhoduje se, jestli má zákon pokračovat dál, nebo skončit dřív, než začne."),
    ("Co je druhé čtení?", "Začíná vrtání v detailech a přepisování jednotlivých částí zákona."),
    ("Co je třetí čtení?", "Poslední zastávka před hlasováním. Pak už padne ano, nebo ne."),
    ("Co je procedurální návrh?", "Neřeší se zákon, ale způsob, jak se o něm bude mluvit."),
    ("Co je obstrukce?", "Když se dlouze mluví proto, aby se co nejdéle nehlasovalo."),
    ("Co je přerušení schůze?", "Poslanci si dali pauzu a slíbili, že se k tomu vrátí."),
    ("Co je legislativní nouze?", "Režim, kdy se zákony schvalují rychleji než obvykle."),
    ("Co je mimořádná schůze?", "Schůze svolaná mimo běžný program, když něco spěchá nebo se někdo hodně rozčílí."),
    ("Co je interpelace?", "Čas, kdy se poslanci ptají vlády a vláda odpovídá. Někdy i na položenou otázku."),
    ("Co je důvěra vládě?", "Hlasování, jestli má vláda podporu většiny poslanců."),
    ("Co je nedůvěra vládě?", "Pokus vládu poslat do politického důchodu dřív, než odejde sama."),
    ("Co je koalice?", "Strany, které spolu vládnou a snaží se najít společnou řeč."),
    ("Co je opozice?", "Strany, které nevládnou a hlídají, jestli vláda nevaří z cizích peněz příliš odvážně."),
    ("Co je Senát?", "Druhá komora Parlamentu. Kontroluje zákony, které schválila Sněmovna."),
    ("Co je veto Senátu?", "Senát zákon vrátí nebo navrhne změny. Poslanci ale mohou jeho nesouhlas přehlasovat."),
    ("Co je veto prezidenta?", "Když prezident zákon vrátí poslancům s tím, aby si ho ještě jednou rozmysleli."),
    ("Co jsou rozpočtové brzdy?", "Zákon, který státu připomíná šlápnout na brzdu, když utrácí moc rychle."),
    ("Co jsou fiskální pravidla?", "Pravidla, která mají státu připomínat, že kreditka není bezedná."),
    ("Co je schodek?", "Když stát utratí víc, než vybere. Něco jako když hospoda jede na sekeru."),
    ("Co je EET?", "Elektronická evidence tržeb, každá účtenka hlásila státu, kolik kdo utržil."),
    ("Co je usnesení?", "Stanovisko nebo rozhodnutí sněmovny. Nejde o zákon."),
    ("Co je Dozimetr?", "Korupční kauza spojená s pražským dopravním podnikem, kterou vyšetřuje policie."),
    ("Co je superdávka?", "Plán na sloučení několika sociálních dávek do jednoho systému."),
    ("Co je NKÚ?", "Nejvyšší kontrolní úřad. Kontroluje, jak stát hospodaří s veřejnými penězi."),
    ("Co je VZP?", "Největší česká zdravotní pojišťovna."),
    ("Co je OZP?", "Osoba se zdravotním postižením."),
    ("Co je landsmanšaft?", "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení."),
    ("Co je Rada ČT?", "Skupina, která dohlíží na Českou televizi a vybírá její vedení."),
)


# Švejkův překladač z poslanečtiny: pro rubriky a sociální sítě.
POSLANECINY_PREKLAD: tuple[tuple[str, str], ...] = (
    ("První čtení", "Ještě se nic nerozhodlo"),
    ("Druhé čtení", "Teď se vrtá v paragrafech"),
    ("Třetí čtení", "Poslední šance, pak ano nebo ne"),
    ("Procedurální návrh", "Hádka o tom, jak se budou hádat"),
    ("Přerušení schůze", "Pauza"),
    ("Senát vrátil zákon", "Senát řekl: zkuste to ještě jednou"),
    ("Usnesení", "Vzkaz"),
    ("Interpelace", "Vysvětlování ministrů"),
    ("Výbor", "Menší sněmovna"),
    ("Střet zájmů", "Když politik řeší vlastní byznys"),
    ("Rozpočtové brzdy", "Brzda na státní kreditku"),
    ("Fiskální pravidla", "Pravidla, že kreditka není bezedná"),
    ("Schodek", "Utratili víc, než vybrali"),
    ("Kvorum", "Málo poslanců v sále, hlasovat nejde"),
    ("Lex developer", "Zákon pro velké stavitele"),
    ("EET", "Účtenka hlásí státu každou korunu"),
    ("Odročení", "Dneska už ne"),
)


def slovnicek_box() -> tuple[tuple[str, str], ...]:
    return SLOVNIK_BOX


def slovnicek_entries() -> tuple[tuple[str, str], ...]:
    return SLOVNIČEK


def poslaneciny_entries() -> tuple[tuple[str, str], ...]:
    return POSLANECINY_PREKLAD


def glossary_entries() -> tuple[tuple[str, str], ...]:
    return GLOSSARY
