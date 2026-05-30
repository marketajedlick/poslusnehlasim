"""Občansky srozumitelne glosy k tematum ze snemovny — ve stylu Svejka."""

from __future__ import annotations

import re

# (klicova slova, text kdyz proslo, text kdyz neproslo) — specifictější pravidla dřív
GLOSY: list[tuple[tuple[str, ...], str, str]] = [
    # --- sociální agenda ---
    (
        ("státní sociální podpo", "statni socialni podpo", "117/1995"),
        (
            "Poslušně hlásím, úřady nestihly připravit počítače na nové dávky — "
            "takže to posunuli. Kdo teď chodí na Úřad práce pro příspěvek na bydlení "
            "nebo přídavek na dítě, nemusí se zatím bát, že by se mu všechno přes noc "
            "přeházelo. Prostě to ještě chvíli potrvá, než to sjednotí."
        ),
        (
            "Posun nových dávek neprošel — u úřadu práce zatím platí staré papíry "
            "jako doteď."
        ),
    ),
    (
        ("dávce státní sociální pomoci", "dávka státní sociální pomoc"),
        (
            "Jde o dávky pro lidi v těžké situaci — kdo má málo peněz a potřebuje "
            "pomoc státu. Změna se týká pravidel, kolik a komu se vyplatí."
        ),
        "Úpravy dávek státní sociální pomoci neprošly — současná pravidla platí.",
    ),
    (
        ("životním a existenčním minimu", "životní minimum", "existenční minimum"),
        (
            "Životní a existenční minimum — částka, pod kterou stát považuje život "
            "za příliš chudý. Od toho se odvíjí dávky a některé soudní exekuce. "
            "Když se minimum mění, dotkne se to lidí na sociálních dávkách."
        ),
        "Změna minima neprošla — hranice chudoby zůstávají jako doteď.",
    ),
    (
        ("sociálních služb", "socialnich sluzb", "108/2006"),
        (
            "Jde o to, kam budete chodit pro péči o staré rodiče nebo hendikepované — "
            "zatím pořád na Úřad práce, ne na jiný úřad, jak chtěli. "
            "A pacienti na kyslík doma nebo ventilátor dostanou vyšší příspěvek "
            "na jízdu ještě rok navíc. To se aspoň týká lidí, co to opravdu potřebují."
        ),
        (
            "Úpravy péče a dávek pro hendikepované neprošly — kam chodit a co platí, "
            "zůstává na další kolo."
        ),
    ),
    (
        ("pojistn", "osvč", "5 720", "715", "živnost"),
        (
            "Týká se živnostníků a dalších, kdo platí zálohy na sociálním pojištění sami — "
            "ne běžných zaměstnanců na výplatní pásce. "
            "Od ledna klesne minimální záloha z 5 720 na 5 005 korun měsíčně "
            "(ušetříte zhruba 715 korun); přeplatek vám stát vrátí. "
            "Míň odvodů znamená i míň budoucího důchodu."
        ),
        "Snížení odvodů pro živnostníky neprošlo — zálohy zůstávají.",
    ),
    (
        (
            "penzijního spoření",
            "penzijním spoření",
            "doplňkovém penzijním",
            "doplňkového penz",
            "doplňkové penz",
        ),
        (
            "Doplňkové penzijní spoření — dobrovolné odkládání peněz na důchod vedle státního. "
            "Týká se lidí, kteří si spoří na stáří, často s příspěvkem od zaměstnavatele. "
            "Upraví se podmínky výběru peněz a pravidla pro spořitele — podle toho, co přesně "
            "návrh obsahuje."
        ),
        "Úpravy penzijního spoření neprošly — smlouvy zůstávají podle dnešních pravidel.",
    ),
    (
        ("penz",),
        (
            "Penze a důchody — mění se pravidla pro lidi před odchodem do důchodu i pro důchodce. "
            "Sledujte, jestli jde o výši měsíčního důchodu, dobrovolné spoření nebo věk odchodu."
        ),
        "Úpravy penze neprošly — důchody a spoření zůstávají jako doteď.",
    ),
    # --- rozpočty ---
    (
        ("státním rozpočtu", "státní rozpočet", "rozpočtu čr na rok"),
        (
            "Státní rozpočet — kolik může vláda utratit příští rok na školy, silnice, "
            "armádu i úřady. Platíte to z daní, i když jednotlivé řádky nevidíte. "
            "Kdo čeká na opravu silnice nebo vyšší plat sestře, ten ví, proč se o tom "
            "hádají celé dny."
        ),
        "Rozpočet neprošel — vláda musí přijít s novým návrhem.",
    ),
    (
        ("veřejných rozpočt", "verejnych rozpoct", "rozpočtových pravidel", "rozpoctov"),
        (
            "Šlo o to, kolik smí stát utratit — hlavně na armádu a velké stavby jako dálnice. "
            "Vás to doma u pokladny netankuje, ale z daní se platí i tohle. "
            "Kdo jezdí po rozbitých silnicích, ten chápe, proč se o tom hádají celé dopoledne."
        ),
        (
            "Pravidla, kolik smí stát utratit, neprošla — limity na výdaje zůstávají "
            "jako byly."
        ),
    ),
    (
        ("státního závěrečného účtu", "závěrečný účet"),
        (
            "Účet za minulý rok — kolik stát skutečně utratil a jestli to sedí s rozpočtem. "
            "Občana se to netýká přímo, spíš účetní a kontrolory."
        ),
        "Závěrečný účet neprošel — účetní uzávěrka státu zůstává otevřená.",
    ),
    (
        ("harmonogramu projednávání", "časového harmonogramu", "časového harm.",
         "st. závěrečného účtu"),
        (
            "Harmonogram rozpočtu — kdy se o penězích státu bude mluvit a hlasovat. "
            "Pro vás spíš kalendář politiků než váš diář."
        ),
        "Harmonogram neprošel — termíny rozpočtu zůstávají nejisté.",
    ),
    (
        ("rozpočet sfžp", "rozpočtu sfžp", "sfžp"),
        (
            "Rozpočet fondu životního prostředí — peníze na ochranu přírody "
            "a ekologii. Občana se to netýká u pokladny, spíš dotace a projekty."
        ),
        "Rozpočet SFŽP neprošel.",
    ),
    (
        ("souhlasu s trestním stíháním", "trestním stíháním poslance"),
        (
            "Sněmovna rozhodla, jestli může policie stíhat poslance — "
            "imunita jinak trestní řízení blokuje. Občana se to netýká, "
            "spíš politici a justice."
        ),
        "Souhlas se stíháním poslance nebyl udělen.",
    ),
    (
        ("rozpočtu sfa", "rozpočtu sfdi", "rozpočtu sfpi", "rozpočtu szif",
         "rozpočet sfa", "rozpočet sfdi", "rozpočet sfpi", "rozpočet szif", "státní fond"),
        (
            "Rozpočet státního fondu — peníze na dálnice, bydlení nebo zemědělství. "
            "Dotkne se vás, když jedete po silnici, stavíte nebo farmáříte; jinak spíš "
            "suché číslo v tabulce."
        ),
        "Rozpočet fondu neprošel — peníze zůstávají rozdělené jako doteď.",
    ),
    (
        ("pravidel hospodaření poslaneckých klubů", "poslaneckých klubů"),
        (
            "Kolik peněz dostanou poslanecké kluby na kanceláře a lidi. "
            "Občana se to netýká — to platí daňový poplatník, ale ne u pokladny v obchodě."
        ),
        "Pravidla pro kluby neprošla.",
    ),
    # --- vláda, ústava ---
    (
        ("nedůvěry vládě", "nedůvěru vládě"),
        (
            "Hlasovalo se, jestli vláda padne. Neprošlo — kabinet zůstává. "
            "Pro vás to znamená, že se nemění ministr ani zákony hned teď."
        ),
        "Nedůvěra neprošla — vláda dál sedí.",
    ),
    (
        ("důvěry vládě", "důvěru vládě", "vyslovení důvěry"),
        (
            "Nová vláda potřebovala souhlas sněmovny — poslanci ji potvrdili. "
            "Od té chvíle může vládnout a předkládat zákony. Občan to pozná "
            "až u konkrétních návrhů, ne u sammečítla."
        ),
        "Vláda důvěru nedostala — musela by odstoupit nebo jít znovu k hlasování.",
    ),
    (
        ("ústav. z.", "ústava čr", "ústavní zákon"),
        (
            "Ústava — nejvyšší zákon státu. Když se mění, jde o velké věci: "
            "pravidla voleb, soudů, pravomocí. Občana se to netýká každý den, "
            "ale dotkne se to demokracie jako celku."
        ),
        "Ústavní změna neprošla — ústava zůstává beze změny.",
    ),
    # --- zdravotnictví ---
    (
        ("všeobecné zdravotní pojišťovny", "zdravotní pojišťovny čr", "vzp"),
        (
            "Dosazování nebo odvolávání lidí ve vedení VZP — kdo řídí největší "
            "zdravotní pojišťovnu. Pacienta to netankuje u lékaře hned, "
            "spíš kdo rozhoduje o směru pojišťovny."
        ),
        "Personální změny ve VZP neprošly.",
    ),
    (
        ("přeshraniční spol", "zdravotnické záchrann"),
        (
            "Smlouva se Slovenskem — když vám na dovolené nebo u hranice "
            "přijede záchranka, kdo platí a kdo pomůže. Pro běžný den doma "
            "spíš teoretické, pro cestovatele užitečné."
        ),
        "Smlouva o záchranné službě neprošla.",
    ),
    (
        ("in vitro", "diagnostick", "zkumavk"),
        (
            "Týká se lidí, co chodí na odběry v nemocnici, a sester v laboratoři. "
            "Nemocnice dostanou včas vědět, když hrozí nedostatek zkumavek — "
            "méně zrušených termínů a kratší čekání v chodbě."
        ),
        "Pravidla pro laboratoře neprošla — pro pacienty se zatím nic nemění.",
    ),
    # --- stavební, doprava ---
    (
        ("stavební zákon", "stavební zák", "stavebn"),
        (
            "Stavební zákon určuje, jak získat povolení ke stavbě, přestavbě nebo bourání. "
            "Týká se každého, kdo staví dům, dělá přístavbu nebo čeká na úřad. "
            "Úprava může zkrátit nebo prodloužit řízení u stavebního úřadu — podle znění návrhu."
        ),
        (
            "Stavební zákon určuje povolení ke stavbě a přestavbě. Sněmovna úpravu neschválila — "
            "kdo staví nebo řeší papíry u úřadu, pokračuje podle dnešních pravidel."
        ),
    ),
    (
        ("silničním provozu", "silniční provoz"),
        (
            "Pravidla silnic — technická úprava kvůli EU. Řidiče se může dotknout "
            "papírování k autu nebo homologace; běžná jízda do práce se nemění "
            "každým takovým hlasováním."
        ),
        "Úprava silničního zákona neprošla.",
    ),
    # --- EU a technické novely ---
    (
        ("investičních společnostech", "investiční společnost"),
        (
            "Investiční společnosti spravují peníze investorů a nakupují za ně cenné papíry. "
            "Týká se hlavně firem a lidí, kteří investují přes fondy — ne běžného účtu v bance. "
            "Poslanci sjednotili pravidla dohledu a povinností vůči klientům podle evropských norem."
        ),
        "Úprava pravidel pro investiční společnosti neprošla.",
    ),
    (
        ("rostlinolékařské péči", "rostlinolékař"),
        (
            "Pravidla pro postřiky a péči o rostliny na polích a v zahradách. "
            "Týká se hlavně farmářů a podnikatelů v zemědělství — "
            "běžný občan v bytě to prakticky neřeší. "
            "Úprava sjednotí postupy při registraci přípravků podle evropských norem."
        ),
        "Novela o rostlinolékařské péči neprošla.",
    ),
    (
        ("účetnictví",),
        (
            "Účetnictví — jak firmy a úřady vedou knihy. Transpozice EU, "
            "běžného člověka se netýká, spíš účetní a podnikatele."
        ),
        "Úprava účetnictví neprošla.",
    ),
    (
        ("správě dat", "přístupu k datům"),
        (
            "Jak stát sdílí a chrání data — digitalizace úřadů. "
            "Občana se to dotkne, až bude něco řešit online místo na přepážce."
        ),
        "Zákon o datech neprošel — úřady jedou dál po staru.",
    ),
    (
        ("finančních služb", "smlouv o finančních"),
        (
            "Úpravy kvůli smlouvám o finančních službách — banky a pojišťovny "
            "musí plnit EU pravidla. Běžný účet u banky se nemění každým hlasováním."
        ),
        "Úpravy finančních služeb neprošly.",
    ),
    (
        ("sbírce zákonů",),
        (
            "Technická úprava Sbírky zákonů — kde se zveřejňují zákony. "
            "Právník to potřebuje, občan u snídaně ne."
        ),
        "Úprava Sbírky zákonů neprošla.",
    ),
    # --- státní správa, zaměstnanci ---
    (
        ("státních zaměstnancích", "státní zaměstnanec"),
        (
            "Pravidla pro úředníky — platy, kariéra, dovolená ve státní správě. "
            "Občana se to netýká, ledaže pracujete na úřadě nebo tam čekáte ve frontě."
        ),
        "Novela o státních zaměstnancích neprošla.",
    ),
    (
        ("jednacím řádu ps", "jednacího řádu"),
        (
            "Jednací řád sněmovny — jak poslanci smějí mluvit, kdy hlasovat "
            "a kdo má slovo. Občana se to netýká, spíš pořadatelé televizního přenosu."
        ),
        "Změna jednacího řádu neprošla.",
    ),
    (
        ("veřejného ochránce práv", "veřejném ochránci práv", "veřejný ochránce práv",
         "ochránce práv dětí"),
        (
            "Pravidla volby Veřejného ochránce práv — kdo hlídá stát, "
            "když vám úřad nebo policie ublíží. Občan to pozná, až bude "
            "potřebovat ombudsmana."
        ),
        "Pravidla volby ombudsmana neprošla.",
    ),
    (
        ("státních svátcích", "státní svátek"),
        (
            "Státní svátky — které dny máte volno. Když se seznam mění, "
            "dotkne se to kalendáře a obchodů."
        ),
        "Úprava státních svátků neprošla.",
    ),
    # --- zemědělství ---
    (
        ("dotační programy zemědělství", "szif", "zemědělství pro rok"),
        (
            "Dotace pro farmáře — kolik dostanou na hektar nebo dobytče. "
            "Město to neřeší, vesnice a statky ano."
        ),
        "Dotace pro zemědělství neprošly.",
    ),
    (
        ("grantové agentury", "kontrolní rady grant"),
        (
            "Odměny lidem v grantové agentuře — kdo rozděluje peníze na vědu. "
            "Občana se to netýká, spíš vědce s žádostí o grant."
        ),
        "Návrh o grantové agentuře neprošel.",
    ),
    # --- úvod období, komise ---
    (
        ("inf. o ustavení volební komise", "ustavení volební komise"),
        (
            "Po volbách se nejdřív založí volební komise — ověří, že poslanci "
            "byli zvoleni legálně. Občana se to netýká, to je rozcvička sněmovny."
        ),
        "Ustavení volební komise neprošlo.",
    ),
    (
        ("miv", "mandátového a imunitního výboru"),
        (
            "MIV — výbor, co řeší poslanecké imunity a mandáty. "
            "Občana se to netýká, spíš poslance v průšvihu."
        ),
        "Návrh k MIV neprošel.",
    ),
    (
        ("ověřovatel", "ověření platnosti volby poslanců"),
        (
            "Ověřovatelé — poslanci, kdo kontrolují, že volby poslanců byly v pořádku. "
            "Formální krok po volbách, pro občana prázdná formalita."
        ),
        "Volba ověřovatelů neprošla.",
    ),
    (
        ("místopředsedů ps", "místopředseda ps"),
        (
            "Kolik bude místopředsedů sněmovny — kdo zvedá kladívko, když "
            "předseda není. Politické křeslo, ne vaše."
        ),
        "Počet místopředsedů nebyl schválen.",
    ),
    (
        ("zasedacího pořádku", "zasedací pořádek"),
        (
            "Kdo kde sedí v sále — jako rozdělení míst v kasárnách, "
            "jen dražší stoličky."
        ),
        "Pořádek zasedání nebyl schválen.",
    ),
    (
        ("zřízení stálých komisí", "zřízení sk ", "zřízení stálé komise", "stálé komise pro kontrolu"),
        (
            "Založení kontrolních komisí — BIS, NBÚ, policie. Kdo bude dohlížet "
            "na tajné služby a bezpečnost. Občana se to netýká přímo."
        ),
        "Zřízení komise neprošlo.",
    ),
    (
        ("delegací ps", "stálých delegací"),
        (
            "Kolik poslanců pojede do zahraničních delegací — cestování "
            "za státní peníze. Občana se to netýká."
        ),
        "Počet delegátů nebyl schválen.",
    ),
    (
        ("volebních nákladů", "příspěvek na úhradu volebních"),
        (
            "Kdo dostane peníze na volební kampěň zpět od státu. "
            "Platíte to z daní, ale rozhodují politici o politicích."
        ),
        "Příspěvek na volební náklady neprošel.",
    ),
    (
        ("týrání zvířat",),
        (
            "Usnesení odsuzující týrání zvířat — politické prohlášení, "
            "ne nový trestní zákon. Symbolické, ne soudní."
        ),
        "Usnesení o zvířatech neprošlo.",
    ),
    (
        ("interpelac",),
        (
            "Ministr odpovídal, poslancům to nestačilo, hlasovalo se, jestli stačilo. "
            "Občana se to netýká přímo — to je spíš divadlo pro televizi."
        ),
        "Interpelace neuspěly — debata bez dopadu na váš život.",
    ),
    (
        ("návrh na volbu", "volbu předsedy", "volbu člena", "volba člena"),
        (
            "Volba do funkce — předseda sněmovny, ombudsman, člen rady ČT "
            "nebo kontrolního úřadu. Kdo sedí kde v instituci. Občana se to "
            "netýká u pokladny, spíš kdo má moc v úřadu."
        ),
        "Volba neprošla — ve funkci zůstává předchozí nebo se hledá nový kandidát.",
    ),
    (
        ("vyšetřovací komise", "dozimetr"),
        (
            "Dosazování lidí do komise kolem kauzy Dozimetr. "
            "Kdo sedí kde — to je ve sněmovně vždycky drama."
        ),
        "Dosazování k Dozimetru neprošlo.",
    ),
    (
        ("orgánů poslanecké", "orgánů ps", "změny ve složení orgánů"),
        (
            "Přesazování lidí ve výborech a funkcích — personálka ve velkém. "
            "Občana se netýká, leda že zná někoho z poslanců osobně."
        ),
        "Personálka neprošla.",
    ),
    (
        ("výbor", "personál", "jmenování", "volbu členů", "volba členů", "návrh na odvolání"),
        (
            "Personální volba — kdo sedí v komisi nebo radě. "
            "Občana se to netýká, leda že zná jména z televize."
        ),
        "Personální návrh neprošel.",
    ),
    # --- obecné fallbacky (poslední) ---
    (
        ("sudeton", "landsmanšaft"),
        (
            "Politické usnesení ke sjezdu Sudetoněmců — historie a symbolika, "
            "ne běžný zákon. Občana se to netýká, spíš vztahy se sousedy."
        ),
        "Usnesení ke sjezdu neprošlo.",
    ),
    (
        ("legislativní nouze",),
        (
            "Legislativní nouze — stát může rychleji přijímat zákony v krizi. "
            "Občan to pozná, až se změní pravidla, která musí jít rychle."
        ),
        "Legislativní nouze nebyla potvrzena.",
    ),
    (
        ("zkráceném jednání", "zkrácené jednání", "posouzení podmínek"),
        (
            "Zkrácené jednání — poslanci zrychlí schvalování zákona. "
            "Méně času na debatu, rychlejší výsledek. Občan to pozná, "
            "až zákon projde dřív, než čekal."
        ),
        "Zkrácené jednání nepovolili — zákon se projednává standardně.",
    ),
    (
        ("sloučená rozprava",),
        (
            "Sloučená rozprava — dva body programu najednou, aby se ušetřil čas. "
            "Pro občana stejné jako normální debata, jen kratší procedura."
        ),
        "Sloučená rozprava nebyla schválena.",
    ),
    (
        ("termínu 2. schůze", "2. schůze ps"),
        (
            "Kdy bude další schůze sněmovny — kalendář politiků. "
            "Občana se to netýká."
        ),
        "Termín další schůze nebyl schválen.",
    ),
    (
        ("sk ceú", "ceú"),
        (
            "Založení kontrolní komise — tentokrát CEÚ. Kdo dohlíží na úřady. "
            "Občana se to netýká přímo."
        ),
        "Zřízení komise CEÚ neprošlo.",
    ),
    (
        ("nařízení rady", "diverzif"),
        (
            "EU pravidla o financování — technická transpozice. "
            "Běžného člověka se netýká."
        ),
        "EU nařízení nebylo schváleno k provedení.",
    ),
    (
        ("potvrzení platnosti usnesení", "změna usn"),
        (
            "Potvrzení starých usnesení sněmovny — formální krok po volbách. "
            "Občana se to netýká."
        ),
        "Potvrzení usnesení neprošlo.",
    ),
    (
        ("návrh usnesení", "usnesení ps"),
        (
            "Usnesení sněmovny — politické prohlášení, ne zákon. "
            "Občana se většinou netýká, spíš signalizace postoje stran."
        ),
        "Usnesení neprošlo.",
    ),
    (
        (" - eu", "předpisy eu", "v souladu s předpisy evropsk"),
        (
            "Úprava zákona kvůli pravidlům EU — technická novela. "
            "Doma vás to většinou netankuje, pokud v názvu není daně, dávky nebo silnice."
        ),
        "EU novela neprošla — stávající pravidla platí.",
    ),
    (
        ("vl.n.z.", "vl. n. z."),
        (
            "Změna zákona — podrobnosti jsou v samotném návrhu. "
            "Jako občan sledujte, jestli jde o daně, dávky, silnice nebo úřad."
        ),
        "Návrh zákona neprošel — pro vás se zatím nic nemění.",
    ),
]

# úryvky textů obecných fallback glos — validate na ně upozorní
GENERIC_GLOSA_MARKERS: tuple[str, ...] = (
    "změna zákona — podrobnosti jsou v samotném návrhu",
    "úprava zákona kvůli pravidlům eu",
    "technická novela",
    "politické prohlášení, ne zákon",
    "formální krok po volbách",
    "občana se to netýká přímo",
    "běžného člověka se netýká",
    "procedurální",
    "eu finance —",
    "suchá botanika",
)


def _match_text(t: str) -> tuple[str, str] | None:
    """Nejdelší shoda klíčového slova — aby „penz“ nepřebilo „penzijní spoření“."""
    best: tuple[str, str] | None = None
    best_len = 0
    for klicova, text_ok, text_ne in GLOSY:
        for k in klicova:
            if k in t and len(k) > best_len:
                best = (text_ok, text_ne)
                best_len = len(k)
    return best


def glosa_pro_obcana(
    nazev: str,
    vysvetleni: str = "",
    *,
    proslo: bool = True,
    nahled: bool = False,
) -> str:
    t = (nazev + " " + vysvetleni).lower()
    matched = _match_text(t)
    if matched:
        text_ok, text_ne = matched
        text = text_ok if proslo else text_ne
        if nahled and proslo:
            veta = text.split(".")[0].strip()
            veta = re.sub(r"^Poslušně hlásím,?\s*", "", veta, flags=re.I)
            veta = re.sub(r"^Prošlo\.?\s*", "", veta, flags=re.I)
            if not veta.lower().startswith(("šlo o", "jde o", "poslanci")):
                veta = f"šlo o to, {veta[0].lower()}{veta[1:]}"
            return f"Poslanci mezitím čekali na hlasování — {veta}."
        return text
    if not proslo:
        return "Návrh neprošel — pro vás se zatím nic nemění."
    return ""


def ma_glosu(nazev: str, vysvetleni: str = "", *, proslo: bool = True) -> bool:
    if not proslo:
        return True
    t = (nazev + " " + vysvetleni).lower()
    return _match_text(t) is not None
