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
        "volební komisi",
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
        "místopředsedové",
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
        "zpravodajem",
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
        "Zrychlený režim pro spěšné zákony. Vyhlašuje ho předseda Sněmovny na návrh vlády, jen za mimořádných okolností. Zákon pak může projít velmi rychle.",
    ),
    (
        "legislativní nouzi",
        "Zrychlený režim pro spěšné zákony. Vyhlašuje ho předseda Sněmovny na návrh vlády, jen za mimořádných okolností. Zákon pak může projít velmi rychle.",
    ),
    (
        "zkrácení lhůty",
        "Poslanci si zkrátí čas na přípravu dalšího kola, zákon jde dál rychleji.",
    ),
    (
        "zkrácení lhůt",
        "Poslanci si zkrátí čas na přípravu dalšího kola, zákon jde dál rychleji.",
    ),
    (
        "garanční výbor",
        "Výbor, který má zákon na starosti a připraví ho na další hlasování.",
    ),
    (
        "garančního výboru",
        "Výbor, který má zákon na starosti a připraví ho na další hlasování.",
    ),
    (
        "veto",
        "Když Senát nebo prezident zákon vrátí, aby si ho poslanci ještě jednou rozmysleli.",
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
        "Závěrečné hlasování o zákonu ve Sněmovně. Pak jde zákon do Senátu a potom k prezidentovi.",
    ),
    (
        "třetí čtení",
        "Závěrečné hlasování o zákonu ve Sněmovně. Pak jde zákon do Senátu a potom k prezidentovi.",
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
        "Poslední hlasování o zákonu ve Sněmovně (třetí čtení). Pak jde zákon do Senátu a potom k prezidentovi.",
    ),
    (
        "finální hlasování",
        "Poslední hlasování o zákonu ve Sněmovně (třetí čtení). Pak jde zákon do Senátu a potom k prezidentovi.",
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
        "interpelaci",
        "Část jednání, kdy poslanci pokládají otázky členům vlády.",
    ),
    (
        "interpelace",
        "Část jednání, kdy poslanci pokládají otázky členům vlády.",
    ),
    (
        "oprávněný zájem",
        "Důvod, který musíte prokázat, když chcete nahlédnout do údajů, které už nejsou veřejné.",
    ),
    (
        "skutečný majitel",
        "Člověk, který firmu opravdu ovládá, i když na papíře stojí někdo jiný nebo další firma.",
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
        "Jedna sociální dávka, která od října 2025 spojila čtyři dřívější dávky do jedné žádosti. "
        "Nejde o dávku navíc, ale o sjednocení těch starých.",
    ),
    (
        "superdávky",
        "Jedna sociální dávka, která od října 2025 spojila čtyři dřívější dávky do jedné žádosti. "
        "Nejde o dávku navíc, ale o sjednocení těch starých.",
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
        "ratifikací",
        "Konečné potvrzení mezinárodní smlouvy prezidentem. U důležitých smluv k tomu potřebuje souhlas Sněmovny i Senátu.",
    ),
    (
        "ratifikace",
        "Konečné potvrzení mezinárodní smlouvy prezidentem. U důležitých smluv k tomu potřebuje souhlas Sněmovny i Senátu.",
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
        "Korupční kauza v pražském dopravním podniku. Policie ji odhalila v roce 2022, od roku 2025 ji řeší soud.",
    ),
    (
        "dozimetr",
        "Korupční kauza v pražském dopravním podniku. Policie ji odhalila v roce 2022, od roku 2025 ji řeší soud.",
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
        "Elektronická evidence tržeb: podnikatelé hlásí státu, kolik utržili. Původní EET běžela v letech 2016 až 2020, nová verze platí od ledna 2027.",
    ),
    (
        "elektronická evidence tržeb",
        "Systém, kterým podnikatelé hlásí státu své tržby. Původní EET běžela v letech 2016 až 2020, nová verze platí od ledna 2027.",
    ),
    (
        "šedá ekonomika",
        "Peníze a podnikání, které stát oficiálně nevidí, hlavně kvůli nehlášeným tržbám.",
    ),
    (
        "šedou ekonomiku",
        "Peníze a podnikání, které stát oficiálně nevidí, hlavně kvůli nehlášeným tržbám.",
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
        "lex developerem",
        "Přezdívka kritiků stavebního zákona: podle nich nahrává velkým developerům.",
    ),
    (
        "lex developerovi",
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
        "SZIF",
        "Státní zemědělský intervenční fond. Vyplácí dotace farmářům a zemědělcům.",
    ),
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
    ("Ratifikace", "ratifikac"),
    ("Kvorum", "kvorum"),
    ("Výbor", "výbor"),
    ("EET", "EET"),
    ("Lex developer", "lex developer"),
    ("Švarcsystém", "švarcsystém"),
    ("Závislá práce", "závislá práce"),
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

def slovnicek_display_term(label: str) -> str:
    """Zobrazitelný pojem bez úvodního „Co je …“ a koncového „?“."""
    text = label.strip()
    for prefix in ("Co jsou ", "Co je ", "Co je to "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.rstrip("?").strip()


_ABBREV_PAREN = re.compile(r"^\([^)]+\)$")


def _is_acronym_token(token: str) -> bool:
    """Zkratka typu EET, NKÚ, ČT (všechna písmena velká)."""
    letters = [c for c in token if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


def slovnicek_term_label(term: str) -> str:
    """Popisek ve Švejkově slovníčku: zkratky beze změny, ostatní malými."""
    text = term.strip()
    if not text or _ABBREV_PAREN.match(text):
        return text
    return " ".join(
        part if _is_acronym_token(part) else part.lower() for part in text.split()
    )


def slovnicek_anchor(question: str) -> str:
    """URL kotva z pojmu ve slovníčku (např. „obstrukce“ → obstrukce)."""
    text = slovnicek_display_term(question).lower()
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def slovnicek_term_slug(term: str) -> str:
    """Slug pro `/slovnicek/{slug}/` — jako `slovnicek_anchor`, aliasy míří na kanonickou stránku."""
    return slovnicek_canonical_slug(slovnicek_anchor(term))


# Švejkův slovníček: panel vpravo na webu (pojem → vysvětlení).
SLOVNIČEK: tuple[tuple[str, str], ...] = (
    ("pozměňovací návrh", "Chvíle, kdy někdo řekne: „Já bych to napsal trochu jinak.“"),
    ("první čtení", "Rozhoduje se, jestli má zákon pokračovat dál, nebo skončit dřív, než začne."),
    ("druhé čtení", "Začíná vrtání v detailech a přepisování jednotlivých částí zákona."),
    (
        "třetí čtení",
        "Třetí čtení je závěrečné hlasování o zákonu ve Sněmovně. Nové změny už navrhovat nejde, "
        "poslanci hlasují o pozměňovacích návrzích z druhého čtení a pak o celém zákonu. "
        "Když projde, míří do Senátu a potom k prezidentovi.",
    ),
    ("procedurální návrh", "Neřeší se zákon, ale způsob, jak se o něm bude mluvit."),
    (
        "obstrukce",
        "Obstrukce znamená zdržování jednání, nejčastěji dlouhými projevy nebo opakovanými "
        "procedurálními návrhy. Cílem je oddálit hlasování, ne vyhrát debatu argumentem. "
        "Ve Sněmovně se o ní mluví, když opozice chce zpomalit zákon.",
    ),
    ("přerušení schůze", "Poslanci si dali pauzu a slíbili, že se k tomu vrátí."),
    (
        "legislativní nouze",
        "Legislativní nouze je zvláštní režim pro opravdu spěšné zákony. Vyhlašuje ji předseda "
        "Sněmovny na návrh vlády, a jen za mimořádných okolností, třeba když hrozí velké škody "
        "nebo je ohrožena bezpečnost. Zákon pak přeskočí první čtení a třetí může přijít hned po druhém.",
    ),
    ("zkrácení lhůty", "Poslanci si zkrátí čas na přípravu dalšího kola, zákon jde dál rychleji."),
    (
        "rafinérská marže",
        "Rozdíl mezi cenou ropy, kterou rafinérie koupí, a cenou paliva, které prodá. Když palivo zdraží víc než ropa, marže roste.",
    ),
    (
        "firemní dluhopis",
        "Půjčka firmě. Koupíte papír, firma slíbí vrátit peníze i s úrokem. Když nesplatí, můžete o peníze přijít, klidně o všechny.",
    ),
    ("garanční výbor", "Výbor, který má zákon na starosti a připraví ho na další hlasování."),
    ("veto", "Když Senát nebo prezident zákon vrátí, aby si ho poslanci ještě jednou rozmysleli."),
    ("mimořádná schůze", "Schůze svolaná mimo běžný program, když něco spěchá nebo se někdo hodně rozčílí."),
    (
        "interpelace",
        "Interpelace je část jednání, kdy poslanci kladou otázky ministrům a premiérovi. "
        "Vláda má odpovídat, i když odpověď někdy míjí položenou otázku. "
        "Lidsky řečeno: čas na veřejné vysvětlování.",
    ),
    (
        "oprávněný zájem",
        "Důvod, který musíte prokázat, když chcete nahlédnout do údajů, které už nejsou veřejné. "
        "Nestačí zvědavost, potřebujete věcný důvod.",
    ),
    (
        "skutečný majitel",
        "Člověk, který firmu ve skutečnosti vlastní nebo ovládá, i když na papíře stojí někdo jiný nebo další firma.",
    ),
    ("důvěra vládě", "Hlasování, jestli má vláda podporu většiny poslanců."),
    ("nedůvěra vládě", "Pokus vládu poslat do politického důchodu dřív, než odejde sama."),
    ("koalice", "Strany, které spolu vládnou a snaží se najít společnou řeč."),
    ("opozice", "Strany, které nevládnou a hlídají, jestli vláda nevaří z cizích peněz příliš odvážně."),
    ("Senát", "Druhá komora Parlamentu. Kontroluje zákony, které schválila Sněmovna."),
    (
        "veto Senátu",
        "Senát zákon zamítne, nebo ho vrátí se změnami. U běžných zákonů ho poslanci můžou "
        "přehlasovat 101 hlasy, u ústavních ne.",
    ),
    ("veto prezidenta", "Když prezident zákon vrátí poslancům s tím, aby si ho ještě jednou rozmysleli."),
    ("rozpočtové brzdy", "Pravidla v zákoně o rozpočtové odpovědnosti, která státu připomínají šlápnout na brzdu, když se moc zadlužuje."),
    ("fiskální pravidla", "Pravidla, která mají státu připomínat, že kreditka není bezedná."),
    ("schodek", "Když stát utratí víc, než vybere. Něco jako když hospoda jede na sekeru."),
    ("EET", "Elektronická evidence tržeb: podnikatelé hlásí státu, kolik utržili. Původní EET běžela v letech 2016 až 2020, nová verze platí od ledna 2027."),
    ("elektronická evidence tržeb", "Systém, kterým podnikatelé hlásí státu své tržby. Původní EET běžela v letech 2016 až 2020, nová verze platí od ledna 2027."),
    ("šedá ekonomika", "Peníze a podnikání, které stát oficiálně nevidí, hlavně kvůli nehlášeným tržbám."),
    (
        "švarcsystém",
        "Když člověk dělá práci jako zaměstnanec, ale na papíře je živnostník. Firma šetří na odvodech, člověk přijde o jistoty.",
    ),
    (
        "závislá práce",
        "Práce, která vypadá jako zaměstnání: někdo řídí, kontroluje a určuje, co a kdy se dělá. Od toho se odvíjí, jestli jste zaměstnanec.",
    ),
    ("závěrečné hlasování", "Poslední hlasování o zákonu ve Sněmovně. Pak jde zákon do Senátu a potom k prezidentovi."),
    ("usnesení", "Stanovisko nebo rozhodnutí sněmovny. Nejde o zákon."),
    (
        "ratifikace",
        "Ratifikace je konečné potvrzení mezinárodní smlouvy prezidentem. U důležitých smluv "
        "k tomu potřebuje souhlas Sněmovny i Senátu, bez něj ji ratifikovat nesmí. Poslanci "
        "o souhlasu hlasují podobně jako o zákonu, jen bez pozměňovacích návrhů.",
    ),
    ("Dozimetr", "Korupční kauza v pražském dopravním podniku. Policie ji odhalila v roce 2022, od roku 2025 ji řeší soud."),
    ("superdávka", "Jedna sociální dávka, která spojila čtyři dřívější dávky pro lidi s nízkými příjmy. Platí od října 2025."),
    ("NKÚ", "Nejvyšší kontrolní úřad. Kontroluje, jak stát hospodaří s veřejnými penězi."),
    ("VZP", "Největší česká zdravotní pojišťovna."),
    (
        "OZP",
        "OZP znamená osoba se zdravotním postižením. Ve Sněmovně se zkratka objevuje u dávek, "
        "průkazů a příspěvků na péči nebo mobilitu. Nejde o Oborovou zdravotní pojišťovnu, "
        "to je něco jiného.",
    ),
    ("landsmanšaft", "Organizace sdružující část sudetských Němců a jejich potomků po poválečném vysídlení."),
    ("Rada ČT", "Skupina, která dohlíží na Českou televizi a vybírá její vedení."),
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


# ---------------------------------------------------------------------------
# Stránky pojmů /slovnicek/{slug}/ — SEO rozšíření
# ---------------------------------------------------------------------------

# Pojmy, které sdílí jednu stránku: alias slug → kanonický slug.
# Alias zůstává v SLOVNIČEK kvůli značkování textů, ale vlastní stránku nemá
# (na staré URL se exportuje přesměrování).
SLOVNICEK_SLUG_ALIASES: dict[str, str] = {
    "elektronicka-evidence-trzeb": "eet",
}


# Rozšířený obsah pro nejhledanější pojmy (podle Google Search Console, 11/2026).
# Klíč = kanonický slug. Pole:
#   title    – volitelný vlastní <title> (bez „| Poslušně hlásím“)
#   meta     – meta description (≤ ~155 znaků), jasná odpověď + háček
#   sections – (nadpis-otázka, odstavec); jdou i do FAQ JSON-LD
#   related  – pojmy ze SLOVNIČEK pro „Souvisí s tím“
SLOVNICEK_DETAIL: dict[str, dict] = {
    "ozp": {
        "title": "OZP: co znamená zkratka, průkaz TP, ZTP a ZTP/P",
        "meta": (
            "OZP znamená osoba se zdravotním postižením. Co je průkaz TP, ZTP a ZTP/P, "
            "co znamená „vhodné pro OZP“ v inzerátu a co k tomu řeší Sněmovna."
        ),
        "sections": (
            (
                "Co znamená zkratka OZP?",
                "OZP je osoba se zdravotním postižením. Zkratku uvidíte v inzerátech práce, "
                "na úřadech, u dávek i ve sněmovních tiscích. Stejnou zkratku používá i Oborová "
                "zdravotní pojišťovna, ale ve Sněmovně a v pracovních inzerátech jde skoro vždy "
                "o osobu se zdravotním postižením.",
            ),
            (
                "Jaký je rozdíl mezi TP, ZTP a ZTP/P?",
                "Jsou to tři stupně průkazu osoby se zdravotním postižením, který vydává Úřad práce. "
                "TP je pro těžce postižené, ZTP pro zvlášť těžce postižené a ZTP/P pro zvlášť těžce "
                "postižené, kteří potřebují průvodce. Podle stupně má držitel nárok například na "
                "vyhrazené místo k sezení (už od TP), MHD zdarma a slevu na jízdném (od ZTP). "
                "Parkovací průkaz nevydává Úřad práce, ale obec, a jen držitelům ZTP a ZTP/P.",
            ),
            (
                "Co znamená „vhodné pro OZP“ v inzerátu?",
                "Že práci zvládne i člověk se zdravotním omezením. Pro zaměstnání se za OZP považují "
                "lidé uznaní invalidními (v kterémkoli ze tří stupňů) a lidé, které úřad uznal za "
                "zdravotně znevýhodněné. Firmy s více než 25 zaměstnanci musí zaměstnávat aspoň 4 % "
                "lidí se zdravotním postižením, nebo místo toho odebírat výrobky a služby od firem, "
                "kde lidé se zdravotním postižením tvoří většinu zaměstnanců, případně zaplatit "
                "odvod státu. Způsoby jde kombinovat.",
            ),
            (
                "Jaké dávky se OZP týkají?",
                "Nejčastěji příspěvek na mobilitu, příspěvek na zvláštní pomůcku a příspěvek na péči. "
                "O jejich výši a podmínkách rozhoduje zákon, takže se k nim Sněmovna pravidelně vrací, "
                "typicky při valorizaci nebo při změnách sociálních dávek.",
            ),
        ),
        "related": ("superdávka",),
    },
    "interpelace": {
        "title": "Interpelace: co to je a co znamená interpelovat",
        "meta": (
            "Interpelace je otázka poslance ministrovi nebo premiérovi, na kterou musí odpovědět. "
            "Jak probíhají ústní a písemné interpelace a co znamená interpelovat."
        ),
        "sections": (
            (
                "Co znamená interpelovat?",
                "Interpelovat znamená veřejně se zeptat člena vlády na něco, co spadá do jeho "
                "práce. Právo interpelovat má podle Ústavy každý poslanec a ministr musí odpovědět. "
                "Je to jeden z hlavních nástrojů, kterými Sněmovna kontroluje vládu.",
            ),
            (
                "Jak probíhají ústní interpelace?",
                "Ve Sněmovně mají vyhrazený čas, ve čtvrtek odpoledne. Nejdřív přijdou na řadu "
                "otázky na premiéra, potom na ostatní ministry. Pořadí poslanců se losuje, takže se často stane, "
                "že na dotaz nedojde, nebo že ministr zrovna chybí a odpoví písemně.",
            ),
            (
                "Co je písemná interpelace?",
                "Poslanec pošle otázku ministrovi písemně a ten má na odpověď 30 dní. Když poslance "
                "odpověď neuspokojí, může ji dát Sněmovně k projednání a ta může s odpovědí vyslovit "
                "nesouhlas. Ministr pak musí do 30 dní napsat novou odpověď. Jiný trest nehrozí, "
                "ale je to veřejná výtka.",
            ),
        ),
        "related": ("opozice", "koalice", "nedůvěra vládě"),
    },
    "ratifikace": {
        "title": "Ratifikace: co to je a co znamená ratifikovat smlouvu",
        "meta": (
            "Ratifikace je konečné potvrzení mezinárodní smlouvy. Kdo ji ratifikuje, proč k tomu "
            "potřebuje souhlas Sněmovny a Senátu a co znamená ratifikovat."
        ),
        "sections": (
            (
                "Co znamená ratifikovat?",
                "Ratifikovat znamená definitivně potvrdit mezinárodní smlouvu, kterou vláda "
                "vyjednala a podepsala. Teprve po ratifikaci je pro Česko závazná. Samotný podpis "
                "ministra je jen slib, že se o smlouvě bude doma rozhodovat.",
            ),
            (
                "Kdo smlouvu ratifikuje?",
                "Prezident. U důležitých smluv, třeba když upravují práva a povinnosti lidí, jde "
                "o spojenectví nebo mír, o členství v mezinárodní organizaci, o obecná hospodářská "
                "pravidla nebo o věci, které jinak musí řešit zákon, ale smí ratifikovat jen se "
                "souhlasem obou komor Parlamentu. Proto o nich hlasuje Sněmovna i Senát.",
            ),
            (
                "Jak o ratifikaci hlasuje Sněmovna?",
                "Poslanci smlouvu nemůžou přepsat, protože ji vyjednaly dva nebo víc států. Můžou jen "
                "souhlasit, nesouhlasit nebo rozhodnutí odložit. Obvykle stačí většina přítomných "
                "poslanců. Smlouvy, které přenášejí pravomoci na mezinárodní organizaci, potřebují "
                "tři pětiny všech poslanců, tedy 120, a tři pětiny přítomných senátorů.",
            ),
        ),
        "related": ("Senát", "usnesení"),
    },
    "prvni-cteni": {
        "meta": (
            "První čtení je první kolo projednávání zákona ve Sněmovně. Poslanci rozhodnou, "
            "jestli zákon zamítnou, vrátí, nebo pošlou do výborů. Jak to probíhá."
        ),
        "sections": (
            (
                "Co se v prvním čtení děje?",
                "Navrhovatel zákon představí a poslanci debatují o jeho smyslu, ne o detailech. "
                "Pozměňovací návrhy se v prvním čtení podávat nedají. Na konci Sněmovna hlasuje, "
                "jestli zákon zamítne, vrátí k dopracování, nebo ho přikáže výborům.",
            ),
            (
                "Co následuje po prvním čtení?",
                "Zákon jde do garančního výboru, případně i do dalších výborů. Ty mají na jeho "
                "projednání obvykle 60 dní a mohou navrhnout změny. Pak přichází druhé čtení.",
            ),
            (
                "Může zákon projít už v prvním čtení?",
                "Ano. Když spěchá nebo je jednoduchý, může Sněmovna souhlasit s tím, že ho schválí "
                "hned v prvním čtení. Stačí ale, aby proti tomu do konce obecné rozpravy vznesly "
                "námitku dva poslanecké kluby nebo 50 poslanců. U ústavních zákonů a státního "
                "rozpočtu tahle zkratka vůbec nejde.",
            ),
        ),
        "related": ("druhé čtení", "třetí čtení", "garanční výbor", "zkrácení lhůty"),
    },
    "druhe-cteni": {
        "meta": (
            "Druhé čtení je fáze, kdy poslanci zákon upravují pozměňovacími návrhy. "
            "Jak druhé čtení probíhá a proč se v něm často zdržuje."
        ),
        "sections": (
            (
                "Co se ve druhém čtení děje?",
                "Navrhovatel zákon znovu představí a zpravodaj řekne, jaké změny doporučil výbor. "
                "Pak proběhne obecná rozprava a podrobná, ve které můžou poslanci podávat další "
                "pozměňovací návrhy. Ve druhém čtení se o nich ještě nehlasuje, jen se sbírají.",
            ),
            (
                "Proč druhé čtení trvá dlouho?",
                "Protože do podrobné rozpravy se může přihlásit kdokoli a návrhů může být desítky. "
                "Opozice tu často zdržuje, aby se zákon nedostal ke hlasování. Druhé čtení je proto "
                "jedním z oblíbených míst obstrukce.",
            ),
            (
                "Co následuje po druhém čtení?",
                "Garanční výbor posoudí všechny pozměňovací návrhy a doporučí, jak o nich hlasovat. "
                "Třetí čtení může začít obvykle nejdřív 14 dní poté, co poslanci návrhy dostanou.",
            ),
        ),
        "related": ("první čtení", "třetí čtení", "pozměňovací návrh", "obstrukce"),
    },
    "treti-cteni": {
        "meta": (
            "Třetí čtení je závěrečné hlasování o zákonu ve Sněmovně. Co se v něm ještě "
            "smí měnit, kolik hlasů je potřeba a kam zákon jde potom."
        ),
        "sections": (
            (
                "Co se ve třetím čtení ještě smí měnit?",
                "Skoro nic. Jde jen opravit chyby, posunout datum účinnosti, sladit text s už "
                "podanými pozměňovacími návrhy, nebo navrhnout, ať se druhé čtení zopakuje. Hlasuje "
                "se o pozměňovacích návrzích z druhého čtení a nakonec o zákonu jako celku.",
            ),
            (
                "Kolik hlasů zákon potřebuje?",
                "Běžný zákon potřebuje většinu přítomných poslanců. Ústavní zákon potřebuje tři "
                "pětiny všech poslanců, tedy aspoň 120 hlasů.",
            ),
            (
                "Kam jde zákon po třetím čtení?",
                "Do Senátu, který má 30 dní. Senát ho může schválit, zamítnout, vrátit s úpravami, "
                "nebo se nevyjádřit (pak platí, že souhlasí). Potom zákon podepisuje prezident, "
                "který ho může vetovat.",
            ),
        ),
        "related": ("druhé čtení", "závěrečné hlasování", "Senát", "veto"),
    },
    "obstrukce": {
        "title": "Obstrukce: co to je a co znamená obstruovat",
        "meta": (
            "Obstrukce je záměrné zdržování jednání, aby se nehlasovalo. Jak poslanci obstruují, "
            "co znamená obstruovat a jak se s tím Sněmovna vypořádává."
        ),
        "sections": (
            (
                "Co znamená obstruovat?",
                "Obstruovat znamená zdržovat. Ve Sněmovně jde o to, aby se o zákonu nehlasovalo, "
                "nebo aby se hlasovalo co nejpozději. Je to legální nástroj, hlavně opozice, který "
                "nepotřebuje většinu. Stačí čas a vytrvalost.",
            ),
            (
                "Jak obstrukce vypadá?",
                "Nejčastěji jsou to dlouhé projevy. Přednostní právo mají hlavně ministři, předsedové "
                "klubů a vedení Sněmovny. Od září 2026 ale předsedové klubů můžou mimo rozpravu mluvit "
                "nanejvýš 30 minut a jen jednou za bod, bez limitu zůstali jen členové vlády. Dalšími "
                "prostředky jsou opakované procedurální návrhy, žádosti o přestávku na poradu klubu "
                "nebo spory o program schůze.",
            ),
            (
                "Jak se dá obstrukce ukončit?",
                "Většina může omezit délku a počet vystoupení, pevně zařadit bod na konkrétní čas "
                "nebo jednat déle do noci (třetí čtení ale ani tak ne po 21. hodině). Od září 2026 "
                "může výjimečně určit i čas hlasování, rozprava pak skončí, i když jsou přihlášení "
                "další řečníci. Každý takový krok se ale musí odhlasovat, a to zase stojí čas.",
            ),
        ),
        "related": ("procedurální návrh", "legislativní nouze", "opozice", "druhé čtení"),
    },
    "veto": {
        "title": "Veto: co to je a co znamená vetovat zákon",
        "meta": (
            "Veto znamená, že Senát nebo prezident vrátí zákon Sněmovně. Co znamená vetovat, "
            "kolik hlasů je potřeba k přehlasování veta a jak dlouho to trvá."
        ),
        "sections": (
            (
                "Co znamená vetovat zákon?",
                "Vetovat znamená odmítnout podepsat nebo schválit zákon a vrátit ho zpět. "
                "U běžných zákonů je veto jen odkladné. Zákon tím nekončí, jen se o něm musí ve Sněmovně "
                "hlasovat znovu. Výjimkou jsou ústavní a volební zákony, ty bez souhlasu Senátu "
                "neprojdou.",
            ),
            (
                "Kolik hlasů je potřeba k přehlasování veta?",
                "Nadpoloviční většina všech poslanců, tedy aspoň 101 hlasů. Nezáleží na tom, kolik "
                "poslanců je zrovna v sále. Proto je přehlasování veta pro vládu těžší než běžné "
                "schválení zákona.",
            ),
            (
                "Jak se liší veto Senátu a veto prezidenta?",
                "Senát může zákon zamítnout, nebo ho vrátit s pozměňovacími návrhy. Ty může "
                "Sněmovna přijmout běžnou většinou. Prezident může zákon vrátit do 15 dnů od "
                "doručení, ale ústavní zákony vetovat nesmí.",
            ),
        ),
        "related": ("veto Senátu", "veto prezidenta", "Senát", "třetí čtení"),
    },
    "superdavka": {
        "title": "Superdávka: co to je, které dávky slučuje a jaký je zákon",
        "meta": (
            "Superdávka je jedna sociální dávka místo čtyř, platí od října 2025. Které dávky "
            "nahradila, jak se úředně jmenuje a co s ní dělá Sněmovna."
        ),
        "sections": (
            (
                "Které dávky superdávka slučuje?",
                "Příspěvek na živobytí, doplatek na bydlení, příspěvek na bydlení a přídavek na "
                "dítě. Místo čtyř různých žádostí a čtyř výpočtů je jedna žádost a jeden výpočet "
                "podle příjmů a nákladů celé domácnosti. Vyplácí ji Úřad práce.",
            ),
            (
                "Jak se superdávka úředně jmenuje?",
                "Dávka státní sociální pomoci, podle zákona č. 151/2025 Sb. „Superdávka“ je "
                "novinářská přezdívka, kterou dnes používají i politici.",
            ),
            (
                "Jaký je stav zákona o superdávce?",
                "Zákon schválila ještě Fialova vláda a platí od října 2025. Přechod lidí, kteří "
                "dostávali staré dávky, se odložil na červenec 2026. Podoba superdávky se ale mění "
                "podle toho, kdo vládne, a další úpravy, o kterých Sněmovna jedná, sledujeme ve "
                "vydáních níže.",
            ),
        ),
        "related": ("OZP", "schodek", "fiskální pravidla"),
    },
    "eet": {
        "title": "EET: co je elektronická evidence tržeb a koho se týká",
        "meta": (
            "EET, elektronická evidence tržeb, posílá údaje o tržbách finanční správě. Jak "
            "fungovala, proč skončila a co přináší EET 2.0 od ledna 2027."
        ),
        "sections": (
            (
                "Jak EET fungovala?",
                "Pokladna při každé platbě poslala údaje o tržbě finanční správě a na účtenku "
                "se vytiskl kód, kterým šlo účtenku ověřit. Cílem bylo omezit neevidované tržby "
                "a šedou ekonomiku.",
            ),
            (
                "Koho se EET týkala?",
                "Od prosince 2016 restaurací a hotelů, od března 2017 obchodů. Další vlny pro "
                "řemeslníky, stánkaře a ostatní podnikatele se odkládaly, nejdřív kvůli Ústavnímu "
                "soudu, pak kvůli covidu. V roce 2020 byla evidence pozastavena a od roku 2023 "
                "zrušena.",
            ),
            (
                "Vrací se EET?",
                "Ano. Sněmovna v roce 2026 schválila EET 2.0 (zákon č. 180/2026 Sb.), platí od "
                "ledna 2027. Evidují se jen platby při osobním kontaktu: hotově, kartou nebo QR "
                "kódem. Převody na účet a platby faktur ne. Povinná papírová účtenka se nevrací. "
                "Kdo má výjimku, stanoví zákon, a co se na něm ještě mění, sledujeme ve vydáních níže.",
            ),
        ),
        "related": ("šedá ekonomika", "švarcsystém"),
    },
}


def slovnicek_canonical_slug(slug: str) -> str:
    """Slug stránky, na které pojem skutečně žije (aliasy → kanonický slug)."""
    return SLOVNICEK_SLUG_ALIASES.get(slug, slug)


def slovnicek_pages() -> tuple[tuple[str, str], ...]:
    """Pojmy, které mají vlastní stránku: bez aliasů a bez duplicitních slugů."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for term, answer in SLOVNIČEK:
        slug = slovnicek_anchor(term)
        if slug in SLOVNICEK_SLUG_ALIASES or slug in seen:
            continue
        seen.add(slug)
        out.append((term, answer))
    return tuple(out)


def slovnicek_detail(slug: str) -> dict:
    """Rozšířený obsah stránky pojmu (prázdný dict, když není)."""
    return SLOVNICEK_DETAIL.get(slovnicek_canonical_slug(slug), {})
