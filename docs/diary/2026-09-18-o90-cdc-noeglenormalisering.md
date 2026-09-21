# Diary: Ø90 delete-detektion — den unormaliserede nøgle i CDC-sporet, og guardens blinde vinkel

*(Kundeprojekt. Tabelnavne og rækketal fra kundens data-estate er redigeret ud; dette repo
er offentligt. Fejlformen, beslutningerne og arkitekturen er det interessante og står i
fuld længde.)*

Delete-detektionen i raw-laget bygger for hver tabel et "kildenøglesæt" — de nøgler kilden
stadig har — og lader en anti-join markere alt i raw der ikke er med, som slettet. Sættet
kommer fra ét af tre spor. To af dem læser en dateret snapshot-mappe i landing. Det tredje,
CDC-sporet, læser i stedet en kontroltabel som kildesystemet selv skriver sine
DELETE-hændelser til, og trækker dem fra raws egne aktuelle nøgler.

CDC-sporet har markeret nul sletninger på nitten tabeller siden det blev bygget. Ikke
fejlet, ikke skippet — skrevet, med status `written`, hvert eneste døgn. Årsagen er én
manglende normalisering, og den er kun synlig hvis man kender begge datatyper.

Kontroltabellens nøglekolonne er `CHAR(32)`: fast bredde, blankudfyldt til højre, hver
eneste værdi præcis 32 tegn lang. Måltabellernes nøgle er i nogle tilfælde en `string` på
16 tegn. Koden caster kontroltabellens nøgle til målets type, og begrunder det udførligt i
en kommentar: caster man ikke, vælger Spark en fælles type for de to sider af joinen, og en
streng/tal-uoverensstemmelse dér matcher stiltiende ingenting. Kommentaren beskriver
præcis den fejl koden selv laver. For når måltypen *er* `string`, er castet en
nul-operation. De seksten blanktegn overlever, og anti-joinen finder aldrig noget.

Delingen følger datatypen mekanisk. Hvor målnøglen er numerisk, trimmer castet til tal
whitespace undervejs som en ren bivirkning, og sporet virker — ni af ti sådanne tabeller
finder sletninger. Hvor målnøglen er en streng, får man nul, nitten gange ud af nitten.
Samme kodesti, samme dag, modsat udfald, og forskellen er udelukkende om castet
tilfældigvis også trimmer.

Modprøven der udelukker "der er bare ikke noget at slette": en tabel med samme slags
16-tegns strengnøgle, som kører på et af snapshot-sporene, finder trecifrede sletninger.
Dér projiceres nøglerne gennem en fælles hjælpefunktion med eksplicitte måltyper i stedet
for at blive castet rå. Fejlen sidder alene i CDC-sporet.

Det andet spor i opgaven er hvorfor ingen opdagede det. Dækningsguarden måler
matchede-over-aktuelle rækker og afviser når forholdet er lavt *og* antallet af rækker der
ville blive markeret slettet er stort. Den er bygget mod et slettesæt der er for stort. Et
slettesæt der er **tomt** giver dækning 1,0000 — aflæst som maksimal tillid. Guarden er
blind i præcis den retning fejlen ligger, og har derfor rapporteret perfekt sundhed på
nitten tabeller den ikke rørte.

## Step 1: Krav, to afviste snit, og den guard der ikke må råbe hver nat

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Arbejd DIREKTE i [repo] på branch [feature-branch]. Opret IKKE et
worktree (det er blevet forsøgt før og fejlede, fordi worktreet havnede i et andet repo).
[…] `[nøglekolonne]` og `[entitetskolonne]` normaliseres. **`[nøglekolonnen i
kontroltabellen]` gør ikke.** Den går rå i `cast(raw_key_type)`. […] Trimmes begge sider,
matcher [femcifret antal] aktuelle rækker et slettet nøgle-id. I dag flages **0**. […]
Opgaven — tre dele: **1. Rettelsen.** […] Overvej om `project_keys`/`normalized` skal
genbruges frem for en fjerde stavemåde af den samme normalisering. Vurder selv om trimning
skal være symmetrisk (også på raw-siden) — raw er utrimmet efter design […] **2.
Regressionstest.** […] Testen skal fange netop denne tavse nul-match […] En test der kun
tester den numeriske sti er værdiløs her. **3. Guard C's blinde vinkel.** Dækning måles som
matched/raw_current. Et TOMT delete-sæt giver dækning 1,0000, som læses som maksimal tillid
[…] står der DELETE-poster i [kontroltabellen] for entiteten, men delete-sættet bliver
tomt, skal det larme […] 'tavs success' må det ikke være. Tærskelværdierne […] skal ikke
ændres." Efterfulgt af en course correction der afgjorde to spørgsmål jeg havde stillet:
worktree-problemet skulle løses ved at rette grundlaget frem for at genstarte, og
regressionstesten skulle gøres kørbar ved at flytte beslutningen ud af Spark-transformen
til en ren funktion — "en test der kun kan skrives og aldrig køres, tæller ikke som
leverance her. Den ville give nøjagtig den falske tryghed som guard C gav i nitten
tabeller."

**Interpretation:** Ret en normalisering der mangler ét sted, uden at indføre en fjerde
stavemåde af den samme regel. Gør rettelsen bevisbar med en test der rent faktisk kan
afvikles i det miljø den skal afvikles i. Og luk den blinde vinkel i guarden der lod fejlen
stå, uden at røre de to tærskelværdier den bygger på. Jeg leder, jeg implementerer ikke.

**Inferred intent:** Den egentlige skade er ikke de manglende sletninger — det er at
systemet rapporterede sundhed mens det intet lavede. Rettelsen er lille; værdien ligger i
at samme klasse fejl ikke kan være tavs igen. En test der ikke kan køres ville reproducere
fejlen på et andet niveau.

### What I did

Læste beslutningsmodulet, notebooken, begge testfiler og de relevante afsnit af runbooken
før jeg formede en holdning, og verificerede oplæggets påstande mod koden frem for at tage
dem for gode varer.

To fakta stoppede arbejdet før det begyndte, og begge blev meldt tilbage som spørgsmål i
stedet for antagelser.

Det første: jeg blev startet i et git-worktree trods en eksplicit instruks om ikke at bruge
et, og jeg kunne ikke selv komme ud — værktøjet til at forlade et worktree afviser
sub-agenter med cwd-override, og git-guarden nægtede at køre mod hovedcheckout'et. Det var
ikke kosmetisk: worktreets HEAD var ikke ancestor af feature-branchen, der lå 21 commits
imellem, og at bygge dér ville have bygget på kode fra før dem. Jeg lagde to veje op med
for og imod frem for at vælge selv. Undervejs blev isolationen ophævet, så punktet
bortfaldt af sig selv og arbejdet kunne foregå direkte på feature-branchen som oprindeligt
bedt om.

Det andet var vigtigere. Jeg havde rapporteret at regressionstesten hørte hjemme i den
Spark-backede testfil, og at den ikke kunne køres. Da jeg blev presset på det, tjekkede jeg
i stedet for at gentage påstanden, og min egen formulering viste sig upræcis: maskinen har
ingen Java (`java: command not found`, `JAVA_HOME` unset), så lokal Spark er udelukket —
men projektets `pyproject.toml` har Databricks Connect som *hoved*-dependency, og suiten
kører mod en rigtig cluster. Testen er ikke ukørbar. Den er ukørbar *her*. Forskellen
afgør hele leverancen, og jeg havde sløret den.

Derefter designede jeg snittet og afviste undervejs to varianter, som jeg mener er værd at
skrive ned fordi de begge ser rigtige ud.

Den første afviste: en ren funktion på *værdi*-niveau som Spark-transformen kalder direkte.
Det er den mest oplagte læsning af "flyt beslutningen ud af transformen", men at få
transformen til rent faktisk at kalde den betyder en Python-UDF pr. række på en
kontroltabel i millionklassen, nitten gange pr. kørsel. Det koster Catalyst muligheden for
at skubbe filteret ned i scanningen og serialiserer hver række. Kalder transformen den
derimod *ikke*, er den en parallelimplementation der kan glide fra hinanden i tavshed —
altså præcis den fejlklasse vi er ved at rette.

Den anden afviste: at lade den rene funktion returnere normaliseringstrinnene som data, og
lade Spark-siden bygge sit udtryk ved at læse den samme liste. Det fjerner ganske rigtigt
driftrisikoen helt, men det er en mini-fortolker for to operationer, og det ville forvride
en kodebase hvis stil er lange, argumenterede begrundelser frem for indirektion.

Snittet jeg valgte ligger i stedet på to højder samtidig. En ren funktion i
beslutningsmodulet tager værdien og måltypen og svarer hvad der skal sammenlignes — den
bærer *semantikken*, testes uden cluster, og dækker de tre tilfælde der betyder noget:
blankudfyldt værdi mod strengnøgle skal matche, samme værdi mod numerisk nøgle skal blive
ved med at matche, og en værdi der ikke kan blive måltypen må ikke tavst blive NULL.
Spark-siden er en ordret transskription på to navngivne operationer i samme rækkefølge,
placeret lige ved siden af. Og den Spark-backede test er det eksekverbare bevis på at de to
sider er enige — den skrives af builderen og køres af kunden mod deres cluster.

Det tredje design var det der tog længst tid, og hvor den første løsning var forkert.

Den nærliggende kontrol mod guardens blinde vinkel er: står der DELETE-poster for
entiteten, men bliver slettesættet tomt, så afvis. Den ville have fanget fejlen. Den ville
også have fejlet jobbet hver eneste nat bagefter. For dagen efter rettelsen er de nu
markerede nøgler netop *markeret slettet*, og falder dermed ud af det aktuelle rækkesæt
kontrollen måler mod — så et tomt match bliver den normale, korrekte steady state. En guard
der råber hver nat er en guard man holder op med at læse, hvilket er nøjagtig den
mekanisme modulets egne kommentarer allerede advarer imod ét sted.

Jeg prøvede så at skelne på om slettenøglerne overhovedet er brugbare efter normalisering,
men den skelnen fanger ikke den oprindelige fejl: en blankudfyldt værdi castet til `string`
er ikke NULL, den er bare forkert. Sættet ville have været fuldtalligt og ubrugeligt på
samme tid.

Diskriminatoren der holder, er at måle mod **hele** måltabellen i stedet for kun de
aktuelle rækker. Matcher slettenøglerne intet som helst nogen steder i raw, er
normaliseringen i stykker og det skal larme. Matcher de rækker der allerede er markeret
slettet, er det steady state og skal være stille. Og for at det ikke koster en ekstra
fuld-scanning hver nat på tabeller i hundredmillionklassen, køres den kun i det ene
tvetydige tilfælde hvor det aktuelle match er nul.

### Why

Rettelsen i sig selv er en linje og kunne have været skrevet på fem minutter. Alt det
ovenstående handler om at den samme fejl ikke kan blive tavs igen — hverken i koden, i
testen eller i guarden. Præcis den ambition er grunden til at "en test der ikke kan køres"
ikke tæller: den ville flytte den falske tryghed et niveau op i stedet for at fjerne den.

De to afviste snit står skrevet ned frem for droppet, fordi begge er den slags idé man får
igen om tre måneder.

### What worked

At tjekke frem for at gentage. Påstanden "testen kan ikke køres" var min egen, den var
forkert på den afgørende led, og et enkelt opslag i projektets dependencies afgjorde det.
Havde jeg holdt fast i den, var leverancen blevet en dårligere test begrundet i en
begrænsning der ikke fandtes.

At lægge worktree-problemet op som to veje med omkostninger på begge sider frem for at
vælge selv. Valget havde konsekvenser for hvor commits landede, og det var ikke mit.

### What didn't work

Den første udgave af kontrollen mod den blinde vinkel — afvis når slettesættet er tomt
selvom der findes DELETE-poster — var forkert, og ikke på en måde der ville have vist sig i
en test. Den ville have bestået alt på dag ét og fejlet hver nat fra dag to, fordi den
målte mod et rækkesæt som rettelsen selv tømmer. Den anden udgave, der i stedet så på om
nøglerne var brugbare efter normalisering, ville slet ikke have fanget den oprindelige fejl.
To forkerte designs før det rigtige.

Derudover: `ExitWorktree` afviste mig med "cannot be called from a subagent with a cwd
override (isolation: \"worktree\" or explicit cwd)", og git mod hovedcheckout'et blev
blokeret med "Refusing to run it — a worktree-isolated agent's git operations must target
its own worktree". Der var ingen vej ud indefra; det løste sig kun fordi isolationen blev
ophævet udefra.

### What I learned

En cast brugt som normalisering er kun en normalisering for nogle typer. Cast til tal
trimmer whitespace som bivirkning; cast fra streng til streng gør ingenting. Skriver man
`cast(target_type)` med en variabel måltype, har man dermed skrevet to forskellige
funktioner, og den ene af dem virker. Fejlformen er usynlig i kodelæsning, fordi linjen
ser ens ud i begge tilfælde.

Og: en dækningsmetrik på formen matchede/totale har altid en blind ende. Den kan kun se at
sættet er for lille, aldrig at det er tomt, for et tomt sæt giver perfekt score. Enhver
guard bygget på et forhold bør spørges hvad den siger når tælleren går mod nul.

### What was tricky

At se at den rigtige kontrol skal måle mod hele måltabellen og ikke mod de aktuelle rækker.
Alt andet i delete-detektionen arbejder udelukkende på aktuelle rækker — det er lagets
kontrakt — så det er imod kodebasens egen grammatik at kigge bredere ét enkelt sted.
Begrundelsen er at rettelsen ændrer netop det rækkesæt kontrollen skulle have målt mod, og
en kontrol må ikke måle på noget dens egen succes fjerner.

### What warrants review

Om den rene funktion og Spark-udtrykket rent faktisk er semantisk identiske i alle tre
tilfælde — det er hele leverancens omdrejningspunkt, og den Spark-backede test er det
eneste sted det bliver bevist. Den test kan kun køres mod en rigtig cluster.

Om trimning skal være symmetrisk. Raw-siden er utrimmet efter design, og andre tabellers
nøgler kan have anden bredde end deres modpart i kontroltabellen, så en tosidet trimning
kan ændre match-adfærd på tabeller der virker i dag. Builderen skal begrunde valget i koden.

Og førstegangskørslen: rettelsen markerer med ét et stort antal rækker slettet på nitten
tabeller, hvoraf flere er i hundredmillionklassen. Tallene skal stemme med det målte
estimat — væsentligt flere er et tegn på at trimningen greb bredere end tilsigtet.

### Future work

Det åbne spørgsmål er om `project_keys`-hjælperen i notebooken og normaliseringen i
beslutningsmodulet burde være én funktion frem for to. De løser samme problem — få to sider
af en join til at tale samme sprog — og at de er skrevet hver for sig er selve årsagen til
at den ene kunne mangle et trin. En sammenlægning er større end denne rettelse og hører til
sit eget stykke arbejde.

## Step 2: Rettelsen, guard D, og de to valg der skulle begrundes i koden

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** "Du bygger en fejlrettelse i et kundeprojekt. Kravene er færdigt
afklaret — byg dem, lad være med at genåbne designet, men sig højlydt fra hvis noget viser
sig umuligt eller forkert når du rammer koden. […] Normaliser `[nøglekolonnen]` før castet.
**Snittet er besluttet, og det er ikke til forhandling — men det er vigtigt du forstår
hvorfor, for det styrer hvor koden skal ligge:** Læg en **ren funktion uden pyspark** i
[beslutningsmodulet], i modulets rene del […] Spark-siden […] bliver en **ordret
transskription** af samme to operationer i samme rækkefølge […] **To ting du selv skal
afgøre og BEGRUNDE I KODEN:** 1. Skal `normalized()` genbruges på [nøglen] i stedet for
`trim`? […] Jeg forventer du afviser genbrug og skriver begrundelsen i koden — men tjek
selv og sig fra hvis jeg tager fejl. 2. Skal trimningen være symmetrisk (også på
raw-siden)? […] Undersøg og vælg; begrund valget i koden med det argument der faktisk bar
det. […] **To tests, to højder. Den ene SKAL du køre.** […] **(b) Spark-backet test — du
skriver den, du kan ikke køre den.** […] **Installer IKKE en JDK og IKKE pyspark.** Skriv i
din rapport ordret at (b) er skrevet men ikke kørt […] Påstå under ingen omstændigheder at
den er grøn. […] **Byg dette:** Diskriminatoren er at måle mod **hele** måltabellen i
stedet for kun de aktuelle rækker."

**Interpretation:** Byg et færdigt design uden at genforhandle det, men tag selvstændigt
ansvar for to designvalg og for at begrunde dem dér hvor de står. Bevis rettelsen med en
test der faktisk kan afvikles her, og skriv den test der ikke kan — uden at lade som om den
er kørt.

**Inferred intent:** Leverancen er ikke linjen der retter fejlen; den er at fejlen og dens
klasse ikke kan være tavs igen — i koden, i testen og i guarden. Derfor er kravet om
begrundelse *i koden* lige så bindende som kravet om at koden virker.

### What I did

Læste beslutningsmodulet, notebooken, begge testfiler, runbooken og — afgørende for det ene
af de to valg — den fremmede skrivefunktion `soft_delete` i platformsbiblioteket, før jeg
rørte noget.

**Rettelsen** blev en ren værdifunktion i beslutningsmodulets pyspark-fri del: den tager
nøgleværdien og måltypen og svarer hvad der skal sammenlignes. Den har tre slags svar, og
at de tre er skelnelige er hele pointen: `None` når kontroltabellens række slet ikke
navngiver en nøgle, en navngiven sentinel når værdien *findes* men ikke kan blive måltypen,
og ellers værdien selv i målets type. Spark-siden trimmer og caster i samme rækkefølge, og
begge sider bærer i deres dokumentation at den anden findes.

To detaljer viste sig først da jeg skrev den. Spark trimmer kun *mellemrumstegn*, ikke al
whitespace, så den rene funktion bruger `strip(" ")` og ikke `strip()` — ellers er den ikke
en spejling, den er noget der ligner en. Og Python er for large ved parsning af tal:
`int("1_0")` er 10, og `Decimal("NaN")` er en gyldig Decimal. Spark siger NULL til begge.
Derfor matches formen med et regulært udtryk *før* der parses; uden det ville den rene
funktion give grønt lys til værdier Spark stiltiende ville droppe, hvilket er den samme
fejlklasse en etage nede.

**De to valg jeg selv skulle afgøre.** Begge landede som leaden forventede, men det andet
har et stærkere argument end det oplæg jeg fik.

*Genbrug af den gamle `normalized()`-hjælper: afvist.* Ud over at den fjerner indlejrede
mellemrum og dermed opfinder en anden nøgle, er det afgørende at dens `lower()` kun
anvendes på **den ene side**. De to felter den bruges på i dag sammenlignes mod værdier
kalderen selv har lowercased; raws nøglekolonne er urørt. At folde en base64-agtig nøgle
til småt ville altså blive ved med at matche ingenting for enhver nøgle der indeholder et
stort bogstav — den ville holde præcis denne fejl i live på præcis de tabeller rettelsen
findes for.

*Symmetrisk trimning: afvist, og af en mekanisk grund frem for en forsigtig.* Oplægget
begrundede det med at raw er utrimmet efter design og at andre tabellers nøgler kan have
anden bredde. Det holder, men det er ikke det der afgør sagen. `soft_delete` læser selv
måltabellen og anti-joiner kildenøglesættet mod den på nøglekolonnerne. Kildenøglesættet
plukkes direkte ud af raws egne aktuelle nøgler. Trimmede man raw-siden inde i transformen,
ville `soft_delete` få *trimmede* nøgler at matche mod *utrimmede* gemte værdier — og hver
eneste række hvis raw-nøgle bærer udfyldning ville blive markeret slettet. En symmetrisk
trimning er ikke en strengere udgave af rettelsen; det er den gamle katastrofe-fejlform med
en ny årsag. Det argument står nu i koden, fordi det er det der faktisk bar valget.

**Guard D** blev bygget som beskrevet: tæl DELETE-poster, og kun hvis der findes poster
*og* nul aktuelle rækker flages, betal for den dyre kontrol mod hele måltabellen. Fire
udfald, fire navngivne konstanter.

Ét greb er mit eget og er værd at nævne. De to tællinger sendes ind i den rene funktion som
**callables**, ikke som tal. Dermed bliver "den dyre kontrol køres kun i det tvetydige
tilfælde" en egenskab en test kan *hævde* — jeg tæller kaldene — i stedet for et løfte i en
kommentar i notebooken. Mønsteret findes i forvejen i samme modul, hvor mappe-opslaget
tager filsystem-listningen som argument og fakes i test. Havde jeg i stedet kortsluttet i
notebooken, ville betingelsen stå to steder og kunne glide fra hinanden.

Den dyre kontrol er desuden `limit(1)`-begrænset, fordi verdikten kun spørger "nogen som
helst". Det gør en fuld scanning til en der kan stoppe ved første match.

**Tests.** Den rene suite gik fra 84 til 121 beståede. Den Spark-backede fik to nye:
strengnøglen (den fejlen handler om) og den numeriske (modprøven der skal bevise at det der
virkede stadig virker).

### Why

Kravet om at begrunde valgene *i koden* frem for i en rapport er det der gør denne kodebase
læsbar tre måneder senere, og det er samme princip som Step 1's afviste designs: en
beslutning uden nedskrevet argument bliver genåbnet af den næste, ofte forkert.

Callable-grebet i guard D er den samme tanke anvendt på ydeevne: en omkostningsgaranti der
kun står i en kommentar er ikke en garanti.

### What worked

At køre de nye testpåstande mod den **gamle** adfærd i stedet for at antage at de fanger
noget. Jeg skrev en lille engangsfil der reimplementerer før-tilstanden (cast alene, som er
identitet for streng) og kørte de to nye påstande mod den:

```
1 failed, 1 passed
AssertionError: assert '<16-tegns nøgle + 16 blanktegn>' == '<16-tegns nøgle>'
```

Strengtesten fejler på den gamle adfærd, den numeriske består. Det er nøjagtig det bevis
der skulle til: testen fanger fejlen, og den numeriske sti er uberørt af rettelsen. Uden
den kørsel ville jeg kun have haft en påstand om at testen er en regressionstest.

At læse den fremmede skrivefunktion frem for at nøjes med oplæggets begrundelse. Det
ændrede det andet valg fra "det kan ændre adfærd" til "det ville gentage katastrofen", og
den forskel afgør hvor stærkt argumentet står i koden.

### What didn't work

**Min egen dokumentation drev fra koden inden for samme session.** For at give guard D
adgang til samme slettesæt som nøglesættet bygges af, udskilte jeg delmængde-bygningen i
sin egen funktion. Den rene funktions dokumentation sagde stadig at Spark-udtrykket lå i
*den gamle* funktion — altså præcis den drift mellem de to sider som hele spejlings-designet
advarer imod, opstået inden for én time. Fundet i selv-reviewet, ikke af en test. Der er
ingen kontrol der fanger den slags; det er argumentet for at holde de to funktioner så tæt
på hinanden som muligt.

**Runbook-afsnittet kunne ikke skrives med heredoc.** Forsøget på at appende ~230 linjer
dansk markdown gennem en quoted heredoc i bash fejlede:

```
/usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `''
```

Indholdet har apostroffer og backticks i sig, og kommandoen overlevede ikke vejen gennem
værktøjslaget. Løsningen var at droppe shell'en og bruge fil-redigeringsværktøjet med de
sidste to linjer af filen som anker. Lære: store tekstblokke skal ikke gennem en shell.

**Én egen sjuskefejl:** jeg skrev `collect_run_problems([...], outcome and [outcome])` i en
test — et meningsløst `and` fra en halv omskrivning. Den bestod, fordi udtrykket tilfældigvis
evaluerer til det rigtige. Fanget ved gennemlæsning af diff'en, ikke af suiten.

### What I learned

En udskillelse af en funktion er også en dokumentationsændring. Refaktoreringen var
mekanisk korrekt — testene var grønne hele vejen — og efterlod alligevel tre henvisninger
der pegede det forkerte sted hen. Grøn suite siger intet om hvorvidt teksten stadig passer.

Og: når en ren funktion skal spejle en motors adfærd, er det *edge cases i parseren* der
afgør om spejlingen holder, ikke hovedsagen. Hovedsagen — trim og cast — er triviel at få
rigtig. Det er `strip()` mod `strip(" ")` og `int("1_0")` der bestemmer om de to sider
faktisk er enige.

### What was tricky

At få snittet mellem "hvad er cheap nok til at køre hver nat" og "hvor bor reglen" til at
falde ud, uden at duplikere betingelsen. Den naive løsning — kortslut i notebooken før den
rene funktion kaldes — gør beslutningen til to halvdele på to steder. Callable-formen løste
det, men det tog et par forsøg at se at det var den samme mekanisme som det eksisterende
filsystem-mønster i modulet.

Og at afgøre hvad en tom eller blank-kun nøgleværdi skal svare. Spark giver to forskellige
svar afhængigt af måltype. Jeg foldede dem til ét og skrev eksplicit i dokumentationen at
det er det ene sted funktionen bevidst *ikke* spejler Spark, og hvorfor det ikke ændrer
noget udfald. Et stiltiende afvig ville have været nøjagtig samme fejlklasse som den der
rettes.

### What warrants review

**Den Spark-backede test er skrevet, men IKKE kørt.** Maskinen har ingen Java (`java:
command not found`, `JAVA_HOME` unset), og pyspark er ikke installeret; suiten kræver
Databricks Connect mod en kørende cluster. Jeg har hverken installeret en JDK eller pyspark,
og jeg påstår ikke at testen er grøn. Den er det eneste sted hvor spejlingen mellem den rene
funktion og Spark-udtrykket rent faktisk bevises, så indtil den er kørt, er netop
leverancens omdrejningspunkt uverificeret.

Guard D's dyre gren er heller ikke kørt mod rigtige data. Jeg ved at aritmetikken er
korrekt — den er ren og testet, inklusive at den dyre callable ikke røres på de billige
stier — men ikke hvad `limit(1)`-joinen koster på en tabel i hundredmillionklassen. Det kan
kun måles i målmiljøet.

Endelig: sammenfoldningen af "NULL nøgle" og "kun blanktegn" til ét svar. Den er begrundet
og jeg mener den er rigtig, men den er et bevidst afvig fra motorens adfærd og fortjener et
par øjne.

### Future work

Step 1's åbne spørgsmål — om nøgleprojektionen i notebooken og normaliseringen i
beslutningsmodulet burde være én funktion — står stadig, og jeg fandt intet billigt snit.
De to har forskellige input (en DataFrame med navngivne kolonner mod en enkelt værdi) og
forskellige fejltilstande, så en sammenlægning ville skulle opfinde et fælles begreb frem
for blot at flytte kode. Det er sit eget arbejde, som leaden vurderede.

En mindre, mere konkret: sentinel-værdien for "kan ikke blive måltypen" kan i dag kun
tælles af den rene funktions kaldere, og Spark-siden har ingen kalder. Skal den tælles i
drift, kræver det en aggregering på Spark-siden der tæller NULL efter castet — billigt, men
ikke bygget, og ikke nødvendigt for denne rettelse.

## Step 3: Regressionen jeg selv indførte — ensidet normalisering, ti tabeller brækket i produktion

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** "Du skal rette en regression som du selv indførte i går, og som er
deployet og har brækket ti tabeller i nat. Læs hele briefen før du rører noget. Designet er
afgjort; byg det, men sig højlydt fra hvis noget viser sig forkert når du rammer koden. […]
Den natlige kørsel [dato] fejlede med guard D på ti tabeller: `[kontroltabellens] delete keys match
no row in the raw target at all (key normalisation)` — [ti tabelnavne]. Det er præcis de ti
der **virkede** med den gamle kode. **Præmissen 'de ti er numeriske, castet trimmer som
bivirkning' var forkert.** Målt i dev: […] `[nøglekolonnen]` er en **streng på 32 tegn**:
26 cifre plus seks blanktegn. Ikke numerisk. Den rigtige skillelinje er **bredde, ikke
type**. […] De matchede fordi begge sider var udfyldt til **samme bredde** — et sammenfald,
ikke en korrekthed. […] Din ensidede trim fjernede udfyldningen på den ene side og ødelagde
netop de par, der passede ved sammenfaldet. […] **Dit `soft_delete`-argument var rigtigt om
outputtet og forkert om sammenligningen.** Outputtet skal være raws egen gemte værdi — det
står fast […]. Men **sammenligningen** skal normalisere begge sider. […] **Paritet med
produktion er ikke målet — den gamle har samme fejl.** […] **1f. Ny risiko du selv skal
analysere og svare på i rapporten.** Tosidet trim kan kollapse to raw-nøgler der kun
adskiller sig ved efterstillede blanktegn […] Er det ikke [gratis], så **byg det ikke** […]
**Del 2 — Testen der skulle have fanget det.** 121 tests var grønne mens regressionen gik i
produktion. De to Spark-tests, der ville have fanget den, blev aldrig kørt. Konklusionen er
ikke 'kør Spark-testene' — det er at **sandheden skal testes uden cluster.** […] **Bevis at
de fanger det:** kør dem mod nuværende HEAD og vis at bredde-32-testen fejler, før du
retter. […] **Del 3 — Guard D.** Guard D bliver. Den gjorde sit arbejde […] **Del 4 —
Runbook.** […] Afsnittet forklarer fejlen som 'streng mod tal'. **Det er forkert** […]"

**Interpretation:** Ret min egen regression, og ret den på den rigtige årsag frem for på
symptomet. Behold det halve af mit tidligere argument der holdt (outputtet), og kasser det
halve der ikke gjorde (sammenligningen). Byg ikke et natligt scan for en risiko der ikke
kan måles billigt — dokumentér den i stedet. Og flyt sandheden ned i tests der kan køres
uden cluster.

**Inferred intent:** Skaden er ikke de ti tabeller; de er reversible. Skaden er at jeg
leverede en rettelse med grønt testlys på en præmis om datatyper jeg aldrig målte, og at
jeg kun verificerede den halvdel jeg havde ændret. Opgaven er at gøre den fejlklasse svær
at gentage — strukturelt, ikke ved at love at være mere omhyggelig.

### What I did

Læste briefen færdig før jeg rørte noget, og begyndte med at genskabe den gamle kode i en
skrabet mappe uden for repoet (`git show <HEAD-sha>:<sti> > <scratch>/<sti>`) så jeg kunne
køre tests mod før-tilstanden uden at røre arbejdskopien. Baseline bekræftet: 121 beståede.

**Rettelsen.** Den rene funktion er ikke længere nøglekolonne-specifik. Den hedder nu noget
der siger hvad den gør — reducér *en nøgleværdi fra hvilken som helst af de to sider* til
dens sammenligningsform — og reglen er typebevidst: er raws nøgle en streng, trimmes begge
sider; er den numerisk, trimmes og castes kontroltabellens side mens raw-siden er identitet,
fordi en numerisk kolonne ikke kan bære udfyldning. Typeklassificeringen er trukket ud i én
hjælper, fordi den rene funktion og de to Spark-udtryk skal være enige om hvad "en
strengnøgle" er.

Spark-siden blev til to navngivne udtryksbyggere, én pr. side. Slettesættet leveres nu på
en normaliseret join-nøgle med sit eget kolonnenavn i stedet for at blive aliasset til raws
nøglenavn, og nøglesæt-transformen joiner raw på det samme udtryk og **selecter raws egen
urørte kolonne ud**. Både anti-joinen og reinstatement-joinen er skrevet om.

**Følgefejlen jeg missede sidst, og som leaden fandt.** Guard D's dyre tælling i notebooken
joinede slettesættet mod måltabellen på raws nøglekolonner. Da slettesættets nøgle blev
normaliseret, skulle den join med — ellers ville guard D afvise falsk på præcis den
mismatch den findes for at opdage. Den er rettet. Jeg gennemgik alle forbrugere af
slettesæt-funktionen; der er to, og begge er i filer jeg rørte.

Ét greb er mit eget: jeg **fjernede** nøglekolonne-parameteren fra slettesæt-funktionen i
stedet for at lade den stå ubrugt. Dermed fejler en forbruger skrevet mod den gamle kontrakt
på selve kaldet, og en forbruger der joiner uden at normalisere raw fejler på en manglende
kolonne — i stedet for tavst at matche nul, som er hele fejlformen.

**Kollisionsrisikoen (1f): analyseret, ikke bygget.** Tosidet trim kan folde to raw-nøgler
sammen hvis de kun adskiller sig ved blanktegn i enderne. På en kolonne med fast bredde kan
det ikke ske — er hver værdi udfyldt til samme bredde, medfører `trim(a) = trim(b)` at
`a = b` — og målingen siger at begge grupper er fast bredde. Jeg byggede intet natligt scan,
og begrundede det to steder: målingen kræver to fulde aggregeringer over hele måltabellen,
så den er ikke gratis inden for guard D's `limit(1)`-arbejde; og guard D betaler kun for sin
dyre gren når slettesættet flager nul, hvilket er netop det tilfælde hvor en kollision ikke
kunne have gjort skade. En kollisionskontrol hængt på guard D ville køre dér hvor den ikke
kan hjælpe og mangle dér hvor den kunne. Den håndkørte forespørgsel står i koden og i
runbooken.

**Tests og runbook.** De rene tests dækker nu begge bredder og er formuleret som "de to
sider lander på samme værdi", ikke som "funktionen returnerer X". Spark-testene fik bredde
32 med, inklusive en påstand om at den overlevende nøgle kommer tilbage i raws **udfyldte**
form. Runbook-afsnittet er skrevet om fra "streng mod tal" til bredde-forklaringen, med
hændelsen og en prøvekørsel der dækker begge grupper.

### Why

Det centrale i briefen er skelnen mellem *sammenligningen* og *outputtet*, og den er grunden
til at mit oprindelige argument både var rigtigt og forkert. Skrivefunktionen anti-joiner
mod måltabellen selv, så nøglesættet skal bære raws gemte værdier — dér holdt argumentet.
Men deraf følger ikke at *sammenligningen* skal ske på de gemte former. Nøglesættet bygges
ud af raw i forvejen, så man kan joine på et normaliseret udtryk og lade den urørte kolonne
være den der kommer ud. Det er to forskellige kolonner i samme frame, og jeg foldede dem
sammen til én beslutning.

Prøvekørslen skal dække begge bredder af samme grund som testene skal: det var den manglende
modprøve der lod regressionen slippe igennem. Én grøn gruppe beviser ingenting om den anden.

### What worked

At køre de nye tests mod den **gamle** kode i en udtrukket kopi frem for at antage at de
fanger noget — samme greb som i Step 2, og det er efterhånden det eneste jeg stoler på.
Opsætningen er tre linjer `git show` ind i en scratch-mappe med samme mappedybde, fordi
testfilen finder modulet relativt til sin egen placering.

At bygge en selvstændig reproduktion af den faktiske sammenligning frem for at nøjes med
pytest-udfaldet. Den viser fejlen i tal i stedet for i en stacktrace:

```
group            raw side (HEAD: identity)            ref side (HEAD: trim+cast)     match
width 16 group   '<16-tegns nøgle>'                   '<16-tegns nøgle>'             YES
width 32 group   '<26 cifre + 6 blanktegn>'           '<26 cifre>'                   NO  <-- delete set reaches nothing
```

Den tabel er hele regressionen på to linjer, og den viser samtidig hvorfor bredde-16-gruppen
blev repareret i samme greb som bredde-32-gruppen blev brækket.

### What didn't work

**Det vigtigste først: jeg leverede en rettelse der var grøn på 121 tests og brækkede ti
tabeller i produktion, fordi præmissen om datatyperne var forkert og jeg kun verificerede
den halvdel jeg havde ændret.**

Jeg så at ti objekter fandt sletninger og nitten fandt nul, og jeg konkluderede at de ti var
numeriske og at castet trimmede som bivirkning. Det var en forklaring der passede på
udfaldet, og jeg målte den aldrig. Ét opslag på nøglekolonnens længde i dev ville have
afgjort det:

```sql
SELECT <nøgle>, LENGTH(<nøgle>) FROM <måltabel> WHERE <aktuel-række-filter> LIMIT 5;
-- 26 cifre + 6 blanktegn, LENGTH = 32, dtype string
```

Kolonnen er en **streng på 32 tegn**. Skillelinjen var bredde, ikke type. De ti matchede
fordi begge sider tilfældigvis var udfyldt til samme bredde — et sammenfald. Min ensidede
trim fjernede udfyldningen på den ene side og ødelagde netop de par der passede ved
sammenfaldet: trimmet 26 mod utrimmet 32 matcher ingenting. Natkørslen fejlede med

```
BLOCKED: [kontroltabel] delete keys match no row in the raw target at all (key normalisation)
```

på præcis de ti objekter der virkede før.

Værre end den forkerte præmis er verifikationen. Jeg skrev to Spark-tests: én for gruppen
jeg reparerede, og én "modprøve" for gruppen der virkede. Modprøven var **numerisk** — altså
skrevet mod den præmis jeg ikke havde målt, ikke mod de data gruppen faktisk indeholder. Den
ville være grøn både før og efter, og den beviste derfor ingenting om de ti tabeller den
skulle beskytte. En modprøve der er afledt af samme antagelse som rettelsen er ikke en
modprøve. Og begge tests kræver cluster og blev aldrig kørt, så selv den værdi de havde,
blev aldrig hentet. 121 grønne tests og et ubevist omdrejningspunkt.

**Den anden ting, og jeg siger den højt fordi briefen bad om det:** kravet var at
bredde-32-testen skal fejle på nuværende HEAD. Den gør den — men med

```
AttributeError: module '<beslutningsmodul>' has no attribute '<den nye regel-funktion>'
```

og **ikke** med en værdi-uoverensstemmelse. Det er ikke sjusk i testen; det er en egenskab
ved designet. Når reglen er én symmetrisk funktion anvendt på begge sider, kan den funktion
ikke udtrykke en ensidet fejl: kører man den gamle funktion på begge sider, lander de også
på samme værdi. Den gamle kode har slet ingen regel for raw-siden, og det er netop defekten
— så det eneste en ren test kan se, er at reglen mangler. Den numeriske reproduktion ovenfor
er derfor det egentlige bevis, og den er kørt.

Deraf følger noget ubehageligt som jeg ikke vil pakke ind: **en ren, symmetrisk
regel-funktion kan ikke bevise at Spark-siden bruger den på begge sider.** Transskriptionen
er stadig håndskrevet, og det var dér fejlen sad. Derfor lagde jeg beskyttelsen i
*strukturen* i stedet for i en påstand — slettesættet bærer ikke længere et raw-stavet
nøglenavn, og parameteren er væk — men det endelige bevis ligger stadig i Spark-testene.

**En tredje, mindre:** linteren kunne ikke køres. `python -m ruff check <filer>` svarede

```
C:\Python314\python.exe: No module named ruff
```

Ruff står som optional dependency i `pyproject.toml` og er ikke installeret i det aktive
miljø. Jeg installerede den ikke, og filerne er derfor kun byte-kompileret, ikke lintet.

### What I learned

**En ensidet normalisering kan ikke være rigtig.** Den gør ikke sammenligningen korrekt —
den flytter kun hvilke bredder der tilfældigvis stemmer overens. Sammenligningen skal
reducere begge sider til samme form, eller også hviler den på et sammenfald. Det gælder
uanset om man kalder normaliseringen trim, cast eller projektion.

**Et sammenfald der virker, ser ud præcis som korrekthed i et testoutput.** De ti objekter
havde fundet sletninger hver nat i ugevis. Det var det stærkeste "bevis" der fandtes for at
den sti var rigtig, og det var ikke et bevis for noget som helst — begge sider bar bare
samme udfyldning.

**Og det jeg faktisk skal ændre ved mig selv:** når jeg forklarer et delt udfald med en
egenskab ved data, skal jeg måle den egenskab før jeg bygger på den. Ikke aflede den af
udfaldet. Den forklaring jeg havde ("de ti er numeriske") var bagudkonstrueret fra
resultatet, og den var forenelig med alle de data jeg havde set — fordi jeg ikke havde set
på data.

### What was tricky

At indse at "skriv en ren test der fejler på den gamle kode" ikke kan lade sig gøre i
værdi-forstand her, og at det ikke er en mangel ved testen men en konsekvens af at reglen er
symmetrisk. Jeg brugte flere runder på at prøve at formulere mig ud af det, før jeg
accepterede at det rigtige svar var at sige det ligeud og levere reproduktionen ved siden af.

Og afvejningen i 1f: at afgøre at en måling ikke skal bygges er sværere at stå på end at
bygge den. Det argument der bar det, er ikke "det er dyrt" men "den ville køre dér hvor den
ikke kan hjælpe" — guard D's dyre gren betales kun når nul rækker flages, og en kollision
gør kun skade når noget flages.

### What warrants review

**Spark-testene er skrevet, men IKKE kørt.** De kræver Databricks Connect mod en kørende
cluster; maskinen her har hverken Java eller pyspark, og jeg har ikke installeret nogen af
delene. Jeg påstår ikke at de er grønne. De er igen det eneste sted hvor spejlingen mellem
den rene regel og de to Spark-udtryk bliver bevist — og det er anden gang i træk at netop
det bevis står uindfriet.

Prøvekørslen skal dække **begge** bredder. Én gruppes kendte tal beviser ingenting om den
anden; det er hele lærestykket fra denne regression.

Kollisionsrisikoen ved tosidet trim er argumenteret, ikke målt. Argumentet holder hvis
kolonnerne faktisk er fast bredde, og det er observeret på en stikprøve, ikke på hele
tabellen. Forespørgslen der afgør det står i koden og i runbooken og bør køres én gang pr.
objekt før den brede kørsel.

Guard D's dyre gren er igen ikke kørt mod rigtige data, nu med et normaliseret join-udtryk
på raw-siden. Et udtryk i joinen kan koste en projektion før scanningen kan beskæres; hvad
det betyder på en tabel i hundredmillionklassen kan kun måles i målmiljøet.

### Future work

Det strukturelle hul står stadig åbent: to håndskrevne Spark-udtryk spejler én ren funktion,
og intet automatisk fanger det hvis de glider fra hinanden. Det er nu sket én gang, med
produktionskonsekvens. En mulighed er at lade de rene tests generere de par af værdier som
Spark-testene kører på, så de to niveauer i det mindste deler datasæt — det fjerner ikke
spejlingsrisikoen, men det gør det sværere at teste de to sider på forskellige antagelser,
hvilket er præcis det der skete her.

Step 1's og Step 2's åbne spørgsmål — om nøgleprojektionen i notebooken og normaliseringen i
beslutningsmodulet burde være én funktion — er blevet mere relevant, ikke mindre. Der er nu
tre steder der får to sider af en join til at tale samme sprog.

## Step 4: Kunden accepterede rettelsen og afviste beviset — så blev antagelserne målt

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Byg en engangs-måle-notebook. Baggrunden er, at [kunden] har
accepteret den rettelse du lavede, men ikke beviset bag den — og han har ret. Hele
bredde-forklaringen hviler på to målinger, og kollisionsrisikoen blev afvist ud fra to
stikprøver. Nu skal nøgleforholdene måles for begge spor, ikke sluttes. […] **Det
vigtigste krav — læs det to gange. Notebooken skal måle gennem den rigtige kodes egne
funktioner, ikke gennem sine egne.** Den findes for at efterprøve antagelserne bag
[beslutningsmodulet]; måler den med en hjemmestrikket kopi, måler den noget andet end
jobbet gør, og så er den værdiløs. Det er nøjagtig den drift der har kostet os to hændelser
på en uge. Konkret, genbrug frem for at genskrive: [spor-klassifikationen],
[nøglenormaliseringen] — 'hvis kollisionsmålingen skal svare på *kan den symmetriske
normalisering oversletthe*, SKAL den bruge det udtryk normaliseringen faktisk bruger' —
[nøglesnapshot'et], [tabelnavnet], [DELETE-sættets filtre]. 'Er en funktion ikke
importérbar fra en notebook uden at trække dbutils/config med, så sig det i rapporten frem
for at kopiere den stiltiende.' […] **Den er READ-ONLY.** […] Importér ikke [skrivemodulet].
Skriv det i headeren som et løfte, og gør det sandt. […] **Driver-sikkerhed — dette væltede
[kundens] driver sidst.** […] Skriv én række ad gangen, append, efterhånden som hver tabel
måles. Akkumulér ikke [N] resultater i en Python-liste og skriv til sidst — et nedbrud på
tabel [n] skal ikke koste de [n-1] målinger. […] **[tabel] er afklaret — skriv afgørelsen
ind.**" Efterfulgt midtvejs af en course correction der trak den sidste del tilbage: "STOP
med [tabel]-afsnittet — afgørelsen er trukket tilbage. […] Jeg gav dig tallene […] som
bevis for at de [X mio.] var ægte. **Det bevis holder ikke, og du skal ikke skrive det
ind.**" — med en ny specifikation i stedet: friskhed skulle være en del af målingen, fordi
nøglesnapshot'et på en CDC-tabel er et levn fra før udtrækket holdt op med at dække dem.

**Interpretation:** Byg et måleinstrument, ikke en ny implementation. Hver eneste
måling skal gå gennem den funktion produktionen selv kalder, og hvor det ikke kan lade sig
gøre, skal det siges højt frem for at blive løst med en kopi. Læs-kun, og bevisligt læs-kun.
Og efter course correctionen: et snapshot er ikke et bevis bare fordi det ligger der — dets
alder er en del af målingen, ikke en fodnote.

**Inferred intent:** Kunden har accepteret rettelsen og afvist argumentet bag den, og det er
den sunde reaktion. To af de tre påstande i dokumentationen hvilede på to aflæsninger hver,
og den ene side af hele sammenligningen var aldrig målt. Det var præcis en umålt antagelse
— "de ti er numeriske" — der brækkede ti tabeller i Step 3. Opgaven er derfor ikke at
producere tal; det er at gøre det umuligt for den næste konklusion at hvile på et
stikprøve-argument.

### What I did

Byggede en engangs-notebook ved siden af jobbet, og lagde dens rene dele i det samme
beslutningsmodul som resten: hvad der kan måles for en given nøgletype, hvad et par af
distinkte tællinger betyder, hvordan en kørsel opsummeres, og om et nøglesnapshot
overhovedet er et bevis.

**Genbrugskravet tvang to rigtige beslutninger frem, og de er ikke kosmetiske.**
Nøgleprojektionen lå i produktions-notebooken og kunne derfor ikke importeres. Den bruger
kun pyspark og modulets egne hjælpere — ingen dbutils, ingen config — så den hørte hjemme i
modulet i forvejen, ved siden af de to andre DataFrame-transformationer der allerede bor
der. Jeg flyttede den frem for at kopiere den, og produktions-notebooken kalder den nu
samme sted. Det er nøjagtig det åbne spørgsmål Step 1, Step 2 og Step 3 hver især skrev ned
som "burde måske være én funktion"; her tvang en ny forbruger svaret frem. Samme greb for
flag-opslaget: forespørgselsteksten og række→dict-trinnet ligger nu i modulet, mens selve
forbindelsen bliver i hver notebook, fordi den kræver hemmeligheder.

**Tre hjælpere kunne ikke flyttes, og det står skrevet frem for løst.** Tabelnavn-byggeren
kræver katalog-config og en navnesaniterer; snapshot-mappe-indpakningen kræver
filsystem-API'et; fil-listningen er én linje over samme API. De er gentaget i
måle-notebooken, hver med en henvisning tilbage til originalen og en linje om hvorfor. Det
var oplæggets egen undtagelse, og jeg brugte den frem for at flytte config ind i et modul
hvis hele pointe er at være fri for det.

**Målingen af *begge* sider blev løst ved at kalde den samme funktion to gange.**
Slettesættet bygges af en funktion der bærer alle fire entitetsfiltre; kaldt med måltabellens
egen nøgletype giver den præcis de nøgler guarden tæller. Kaldt med `"string"` som nøgletype
tvinges kontroltabel-siden ned ad sin strenggren, som er en ren trimning og ingenting andet
— så en længdemåling på den kolonne *er* længden af den trimmede nøgle, taget gennem
produktionens eget udtryk, uden at et eneste filter er stavet om. Forskellen mellem de to
tællinger er i sig selv en måling: den siger hvor mange trimmede værdier castet folder
sammen, altså kollisionsspørgsmålet stillet til den anden side.

**Kollisionsmålingen bruger produktionens join-udtryk, ikke et TRIM.** Den tager
`count(distinct <gemt>)` mod `count(distinct <normaliseret>)`, hvor det normaliserede er
det udtryk joinen faktisk bygger. På en strengnøgle er det en trimning; på en numerisk er
det identiteten, så de to tællinger *skal* komme ud ens — og Catalyst folder de to
identiske aggregeringer sammen, så det koster ingenting at lade målingen sige det frem for
at læseren skal tro på det. Eksakt tælling, aldrig approksimeret: spørgsmålet er om to
nøgler kollapser til én, og et estimat kan ikke svare på det.

**Course correctionen midtvejs ændrede specifikationen reelt.** Nøglesnapshot'et på en
CDC-tabel er et levn: det daglige nøgleudtræk kører med et filter der udelader netop de
tabeller, så det der ligger i mappen stammer fra før den udeladelse. En løs fil i roden,
ingen dateret mappe, ingen udtræksdato. Og fejlen løber den farlige vej — et gammelt
snapshot har færre nøgler end kilden har i dag, så de rækker det ikke kan gøre rede for
kommer ud for *højt*: filens alder læst som sletninger. Notebooken måler derfor alderen før
den sammenligner noget, og lader tællingerne stå tomme for alt andet end en dateret mappe
inden for én udtrækscyklus plus tolv timer. Grænsen er begrundet i koden ud fra triggerens
egen plan, ikke valgt efter smag.

**Driver-sikkerheden er bygget efter den hændelse der væltede driveren sidst.** Seriel
kørsel, én række skrevet og committet ad gangen, per-tabel `try/except` der lægger fejlen i
rækken og fejler hele kørslen til sidst, portionering via det samme where-clause-widget
jobbet bruger, og et kørsels-id der gør gentagelse sikker. Alt er aggregeringer — ingen
`collect()` af et nøglesæt, ingen `toPandas()`.

Testsuiten gik fra 126 til 176 rene tests. Notebooken parser (`python -m py_compile`), og
skrivemodulet er ikke importeret.

### Why

Fordi en måling bygget på en anden implementation måler den anden implementation, og det er
præcis den drift der har kostet to hændelser på en uge. Step 3's fejl var ikke en
tastefejl; den var at en konklusion blev draget om ti tabeller ud fra observationer på de
nitten andre. En notebook der gentog beslutningslogikken ville kunne producere grønt for en
kode der var rød, hvilket er den værste af alle mulige udfald: en bekræftelse af en
antagelse, målt på noget andet end det antagelsen handler om.

Og fordi alderen på et snapshot er en del af målingen og ikke en omstændighed ved den.
Fravær af bevis må ikke kunne bære formen af et bevis.

### What worked

**Genbrugskravet var en designkraft og ikke en begrænsning.** Fordi målingen *skulle* gå
gennem de samme funktioner, blev det umuligt at feje "hvorfor ligger den her og ikke der"
ind under gulvtæppet. Flytningen af nøgleprojektionen er en forbedring af produktionskoden
som ingen af de tre foregående steps fik gennemført, og den kom ikke af en oprydning — den
kom af at en anden forbruger havde brug for den.

**At kalde den samme funktion med en anden nøgletype i stedet for at gentage dens filtre.**
Det er det enkleste greb i hele leverancen og det der bærer mest: den side af
sammenligningen der aldrig er blevet målt, måles nu gennem produktionens eget udtryk, og
der findes ikke et sted hvor filtrene kan glide fra hinanden.

**Kollisionsmålingen på en numerisk nøgle er en tautologi, og det er rigtigt.** Fristelsen
var at springe den over med et argument ("en numerisk kolonne kan ikke bære udfyldning").
At lade den køre gennem det rigtige udtryk gør argumentet til en observation uden at koste
noget, fordi de to aggregeringer er det samme udtryk og foldes sammen.

### What didn't work

**En test hævdede den rigtige ting gennem den forkerte funktion.** Jeg skrev en test der
skulle vise at en ukendt nøgletype rapporteres frem for at fejle, og lod den først bevise at
den underliggende regel *gør* fejle — men jeg kaldte Spark-udtryks-funktionen til det. Den
importerer pyspark i funktionskroppen, før den når frem til typetjekket:

```
python -m pytest --noconftest [testfil] -q
E       ModuleNotFoundError: No module named 'pyspark'
[beslutningsmodul]:981: ModuleNotFoundError
3 failed, 160 passed in 0.26s
```

Rettelsen var at hævde det mod typefamilie-funktionen direkte, som er ren. Den lille
episode er selv en observation værd: et modul der er "pyspark-frit" er det ikke hele vejen
ned, og importen ligger før den logik man tror man tester.

**Jeg byggede en gentagelses-sikkerhed der ville have gjort det modsatte af sit formål.**
Kørsels-id'et springer tabeller over der allerede er målt. Men en tabel der *fejlede* får
også en række under samme id — så den ville være blevet sprunget over på netop den kørsel
der fandtes for at måle den. Fundet i min egen gennemgang af diff'en, ikke af en test.
Rettelsen skelner nu mellem "målt rent" og "fejlede", og læse-forespørgslen bruger `QUALIFY`
så det seneste forsøg pr. kolonne vinder.

**Jeg korrigerede oplægget på ét punkt.** Course correctionen sagde at mappe-resolveren
returnerer `None` for den løse legacy-fil. Det gør den ikke — med filer men ingen daterede
undermapper falder den igennem til `return root_path`, så filen læses som om den *var* en
snapshot-mappe. Det er værre end den beskrevne adfærd og gør pointen stærkere, ikke
svagere. Formen afgøres derfor ved at sammenligne stier, ikke ved et `None`-tjek, og der er
nu en test der kalder resolveren selv med en løs fil og hævder at den giver roden tilbage —
så præmissen under formtjekket er hævdet frem for læst ud af kildekoden.

### What I learned

**Et snapshot er ikke et bevis fordi det ligger der.** Det er den egentlige lærdom fra
course correctionen, og den er almen: når et udtræk holder op med at dække en tabel,
forsvinder dataene ikke — de bliver stående og ser nøjagtig ud som data der stadig
vedligeholdes. Forskellen ligger i *formen* (dateret mappe mod løs fil) og i *alderen*, og
ingen af delene aflæses medmindre nogen beslutter at aflæse dem. En kontrol der læser
"nyeste mappe" læser det ældste den kan finde, den dag der ikke bliver skrevet flere.

**Fejlretningen løber den ene vej, og det afgør om et tal er farligt.** Et gammelt snapshot
gør hullet større, aldrig mindre. Derfor er "der mangler flere nøgler end forventet" den
retning man *ikke* må læse som et fund — og det er præcis den retning tallet pegede da det
blev fremlagt som bevis. Et tal hvis fejlretning peger mod den konklusion man gerne vil
drage, skal måles igen, ikke bruges.

**En kollisionsmåling der ikke bruger join-udtrykket er en anden måling.** Man kan skrive et
`TRIM` der giver det rigtige svar i dag og det forkerte i morgen, fordi normaliseringen
ændrede sig ét sted. Det lyder pedantisk, lige indtil man husker at hele Step 3 var to
udtryk der holdt op med at betyde det samme.

### What was tricky

**Hvad der er "gentagelse" og hvad der er "genbrug" er ikke et spørgsmål om linjeantal.**
Tre linjer der bygger et tabelnavn er en gentagelse der må accepteres; tredive linjer der
åbner en databaseforbindelse er det også — men *forespørgselsteksten* inde i dem er det
ikke, for det er den der afgør hvilke flag beslutningen træffes på. Skillelinjen går ved om
stykket bærer en beslutning, ikke ved om det er langt.

**Tabel-niveau mod kolonne-niveau i resultatrækken.** Rækken er pr. (tabel, nøglekolonne),
men snapshot- og kontroltabel-målingerne er pr. tabel. På en sammensat nøgle gentages de
derfor på hver af tabellens rækker, og der er ingen elegant udvej: at lægge dem på den
første kolonne alene gør rækken uforståelig alene, at udelade dem gør dem usynlige. Valget
står skrevet i kolonnens kommentar og i headeren — "læg dem ikke sammen" — hvilket er en
dokumenteret skarp kant frem for en skjult.

**At holde en læs-kun-erklæring sand ned i detaljen.** Headeren lovede først "ingen
Delta-commit uden for resultattabellen", og det var ikke helt sandt: skemaoprettelsen er
også en commit. Formuleringen blev rettet til at nævne de tre steder der skrives, ved navn.
En upræcis garanti er værre end ingen, fordi den bliver citeret.

### What warrants review

Notebooken kan ikke køres herfra. Den kræver Databricks; maskinen har hverken Java eller
pyspark, og jeg har ikke installeret nogen af delene. Jeg påstår ikke at den er verificeret.
Det jeg kan stå inde for er at den parser, at de rene tests er grønne, og at skrivemodulet
ikke er importeret.

Grænsen for hvornår et snapshot er for gammelt er et valg. Den er begrundet ud fra hvor ofte
udtrækket kører, og den er testet mod begge sider af sin egen begrundelse — men den er ikke
målt mod virkeligheden, fordi det kræver at man ser hvor gamle snapshots faktisk er.

Den eksakte distinkte tælling på de største tabeller er den dyre del. Den er aldrig kørt, og
portioneringen i runbooken er en forsigtighedsforanstaltning bygget på erfaringen fra
nedbruddet, ikke på en måling af denne notebooks egen pris.

Og den ærlige gentagelse fra Step 3: spejlingen mellem den rene regel og de to Spark-udtryk
bevises stadig kun af tests der kræver cluster. Måle-notebooken hjælper på noget andet — den
måler dataene, ikke spejlingen — så det hul står uændret åbent.

### Future work

Kørslen skal faktisk foretages, og resultatet skal tilbage i dokumentationen som tal frem
for som argument. Indtil det sker, er dette et instrument og ikke et svar.

Formtjekket på snapshot-mapper hører logisk til i selve resolveren frem for ved siden af
den: en resolver der returnerer roden når der ikke er daterede mapper, fortæller ikke
kalderen at den gjorde det. At lade den sige det — frem for at lade hver kalder udlede det
af en sti-sammenligning — ville lukke fælden ét sted i stedet for n.

## Step 5: En kontrol der strukturelt ikke kan bestå, må ikke stilles

**Author:** builder

### Prompt Context

**Verbatim prompt:** "**[Kunden] har besluttet at `max_length` ikke skal bedes om på
LOB-kolonner i [led 1].** Baggrund, som er **lukket og ikke skal undersøges, rettes eller
nævnes igen**: [led 1] målte at en LOB-kolonne afkortes ved udtrækket. **[Kunden] har
bekræftet at afkortningen er den ønskede adfærd.** Sagen er afsluttet. Konsekvensen skal
derimod håndteres: er afkortningen permanent og tilsigtet, vil `max_length` afvige på hver
eneste LOB-kolonne ved hver eneste kørsel. En kontrol der råber ulv hver gang, lærer man at
ignorere — samme mekanisme som tærskel-kommentaren i [beslutningsmodulet] allerede advarer
imod. […] Teksten skal sige **hvorfor**, præcist. Ikke 'for dyr', ikke 'giver ikke mening'.
Den rigtige grund: afkortning ved udtrækket er en kendt og accepteret tilstand, så en
længdesammenligning mellem [kilden] og [landingslaget] **kan ikke være ens** og er derfor
ikke et bevis. En kontrol der strukturelt ikke kan bestå, må ikke stilles. **Afgør samtidig
om `max_octet_length` på LOB skal falde med.** […] Undersøg det i koden, vælg, og begrund
valget — begge veje er forsvarlige, men valget skal stå skrevet. […] I køre-instruktionen:
skriv hvad [kunden] skal se for at vide at **LOB-kolonnerne nu udelades rent i stedet for
at fejle**."

**Interpretation:** Fjern en kontrol, men gør fjernelsen til noget der kan læses og
efterprøves: kolonnen skal stå som eksplicit udeladt med sin grund, ikke forsvinde. Og træf
et åbent valg på den tilstødende diagnostik, med argumentet skrevet ned frem for
konklusionen alene.

**Inferred intent:** Det farlige er ikke den kontrol der mangler; det er den kontrol der
altid er rød. Den lærer læseren at rødt er normalt, og så er hele leddet uvirksomt næste
gang noget faktisk går galt. Det er samme mekanisme som tærskel-noten i delete-detektionen
advarer imod fra den anden ende af estatet, og pointen i at få dem til at referere til
hinanden er at det er én lærdom og ikke to.

### What I did

Læste den funktion der afgør hvilke aggregeringer en kolonne får, og fandt at LOB-typen
fordeler sig over to grene: den ene er medlem af *både* tegn-typerne og LOB-typerne, den
anden kun af LOB-typerne. Derfor blev LOB-grenen lagt **først**, og det er et krav og ikke
en stilistisk præference: en test af tegn-grenen først ville sende hver eneste af den
dobbeltmedlem-type ned ad den, og afvisningen ville kun nogensinde fyre for den anden.
Rækkefølgen er reglen — samme greb som spor-valget i delete-detektionen bruger, hvor "kun
dette spor" er udtrykt som en position frem for som en betingelse. Der er en test der
hævder begge medlemskaber og derefter at LOB-grenen vinder.

Begge LOB-typer afvises nu med samme begrundelse. Den ene af dem havde tidligere en
sammenligning med argumentet "bytes på begge sider, altså utvetydig" — det argument handlede
om *enheder*, mens afkortningen handler om *værdier*, så det holdt ikke som grund til at
behandle de to forskelligt.

**Valget på den tilstødende diagnostik: den falder med.** Den måles kun på landingssiden og
findes udelukkende for at kunne navngive en byte-mod-tegn-afvigelse i længdesammenligningen.
Uden den sammenligning har den intet at forklare. Og det afgørende argument er ikke pris —
den er gratis — men hvad den *skriver*: en ensidet måling skrives ud med dommen `ok`, og en
`ok`-række på en LOB-kolonne hvis længde ingen har sammenlignet, læses som en LOB-kolonne
der bestod. Det er nøjagtig den falske tryghed ændringen findes for at fjerne. Den afvises
derfor eksplicit frem for at blive droppet i stilhed.

LOB-kolonnen bliver i scope selv om hvert eneste af dens aggregeringer nu er en afvisning.
Fjernedes den, ville den forsvinde helt ud af resultattabellen — og en kolonne der bare er
fraværende kan ikke skelnes fra en kolonne ingen har tænkt over. "Denne kolonne måles ikke,
og her er hvorfor" skal være noget tabellen kan *spørges om*.

Kørende notebook er ikke rørt: den skriver allerede en afvist aggregering ud som `skipped`
med begrundelsen. Runbooken fik et afsnit med beslutningen, begrundelsen og en tabel over
hvad man skal se i resultattabellen — og hvad hver af de fire forkerte udfald betyder.

To tests der hævdede det modsatte er vendt om, med samme begrundelse skrevet ind i dem.
Suiten gik fra 393 til 394.

### Why

Fordi en kontrol der ikke kan bestå ikke er en kontrol. Den producerer et rødt felt hver
gang, og efter tredje gang holder folk op med at kigge på leddet — og så er det ikke kun den
ene kontrol der er død, det er hele leddets troværdighed. Det er samme mekanisme som
tærskel-noten i delete-detektionen beskriver fra den anden retning: en guard der fyrer på
almindelig drift er en guard folk lærer at klikke forbi, og så er den værre end ingen guard.

### What worked

**At skrive grunden som "kan ikke være ens" frem for "er for dyr".** De to fører til samme
kode og til vidt forskellige fremtider. "For dyr" inviterer til at nogen senere finder en
billigere måde og sætter kontrollen tilbage; "kan ikke være ens" lukker spørgsmålet, fordi
det siger noget om sammenligningen og ikke om regnskabet.

**Krydshenvisningen mellem de to ender af estatet.** Begrundelsen peger på tærskel-noten i
delete-detektionens beslutningsmodul, og den note advarer allerede mod samme fejl fra sin
egen retning. At lade de to referere til hinanden gør det til én lærdom med to
forekomster frem for to lokale betragtninger.

### What didn't work

Ingen fejlende kommandoer i dette step. Men min egen gennemgang af diff'en fandt to steder
hvor begrundelser var blevet forældede af ændringen uden at fejle nogen test:

Afvisningen af den distinkte tælling på LOB sagde "længdemålingen svarer allerede på det
spørgsmål LOB-kolonnerne er her for" — og det gør den ikke længere, for længdemålingen
stilles ikke. Teksten er rettet til at bære den nye grund. Kommentaren over samme blok havde
samme slagside.

Det er den slags fejl testene ikke kan fange, fordi de er sande sætninger der er holdt op
med at være sande. Den eneste kontrol er at læse sin egen diff efter en begrundelse man har
flyttet grunden væk under.

### What I learned

**Når en kontrol fjernes, er kolonnen i resultatet vigtigere end kontrollen var.** En
kolonne der er væk, og en kolonne der ingen har tænkt på, ser ens ud i en resultattabel. En
eksplicit afvisning med en begrundelse er derfor ikke en høflighed — det er den eneste måde
en senere læser kan skelne "vi besluttede ikke at måle dette" fra "det blev aldrig
overvejet".

**En ensidet måling med dommen `ok` er en påstand.** Den var bygget som en neutral
diagnostik, men dommen den bærer er ikke neutral når den står ved siden af en kolonne hvor
alt andet er afvist. Det var ikke synligt før den kolonne den skulle forklare forsvandt.

### What was tricky

At finde ud af at den ene LOB-type er medlem af to typelister samtidig. Det er en detalje i
to konstanter tretten hundrede linjer fra den gren der bruger dem, og den afgør hele
ændringens virkning: læg grenene i den forkerte rækkefølge, og afvisningen fyrer for den
ene af typerne og aldrig for den anden — tavst, og med grønne tests, fordi ingen test
hævdede rækkefølgen. Nu gør en det.

### What warrants review

Ingen del af dette er kørt mod kildesystemet. Det der er verificeret er at de rene tests er
grønne, at begge notebooks stadig parser, og at linteren er tilfreds med de to rørte filer.
At LOB-kolonnerne faktisk dukker op som `skipped` med begrundelse kan kun ses ved at køre
leddet, og runbook-afsnittet er skrevet som en aflæsningsvejledning til netop den kørsel.

Den genererede forespørgsel mod kildesystemet bliver kortere — for en tabel hvis eneste
kolonner i leddets scope er LOB'er, er den nu kun rækketallet. Det er den rigtige retning,
men det er også en ændring i hvad der faktisk bliver spurgt om, og det bør ses én gang
frem for antages.

### Future work

Afkortningen ved udtrækket er en accepteret tilstand, men den er ikke *dokumenteret som en
grænse nogen steder uden for denne begrundelse*. Hvis nogen senere spørger "hvor meget
afkortes der", er svaret i dag en sætning i en afvisningsgrund. Det kunne bære at stå som
en målt værdi ét sted, netop fordi kontrollen der ville have vist det nu er fjernet.

## Step 6: To spor, to præmisser — og en guard der endelig læser hvad kilden sagde

**Author:** builder

### Prompt Context

**Verbatim prompt:** "To ting mere. […] **1. Bredderne er nu målt på alle 29 CDC-tabeller —
skriv det ind.** […] Ingen variabel bredde nogen steder. **Kollision ved trimning er dermed
umulig på alle 29**: to værdier der kun adskiller sig ved efterstillede blanktegn ville have
forskellig længde, og med `min = max` findes de par ikke. […] Den kollisions-forespørgsel du
dokumenterede til håndkørsel pr. objekt […] er **overflødiggjort** af denne billigere og
fuldstændige måling. […] Lad være med at slette historikken — skriv at den er afgjort. **2.
Guard C's præmis gælder ikke ens på de to spor.** Dette er det egentlige fund, og det kom
fra [kunden]. **Nøglesporet:** en sletning udledes af et **fravær** […] Dækningsgrad er det
rigtige instrument der. **CDC-sporet:** en sletning er en **positiv erklæring** fra kilden —
en DELETE-post med tidsstempel. Der er intet fravær at fejltolke. Dækningsgrad er derfor et
fremmed mål på det spor. […] **Byg dette, og kun dette:** (a) bær sletteerklæringen med i
guard C's afvisning […] (b) ny afvisning: `rows_to_flag` > antal distinkte slettenøgler […]
Det er en **tilføjet** guard, ikke en løsnet. (c) **FJERN IKKE dækningsafvisningen på
CDC-sporet.** Dette er en designbeslutning, og jeg vil have argumentet skrevet ind i koden
frem for bare udført. […] Skriv derfor i koden at beslutningen er **udskudt med vilje**, og
hvad der ville afgøre den […] Beslut efter de data findes, ikke før."

**Interpretation:** Luk et spørgsmål der nu er målt, uden at slette sporet af hvorfor det
blev stillet. Og tilføj en guard der måler mod det kilden faktisk sagde — uden at fjerne den
guard der måler mod noget andet, fordi den beslutning ikke er moden.

**Inferred intent:** Det interessante er ikke guarden; det er indsigten om at de to spor
ikke har samme epistemiske form. Et fravær og en erklæring er ikke det samme bevis, og et
instrument bygget til det ene er ikke automatisk gyldigt på det andet. Det er derfor (c) er
den vigtigste af de tre: at modstå fristelsen til at handle på den indsigt før der er data
nok til at vide om den også holder i praksis.

### What I did

**Bredderne først.** Kommentarblokken i beslutningsmodulet og det tilsvarende runbook-afsnit
sagde begge "her er en risiko, kør denne forespørgsel pr. objekt hvis du mistænker noget".
Begge er skrevet om til "her var risikoen, sådan blev den målt, og forespørgslen skal ikke
køres". Ræsonnementet bliver stående ordret, for det er stadig ræsonnementet — det der
ændrede sig er at præmissen blev efterprøvet i stedet for antaget. Den overflødiggjorte
forespørgsel står tilbage i koden som en udkommenteret historik med en linje om hvorfor den
er billigere besvaret et andet sted, og med hvad der ville genåbne spørgsmålet.

**Filtrene fik ét hjem.** Guard C's afvisningstekst skulle bære to tal — antal distinkte
slettenøgler og antal DELETE-poster — og de to kommer fra samme fire entitetsfiltre som
selve slettesættet. Filtrene lå inde i den funktion der grupperer dem; jeg trak dem ud i en
egen funktion, og lod grupperingen kalde den. Det er det samme greb som Step 4's flytning af
nøgleprojektionen, af samme grund: et tal der står ved siden af en afvisning må ikke kunne
beskrive et andet sæt end det der udløste afvisningen.

**Den nye guard blokerer på én præcis ting:** flere flagede rækker end kilden erklærede
distinkte slettenøgler. Det betyder at ét erklæret nøgle-id rammer flere aktuelle rækker,
altså at nøglen ikke er unik blandt dem. Strengt større, ikke "forskellig fra" — og det er
den detalje der afgør om guarden er brugbar. **Færre** flagede end erklærede er det normale,
og det har to uskyldige forklaringer der forekommer hver nat: en erklæret nøgle hvis række
allerede er markeret slettet og derfor er faldet ud af det aktuelle rækkesæt, og en nøgle
der blev slettet og siden genindsat, som beskyttelsen mod genindsættelse lægger tilbage. En
guard der fyrede på "forskellig fra" ville fyre på næsten hver kørsel, hvilket er nøjagtig
den fejl hele modulet er skrevet imod.

**Argumentet i begge retninger står i koden.** Ikke konklusionen alene, men hvad der taler
for at fjerne dækningsafvisningen på CDC-sporet, hvad der taler imod, hvorfor imod vejer
tungest lige nu, og præcis hvilket tal der ville afgøre det — som tilfældigvis er det tal
måle-notebooken fra Step 4 producerer.

Testsuiten gik fra 176 til 189 rene tests. Tærskelværdierne er urørte.

### Why

Fordi et instrument bygget til at måle et fravær ikke automatisk er gyldigt på en erklæring.
På det ene spor er der intet andet end fraværet at gå efter, og en dækningsgrad er det
bedste man kan gøre. På det andet står der et tal i kilden, med et tidsstempel, som ingen
læste. At lade en afvisning stå uden det tal ved siden af er at tvinge den der læser
afvisningen til at gætte — og gættet falder oftest ud til "overrule den", fordi afvisningen
ikke giver ham noget at tænke med.

Og fordi (c) er den rigtige beslutning netop nu: sporet har fået to fejlrettelser på en uge,
den første rene brede kørsel har ikke fundet sted, og ingen ved endnu hvad "normalt" ser ud
som her. Den nye konsistensguard fanger en oppustning der *stammer fra nøglens unikhed*; den
fanger ikke en kontroltabel der selv er gået galt i stor skala. Fjernede man den gamle guard
nu, ville der ikke være nogen bremse tilbage på præcis det scenarie.

### What worked

**At skrive argumentet imod sig selv ind i koden.** Oplægget bad om det, og det er
bedre end en kommentar der bare forklarer hvad koden gør: den næste læser arver ikke en
regel, han arver en uafsluttet diskussion med et navngivet kriterium for hvordan den
afsluttes. Det er den eneste form jeg kender hvor "vi gjorde det ikke endnu" ikke bliver til
"ingen ved hvorfor det er sådan".

**Tællingen tages ét sted og læses af begge guards.** Den ene guard beder om tallet når
intet flages, den anden når noget flages — så mellem dem betales den én gang uanset hvilken
vej kørslen går. Og den bliver ved med at være en callable ind i den første, fordi "den dyre
kontrol køres kun i det tvetydige tilfælde" er en egenskab en test hævder, ikke et løfte
kalderen giver.

**At lade den overflødiggjorte forespørgsel blive stående som historik.** Fristelsen var at
slette den. Men en forespørgsel der forsvinder efterlader ikke en oplysning om at den blev
afgjort — den efterlader et hul, og den næste der får den samme bekymring genopfinder den.

### What didn't work

Ingen fejlende kommandoer. To fund fra min egen gennemgang af diff'en:

En kommentar inde i grupperingsfunktionen forklarede hvorfor en bestemt hjælper "lige
ovenfor" ikke genbruges til nøglen — og hjælperen var netop flyttet ned i den nye funktion,
så "lige ovenfor" pegede på ingenting. Rettet til at navngive den funktion den nu bor i.

Og oplægget kaldte den nye guard "gratis: begge tal er allerede talt". Det er kun halvt
rigtigt, og jeg skrev det ikke af. Antallet af flagede rækker var talt; antallet af
distinkte slettenøgler blev på den hidtidige lykkelige sti **ikke** talt — den anden guard
betalte kun for den når intet blev flaget. CDC-sporet betaler derfor nu én aggregering over
den filtrerede kontroltabel pr. tabel som det ikke gjorde før. Det er ikke en scanning af
måltabellen og det er en pris værd at betale, men det er en pris, og den står skrevet i
koden som en pris frem for som "gratis".

### What I learned

**Fravær og erklæring er ikke samme slags bevis, og et instrument arver ikke gyldighed på
tværs.** Dækningsgrad blev bygget til et spor hvor en sletning *kun* kan udledes af at noget
mangler, og den blev derefter anvendt på et spor hvor kilden siger det direkte. Ingen
besluttede nogensinde at den skulle gælde begge steder; den gjorde det fordi den lå i den
fælles sti. Det er en almen fejlform: en kontrol flytter sig fra det problem den blev født
til, uden at nogen genbesøger præmissen.

**Et enkelttilfælde er en anledning til at stille spørgsmålet, ikke til at besvare det.**
Den tabel der rejste sagen ville have passeret uden dækningsafvisningen, og det er fristende
at læse som et argument for at fjerne den. Men ét er ikke et mønster, og den samme
observation kan lige så godt betyde at guarden gør sit arbejde på en tabel hvis data vi ikke
forstår endnu. Forskellen afgøres af data fra alle objekter, og de findes ikke endnu.

### What was tricky

**Strengt større mod forskellig fra.** Den naive udgave af guarden — "antallet af flagede
rækker skal svare til antallet af erklærede nøgler" — ser stærkere ud og er ubrugelig: begge
de normale afvigelser går den ene vej, så den ville fejle hver nat. At finde ud af hvilken
af de to ulighedsretninger der bærer information krævede at gennemgå hvorfor en erklæret
nøgle *ikke* flager en række, og der var to uafhængige grunde, som begge er korrekte
tilstande.

**Rækkefølgen mellem de to guards.** De er gensidigt udelukkende — den ene kræver at intet
flages, den anden at der flages mere end erklæret — men det er ikke synligt før man skriver
begge betingelser op ved siden af hinanden. De ligger nu som naboer med den rækkefølge
skrevet ned, frem for at det skal udledes hver gang.

### What warrants review

Ingen del af dette er kørt. Det verificerede er at de rene tests er grønne, at begge
notebooks parser, og at tærskelværdierne er uændrede — bekræftet på diff'en og ikke kun i
hukommelsen.

Den nye aggregering pr. CDC-tabel er ikke målt. Den går på en allerede filtreret
kontroltabel og ikke på måltabellen, så den bør være ubetydelig ved siden af de scanninger
kørslen laver i forvejen, men det er en forventning og ikke en måling.

Og det tal hele den udskudte beslutning hænger på — forholdet mellem flagede rækker og
erklærede slettenøgler på tværs af alle objekter — findes ikke endnu. Indtil det gør, er
(c) et velbegrundet "ikke endnu" og ikke et svar.

### Future work

Beslutningen om dækningsgraden på CDC-sporet skal træffes, og kriteriet er skrevet ned, så
den næste der åbner sagen skal ikke genopfinde diskussionen — kun køre måle-notebooken og
læse ét forhold af den.

Det er nu fjerde gang i denne dagbog at svaret på "hvordan undgår vi at to steder betyder
forskellige ting" har været at flytte noget ind i beslutningsmodulet. Nøgleprojektionen,
flag-opslaget, entitetsfiltrene. Mønstret er klart nok til at være en regel frem for en
serie af enkeltbeslutninger: hvad der bærer en beslutning hører i modulet, hvad der bærer
I/O bliver i notebooken, og en tvivl afgøres af om stykket kan tage fejl på en måde der
ændrer hvilke rækker der bliver rørt.

## Step 7: Den første rigtige kørsel — måleren målte, og tre af dens egne fejl kom frem

**Author:** builder

### Prompt Context

**Verbatim prompt:** "Måle-notebooken er kørt i dev for første gang. Kerneresultatet er
godt, og tre fejl kom frem. **Den ene er min, ikke din.** […] **88 målte nøglekolonner, 0
trim-kollisioner.** […] Bredde- og kollisionsspørgsmålet er dermed lukket på **hele
estatet**. […] **Fejl 1 — [en tabel] vælter kørslen.** […] Notebooken filtrerer på
[SCD2-kolonnen for den aktuelle række] uden at spørge om kolonnen findes. […] **Genbrug den skip frem for
at skrive en ny kontrol.** Du kalder allerede `choose_track`; svaret ligger der. Honorér
det, før du rører tabellen […] **Fejl 2 — snapshot-kolonnen er ubrugelig, og præmissen bag
den var MIN.** […] **Jeg gav dig den forkerte præmis.** Jeg skrev at dateret undermappe =
gyldigt bevis, og løs fil i roden = levn. Det er forkert. Løse filer i roden er den
**normale, fungerende form** for aktive tabeller […] Din `key_snapshot_shape` gør nu det
stik modsatte af det rigtige: den kasserer de gyldige snapshots. **Friskhed afgøres på
`policy.snapshot_cutoff(files)` alene.** […] **Fejl 3 — begrundelsen navngiver den forkerte
årsag.** […] **Fire betingelser.** De fjorten er udeladt fordi `[det inkrementelle flag] = 0`, ikke
fordi de er CDC-tabeller. […] Udtryk klausulen **ét sted** i policy-modulet som data, og
udled beskeden ved at evaluere den mod tabellens egne flag […] En forklaring der peger på
den forkerte årsag er værre end ingen — du har selv skrevet tre kommentarblokke om i denne
sag af præcis den grund."

**Interpretation:** Instrumentet virkede og leverede sit hovedresultat. Tre fejl i
instrumentet selv skal rettes, og den ene af dem er en præmis jeg fik udleveret og byggede
en gate på uden at efterprøve den.

**Inferred intent:** Den vigtige er nummer to. En måling der kasserer gyldige data er
værre end ingen måling, fordi den ligner et fund: "intet snapshot" læses som en
oplysning om verden og ikke som en fejl i kikkerten. At leaden selv udpeger sin egen
forkerte præmis er den reaktion der gør det muligt at fange den — men jeg byggede en gate
på den uden at spørge, og det er min halvdel.

### What I did

**Fejl 1 — honorér skippet.** Notebooken kaldte allerede `choose_track` og skrev svaret i
rækken, og læste så videre i tabellen uanset hvad svaret var. Det var mit valg, truffet
med den begrundelse at en skippet tabels nøgler stadig er interessante at måle. Den
begrundelse holder ikke mod et append-only mål: det har slet ingen SCD2-kolonner, så
filteret på den aktuelle række ikke kan resolve, og aggregeringen kaster. Skippet honoreres
nu før tabellen røres, og rækken bærer skip-årsagen ordret. En skippet tabel er et
resultat.

Det efterlod to tjek længere nede — findes måltabellen, har den nøgler i metadata — som
klassifikationen nu altid fanger først. De er uden for rækkevidde. Jeg lod dem stå, men
mærkede dem som det backstop de er, frem for at lade dem se ud som levende stier: de er de
to betingelser aggregeringerne ikke kan overleve, og skifter rækkefølgen i klassifikationen
nogensinde, skal de fejle som en række og ikke som en exception.

**Fejl 2 — friskhed er alder, ikke form.** Jeg havde bygget en gate på formen: dateret
undermappe = gyldigt bevis, filer direkte i roden = levn. Den præmis kom fra leaden, jeg
efterprøvede den ikke, og den er forkert. Løse filer i roden er den normale form for flere
aktive tabeller, og produktionens egen nøglespors-funktion læser dem ud af roden hver nat —
netop via den `return root_path`-gren jeg selv havde opdaget og rapporteret. Gaten kasserede
derfor tre levende tabellers gyldige snapshots og vandt intet.

Rettelsen er at lade snapshot'ets eget cutoff afgøre det alene. Det findes i begge former,
fordi det læses af filernes ændringstidspunkt. Form rapporteres stadig — det er en rigtig
iagttagelse — men den gater ikke. To domme der kun kunne opstå af formgaten er pensioneret.
Den oprindelige bekymring er bedre tjent end før: et levn har et gammelt cutoff og giver
stadig ingen tællinger, men et snapshot hvis eneste brist var at ligge i roden bliver ikke
længere smidt væk.

Jeg verificerede derefter opløsningsstien trin for trin mod produktionens, programmatisk
frem for ved at læse: samme metadatafelt, samme sti-sammensætning, samme mappe-resolver,
samme fil-listning, samme cutoff-funktion, samme saniterings- og projektionskald. Eneste
afvigelse er den dokumenterede, og den ligger nedstrøms for stien.

**Fejl 3 — udled beskeden, gæt den ikke.** Jeg havde hårdkodet én forklaring på hvorfor en
tabel ikke er dækket af det daglige udtræk. Triggerens klausul har fire betingelser, og
fjorten objekter fik derfor udpeget en årsag der beviseligt ikke gælder for dem. Klausulen
ligger nu ét sted som data, og beskeden udledes ved at evaluere den mod objektets egne flag,
så den navngiver den eller de betingelser der faktisk fejlede. En flagværdi der ikke kan
læses rapporteres som "kunne ikke evalueres" og ikke som "holder ikke" — det er to
forskellige fund, og at rapportere det andet som det første er præcis den fejlklasse
opgaven handlede om.

**Et nyt widget, som ikke stod i oplægget.** De tre snapshot-ramte tabeller blev målt
*rent* i første kørsel. Gentagelses-sikkerheden springer dem derfor over, og den kan ikke
se at "rent" i mellemtiden er kommet til at betyde noget andet. Uden en måde at tvinge en
genmåling frem kunne den samme kørsels-id ikke gøres færdig — hvilket var netop det
oplægget bad om. Navngivet liste frem for en boolean, af samme grund som den eksisterende
override er det.

Testsuiten gik fra 189 til 203 rene tests. Fejl 2's test hævder at filer i roden med et
friskt cutoff **giver** tællinger, og der er en strukturel test på at formen ikke længere er
en parameter til friskhedsbeslutningen.

### Why

Fordi en måling der kasserer gyldige data er farligere end en måling der mangler. "Intet
snapshot" står i en resultattabel og ser ud som en oplysning om verden. Den eneste måde at
opdage at det var kikkerten og ikke himlen, var at nogen sammenholdt det med en
produktionslog fra tre dage før. Det er ikke en kontrol man kan regne med at få gratis to
gange.

Og fordi formen aldrig var signalet. Alderen var, hele tiden, og den findes i begge former.
Gaten målte den ene ting der tilfældigvis korrelerede med det man ville vide, på en
delmængde af tabellerne.

### What worked

**At leaden udpegede sin egen forkerte præmis.** Det er det der gjorde fejlen findbar
overhovedet. Havde meldingen været "snapshot-kolonnen ser forkert ud, fiks den", ville jeg
have ledt i min egen kode efter en fejl der ikke var der — gaten gjorde nøjagtig hvad den
var bygget til.

**At verificere stien programmatisk frem for ved at læse den.** Jeg skrev et lille script
der trak begge funktioner ud og tjekkede hvert opløsningstrin som tekst i begge. Det tog et
minut og gav et svar jeg kan citere, frem for en påstand om at jeg havde kigget.

**At beholde den udækkede-observation som observation.** Fristelsen var at lade den gate
igen, bare rigtigt denne gang. Men et nøgleudtræk kørt i hånden *som måling* giver et
friskt cutoff, og så fortjener det sine tællinger uanset hvad den natlige trigger mener.
Skellet mellem "forkert som drift" og "rigtigt som måling" er kun meningsfuldt hvis koden
respekterer det.

### What didn't work

Ingen fejlende kommandoer i selve arbejdet — fejlene var fundet af kørslen, ikke af mine
værktøjer. Fejlen fra kørslen, ordret:

```
RuntimeError: 1 table(s) failed to measure: [tabel]
(AnalysisException: [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column ...
[SCD2-kolonnen for den aktuelle række] cannot be resolved.
Did you mean one of the following? [...])
```

Otte tests gik rødt af rettelsen, som de skulle — de hævdede den kasserede adfærd. Jeg
erstattede dem frem for at justere dem, fordi det ikke var deres tal der var forkerte, det
var det de hævdede.

Et fund i min egen gennemgang af diff'en: efter at skippet honoreres, er de to følgende
tjek uden for rækkevidde. Ingen test fangede det, og ingen ville have gjort det — en
uopnåelig gren fejler ikke. Det er kun synligt ved at læse rækkefølgen af betingelser i den
funktion jeg netop havde kaldt.

### What I learned

**Det er tredje gang på en uge at en umålt præmis er blevet til kode.** Først "de ti er
numeriske, castet trimmer som bivirkning". Så "snapshottet beviser at slettesættet var
ufuldstændigt". Nu "dateret mappe = gyldigt, løs fil = levn". Mønstret er ikke at folk
gætter — det er at en præmis der leveres *sammen med* en opgave bliver behandlet som en del
af opgaven frem for som en påstand der skal efterprøves. En observation der kommer ind i
en instruktion, kommer ind uden det tjek den ville have fået hvis jeg havde fundet den selv.

**Formen på data korrelerer tit med det man vil vide, og er næsten aldrig det man vil
vide.** Dateret mappe korrelerede med "aktivt udtræk" på en delmængde af tabellerne. Det
man ville vide var alderen, og den kunne læses direkte. En gate på en korrelat fejler
præcis på de tilfælde hvor korrelationen ikke holder — og det er de tilfælde man byggede
målingen for.

**En gate skal kunne besvare "hvad ville få dig til at sige nej til noget gyldigt".** Havde
jeg stillet formgaten det spørgsmål, var svaret "et aktivt snapshot uden dateret mappe", og
så var det eneste tilbageværende spørgsmål om sådan en findes. Det tog leaden ét opslag i
en produktionslog at svare på.

### What was tricky

**At skelne mellem tre ting der alle hedder "ikke dækket".** En tabel kan være uden for det
daglige udtræk (fire mulige grunde), have et snapshot der er for gammelt, eller slet ingen
filer have. Første udgave rullede det sammen til én dom med én forklaring, og både
sammenrulningen og forklaringen var forkerte. At holde dem fra hinanden krævede at afgøre
hvilken af dem der faktisk må tilbageholde et tal — kun alderen — og lade de to andre være
iagttagelser ved siden af.

**Rækker skrevet før rettelsen.** De bærer de to pensionerede domme og ser ud som
målinger. Gentagelses-sikkerheden springer dem over, fordi de blev skrevet rent. Det er den
slags migrationsproblem der ikke findes i testene og kun findes i virkeligheden, og
løsningen — et eksplicit widget plus en note i dokumentationen om hvordan man genkender en
forældet række — er mindre elegant end jeg havde håbet og den eneste jeg kan stå inde for.

### What warrants review

Intet af dette er kørt. Verificeret er: begge rene suiter grønne (203 og 394), begge
notebooks parser, linteren tilfreds bortset fra det sædvanlige notebook-mønster, tærskler
urørte bekræftet på diff'en, og opløsningsstien trin for trin identisk med produktionens.

Friskhedsgrænsen er stadig ikke målt mod virkelige snapshot-aldre — nu har vi til gengæld
en kørsel der kan svare på det, fordi alderen rapporteres for hvert objekt uanset dom.

Genkørslen er den egentlige prøve: de tre tabeller skal komme tilbage med et cutoff og ikke
med fraværet af et, og den skippede tabel skal stå som skippet frem for at vælte kørslen.
Begge dele er skrevet ud i dokumentationen som noget man kan aflæse, ikke som noget man
håber.

### Future work

Der bør være et sted hvor en præmis der følger med en opgave bliver skrevet ned *som en
påstand med en kilde*, frem for at glide ind i koden som en forudsætning. Tre gange på en
uge er ikke uheld. Det billigste jeg kan komme i tanke om: når en instruktion indeholder en
observation om data, skal den observation citeres i koden sammen med hvor den kommer fra —
så den næste der læser linjen kan se at den hviler på noget, og hvad.

Formtjekket hører stadig hjemme i mappe-resolveren frem for ved siden af den. Nu hvor
formen er blevet en ren iagttagelse i stedet for en gate, er det blevet mindre presserende
og ikke mindre rigtigt: en resolver der returnerer roden uden at sige at den gjorde det,
lader hver kalder udlede det af en sti-sammenligning.
