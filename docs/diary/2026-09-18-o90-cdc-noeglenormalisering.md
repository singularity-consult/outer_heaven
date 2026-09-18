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
