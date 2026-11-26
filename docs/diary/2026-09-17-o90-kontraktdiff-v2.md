# Diary: Kontraktdiff mellem gammelt og nyt enriched-lag (o90 → o90_v2)

Kundeprojekt hos SEGES. Et enriched lag er skrevet om fra bunden i en v2-udgave,
og beslutningen er truffet: v2 skal **erstatte** det gamle lag ved en omdøbning,
ikke leve side om side. Det betyder at alle downstream-notebooks i curated- og
integrationslaget bliver hængende på det samme skemanavn og derfor rammer det nye
indhold uden at én eneste linje kode ændrer sig.

Det er netop derfor opgaven er farlig. Konventionerne er ikke ens mellem de to
lag — kolonnen der markerer en aktuel række hedder noget andet, sletteflaget
hedder noget andet, en oprettelsesdato er væk, en række booleans er blevet
heltal, klokkeslæt er blevet strenge, en stribe numeriske datofelter er blevet
rigtige datoer med sentinelværdier, og tekstfelter bliver nu trimmet så tomme
strenge ender som NULL. Ingen af de ting får et job til at fejle. De får et filter
til at returnere nul rækker, eller et tal til at flytte sig, i stilhed.

Leverancen er ét dokument: en kontraktdiff der pr. fil og pr. tabel siger hvad
der læses, hvad der går i stykker under v2, og hvor alvorligt det er — stille
fejl først, med fil og linjenummer på hver påstand.

## Step 1: Afgrænsning, faktatjek og holdopsætning

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Go with your own recommendation: A for the 40 files (pure
diagnosis, file:line, what happens under v2, category silent/loud/cosmetic), and
B only for the derived columns, where the point IS the decision - there include
the concrete shape of the fix and whether a shared helper in curated pays off
(with the count of files sharing each derivation). Cross-reference the runbook
(12.6, lines 2733-2753, 3405-3425) rather than repeating it. Two more things: -
Report the real file count as 40 and say explicitly what the \"43\" in the plan
counted, so the number does not keep floating around. - Verify the semantic
models and any SQL as well, and say clearly if you could not determine something
from the repo alone."

**Interpretation:** Rapporten skal være ren diagnose for konsument-filerne —
konstatering, ikke forslag — mens afsnittet om afledte kolonner er det ene sted
hvor en anbefaling er ønsket, fordi det er dér en beslutning skal træffes. Tallet
40 skal fastslås og det gamle tal forklares, ikke bare erstattes. Den eksisterende
runbook skal krydshenvises frem for at blive kopieret.

**Inferred intent:** Benny vil have et evidensdokument der ikke ældes, når holdet
senere vælger en anden løsning end den jeg ville have foreslået. Og han vil have
et tal han kan sige højt uden at blive modsagt.

### What I did

Jeg brugte lead-rollen som den er tænkt: undersøgte nok til at kunne stille ét
skarpt spørgsmål, stillede det, og lod være med at bygge selv.

Først et faktatjek på tre ting, fordi alle tre viste sig at være forkerte i det
oplæg jeg fik. Arbejdskopien jeg blev sat i gang i var bygget på en commit der
**ikke** var forfader til målbranchen — en analyse foretaget dér ville have
beskrevet en anden kodebase end den rapporten skulle committes på. Det blev
opdaget med en simpel forfader-test frem for at blive antaget.

Dernæst filtællingen. Oplægget sagde 43 filer. Ved at skelne mellem filer der
*nævner* skemaet og filer der faktisk *læser* enriched-skemaet landede tallet på
40 læsende filer på tværs af curated og integration, fordelt på ~100 referencer.
De filer der kun rører curated-skemaet af samme navn er ikke konsumenter af
enriched og hører ikke med. Jeg fandt ikke tallet 43 nogen steder i repoet som et
filantal — derimod optræder 43 som et *kolonne*antal i runbookens afsnit om
typeskiftet. Det er en hypotese om forvekslingen, ikke en konklusion, og den er
givet videre som noget der skal verificeres frem for påstås.

Endelig en hurtig kortlægning af hvad der ligger uden for databricks-mapperne:
semantiske modeller og SQL-objekter. De semantiske modeller rører skemanavnet i
kolonne- og measure-navne, men spørgsmålet om hvorvidt nogen af dem læser
enriched **direkte** frem for via curated er ikke afgjort af en filsøgning — det
er givet videre som et punkt der skal verificeres, ikke gættes.

Spørgsmålet jeg stillede Benny var det eneste der reelt ændrede formen på
leverancen: skulle rapporten kun diagnosticere, eller også foreskrive rettelsen
pr. fund? Med begge siders argumenter — et rent evidensdokument der holder, mod
en direkte arbejdsplan der til gengæld ældes hver gang holdet vælger anderledes.
Han valgte den delte model jeg hældte til.

### Why

Lead-rollen står og falder med at rammen er rigtig, inden nogen bygger. De tre
faktafejl ville hver især have gjort leverancen forkert på en måde der først
opdages sent: forkert kodebase, et tal der bliver ved med at flyde rundt, og et
ubelyst hjørne af konsumentlandskabet.

Spørgsmålet om diagnose kontra foreskrift blev stillet frem for afgjort, fordi
det ikke er et teknisk valg. Det handler om hvor længe dokumentet skal kunne
holde, og det er ejerens kald.

### What worked

At tælle før jeg troede. Forskellen mellem "nævner" og "læser" var hele
afstanden mellem 44 og 40, og den slags skelnen koster ét ekstra søgeudtryk.

At forfader-testen blev kørt eksplicit i stedet for at stole på at en
arbejdskopi står det rigtige sted. Den ene kommando afværgede en analyse af den
forkerte kodebase.

### What didn't work

Ingen fejl i dette trin. Den eneste friktion var at målbranchen var i brug et
andet sted, hvilket kortvarigt så ud til at kræve en omvej — den løste sig da
arbejdsområdet blev flyttet til hovedkopien, hvor branchen allerede lå.

### What I learned

Et tal i et oplæg er en påstand på linje med alle andre påstande, og det skal
efterprøves med samme mistro. "43 filer" holdt ikke, og forklaringen — at det
formentlig er et kolonneantal der er vandret over i den forkerte sætning — er
mere værd for læseren end bare at rette tallet til 40. At sige hvad det gamle tal
*talte* er det der stopper det fra at dukke op igen.

Et delt dokument kan godt have to ambitionsniveauer: konstaterende dér hvor
evidensen skal overleve beslutningerne, og foreskrivende præcis dér hvor pointen
er at en beslutning skal træffes. Det er ikke inkonsekvens, det er at lade formen
følge formålet.

### What was tricky

Grænsen mellem "denne fil rører skemaet" og "denne fil er konsument af det lag
der udskiftes" er ikke synlig i en almindelig tekstsøgning, fordi curated-laget
har et skema med samme navn. Uden den skelnen tæller man for højt og undersøger
filer der ikke kan gå i stykker.

Der findes allerede en meget lang runbook på branchen som dækker dele af det
samme stof. Fristelsen er at gentage den. Beslutningen blev at krydshenvise til
de tre konkrete afsnit, så de to dokumenter ikke kan drive fra hinanden.

### What warrants review

Tallet 40 er det der skal efterprøves først — både at ingen konsument er
overset, og at ingen af de 40 i virkeligheden kun rører curated-skemaet.

Forklaringen på "43" er indtil videre en hypotese. Den skal enten bekræftes eller
formuleres som uafklaret i rapporten. Den må ikke stå som en konstatering.

Spørgsmålet om de semantiske modeller læser enriched direkte er uafgjort ud fra
repoet alene og skal ende i rapportens afsnit om det der ikke kunne afgøres.

### Future work

Selve kontraktdiffen skrives af en builder på branchen, med fil- og
linjehenvisning på hver påstand og stille fejl rangeret først. Når den ligger,
er næste beslutning hvorvidt de afledte kolonner skal samles i en fælles hjælper
i curated — rapportens optælling af hvor mange filer der deler hver afledning er
grundlaget for netop det valg.

Der er også en afgrænsning der skal holdes i hævd undervejs: analysen er
læse-only, og ændringer uden for rapportfilen hører ikke til i denne leverance.

## Step 2: Kontraktdiffen skrevet, verificeret og committet

**Author:** builder

### Prompt Context

**Verbatim prompt:** gengivet i afkortet form, fordi den fulde ordlyd indeholder
kundens skema-, tabel- og kolonnenavne, som ikke hører i et offentligt repo.
Kernen: "Du skriver ÉN dansk markdown-rapport i SEGES-kunderepoet. Ren
læse-analyse — du ændrer ikke pipeline-/notebook-kode." Rapporten skal have to
bevidst forskellige ambitionsniveauer: "Del A — ren diagnose for de 40 filer
(INGEN løsningsforslag) … Skriv hvad der sker under v2 — ikke hvad man bør gøre
ved det", og "Del B — afledte kolonner (her ER pointen beslutningen, så vær
foreskrivende)". Dertil en Del C om det der allerede var i stykker, og en Del D
om "det der ikke kunne afgøres ud fra repoet alene". Om tallene: "Oplægget/planen
sagde '43 filer'. Jeg kan ikke finde 43 som et filantal nogen steder i repoet …
Det er en **hypotese** om en forveksling — bekræft den eller skriv eksplicit at
kilden til '43' ikke kan afgøres ud fra repoet." Og til sidst: "Sig det også
højt hvis du fandt noget der modsiger runbooken eller mine tal ovenfor — jeg vil
hellere korrigeres end bekræftes."

**Interpretation:** Leverancen er et evidensdokument, ikke en arbejdsplan. Hver
påstand skal kunne efterprøves med ét opslag, og de steder hvor repoet ikke kan
svare, skal stå som ubesvarede frem for at blive udfyldt med et kvalificeret gæt.
Foreskrivende kun dér hvor en beslutning faktisk afventer.

**Inferred intent:** Han vil kunne lægge dokumentet fra sig og tage det op igen
om tre måneder uden at skulle genvalidere det. Derfor vejer et forkert
linjenummer tungere end et manglende fund, og derfor er invitationen til at
modsige ham ikke høflighed — den er en del af kravspecifikationen.

### What I did

Jeg begyndte med at verificere arbejdsområdet frem for at stole på det:
branchenavn, commit-hash og at fjern-branchen stod samme sted. Det bekræftede
også at der lå tre worktrees under `.claude/worktrees/` med ældre kopier af
kodebasen — dem holdt jeg konsekvent ude af alle søgninger, fordi et grep der
rammer dem giver linjenumre fra en anden commit end den rapporten committes på.

Derefter byggede jeg kontrakten mellem de to lag ved at læse
beslutningsmodulerne i det nye lag selv, frem for at gå ud fra listen i
oplægget. Det gav ti konkrete forskelle, hver med en kildehenvisning. To af
oplæggets punkter viste sig upræcise, og begge havde konsekvenser: sentinelværdien
for "åben periode" er en timestamp med et klokkeslæt, ikke en ren dato — hvilket
gør den nærliggende rettelse af et bestemt filter til en fælde der returnerer nul
rækker — og det gamle lags kolonnenavne for aktuel-række og sletteflag stammer
faktisk fra en *tredje* kilde, en Delta Share, hvis skema ikke findes i repoet.

Selve fil-for-fil-analysen fordelte jeg på fire parallelle agenter, en pr.
løsningsområde, med den verificerede kontrakt som fælles udgangspunkt. Mens de
kørte, tog jeg selv de spørgsmål der krævede overblik snarere end dybde:
filoptællingen, tallet "43", store/små bogstaver i tabelnavne, og hvorvidt noget
uden for de to mapper læser laget.

Sidstnævnte gav det klareste enkeltfund: opgavens afgrænsning var for snæver.
To filer uden for de udpegede mapper læser laget og kører i planlagte jobs, og
den ene af dem bygger en tabel som to BI-modeller læser direkte. Det er den
eneste sti fra det udskiftede lag til rapporteringen der ikke går gennem det
mellemliggende lag — altså præcis den sti man overser, når man afgrænser efter
mappenavn.

"43" fik jeg lukket: tallet er et kolonneantal, ikke et filantal, og det kan
verificeres med ét grep der tæller præcis 43 typekonverteringer fordelt på 22
filer. Fordelingen matcher endda runbookens egen optælling tabel for tabel. Men
jeg lod være med at skrive at oplæggets "43 filer" *er* en forveksling — kun at
intet filantal 43 findes i repoet. Forskellen er hele pointen med at have en
Del D.

Da agenterne kom tilbage, skrev jeg rapporten og verificerede derefter 34
tilfældigt valgte fil:linje-henvisninger ved at åbne linjen. Én var forkert.
Til slut: commit med eksplicit git-identitet pr. kommando, kun rapportfilen
staged ved fuld sti, og push uden force.

### Why

Parallelliseringen var ikke for hastighedens skyld alene. Fire agenter der hver
især kun ser sit eget løsningsområde, kan ikke ubevidst harmonisere deres
konklusioner — så når tre af dem uafhængigt rapporterer samme mekanisme, er det
et signal, og når én af dem afviger, er det noget der skal undersøges. Det
skete faktisk: én agent konkluderede at et bestemt spørgsmål var afgjort, hvor
de to andre kaldte det uafklaret.

At jeg verificerede agenternes stærkeste påstande selv frem for at referere dem,
følger af at rapporten er et evidensdokument. En påstand jeg ikke har set
linjen bag, er ikke evidens — den er andenhåndsviden med et linjenummer på, og
det er værre end ingen henvisning, fordi den ser efterprøvet ud.

### What worked

At bygge kontrakten færdig **før** agenterne blev sendt afsted. De fik en
verificeret liste med kildehenvisninger i stedet for oplæggets beskrivelse, og
det viste sig at være det der gjorde deres fund sammenlignelige: de målte alle
fire mod samme definition.

At tælle tegn frem for at tro på beskrivelser. Både filtallet, referencetallet
og "43" faldt på plads med ét grep hver, og i alle tre tilfælde var tallet
efterprøveligt af læseren bagefter — hvilket er det der gør at de ikke flyder
rundt igen.

Kryds-verifikationen af de 34 henvisninger. Den fandt fejlen, og den kostede
tre kommandoer.

### What didn't work

**Commit-beskeden blev mishandlet af shell-syntaksen.** Jeg skrev den med
PowerShell-here-string-syntaks (`@'…'@`) i et bash-værktøj, hvor den syntaks
ikke findes. Resultatet var en commit hvis emnelinje begyndte med et løst
`@`-tegn og hvis sidste linje var et ensomt `@`:

```
@ Tilføj kontraktdiff mellem <gammelt skema> og <nyt skema>
```
(emnelinjen gengivet med skemanavnene udeladt; det løse `@`-tegn forrest er
fejlen, og den sidste linje i beskeden var tilsvarende et ensomt `@`.)

Værktøjets egen dokumentation advarer eksplicit mod netop dette ("Do not use
PowerShell here-strings (`@'…'@`) here — for multi-line strings use a heredoc"),
så det var ikke en overraskelse man kunne kalde uheldig. Rettet med
`git commit --amend -F - <<'EOF'` før push, så historikken er ren. Jeg valgte
amend frem for en ekstra commit, fordi beskeden endnu ikke havde forladt
maskinen, og en ny commit ville have efterladt den ødelagte emnelinje permanent.

**Et forkert linjenummer i rapporten.** Jeg havde tilskrevet et
optællingsudtryk linje 71; det står på linje 70. Fanget i stikprøven, rettet før
commit. Det er præcis den fejltype opgaven advarede mod, og den slap igennem
fordi jeg havde overtaget nummeret fra en agent uden at åbne linjen.

**En agent overfortolkede sin egen evidens.** Den sluttede fra et
konfigurationsscript — der sætter historik-mønsteret på 19 objekter i repoets
eget råvarelag — at en helt anden datakilde måtte have de samme kolonner. De to
lag er ikke det samme, og slutningen holdt ikke. Jeg beholdt observationen som
modevidens i Del D, men afviste konklusionen.

### What I learned

**Et diff har altid tre parter, ikke to.** Det gamle lag i repoet er selv en
port af et endnu ældre produktionslag, og porten afviger fra produktionen på
flere punkter end den afviger fra det nye lag. Uden at fastslå hvilket af de to
"gamle" lag man differ imod, bliver halvdelen af fundene enten opfundet eller
overset. Jeg brugte et helt afsnit øverst i rapporten på at definere det, og det
er sandsynligvis afsnittet med højest værdi pr. linje.

**Målte tal slår principper.** En hel klasse af fund jeg forventede ville være
alvorlige — sentinelværdier i datofelter — viste sig at være uden virkning,
fordi antallet af rækker med den kritiske værdi er målt til nul for netop den
tabel der læses mest. Målingerne lå allerede i repoet, i kommentarfelterne på et
seed-script. Den slags er let at overse, fordi man ikke leder efter data i en
DDL-fil.

**Den farligste ændring er den ingen har skrevet ned.** Det største stille fund
i rapporten stod ikke i oplæggets liste og ikke i den eksisterende runbooks
konsumentafsnit. Det stod som en sidebemærkning i en docstring i det nye lags
egen kode, og det rammer over halvdelen af de læste tabeller. Oplæggets liste
var god; den var bare ikke udtømmende, og det er den slags man kun finder ved at
læse kilden frem for beskrivelsen af kilden.

**At afgrænse efter mappenavn lækker.** To konsumenter lå uden for de mapper
opgaven pegede på, og den ene var netop den med den korteste vej til
rapporteringslaget.

### What was tricky

Grænsen mellem "allerede i stykker" og "brudt af omlægningen" kunne ikke
trækkes rent, fordi den afhænger af et skema der ikke findes i repoet. Tre filer
bruger kolonnenavne fra den gamle platform; de kører i planlagte jobs, hvilket
betyder at de enten fejler dagligt eller reddes af at datakilden leverer de gamle
navne videre. Fristelsen var at vælge den forklaring der lød mest sandsynlig. Jeg
skrev i stedet begge muligheder frem med deres evidens og noterede at de under
det nye lag fejler uanset hvad — det er den ene konklusion der holder uanset
hvordan spørgsmålet falder ud.

Rapportens to ambitionsniveauer var svære at holde adskilt i praksis. Når man
har fundet en fejl, vil man skrive rettelsen. Jeg endte med at lade Del A stå
rent konstaterende, selv hvor rettelsen var åbenlys, og samle det foreskrivende
i Del B — med undtagelse af ét fund, hvor selve *rettelsen* er fælden, og hvor
en ren konstatering ville have været misvisende.

Fire parallelle agenters output skulle samles uden at deres indbyrdes
uenigheder blev glattet ud. Det kræver at man går tilbage til kilden på hvert
punkt hvor de er uenige, frem for at vælge flertallets version.

### What warrants review

**Del D først.** Ti punkter kan ikke afgøres fra repoet, og det første af dem —
hvilke audit-kolonner det nuværende lag faktisk har — lukker fire andre punkter
på én gang med ét enkelt skemaopslag. Det er det billigste sted at begynde.

**De seks højlydte fund.** Fire af dem er samme mekanisme på samme tabel og bør
verificeres samlet. De to øvrige handler om en beregnet kolonne der forsvinder.

**Mine egne tal.** Filtallet, referencetallet og kolonnetallet er alle
verificerbare med ét grep hver, og de står i rapporten netop for at kunne
efterprøves. Det samme gælder de 34 stikprøvede henvisninger — jeg har åbnet
dem, men ikke de resterende.

**Modsigelserne til sidst i rapporten.** Otte punkter hvor repoet siger noget
andet end enten oplægget eller det eksisterende dokument. De er de mest
sandsynlige steder at jeg har taget fejl, fordi det er dér jeg påstår at andre
har det.

### Future work

Beslutningen om en fælles hjælper i det mellemliggende lag er nu oplyst:
afledningen har to kaldesteder, ikke de mange man kunne frygte, og rapporten
argumenterer imod hjælperen samt peger på en enklere rettelse der helt undgår
konverteringen. Det er Bennys valg, ikke et implementeringsskridt.

Ni af de ti uafklarede punkter kan lukkes med to forespørgsler mod metadata og
ét skemaopslag. Det hører til den næste branch og skal køres af Benny selv.

En hel mappe med ni filer figurerer ikke i noget planlagt job, og den huser
størstedelen af de højlydte fund. Om den er ude af brug eller vedligeholdes uden om
planlægningen, fremgår ikke af repoet — det bør afklares, før nogen bruger tid på
at rette fejl der måske aldrig kører.

## Step 3: Revision 2 — en afvist rettelse, en måling og en omvendt konklusion

**Author:** builder

### Prompt Context

**Verbatim prompt:** afkortet af hensyn til kundefortrolighed; den fulde besked
indeholder kundens tabel- og kolonnenavne. Den kom fra en anden agent i samme
session og havde tre dele. Først en rettelse: "**RETTELSE — dit
tekstkolonne-fund er forkert** … Det er vendt om. Jeg har selv verificeret …
**Skriv i rapporten rent ud at den første version af fundet var forkert** …
Skjul ikke rettelsen i en omformulering." Dernæst målte data: "Benny kørte
forespørgslen på det GAMLE enriched-skema i dev … Dette er **målt**, ikke
udledt … **Brug det til at genudlede klassifikationerne — ikke bare til at
indsætte facts.**" Og en omformulering: "Fra Benny: **v2's aktuel-række-flag er
det KORREKTE.** … Dit største enkeltfund er formuleret som om v2 ødelægger
noget. Vend det … den rigtige rettelse er at gå TIL aktuel-række-flaget, ikke væk
fra det." (kolonnenavnet er erstattet med rollebeskrivelsen i citatet.)

**Interpretation:** To af de tre punkter er nye oplysninger jeg ikke kunne have
haft: en måling mod et miljø jeg ikke må røre, og en forretningsmæssig kontekst
om hvorfor konsumenterne ser ud som de gør. Det tredje er en påstand om at jeg
tog fejl, og den skal efterprøves som enhver anden påstand — ikke accepteres
fordi den kommer med en irettesættelse.

**Inferred intent:** Han vil have rapporten til at holde, ikke have mig til at
være enig. Formuleringen "jeg foreskriver ikke svaret" i rettelsesafsnittet er
en invitation til at gå fundet efter, ikke til at omskrive det efter diktat.

### What I did

Jeg tog rettelsen først, fordi den var den eneste af de tre der kunne betyde at
noget allerede udgivet var forkert.

Påstanden var at det nye lag trimmer en bestemt variabel-længde-tekstkolonne,
fordi et metadataflag sættes for den type. Første halvdel holdt: jeg verificerede
at flaget faktisk sættes, og at kolonnen opfylder betingelsen om ikke at være
nøglekolonne. Anden halvdel holdt ikke. Flaget slår **to** regler til, og kun den
ene gælder alle tre strengtyper — trimningen gælder kun fast længde. Det står
ordret i modulets egen docstring, koden gør netop det, og der findes en
enhedstest hvis navn bogstaveligt er "variable length types are nullified but not
trimmed".

Jeg forsøgte at køre den test. Det kunne jeg ikke: repoets conftest importerer
Spark-biblioteket, som ikke er installeret lokalt. I stedet indlæste jeg
beslutningsmodulet direkte via en fil-sti — det er bygget netop til at kunne
importeres uden klynge — og kaldte funktionen med flaget sat for alle tre
strengtyper. Outputtet viste sort på hvidt at trim kun tilføjes for den faste
type. Det tre-linjers output ligger nu i rapporten som begrundelse.

Så skrev jeg imod. Rapporten har nu et afsnit der siger hvad der er rigtigt i
indvendingen, hvad der ikke følger af det, og hvorfor fundet står. Jeg tilføjede
en note om at flagets *navn* er selve fælden — det hedder noget med "trim", står
sandt på en kolonne der ikke trimmes, og vil blive læst forkert igen.

Målingen behandlede jeg derimod som det den var: ny evidens der omstøder en
hypotese jeg havde bygget et helt afsnit på. Jeg havde antaget at det gamle lags
kolonnenavne ikke kunne fastslås fra repoet, og at tre filer derfor *muligvis*
var i stykker i forvejen. Målingen viser at laget bærer begge navnegenerationer
samtidig, og at de tre filer altså virker i dag. Dermed er de ikke arvet gæld,
men regressioner forårsaget af omlægningen — og to af dem kører dagligt. De er
flyttet fra afsnittet om pre-eksisterende fejl til afsnittet om højlydte fund,
og det afsnit de kom fra er nu tomt og står som opløst med begrundelse.

Målingen flyttede også et fund den anden vej. En dimension læses uden
aktuel-række-filter, hvilket jeg havde kaldt en pre-eksisterende svaghed. Men den
tabel har i dag slet ingen historik-kolonner, så der er kun én række pr. nøgle —
filteret er korrekt som det står. Under det nye lag får tabellen fuld historik, og
samme filter begynder at læse hver version. Det er ikke en gammel fejl der bliver
værre; det er en ny fejl der opstår. Nyt fund, ny kategori.

Til sidst omformuleringen. Jeg vendte hovedfundet om, beholdt alle
fil-og-linje-henvisninger, og skrev rækkefølgen ud: det gamle lag havde en fejl i
aktuel-række-flaget, konsumenterne gik derfor over til datobaserede filtre, og
det nye lag retter fejlen samtidig med at det fjerner den kolonne omgåelsen
hviler på. Begge halvdele rammer samme dag.

### Why

At efterprøve rettelsen frem for at acceptere den er ikke stædighed. Et
evidensdokument hvis rettelser afhænger af hvem der siger noget sidst, er ikke et
evidensdokument. Og havde jeg skrevet "min første version var forkert" om noget
der var rigtigt, ville den næste læser have haft to forkerte oplysninger i stedet
for nul.

Omvendt tog jeg målingen for pålydende uden at kræve bevis, fordi den kommer fra
et miljø jeg hverken kan eller må røre, og fordi den er præcis den forespørgsel
rapporten selv udpegede som den billigste vej til at lukke fire åbne punkter. Der
er forskel på en påstand om hvad koden gør — som jeg kan efterprøve — og en
observation fra et sted jeg ikke har adgang til.

Omformuleringen tog jeg imod, fordi den ikke handler om evidensen men om hvad den
betyder, og det er en forretningsvurdering jeg ikke sidder på. Den gjorde
desuden rapporten mere sammenhængende: den forklarer hvorfor tre filer bruger
mærkelige filtre, hvilket jeg havde noteret som et særpræg uden at have en
forklaring.

### What worked

At køre koden frem for at læse den. Tre linjers output afgjorde en uenighed som
ellers ville være stået påstand mod påstand, og det tog én kommando efter at
enhedstesten ikke kunne køre.

At hver klassifikation var skrevet ned med den evidens den hvilede på. Da
målingen kom, kunne jeg gå direkte til de fund hvis evidens var "kan ikke
afgøres" og genvurdere netop dem, i stedet for at læse hele rapporten igennem
igen.

At skrive rettelserne ind som et revisionsafsnit øverst frem for at redigere dem
ind usynligt. Læseren kan nu se hvad der ændrede sig og hvorfor, og de to steder
hvor min egen første udgave var forkert, står opført i rapportens egen
modsigelsestabel sammen med modsigelserne af alle andre.

### What didn't work

**Enhedstesten kunne ikke køres.** Kommandoen

```
python -m pytest lighthouse/tests/enriched_tests/test_<policymodul>.py -k "trim or clean_expression or nullified" -q
```

fejlede med

```
ImportError while loading conftest '...\lighthouse\tests\conftest.py'.
lighthouse\tests\conftest.py:2: in <module>
    from lighthouse.helpers.spark import get_spark_session
...
E   ModuleNotFoundError: No module named 'pyspark'
```

Ironien er at det modul jeg ville teste, udtrykkeligt er skrevet uden
Spark-afhængighed netop for at kunne testes uden klynge — men den fælles
conftest trækker Spark ind for alle tests i mappen. Løsningen var at indlæse
modulet direkte via `importlib` og kalde funktionen. Det er en dårligere
validering end en grøn test, og rapporten siger derfor hvad der er eksekveret og
hvad der kun er læst.

**Jeg lavede en dubletfejl under redigeringen.** En erstatning efterlod det
samme afsnit to gange lige efter hinanden i den højlydte sektion. Fanget ved at
søge på afsnittets første ord bagefter, som gav to linjenumre hvor der skulle
have været ét. Rettet før commit. Lære: efter en erstatning der flytter
tekstblokke rundt, er det billigt at tælle forekomster af den flyttede tekst.

### What I learned

**En irettesættelse skal efterprøves lige så hårdt som en påstand.** Det er
lettere at acceptere en rettelse end at afvise den, især når den er formuleret
bestemt og kommer med en instruks om at skrive fejlen ud. Men den instruks var
betinget — "gå fundet efter på ny og afgør hvad den reelle risiko er" — og
betingelsen var ikke opfyldt.

**Et flagnavn der beskriver to regler, vil blive læst som én.** Fælden her er
ikke skjult: både docstring, kode og en enhedstest siger det samme. Alligevel
faldt en læser i, fordi navnet lover mere end koden leverer. Den slags navne er
værd at markere eksplicit i en overlevering, ikke kun at dokumentere korrekt.

**Målinger flytter fund i begge retninger.** Jeg havde forventet at nye data
ville bekræfte eller afkræfte, altså tilføje eller fjerne. I praksis flyttede de
fund mellem kategorier: tre blev alvorligere (fra arvet gæld til regressioner der
kører dagligt), og ét skiftede årsag helt (fra gammel svaghed til ny fejl). En
rapport der kun havde skrevet "fund" og ikke "fund med denne begrundelse", ville
ikke have kunnet genudledes på den måde.

**Den rigtige retning på en konklusion er ikke udledelig af koden.** At et tal
flytter sig kan jeg se. Om det flytter sig fra forkert til rigtigt eller omvendt,
afhænger af hvad der var meningen — og det står ingen steder i repoet. Det
ændrer hvad man skal gøre ved fundet: her fra "pas på, noget knækker" til "et
tal bliver rigtigere, og det skal kunne forklares til forretningen".

### What was tricky

At skrive afvisningen uden at gøre den til en diskussion. Afsnittet skal kunne
læses om et halvt år af en der ikke kender udvekslingen, så det er bygget som
"her er reglen, her er hvad der er sandt om flaget, her er hvad koden gør, her er
beviset" — ikke som et svar til nogen.

Balancen mellem at afvise det ene punkt og tage imod de to andre i samme
revision. Risikoen er at det læses som selektiv stædighed. Jeg håndterede det ved
at lade rapportens modsigelsestabel indeholde **både** den afviste indvending og
mine egne to fejl, så listen ikke kun peger udad.

Og så genudledningen. Det fristende var at indsætte måledataene som et nyt
faktaafsnit og lade resten stå. Men to af de tre punkter i beskeden handlede om
klassifikation, ikke om fakta, og det er kategorierne der bærer rapportens værdi
— et fund i den forkerte kategori sender folk det forkerte sted hen.

### What warrants review

**Afsnit A.1.3.1, afvisningen.** Det er det sted hvor jeg påstår at en anden tog
fejl, og derfor det sted hvor det gør mest skade hvis jeg tager fejl. Beviset er
tre linjers eksekveret output plus en navngiven enhedstest; begge kan
efterprøves på et minut.

**De fire fund der skiftede kategori.** Tre opad, ét sidelæns. De hviler alle på
måledataene, så hvis målingen er taget i et miljø der ikke svarer til det der
skal omlægges, falder de alle fire.

**Det ene punkt målingen ikke lukkede.** Den viser kolonners eksistens, ikke
deres værdier. Hypotesen om at sletteflaget er konstant i dag er nu stærkt
understøttet, men ikke bevist, og den står stadig åben med den forespørgsel der
lukker den.

### Future work

Én optælling lukker det sidste af de oprindelige punkter om sletteflaget.

De to filer der nu er bekræftet som dagligt kørende regressioner bør prioriteres
foran resten, netop fordi de kører. Det står i rapporten, men rækkefølgen er
Bennys valg.

Og så er der en dokumentationsopgave der ikke er min: flaget hvis navn lover
trimning uden altid at levere den. Det burde stå i overleveringen, ikke kun i en
docstring som den der læser metadataviewet ikke nødvendigvis åbner.

## Step 4: En måling der omskrev mit eget hovedfund — og en push der blev afvist

**Author:** builder

### Prompt Context

**Verbatim prompt:** afkortet af hensyn til kundefortrolighed. Beskeden kom fra
samme agent som i Step 3 og bragte en ny måling: et sletteflag er nul i hver
eneste af 70 tabeller, mens et *andet* sletteflag er ikke-nul i præcis syv.
Instruksen var eksplicit om hvad jeg skulle gøre med tallene: "**Hvad der skal
udledes — genudled, indsæt ikke bare** … **Omklassificér alt der antog at de to
flag var udskiftelige.**" Og et spørgsmål stillet som et spørgsmål: "**Én ting
jeg vil have din vurdering af:** betyder målingen at det gamle lags
sletteregistrering aldrig har virket, eller at [den ene kolonne] blot er en
efterladt kolonne fra en tidligere generation mens [den anden] er den der reelt
bruges? De syv tabeller med faktiske sletninger peger på det sidste, men **afgør
det på koden.**" Dertil en opfordring til at efterprøve hans egen optælling
("verificér min optælling, tag den ikke for gode varer") og til at overveje om to
spredte krav om før/efter-måling hørte i ét fælles afsnit.

**Interpretation:** Målingen er ikke et supplement til rapporten, den er en test
af den. To af mine egne afsnit hvilede på en antagelse tallene nu kunne afgøre,
og hvis antagelsen faldt, skulle afsnittene omskrives frem for at få en fodnote.

**Inferred intent:** Han vil have rapportens *kategorier* til at holde, ikke bare
dens fakta. Et fund i den forkerte kategori sender folk det forkerte sted hen,
og det er dyrere end et fund der mangler.

### What I did

Jeg tog spørgsmålet om hvorvidt sletteregistreringen nogensinde havde virket
først, fordi svaret bestemte hvor alvorligt alt det andet var.

Det lod sig afgøre på koden. Jeg slog op hvilket kolonnenavn framework'ets
opdateringsfunktion faktisk skriver til, og hvilken parameter der styrer den.
Derefter tjekkede jeg alle de gamle transforms: de 36 der bruger den
opdaterende skrivemetode har alle sletteregistrering slået til — ingen
undtagelser — og de syv tabeller med faktiske sletninger er alle blandt de 36.
Til sidst søgte jeg efter om nogen kode overhovedet skriver til den kolonne der
er nul: det gør ingen. Den optræder ét eneste sted uden for framework'ets gamle
hjørne, og dér bliver den *læst* af et konsumentfilter.

Dermed var svaret entydigt: registreringen har virket hele tiden, i den anden
kolonne. Den nulstillede kolonne er et levn, båret ind af den `SELECT *` som
porten bruger mod sin kilde, og ikke skrevet til siden. Det gør fundet
mindre alvorligt end det så ud — men det gør en bestemt "oprydning" farlig,
fordi det filter der peger på levnet, aldrig har fjernet en række, og et
navneskifte derfor ikke er kosmetik men en forretningsmæssig ændring.

Så kom den ubehagelige del. Det samme kodeopslag afslørede at **min egen
antagelse i rapporten var forkert**. Jeg havde skrevet at sletteflaget
*muligvis* var konstant falsk på alle tabeller, og at filteret derfor var
virkningsløst overalt. Tallene viser at det er levende på 36 tabeller. Men de
viser også noget bedre: på de tabeller der skrives med fuld overskrivning findes
der ingen merge der kan sætte flaget, så dér er det *strukturelt* konstant —
ikke tilfældigvis nul. Fundet overlevede altså, men kun for en undergruppe, og
den undergruppe rummer tilfældigvis de to mest læste tabeller i hele materialet.
Jeg endte med at dele afsnittet i tre grupper — levende og ikke-nul, levende men
nul, strukturelt konstant — og skrive rettelsen som en markeret rettelse øverst i
afsnittet frem for at glatte den ud.

Blast radius efterprøvede jeg selv frem for at overtage tallet. Krydsningen
holdt: kun to af de syv tabeller er også læst af en konsument. Faldgruben var
reel — to par tabelnavne ligner hinanden nok til at kunne forveksles, og den ene
af dem *er* læst mens dens næsten-navnefælle ikke er. Jeg talte også op hvor
mange filer der rammes af den undergruppe der faktisk ændrer sig: 29 af 42.

Forslaget om at samle de to spredte målekrav tog jeg imod og udvidede: der er nu
fire poster, og en bemærkning om at de ikke må ændres samtidig, fordi bidragene
ellers ikke kan skilles ad bagefter.

Til sidst gik pushet galt. Branchen havde fået tre nye commits mens jeg
arbejdede.

### Why

At afgøre det på koden frem for på tallene var ikke pedanteri. Syv tabeller med
sletninger og 63 uden *kunne* forklares på begge måder — enten virker
registreringen og der er bare ikke slettet noget de andre steder, eller også
virker den kun sporadisk. Kun koden siger hvilken. Og forskellen er hele
alvorsgraden: et levn er en oprydningsopgave, en sporadisk virkende
sletteregistrering er et datakvalitetsproblem.

At skrive min egen fejl som en markeret rettelse frem for at redigere den væk
følger af at rapporten nu har været igennem tre revisioner. Læseren skal kunne
se hvad der har flyttet sig og hvorfor, ellers er der ingen måde at vurdere hvor
meget man kan stole på resten.

### What worked

At gå til koden med et spørgsmål tallene ikke kunne besvare. De syv tabeller med
sletninger kunne forklares på to måder, og kun ét opslag i framework'ets
skrivefunktion afgjorde hvilken. Det tog tre kommandoer og flyttede fundet fra
"muligvis alvorligt" til "et levn, men med en farlig oprydning".

At efterprøve den optælling jeg fik forærende. Den holdt, men fælden var reel —
to par tabelnavne i materialet ligner hinanden nok til at kunne byttes om, og i
begge par er den ene læst og den anden ikke.

At have skrevet evidensen ned ved hvert fund i de tidligere revisioner. Da
målingen kom, kunne jeg gå direkte til de afsnit hvis evidens lød "kan ikke
afgøres" og genvurdere netop dem.

### What didn't work

**Pushet blev afvist.**

```
 ! [rejected]        <branch> -> <branch> (non-fast-forward)
error: failed to push some refs
hint: Updates were rejected because the tip of your current branch is behind
hint: its remote counterpart.
```
(branchenavnet er erstattet; det indeholder kundens skemanavn.)

Tre commits var landet på branchen fra andet arbejde mens jeg skrev. Force push
er udelukket, så jeg hentede ned, kiggede på hvad de rørte — fem filer, ingen af
dem min — og rebasede min ene commit ovenpå. Det gik rent, fordi filsættene var
disjunkte.

**Den egentlige risiko var en anden, og den var nær sluppet forbi mig.** En af de
tre commits lagde 288 linjer til det lange dokument min rapport krydshenviser til
**med linjenumre**. Havde de linjer stået i midten, ville hver eneste henvisning
have peget et forkert sted hen efter rebasen — og ingen af mine tidligere
kontroller ville have fanget det, fordi de kun tjekker mine egne filer. Jeg
efterprøvede alle elleve henvisninger bagefter; de holdt, fordi tilføjelsen lå
til sidst. Held, ikke omhu.

**En krydsreference i rapporten har peget forkert siden første udgave.** Den
henviste til et afsnitsnummer der ikke fandtes. Fanget ved at trække alle
"afsnit N"-referencer ud og tælle dem op — et af tallene passede ikke med nogen
overskrift. Den har overlevet to revisioner og tre stikprøverunder, fordi
stikprøverne tjekkede henvisninger til *kode*, ikke til rapporten selv.

### What I learned

**Et tal kan bekræfte og modbevise samtidig.** Målingen bekræftede mønsteret jeg
havde beskrevet og modbeviste rækkevidden af det. Havde jeg kun ledt efter
bekræftelse, ville jeg have set de nul-værdier der passede og ikke de syv der
ikke gjorde.

**"Kan ikke afgøres fra repoet" var for hurtigt sagt.** Jeg havde ført
spørgsmålet om sletteflaget op som noget kun en måling kunne lukke. Men
*halvdelen* af det kunne afgøres på koden hele tiden: at en bestemt skrivemetode
strukturelt ikke kan sætte flaget, kræver ingen data. Jeg havde slået op hvad der
tilføjer kolonnen, men ikke hvad der senere kan opdatere den — og det er præcis
det spørgsmål der skiller "muligvis konstant" fra "kan ikke blive andet".

**Navnelighed mellem tabeller er en fælde der ikke ser ud som en fælde.** To par
navne i dette materiale adskiller sig med ét bogstav i starten eller en endelse,
og i begge par er den ene læst og den anden ikke. En krydsning lavet på øjemål
ville have ramt forkert; den skal laves på den fulde liste.

**Nabocommits kan ugyldiggøre mine linjehenvisninger uden at røre min fil.** Det
er en ny kategori af risiko for et dokument der henviser til andre dokumenter med
linjenummer. Kontrollen hører i rebase-rutinen, ikke kun i skriverutinen.

### What was tricky

At skrive en rettelse af mig selv i samme dokument hvor jeg i forrige revision
afviste en rettelse fra en anden. Det kunne let læses som vilkårlighed. Det
eneste jeg kunne gøre ved det, var at lade begge stå i samme tabel med samme
form — påstand, evidens, konklusion — så forskellen ligger i evidensen og ikke i
hvem der fremsatte påstanden.

Afvejningen mellem "fundet er mindre alvorligt end antaget" og "den nærliggende
rettelse er farlig" skulle stå samtidig uden at ophæve hinanden. Hvis man kun
læser det første, springer man over; hvis man kun læser det andet, går man i
panik. De endte som to adskilte afsnit med en eksplicit henvisning imellem.

Og så var der en fristelse i at lade det gamle afsnit stå og tilføje et forbehold.
Det ville have været hurtigere og ville have set ud som ærlighed. Men et afsnit
hvis overskrift påstår noget forkert, læses på overskriften.

### What warrants review

**Gruppeinddelingen i tre.** Den bærer nu hele sletteflags-fundet, og den er
udledt af skrivemønstret pr. tabel. Hvis en tabel skifter skrivemønster, skifter
den gruppe — listerne er et øjebliksbillede af koden, ikke en egenskab ved
tabellerne.

**Påstanden om at ingen kode skriver til den nulstillede kolonne.** Den hviler på
en søgning i dette repo. Skriver noget uden for repoet til den, falder
konklusionen i D.12.

**De elleve krydshenvisninger til det lange dokument.** De er efterprøvet efter
rebasen nu, men de skal efterprøves igen hver gang det dokument ændrer sig i
midten frem for i slutningen.

### Future work

Antallet af rækker der vil bære et sandt sletteflag i det **nye** lag er stadig
ukendt — det er kildelagets flag, ikke det nuværende, og det er ikke målt. Det
er den ene post i målepligt-afsnittet der ikke kan udfyldes på forhånd.

Rapporten har nu tre revisioner og et revisionslog-afsnit. Bliver der en fjerde,
er det værd at overveje om loggen skal flyttes til bunden; den fylder efterhånden
plads foran det læseren kom efter.
