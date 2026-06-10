"""Sněmovní pojmy — krátká vysvětlení pro tooltipy v HTML.

Pořadí: delší fráze nahoře, aby se neshodily s kratšími prefixy.
"""

from __future__ import annotations

GLOSSARY: tuple[tuple[str, str], ...] = (
    # --- kontext konkrétních schůzí (delší fráze první) ---
    (
        "nechal počkat, až v sále sedí víc ministrů",
        "Pirát Václav Pláteník měl 14. 1. po obědě domluvit projev proti vládě, který "
        "před polední pauzou přerušili uprostřed věty. Předsedající Barták (Motoristé) "
        "ho před pokračováním nechal chvíli počkat, až v sále sedí víc ministrů. "
        "Nešlo o jmenování ministra životního prostředí: šlo o spor, jestli má vláda "
        "sedět v sále, když o důvěře mluví opozice. Richterová chtěla pauzu, dokud se "
        "nevrátí Babiš; Králíček (Motoristé) to označil za pirátskou obstrukci. "
        "Rezort životního prostředí ten den vedl vicepremiér Macinka jen jako pověřený, "
        "prezident odmítl Filipa Turka a plnohodnotného ministra jmenoval až v únoru "
        "(Igor Červený).",
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
        "Výbor, který posuzuje platnost poslaneckého mandátu a imunitu, tedy ochranu před stíháním za výrok ve sněmovně.",
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
        "Poslanci, kteří při volbě funkcí počítají hlasy, vydávají lístky a dohlíží na průběh.",
    ),
    (
        "místopředsedkyně sněmovny",
        "Zastupuje předsedu: řídí schůzi a rozděluje slovo, když předseda není u kladívka.",
    ),
    (
        "místopředsedou sněmovny",
        "Zastupuje předsedu: řídí schůzi a rozděluje slovo, když předseda není u kladívka.",
    ),
    (
        "místopředseda sněmovny",
        "Zastupuje předsedu: řídí schůzi a rozděluje slovo, když předseda není u kladívka.",
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
        "Poslanci, kteří kontrolují přítomnost v sále a průběh hlasování.",
    ),
    (
        "ověřovatele",
        "Poslanec, který kontroluje přítomnost v sále a průběh hlasování.",
    ),
    (
        "ověřovatel",
        "Poslanec, který kontroluje přítomnost v sále a průběh hlasování.",
    ),
    # --- projednávání zákonů ---
    (
        "zrychlené projednávání",
        "Zkrácené lhůty na projednání zákona, obvykle desítky dnů místo standardních tří měsíců.",
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
        "Návrhy poslanců na úpravu znění zákona nebo rozpočtu ještě před finálním hlasováním.",
    ),
    (
        "pozměňovací návrh",
        "Návrh poslance na úpravu znění zákona nebo rozpočtu ještě před finálním hlasováním.",
    ),
    (
        "třetím čtení",
        "Poslední fáze zákona: jen drobné úpravy, pak může jít k prezidentovi k podpisu.",
    ),
    (
        "třetí čtení",
        "Poslední fáze zákona: jen drobné úpravy, pak může jít k prezidentovi k podpisu.",
    ),
    (
        "druhém čtení",
        "Druhá fáze zákona: poslanci řeší konkrétní paragrafy a hlasují o finální podobě.",
    ),
    (
        "druhé čtení",
        "Druhá fáze zákona: poslanci řeší konkrétní paragrafy a hlasují o finální podobě.",
    ),
    (
        "prvním čtení",
        "První fáze zákona: schvalují se obrysy návrhu, detaily přijdou ve druhém čtení.",
    ),
    (
        "první čtení",
        "První fáze zákona: schvalují se obrysy návrhu, detaily přijdou ve druhém čtení.",
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
        "Elektronický systém (eLegislativa) pro tvorbu a projednávání zákonů na úřadech i ve sněmovně.",
    ),
    (
        "eLegislativa",
        "Elektronický systém pro tvorbu a projednávání zákonů. Má sjednotit práci úřadů a sněmovny.",
    ),
    # --- kola hlasování (rozpočet, volby) ---
    (
        "druhém kole",
        "Druhé hlasování: u rozpočtu další fáze projednávání, u voleb funkcí druhý pokus o obsazení míst.",
    ),
    (
        "druhé kolo",
        "Druhé hlasování: u rozpočtu další fáze, u voleb funkcí druhý pokus, když první neobsadilo všechna místa.",
    ),
    (
        "prvním kole",
        "První hlasování: u rozpočtu schvalují obrysy (ne konečný státní rozpočet), u voleb první pokus.",
    ),
    (
        "první kolo",
        "První hlasování: u rozpočtu schvalují obrysy (ne konečný státní rozpočet), u voleb první pokus.",
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
        "Výbor, který posuzuje platnost poslaneckého mandátu a imunitu poslanců.",
    ),
    (
        "mandátový výbor",
        "Výbor, který posuzuje platnost poslaneckého mandátu a imunitu poslanců.",
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
        "interpelací",
        "Poslanci v debatě vyhrávají otázky ministrům. Odpověď se nehlasuje, jde o veřejnou kontrolu vlády.",
    ),
    (
        "interpelace",
        "Poslanci v debatě vyhrávají otázky ministrům. Odpověď se nehlasuje, jde o veřejnou kontrolu vlády.",
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
        "Okamurova novoročního projevu",
        "Video předsedy sněmovny ze 1. ledna 2026: odmítl posílat zbraně Ukrajině a řekl, že za peníze důchodců nelze kupovat zbraně „k udržování nesmyslné války“.",
    ),
    (
        "videa se Zunou",
        "Bartoš připomněl klipy z minulé sněmovny: předseda klubu SPD Fiala s generálem Zunou točil ponižující videa poté, co Zuna řekl, že pomoc Ukrajině je nutná a Rusko je agresor. Ministr Šťastný (SPD) pak musel na tiskovce mlčet.",
    ),
    (
        "landsmanšaft",
        "Spolek sudetoněmeckých krajanů. Sněmovna usneseními reaguje na jeho sjezdy v Česku.",
    ),
    (
        "landsmanšaftu",
        "Spolek sudetoněmeckých krajanů. Sněmovna usneseními reaguje na jeho sjezdy v Česku.",
    ),
    (
        "superdávka",
        "Nová zastřešující sociální dávka, která má postupně nahradit část stávajících příspěvků státu.",
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
        "usnesením",
        "Politické rozhodnutí sněmovny: doporučení, výzva nebo schválení postupu. Není to zákon.",
    ),
    (
        "usnesení",
        "Politické rozhodnutí sněmovny: doporučení, výzva nebo schválení postupu. Není to zákon.",
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
        "Kauza kolem podezřelých zakázek v Dopravním podniku Prahy a dalších institucích; vyšetřovací komise ji prošetřuje.",
    ),
    (
        "dozimetr",
        "Kauza kolem podezřelých zakázek v Dopravním podniku Prahy a dalších institucích; vyšetřovací komise ji prošetřuje.",
    ),
    (
        "Agrofert",
        "Babišův holding (zemědělství, potraviny, média). U premiéra jde o střet zájmů se státem.",
    ),
    (
        "NKÚ",
        "Nejvyšší kontrolní úřad kontroluje, jak stát a firmy nakládají s veřejnými penězi.",
    ),
    (
        "VZP",
        "Všeobecná zdravotní pojišťovna, největší zdravotní pojišťovna v Česku.",
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
