# Diary: ADF-katalogudtræk skrev én kolonne — og ingen af de fire led nedenunder sagde fra

En Copy-aktivitet i Azure Data Factory, der udtrækker kildesystemets
informationsskema fra en DB2-forbindelse ind i en metadata-tabel, havde i fire
måneder skrevet præcis én kolonne til sink. Resten stod NULL. Ingen pipeline
fejlede, ingen alarm gik, og de views der forbruger tabellen returnerede nul
rækker eller faldt tavst tilbage på et manuelt vedligeholdt alternativ.

Opgaven er at rette pipelinen til det mønster, den tilsvarende SQL Server-variant
allerede bruger, og at skrive et runbook-afsnit med snapshot, gendannelse og
efterkontrol. Kundeopgave — indhold her holdes på leveranceniveau.

## Step 1: Diagnose, beslutning om placering, og rammerne for holdet

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Opgave i kundens repo `C:\claudes_folder\repos\DLBR-DataEstate2026`, branch `feature/o90-enriched-v2`. Benny har eksplicit bedt om denne ændring. […] Filen `solutions/data_factory/pipeline/Extract InformationSchema Object DB2.json` skriver kun én kolonne til sink. […] To samvirkende årsager: 1. `translator.mappings` (linje 75-92) indeholder ét enkelt element […] I ADF er `mappings` eksplicit og udtømmende — der auto-mappes ikke resten. 2. Kildeforespørgslens aliasser er UPPER_SNAKE […] mens sink-tabellens kolonner er PascalCase. […] Kritisk detalje, der skal håndteres bevidst: DB2 folder unquoted identifiers til STORE BOGSTAVER […] Brug derfor quoted identifiers i DB2 (`AS \"SchemaName\"`)."

Efterfulgt af koordinatorens svar på mit placeringsspørgsmål: "Valget er C. Én
opskrift, ét sted. […] 24.3 reduceres til en peger på 25 og beholder KUN det, der
er specifikt for de tre nye tabeller. […] Skriv hvorfor fejlen ikke blev opdaget
i fire måneder […] Efterkontrollen skal også dække, at antallet af rækker pr.
tabel er uændret for de EKSISTERENDE tabeller."

**Interpretation:** Diagnosen var stillet på forhånd og verificeret mod den
kørende database, ikke gættet. Min opgave var ikke at genfinde fejlen, men at
efterprøve den i koden, finde det den bestilte løsning ville kollidere med, og
sætte en builder på selve rettelsen.

**Inferred intent:** Det underliggende mål er ikke kun at få kolonnerne udfyldt.
Det er at efterlade et dokument, der gør fejlen umulig at gentage — og at gøre
det uden at skabe to konkurrerende opskrifter på det samme snapshot.

### What I did

Læste den fejlende pipeline-JSON og dens fungerende søstervariant mod en anden
kildesystemtype side om side, samt sink-tabellens DDL. Bekræftede begge
årsagsled: mapping-blokken indeholder ét element, og kildeforespørgslens ydre
`SELECT` bruger `,*` med aliasser i en anden navnekonvention end sinkens
kolonner. Fandt via `git show` den commit, der indførte mapping-blokken, og at
den kom ind sammen med en helt anden pipeline — altså som sidegevinst, ikke som
en bevidst mapping-beslutning.

Sammenlignede branchen mod `main` for at se, om pipelinen var ændret på
feature-branchen. Den var identisk, så rettelsen rammer samme fil begge steder.

Læste dernæst de to views nedenunder for at efterprøve koordinatorens forklaring
på tavsheden. Begge holdt præcist: forbruger-viewet `INNER JOIN`'er på skema- og
tabelnavn, så NULL-fyldte navne giver nul rækker i stedet for en fejl; og det
view, der udleder nøglekolonner, har en `NOT EXISTS`-gren mod netop det tomme
view, som derfor gør tilbagefaldet til den manuelt vedligeholdte nøgletabel
universelt sandt i stedet for undtagelsesvist.

### Why

Diagnosen var leveret som verificeret, ikke som hypotese, og skulle behandles
sådan — men den bestilte løsning rører en fil, der ligger midt i en 7.000-linjers
runbook, og dét kunne kun afgøres ved at læse dokumentet. Derfor gik tiden med at
kortlægge kollisionen frem for at genopdage fejlen.

### What worked

At læse runbooken før jeg svarede. Opgaven bad om "et afsnit til sektion 24", men
sektion 24 var optaget af et andet emne med seksten underafsnit — og dens
underafsnit 24.3 indeholdt allerede en snapshot-opskrift for præcis den pipeline,
rettelsen handler om. Havde jeg skrevet det bestilte afsnit, ville dokumentet have
fået to snapshot-opskrifter med hvert sit tabelnavn.

At stille det som et valg med tre muligheder og argumenterne for og imod, frem
for at vælge selv. Koordinatoren valgte den dyreste af dem — konsolidering, hvor
det gamle afsnit reduceres til en peger — og tilføjede samtidig en oplysning, jeg
ikke kunne have kendt: det snapshot, der faktisk blev taget i dag, hedder noget
andet end det, runbooken foreskriver. Navnekonflikten var allerede en realitet i
databasen, ikke kun en risiko i dokumentet.

### What didn't work

Ingen fejlslagne kommandoer i dette trin. Ét miljøforhold gav friktion: arbejdet
blev startet i en git-worktree udcheckt fra `main`, firs commits bag
feature-branchen, hvor runbook-filen slet ikke fandtes. Jeg nåede at konstatere
det og planlægge rettelsen, hvorefter worktreen forsvandt under mig og
arbejdsmappen blev skiftet til hovedrepoet, som allerede stod på den rigtige
branch med rent træ. Ingen skade, men et minut brugt på en branch-kirurgi, der
viste sig unødvendig.

### What I learned

`mappings` i en ADF TabularTranslator er udtømmende, ikke additiv. Én mapping
betyder én kolonne — ikke "én kolonne eksplicit og resten automatisk". Det er den
slags standardvalg, der ikke fejler, men forarmer.

Den egentlige lære ligger dog under pipelinen. En metadata-tabel, der forbruges
gennem `INNER JOIN` og `NOT EXISTS`, kan gå fra korrekt til tom uden at et eneste
led rapporterer noget. `INNER JOIN` oversætter "data mangler" til "nul rækker", og
`NOT EXISTS` oversætter "nul rækker" til "brug reserveløsningen". To
fuldkommen almindelige SQL-konstruktioner udgør tilsammen et tavst nedbrud.
Kæden havde ingen assertion nogen steder, der kunne skelne "tomt" fra "tomt af
en grund".

### What was tricky

Case-spørgsmålet. DB2 folder unquoted identifiers til store bogstaver, så et
alias skrevet i PascalCase kommer ud af resultatsættet som ét ord i versaler.
Hvorvidt ADF's automapning derefter matcher case-insensitivt mod sinkens
kolonnenavne kan ikke afgøres ved at læse noget som helst — kun ved at køre. Det
er netop derfor, opgaven foreskriver quoted identifiers: det gør spørgsmålet
uinteressant i stedet for at besvare det. Det er den rigtige manøvre, når svaret
kun kan købes for en produktionskørsel.

Dertil den mindre finesse, at tre hjælpekolonner skal være tilgængelige inde i
den CTE, der beregner nøglerækkefølgen, men ikke må projiceres ud til sink. De
kommer fra CTE'ens egen `FROM`-kilde, så de er i scope for `CASE`-udtrykket uden
at stå i select-listen — men det er nemt at komme til at "rydde op" i dem.

### What warrants review

Den rettede kildeforespørgsel skal projicere fjorten kolonner, ikke seksten: to
af sinkens kolonner har ingen kilde i forespørgslen og har altid stået NULL.
Læses diffen hurtigt, ligner de udeladelser en fejl. Runbook-afsnittet skal
skrive hvorfor.

Og konsolideringen: efter rettelsen må der findes præcis ét sted i runbooken, der
beskriver snapshottet, og præcis ét tabelnavn. Det er værd at søge dokumentet
igennem for det gamle navn bagefter.

### Future work

Det tavse nedbrud er ikke rettet af denne opgave — kun den ene forekomst af det.
Der er ingen kontrol nogen steder, der ville fange samme fejlform igen i et andet
led. En billig udgave ville være en assertion på rækkeantal i den tabel, før de
afhængige views bruges.

## Step 2: Selve rettelsen, runbook-konsolideringen og en kurskorrektion undervejs

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Arbejd i `C:\claudes_folder\repos\DLBR-DataEstate2026` (IKKE en
worktree — hovedrepoet, allerede på branch `feature/o90-enriched-v2` @ 59643a7,
rent træ). […] **Leverance 1: ret pipelinen** […] Omskriv det ydre `SELECT` i
CTE'en `final_output` så det projicerer **præcis de sink-kolonner der har en
kilde**, aliaseret til sink-navnene. `,*` skal væk. […] `FullDataTypeName` og
`NullableName` udelades — de har ingen kilde i DB2-forespørgslen og har altid
stået NULL. […] Hjælpekolonnerne […] må IKKE projiceres ud, men skal stadig være i
scope […] Lad være med at \"rydde op\" i dem. […] **Quoted identifiers —
obligatorisk og bevidst valg:** DB2 folder unquoted identifiers til STORE
BOGSTAVER […] Om ADF's auto-mapning matcher case-insensitivt mod sinken kan IKKE
afgøres uden at køre. Brug derfor delimited/quoted identifiers […] Det bevarer
præcis case og gør spørgsmålet irrelevant i stedet for at besvare det. […]
**Leverance 2: runbooken** […] **a) Ny sektion 25** […] INGEN henvisninger til
andre afsnit — alt skal stå der. **b) Reducér 24.3** […] **c) Ét tabelnavn
gennemgående.** Virkeligheden er kommet os i forkøbet […] Søg hele dokumentet
igennem for det gamle navn bagefter — der må ikke stå to navne tilbage. […]
**Deploy og kørsel udfører Benny SELV.**"

Undervejs kom en kurskorrektion fra en sideløbende agent, som fik direkte
konsekvens for indholdet: "et naivt FULL OUTER JOIN mellem snapshot og ny tabel
vil vise tusindvis af \"nye\" tabeller. Det er det FORVENTEDE udfald af en grøn
kørsel, ikke en regression. Skriver du kontrollen som \"nul forskelle =
godkendt\", melder den fejl på en korrekt kørsel, og Benny ruller en rigtig
rettelse tilbage."

**Interpretation:** Rettelsen var specificeret ned til kolonneniveau; min opgave
var ikke at designe den, men at udføre den uden at ødelægge noget i nærheden, og
at bevise med læsning og maskinel kontrol at den gør præcis det, den påstår.
Runbook-delen var derimod reelt forfatterarbejde: et afsnit der skal kunne læses
alene, i et dokuments eksisterende stemme.

**Inferred intent:** At Benny kan deploye og køre uden at skulle spørge om noget
— og at han har et sikkerhedsnet, hvis kørslen går galt igen.

### What I did

Pipelinen blev rettet med tre kirurgiske redigeringer i JSON-filen frem for en
omskrivning: de fire ledende udtryk fik quoted aliasser og `,*` blev erstattet af
de otte kildekolonner der mangler; `CASE`-udtrykkets alias blev citeret og
Navision-flaget flyttet ned som sidste kolonne så rækkefølgen matcher sink-DDL'en
og søstervarianten; og mapping-blokken blev fjernet. Diffen endte på tolv linjer.

Verifikationen var maskinel frem for visuel. JSON'en blev parset før og efter.
Den resulterende forespørgsel blev trukket ud af den parsede struktur og printet,
så jeg læste den SQL databasen faktisk får, ikke den escapede streng. Derefter to
programmatiske kontroller: alle quoted aliasser blev udtrukket med regex og sat
op mod kolonnenavnene i sink-tabellens DDL — fjorten aliasser, nul der ikke
findes i DDL'en, nul dubletter, og præcis de to forventede DDL-kolonner uden
modpart. Og hver ukvoteret kildereference i det nye `SELECT` blev slået op i de
opstrøms CTE'er for at bekræfte at den er defineret der, hjælpekolonnerne
inklusive.

Jeg efterprøvede også den commit, jeg citerer i runbooken. `git show` bekræftede
dato, beskedtekst og at den tilføjede præcis de ti linjer, der udgør
mapping-blokken — den rettede fil er nu byte-identisk med tilstanden før den
commit i netop det område.

Runbooken: det gamle snapshot-afsnit blev skåret ned til en peger plus de to ting
der er specifikke for den igangværende onboarding, det forældede snapshot-navn
blev rettet alle steder, og et nyt afsnit på omkring femhundrede linjer blev
skrevet og føjet til. Til sidst commit og push med korrekt forfatteridentitet
bekræftet efter commit.

### Why

De tre kirurgiske redigeringer frem for en omskrivning var et bevidst valg: hele
forespørgslen ligger på én JSON-linje med escapede anførselstegn og et regulært
udtryk med dobbelte backslashes. En omskrivning ville have krævet at jeg
rekonstruerede escaping, jeg ikke havde brug for at røre — og en forkert
gengivet backslash i et regulært udtryk ville have ødelagt nøgleudledningen uden
at fejle.

Den maskinelle verifikation var nødvendig, fordi der ikke findes nogen test at
køre her. Jeg må hverken deploye eller køre pipelinen, så alt hvad der kan
afgøres ved læsning, skal afgøres ved læsning — og en regex-sammenligning af
fjorten navne mod en DDL er mere pålidelig end mine egne øjne på en stavefejl,
der med vilje er bevaret fra DDL'en.

### What worked

Kurskorrektionen fra den sideløbende agent kom, før jeg havde skrevet et ord af
efterkontrollen, og den forhindrede en reel fejl. Jeg var på vej til at skrive
kontrollen som "nul forskelle = godkendt" på en sammenligning mellem et snapshot,
der kun dækker de registrerede objekter, og en frisk kørsel, der henter hele
kildens systemkatalog. Den kontrol ville have meldt rødt på en perfekt kørsel.
Afsnittet skelner nu tre kategorier eksplicit i prosa og siger direkte, at den
ene af dem forventes at være stor første gang.

At læse tre eksisterende afsnit grundigt før jeg skrev, betalte sig også.
Dokumentet har en meget bestemt stemme — forventede tal skrives ud, forbehold
skrives ud, og der står hvorfor et tal er det forventede, ikke bare hvad det er.
Det kan ikke gættes fra en beskrivelse.

### What didn't work

Én fejlslagen redigering, og den var lærerig. Forsøget på at fjerne
mapping-blokken med en tekstudskiftning fejlede med:

```
String to replace not found in file.
String: 							"type": "TabularTranslator",
							"mappings": [
```

Årsagen var indrykning: filen bruger tabulatorer, og min udskiftningsstreng var
nået frem med mellemrum. Det bekræftede jeg med `sed -n '73,95p' <fil> | cat -A`,
der viste `^I^I^I^I^I^I"mappings": [`. Rettelsen blev at slette linjerne ved
linjenummer i stedet — `sed -i '77,86d'` — efter først at have printet linje 77
og 86 for at bekræfte, at de var blokkens første og sidste.

Derudover gav git ved både `add` og `push` advarslen `warning: in the working
copy of '…Extract InformationSchema Object DB2.json', LF will be replaced by CRLF
the next time Git touches it`. Den er harmløs her — `git show --stat` bekræftede
tolv ændrede linjer og ikke hele filen — men det er værd at vide, at en
linjeskift-normalisering på netop den filtype ville have gjort diffen ulæselig.

### What I learned

Tre observationer i materialet går ikke op, og det er en pointe i sig selv. Det
runbooken hidtil lagde til grund om forholdet mellem basistabellens og viewets
rækkeantal modsiges af det, gendannelsen faktisk målte. Hvilken af dem der er
forkert, kan ikke afgøres fra repoet — kun ved en måling mod databasen, som jeg
ikke må foretage. Fristelsen er at vælge den forklaring, der får regnestykket til
at gå op, og skrive den som om den var afgjort. Det rigtige var at skrive begge
observationer op mod hinanden som et åbent punkt og eksplicit forbyde at bruge
gendannelsens tal som forventning efter en frisk kørsel — netop den forveksling
dokumentet i forvejen advarer imod ét afsnit længere oppe.

Og en konkret SQL-detalje, jeg ikke havde tænkt igennem før: en
NULL-sikker sammenligning skal have sentinelværdien lagt på **inde i**
grupperingen, ikke kun i join-betingelsen. Ellers kan man ikke bagefter skelne
"ingen modpart i join'et" fra "værdien var NULL" i `WHERE`-klausulen — og på
netop denne kontrol er NULL-værdier ikke et kantfælde, men selve det udfald
kontrollen skal fange.

### What was tricky

At skrive et afsnit, der skal kunne læses alene, ind i et dokument hvor det
tilstødende afsnit henviser ind i det. De to må ikke komme til at sige det samme
med hvert sit tabelnavn — det var hele grunden til konsolideringen — men det
reducerede afsnit skal stadig bære den ene distinktion, det er det eneste sted
for. Løsningen blev at flytte opskriften og beholde distinktionen, og at lade det
nye afsnit være det sted, hvor navnekonventionen defineres.

Dertil en rækkefølgekonflikt, jeg først så ved gennemlæsning: det nye afsnit
slutter med at bede læseren droppe snapshot-tabellen, men den igangværende
onboarding bruger det samme snapshot til sin egen sammenligning et par trin
senere. Der står nu en undtagelse på det sidste trin.

### What warrants review

To ting kan kun afgøres ved kørsel, og det står skrevet i runbooken: om
ODBC-driveren accepterer delimited identifiers i netop denne forespørgsel, og om
automapningen faktisk binder alle fjorten. Efterkontrollen er designet til at
besvare begge dele.

Jeg afveg bevidst ét sted fra det bestilte ordvalg. Opgaven beskriver fejlen som
værende uopdaget i fire måneder; commit-datoen og fundsdatoen ligger godt tre
måneder fra hinanden, og runbooken siger derfor "godt tre måneder". Hvis
fire-måneders-tallet stammer fra noget andet end den commit, jeg citerer, er det
min tekst der skal rettes.

### Future work

Ingen ny ud over den fra Step 1, som står uændret: der findes stadig ingen
assertion nogen steder i kæden, der kan skelne "tomt" fra "tomt af en grund".
Efterkontrollen i det nye afsnit er en manuel udgave af netop den assertion,
kørt én gang af et menneske. Den oplagte fortsættelse er at gøre den til noget,
der kører af sig selv.

## Step 3: En fjerde kildetabel, et seed-script der skriver sit eget katalog, og en modsigelse der skulle ryddes op

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Arbejd i `C:\claudes_folder\repos\DLBR-DataEstate2026`
(hovedrepoet, branch `feature/o90-enriched-v2`). Absolutte stier. Byg oven på
commit `9d32e4d`. […] Udvid seed-scriptet fra tre til fire kildetabeller. […] Og
scriptet skal nu **selv skrive de 60 katalogrækker**, i stedet for at kræve at
ADF-pipelinen har kørt. `git mv […]` — brug `git mv`, så historikken følger med.
Scriptet er 695 linjer, seks trin, fem afbrydelsesvagter, fem
verifikations-resultatsæt. Læs det HELT igennem før du rører noget; mønsteret
skal bevares. […] `utility.ExtractInformationSchema` for forbindelsen er
**håndseedet**, ikke pipeline-produceret […] Pipelinens `preCopyScript` sletter
hele forbindelsen, så en kørsel ville erstatte de håndkurerede rækker med et
fuldt dump af `SYSIBM.COLUMNS` […] **Nøgler:** [antal enige, én afvigelse med
årsagsforklaring — elideret] **Typer/længder:** [antal uenige; antal ukendte
kolonner — elideret] **Parkeret som selvstændigt rul. Rør det ikke, nævn det kun
hvor det forklarer hvorfor pipelinen ikke køres.** […] **Leverance 1: nyt trin 0
i seed-scriptet** […] Mønster taget fra `generate_eis_inserts_from_gl_meta.sql`:
**idempotent**, dvs. `DELETE` på (ConnID, SchemaName, TableName) før `INSERT`,
pr. tabel. […] `NavisionFlag` = som de øvrige rækker har den — slå den op i
stedet for at gætte […] `DataTypeName` = typenavnet ordret og i VERSALER som vist
[…] Afvig ikke i stavemåde. […] Verificér den maskinelt i dit eget review — tæl
`INSERT`-rækkerne […] Gæt ikke. […] **Leverance 2: vagterne** [fem vagtkrav, tal
elideret] […] **Leverance 3: to begrundelser der skal stå i scriptet som prosa,
ikke kun som værdi** […] Læs proceduren og bekræft formuleringen, før du skriver
den. […] Skriv målingen ind, så spørgsmålet ikke tages op igen. […] **Leverance
4: runbooken** […] **VIGTIGT: modsigelse du skal rydde op i.** Commit `9d32e4d`
(fra i formiddag, samme branch) tilføjede **sektion 25**, og dens **25.8
kørselstrin instruerer Benny i at deploye OG køre** [katalogpipelinen mod
forbindelsen]. Det er nu direkte forkert […] Lad være med at slette arbejdet —
omformulér forudsætningen. […] **Emnelinjen skal være sand i sig selv.** Forrige
commit på denne opgave sagde \"alle 16 sinkkolonner\", hvor brødteksten korrekt
sagde 14. Lad være med at gentage den. […] **Benny kører og deployer selv.**"

Kildedata — tabelnavne, kolonnenavne, typer og rækketal — er elideret her. De
hører i kundens repo, ikke i en offentlig dagbog.

Undervejs kom en kurskorrektion fra lead, som ændrede en af vagterne før den blev
skrevet: "Scriptet er idempotent i hele sin konstruktion […] Men en vagt der
siger \"afbryd hvis kataloget ikke står på præcis [N]\" gør scriptet **kørbart
nøjagtig én gang**. Anden kørsel ser [N+60] og afbryder — på en fuldkommen
korrekt tilstand, som scriptet selv har skabt. Det er samme fejlform som den vagt
jeg fik afvist tidligere i dag: en vagt der fælder den rigtige tilstand. […]
Skriv den i stedet som en invariant der holder både før og efter: Antal rækker
[…] EKSKLUSIVE de fire tabeller […] Brug `NOT EXISTS` mod `@Tables` […] ikke en
`NOT IN` på strenge. […] Samme overvejelse gælder vagten \"ingen af de fire må
allerede findes i `meta.SourceObjects`\" […] hvis den har samme problem, så sig
det til mig i afleveringen i stedet for at rette det stiltiende — det er en
ændring af eksisterende adfærd, og den skal Benny kende."

**Interpretation:** Tre ting i én opgave, som kun ligner én: udvid et script med
en tabel, flyt en ansvarsgrænse (scriptet skriver nu selv det katalog, det før
kun kontrollerede), og ryd op i en modsigelse, som mit eget arbejde fra samme
formiddag havde skabt. Den sidste var den vigtigste, fordi den var usynlig fra
opgavens overskrift.

**Inferred intent:** At Benny kan køre ét script mod meta-databasen og være
færdig — uden at skulle køre en pipeline, der ville trække en parkeret beslutning
med ind ad bagdøren, og uden at runbooken to steder siger to forskellige ting om
netop den kørsel.

### What I did

Jeg læste hele det eksisterende script igennem, den generator det henviser til,
dens output, udtræksproceduren, katalogtabellens og viewets definitioner og begge
de berørte runbook-sektioner i fuld længde, før jeg rørte noget. Derefter
`git mv` til det nye navn, så omdøbningen stod i indekset som en omdøbning.

Payloaden skrev jeg ikke i hånden. Jeg lagde kildematerialet ordret i en fil i
scratchpad, skrev en generator der parser det og emitterer SQL'en med assertions
undervejs, og splejsede resultatet ind i scriptet på en markør. Så skrev jeg en
**uafhængig** verifikator, der læser det færdige `.sql` tilbage og genudleder hver
eneste påstand: antal rækker i alt og pr. tabel, at ordinalerne er
sammenhængende og skrevet i rækkefølge, at der er præcis én nøglekolonne pr.
tabel med det forventede navn, at de faste felter er de rigtige, at hver type
rammer en gren i typereglen — og de afledte tal, som scriptets egne kommentarer
påstår om antal trimmede kolonner og antal regeludledte transformationer.
Pointen med to programmer er, at det andet ikke må kunne arve det førstes fejl.

Selve scriptet fik et nyt skrivende trin før det eksisterende trin 1, to
pre-flight-vagter uden for transaktionen, to nye vagter inde i den — en på
totalen og en mod **viewet** frem for basistabellen — og to begrundelser skrevet
som prosa frem for som værdier. Begge begrundelser blev efterprøvet i koden
først: den ene ved at læse udtræksproceduren og konstatere, at dens inkrementelle
gren altid bygger prædikatet på tabellen selv, uden join; den anden er en måling,
jeg har fået overleveret og skrevet ind med sin egen aritmetik ved siden af, så
den kan efterprøves uden at måle igen.

Runbooken blev gennemgået sektion for sektion, ikke søg-og-erstat. De mekaniske
rettelser kørte jeg som et script med `assert t.count(old) == 1` på hver eneste
erstatning, så en formulering der optrådte to steder ville stoppe scriptet i
stedet for at blive ændret to steder i blinde. Det fangede reelt noget: et
tilfælde hvor den søgte streng var præfiks af et andet ord.

Til sidst rettede jeg modsigelsen. Kørselstrinene blev skrevet om, så rettelsen
deployes — den er korrekt og gælder bredere end den ene forbindelse — mens
kørslen mod netop den forbindelse er udskudt og begrundet. Gendannelses- og
efterkontrolafsnittene blev bevaret og markeret som hørende til den fremtidige
kørsel, og jeg søgte hele dokumentet igennem bagefter for andre steder, der
stadig instruerede i den kørsel. Der var to, og begge er rettet.

### Why

Ansvarsflytningen er hele pointen: så længe scriptet kun kontrollerede kataloget,
var forudsætningen en pipelinekørsel, og den kørsel har en sideeffekt, ingen har
bedt om. Ved at lade scriptet skrive de rækker, det har brug for, forsvinder
forudsætningen — og dermed også anledningen til at køre pipelinen.

Vagterne er skrevet til at fange netop den sideeffekt. Den vigtigste er
formuleret som en invariant over "alt det vi ikke rører", præcis så den holder
både før og efter en kørsel af scriptet selv.

### What worked

Generator-plus-uafhængig-verifikator var det rigtige valg for en payload af den
her størrelse. Begge kørte grønt i første forsøg efter splejsningen, og
verifikatoren fangede senere en fejl i min egen prosa — se nedenfor — som ingen
læsning ville have fanget.

Den strukturelle kontrol af SQL'en var billig og værd at have: antal
`BEGIN TRANSACTION` mod `COMMIT`, at hver `RAISERROR` har en `RETURN`, at
`BEGIN`/`END` går op når `CASE`-udtrykkene tælles med, at ingen variabel er
erklæret to gange, og at ingen fejltekst overskrider `RAISERROR`'s grænse for
formatstrengen. Alt sammen ting, der ellers først fejler hos Benny.

Lead's kurskorrektion var rigtig og kom tidligt nok. Jeg havde selv set
konflikten og var ved at designe en dårligere løsning på den — en vagt der stadig
afbrød, men med en bedre fejltekst. Invarianten er bedre, fordi den slet ikke
afbryder på den rigtige tilstand.

### What didn't work

Ingen kørselsfejl undervejs — intet mod database, pipeline eller platform, og det
var også rammen. Tre reelle fejl i mit eget arbejde, alle fundet i selvreview:

For det første en aritmetisk fejl i en kommentar, jeg selv havde skrevet: jeg
opsummerede en tabels kolonner som "fire" af en bestemt slags, hvor payloaden har
fem. Summen af min egen opremsning gav 11, mens tabellen har 12. Fundet ved at
tælle opremsningen efter, og bekræftet ved at få verifikatoren til at printe et
type-histogram pr. tabel, som jeg kunne holde prosaen op imod. Det er præcis den
slags fejl, verifikatoren ikke fanger af sig selv, fordi den kontrollerer SQL'en
og ikke kommentaren ved siden af.

For det andet to SQL-detaljer, jeg rettede før de nåede at blive et problem:
`RAISERROR`'s substitutionsparametre kan ikke være `BIT`, så en flagværdi skulle
udvides til `INT` for at kunne stå i en fejltekst — ellers ville vagten fejle med
`Invalid data type for substitution parameter` i stedet for at sige sin egen
diagnose. Og en skalar underforespørgsel inde i en `PRINT CONCAT` blev erstattet
af en variabel; den er formentlig lovlig, men "formentlig lovlig" er ikke godt
nok i et script, ingen af os kan køre.

For det tredje, og vigtigst for anden gang: jeg skrev først en indekstype ind i
en kommentar, som jeg ikke havde fået oplyst. Den var plausibel — de øvrige
tabeller i samme familie har den — men plausibel er ikke målt. Den er nu skrevet
ud som "indgik ikke i målingen og er bevidst ikke opfundet her", med en
begrundelse for hvorfor den heller ikke betyder noget.

Og en ting, jeg ikke kunne rette bagefter: omdøbningen blev lavet med `git mv`,
men fordi filen samtidig voksede med godt halvtreds procent, ligger ligheden
under gits standardtærskel for omdøbningsdetektion.
`git log --follow -- <ny sti>` viser kun den nye commit ved standardindstilling;
med `-M20%` når den tilbage til den oprindelige fil. Git gemmer indhold og ikke
omdøbninger, så `git mv` alene garanterer det ikke. To commits — først ren
omdøbning, så indhold — ville have gjort det. Det opdagede jeg først efter commit
og push.

### What I learned

En vagt kan være rigtig om verden og forkert om sit eget script. Den formulering,
opgaven bad om, var sand som en beskrivelse af udgangstilstanden, men falsk som
en invariant, fordi scriptet selv flytter tilstanden. Kuren er at spørge "hvad er
det, der IKKE ændrer sig her" og lægge vagten dér. Det er samme tankegang som en
god testassertion: hold fast i det, der skal være konstant, ikke i et
øjebliksbillede.

Når en kontrol skal læse gennem et view frem for en tabel, arver den viewets
forudsætninger — her et `INNER JOIN`, som gør et objekt usynligt, indtil det er
registreret. Det tvinger en rækkefølge: kontrollen kan ikke ligge før den
skrivning, den afhænger af, selv om den logisk hører til det, der blev skrevet
først. Begge kontroller skal blive, for de fanger hver sin ting, og den ene kan
ikke flyttes hen til den anden.

Og en ting om at rette sit eget arbejde fra samme dag: modsigelsen var ikke en
fejl i det, jeg skrev i formiddags — det var rigtigt, da det blev skrevet.
Beslutningen ændrede sig bagefter. Fristelsen er at slette afsnittet og skrive et
nyt; det rigtige var at omformulere forudsætningen og lade indholdet blive
stående, markeret med hvornår det gælder. Den viden er dyr at genskabe og billig
at bevare.

### What was tricky

At holde to tal adskilt, som begge er rigtige. Et dokument, der bruger det samme
tal om både en basistabel og et view, og et andet sted advarer mod at forveksle
netop de to, er nemt at gøre værre. Her viste det sig, at de to faktisk er ens —
og af en grund, der samtidig opklarede et åbent punkt et helt andet sted i
dokumentet. Det var fristende at skrive det som "så var det jo ikke noget"; det
rigtige var at skrive hvorfor de er ens, hvad der stadig er ukendt, og hvad man
derfor ikke må bruge tallet til.

Dertil rækkefølgen i runbooken. Et underafsnit er skrevet som "trin N", og
trinnene er ikke længere i samme orden som afsnittene, fordi et af dem er
bortfaldet som kørsel. At renummerere alt ville have knækket krydshenvisninger i
et forbeholds-skema længere nede. Løsningen blev at bytte to trinnumre og skrive
eksplicit i rækkefølgeblokken, at de to står i omvendt dokumentorden — og hvorfor
de gør det.

### What warrants review

Payloadens indhold er transskriberet, ikke målt af mig. Antal, ordinaler, nøgler
og typegrene er maskinelt kontrolleret, men at hver enkelt type og længde svarer
til virkeligheden, kan kun afgøres ved den sammenligning, runbooken beskriver.
Det står som et selvstændigt forbehold i dokumentets forbeholds-skema.

Den ene adfærdsændring skal Benny kende, og den er derfor både i commit-teksten,
i scriptets header og i runbookens køreafsnit: scriptet kan ikke længere køres to
gange ende til ende, fordi en af pre-flight-vagterne afbryder på en tilstand,
scriptet selv har skabt. Det er bevidst, det er bestilt, og det er en ændring fra
den tidligere version, som printede nuller ved en gentagen kørsel. Vil man have
begge dele — både førstegangskontrollen og en genkørsel — skal vagten gøres
betinget, og det er en beslutning, ikke en rettelse.

Og omdøbningens historik: `git log --follow` når ikke tilbage ved
standardtærsklen. Hvis det betyder noget, er kuren at dele commit'en i to og
force-push'e, og det gør jeg ikke uden at blive bedt om det.

### Future work

De parkerede kolonner er nu skrevet ind som et selvstændigt punkt i dokumentets
forbeholds-skema med en henvisning til, hvorfor de ikke må komme ind ad
bagdøren. Det rul findes stadig ikke, og indtil det gør, hviler beslutningen på
to vagter og et afsnit prosa.

Den parameter, der ville gøre katalogudtrækket afgrænsbart til udvalgte tabeller,
er beskrevet i runbooken og stadig ikke bygget. Den er nu tydeligere den rigtige
løsning, end den var før: den er præcis det, der ville gøre det parkerede rul
håndterbart tabel for tabel i stedet for alt på én gang.
