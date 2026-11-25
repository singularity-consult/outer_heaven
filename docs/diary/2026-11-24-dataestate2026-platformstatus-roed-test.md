# Diary: Platformstatus på DataEstate2026, rød test og en vagt der kun fejler efter en pause

Kundeopgave (SEGES, DLBR-DataEstate2026). Det begyndte som et rent statusspørgsmål på dev, test og prod og endte i fem stykker arbejde: et rødt testmiljø med en uventet årsag, en dublet-undersøgelse i raw, to kæder kørt og overvåget i test, en rettelse af en leveringsvagt, og en oprydning i lokale worktrees. Indlægget er holdt på leveranceniveau: ingen personnavne, ingen run-id'er, ingen rækkeantal fra kundens tabeller.

## Step 1: Statusmåling på tre miljøer og fundet af den røde test

**Author:** main

### Prompt Context

**Verbatim prompt:** dlbr dataestate2026 - status på platform, dev, test, prod
**Interpretation:** Giv en aktuel status pr. miljø: hvad er deployet, hvad er kørt, hvad er rødt, hvad er åbent.
**Inferred intent:** Samle tråden op efter en uge uden opfølgning og få at vide, om noget kræver handling nu.

### What I did
Læste projektfilen i det private statusrepo; den var seks dage gammel. Målte derefter live i stedet for at gengive filen: åbne og mergede PR'er og release-kørsler via `gh`, og alle afsluttede jobkørsler siden sidste statusdato via `databricks jobs list-runs` for hver profil, opsummeret af et lille Python-script (antal kørsler pr. job, seneste resultat, alle ikke-grønne). Dev og prod kunne måles med det samme. Test kunne ikke, fordi CLI-profilens refresh token var udløbet. Da brugeren havde logget ind igen, viste test sig at være rød fem nætter i træk.

Årsagen blev fundet i tre trin. Først fejlteksten på den rigtige kørsel: en `DELTA_CONCURRENT_APPEND` inde i en foreachBatch. Dernæst listen over jobs i test: en kollega havde deployet en personlig kopi af hele bundlen til testmiljøet, med præfiks i jobnavnene, og kopien af den daglige kæde havde samme file-arrival-trigger som originalen, upauset. Til sidst tidslinjen: kopien blev oprettet otte timer før den første røde nat. Kopiens egen fejl sagde det direkte: `CONCURRENT_STREAM_LOG_UPDATE ... Multiple streaming jobs detected`. Efter brugerens ja satte jeg kopiens trigger på pause med `databricks jobs update` og verificerede, at originalens trigger stadig var aktiv.

### Why
En statusfil, der er en uge gammel, er en hypotese, ikke en status. Brugeren spurgte om miljøerne, ikke om filen.

### What worked
At opsummere kørsler pr. job i stedet for at læse lister. Fem røde nætter på samme job springer i øjnene i en tabel med "seneste resultat" og en linje pr. ikke-grøn kørsel. At følge `run_job_task` ned til den task, der faktisk fejlede, i stedet for at stoppe ved forælderens "upstream failed".

### What didn't work
Første måling af test:

`Error: A new access token could not be retrieved because the refresh token is invalid. To reauthenticate, run the following command: $ databricks auth login --profile test`

Jeg rapporterede test som "ikke målt" og bad brugeren logge ind. Det var rigtigt, men det betød også, at det eneste røde miljø var det, jeg ikke kunne se i første svar. Et link i et senere svar var desuden opdigtet: jeg skrev en workspace-adresse, jeg ikke havde, og måtte trække den tilbage i samme svar.

### What I learned
En personlig bundle-kopi i et delt miljø er ikke isoleret, bare fordi jobnavnene har et præfiks. Kopien arver triggere, checkpoint-stier og måltabeller. Den skrev i de fælles raw-tabeller og konkurrerede med originalen om samme streaming-checkpoint. Projektet havde allerede en nedskrevet beslutning om ikke at lave personlige bundle-kopier; den forhindrede det ikke.

### What was tricky
Fejlen på den rigtige kørsel pegede ikke på årsagen. `DELTA_CONCURRENT_APPEND` siger kun, at nogen skrev samtidig. Det var først jobbet ved siden af, med sin anden og mere talende fejltekst, der forklarede det.

### What warrants review
At pausen er den rigtige løsning og ikke kun en lindring: det blev bevist af to grønne kørsler bagefter (Step 3). Kopierne er ikke slettet; en ny personlig deploy vil slå triggeren til igen.

### Future work
En teknisk spærre mod upausede triggere i personlige kopier ville være mere værd end endnu en nedskrevet regel. Ikke besluttet.

## Step 2: Dublet-undersøgelsen, og en første måling der var ugyldig

**Author:** main

### Prompt Context

**Verbatim prompt:** undersøg dubletter. kører derefter jobbet og overvåg.
**Interpretation:** Tjek om de fem nætters samtidige kørsler har efterladt dubletter i raw-tabellerne i test, og kør derefter den daglige kæde.
**Inferred intent:** Vide om test-data er til at stole på, før miljøet bruges igen.

### What I did
Brugeren mente først, at et kopi-job fra prod ville rette eventuelle dubletter. Det holdt ikke: kopi-jobbet dækker et andet skema end det, de samtidige kørsler ramte. Jeg sagde det, og brugeren bad om undersøgelsen.

Læste først Delta-historikken for alle tabeller i skemaet siden kopien blev oprettet (`DESCRIBE HISTORY` via SQL Statement API'et, parallelt), og talte commits pr. job-id. Kopien stod for langt de fleste skrivninger; originalen nåede kun de første tabeller hver nat, før den fejlede. Alle skrivninger var MERGE, og de nætter begge kørte, havde den ene nul kilderækker. Derefter et egentligt dublet-tjek pr. tabel: nøgler med mere end én gældende række, og dubletter på nøgle plus gyldig-fra.

### Why
Historikken forklarer, hvorfor der ikke burde være dubletter. Tællingen viser, om der er. Kun det sidste er et svar på spørgsmålet.

### What worked
Historik før tælling. Da jeg vidste, at alt var MERGE, og at den tabende kørsel fik nul rækker, havde jeg en forventning at holde tællingen op imod. Den forventning afslørede fejlen i min første måling.

### What didn't work
Første dublet-tjek grupperede på kolonnen `dw_key_columns` i den tro, at den indeholdt nøgleværdien. Resultatet var "1 nøgle med flere gældende rækker" i samtlige tabeller, også små opslagstabeller med en håndfuld rækker. Kolonnen indeholder navnene på nøglekolonnerne, altså den samme streng i hver række, så hele tabellen blev én gruppe. Jeg kørte det om: læste den ene værdi pr. tabel, parsede kolonnenavnene ud og grupperede på dem. Anden måling gav nul dubletter i alle tabeller på nær én, der ikke kunne tjekkes, fordi den ikke er historiseret.

### What I learned
Et resultat, der er identisk på tværs af meget forskellige tabeller, er et tegn på en fejl i målingen, ikke et fund. "Præcis 1 overalt" er ikke et mønster, data laver af sig selv.

### What was tricky
Jeg nåede at sende en mellemstatus til brugeren, mens den ugyldige måling kørte. Havde resultatet været mindre påfaldende, fx nul overalt af en forkert grund, var det gået igennem.

### What warrants review
Tjekket dækker kun entydighed på nøgle og gyldig-fra. Det siger ikke noget om, hvorvidt kopiens version af koden har skrevet andet indhold end originalen ville have gjort.

### Future work
Ingen.

## Step 3: To kæder i test, en afvist kørsel og en overvågning der døde

**Author:** main

### Prompt Context

**Verbatim prompt:** tjek om clone-jobbet og resten af dash linjen kan køre i test. overvåg jobbet. er der andre ting der skal kiggers på i miljøerne?
**Interpretation:** Forhåndstjek og kør kopi-jobbet fra prod til test med den efterfølgende kæde, følg kørslen, og list hvad der ellers bør ses på.
**Inferred intent:** Få test tilbage i en kendt, brugbar tilstand efter fem røde nætter.

### What I did
Forhåndstjek uden at køre noget: jobbets parametre, at det pegede på den rigtige nedstrøms kæde, at kæden havde alle forventede tasks, og at intet andet kørte. Startede kopi-jobbet og satte et baggrundsscript til at vente på afslutning og udskrive task-resultater. Imens gennemgik jeg resten af miljøerne og fandt blandt andet en prod-kørsel, der havde meldt grøn uden at læsse noget; brugeren afviste den som en gammel løsning på vej ud, og det blev noteret som accepteret forbehold.

Efter dublet-undersøgelsen forsøgte jeg at starte den daglige kæde i test. Det blev afvist:

`Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Destructive or Unwanted Actions].`

Jeg forsøgte ikke at omgå det. Jeg skrev, hvilket job jeg havde læst "jobbet" som, og gav brugeren kommandoen. Han kørte den selv, og jeg overvågede.

### Why
"Kør derefter jobbet" kunne betyde to forskellige jobs. Afvisningen ramte præcis det sted, hvor min tolkning ikke var bekræftet.

### What worked
Forhåndstjekket fangede intet, og det var pointen: kørslen gik rent igennem. Kopi-jobbet og kæden blev grønne. Den daglige kæde blev grøn, både brugerens manuelle kørsel og nattens automatiske, første grønne nat i en uge.

### What didn't work
Overvågningen af den daglige kæde. Scriptet havde en deadline på fem en halv time som værn mod at hænge. Da den udløb, forlod det løkken og forsøgte én sidste læsning, som fejlede, og skrev kun:

`kunne ikke læse run ...`

Det afsluttede med exit 0. Brugeren fik derfor ingen besked den aften. Jeg opdagede det først ved notifikationen næste morgen og læste resultatet direkte.

### What I learned
Et overvågningsscript med en deadline skal skelne mellem "jobbet er færdigt" og "jeg gav op", og det skal fejle højlydt i det sidste tilfælde. Exit 0 efter en opgivet overvågning er værre end ingen overvågning, fordi den ligner en afslutning. En enkelt mislykket læsning til sidst må heller ikke være hele rapporten; den skal prøves igen.

### What was tricky
Brugeren spurgte "status" fem gange undervejs. Hver gang læste jeg tilstanden direkte i stedet for at stole på baggrundsscriptet. Det var de direkte læsninger, der bar forløbet, ikke overvågningen.

### What warrants review
En release til testmiljøet landede midt i den manuelle kørsel af den daglige kæde. Kørslen blev grøn alligevel, men jeg har ikke undersøgt, om en deploy midt i en kørsel kan give en blanding af gammel og ny kode.

### Future work
Overvågningsscriptet bør blive et genbrugeligt stykke værktøj med ordentlig exit-kode og gentagne forsøg, i stedet for at blive skrevet om i hver session.

## Step 4: En leveringsvagt, der kun fejler efter mere end syv dages pause

**Author:** main

### Prompt Context

**Verbatim prompt:** bekræft årsag
**Interpretation:** Læs leverings-notebooken og fastslå, hvorfor leveringstasken fejlede i test.
**Inferred intent:** Vide om fejlen er et testfænomen eller kan ramme prod.

### What I did
Under overvågningen dukkede to manuelle kørsler op i test, som jeg ikke havde startet. Den ene, en leveringskæde til en ekstern modtager, fejlede i sidste task med:

`[DELTA_UNSUPPORTED_TIME_TRAVEL_BEYOND_DELETED_FILE_RETENTION_DURATION] Cannot time travel beyond delta.deletedFileRetentionDuration (168 HOURS) set on the table.`

Jeg rapporterede først en formodning med tallene bag: forrige kørsel i test lå lidt over syv døgn tilbage. Brugeren bad om bekræftelse. Notebooken viste mekanikken: en vagt læser forrige skrivning af tabellen med `versionAsOf` for at sammenligne rækkeantal og stoppe ved et for stort fald. Delta-historikken for de to tabeller viste, at forrige skrivning var 178,6 timer gammel mod en grænse på 168. Dermed var årsagen bekræftet og ikke kun sandsynlig.

Jeg lagde to rettelser frem: fang fejlen og behandl den som "ingen forrige kørsel" med en advarsel, eller forlæng retention på tabellerne. Brugeren valgte den første. Implementeringen gik til builder-agenten i et isoleret worktree med en brief, der indeholdt fejlteksten, tallene, kravet om kun at fange den ene fejlklasse, og git-reglerne for kundens repo. Builderen leverede en ren genkendelsesfunktion i det testbare modul, 16 nye unit tests og en PR. Jeg verificerede PR'en på GitHub, før jeg rapporterede den. Efter godkendelse fra en reviewer squash-mergede jeg på brugerens besked og ryddede branch og worktree op.

### Why
Vagten fejlede hårdt præcis i den situation, hvor den burde være mest tolerant: første kørsel efter en lang pause. I prod ville det betyde en dag uden levering efter et længere nedbrud.

### What worked
At adskille "formodning med tal" fra "bekræftet" i to svar, og lade brugeren vælge, om bekræftelsen var værd at bruge tid på. At give builderen den ordrette fejltekst og tallene, så den ikke skulle genopdage problemet.

### What didn't work
Rettelsen er aldrig afprøvet mod den rigtige undtagelse. Unit testene bruger efterligninger, fordi pyspark ikke var installeret lokalt. Om serverless oplyser fejlklassen via en getter eller kun i teksten, er ikke set; koden dækker begge veje, men det er ræsonneret. Muligheden for at bevise det i test forsvandt, da en anden kørte hele kæden igen samme eftermiddag: den nye skrivning gjorde en læsbar version til "forrige". Jeg havde forudsagt, at vinduet ville lukke, og brugeren valgte bevidst at nøjes med unit tests.

### What I learned
En vagt, der sammenligner med "forrige version", har en skjult afhængighed af, hvor ofte jobbet kører. Den afhængighed ses ikke i et miljø med daglig drift og dukker først op i et pauset miljø. Pausede testmiljøer finder altså en klasse af fejl, som prod kun møder efter et nedbrud.

### What was tricky
Fejlen opstod i en kørsel, jeg ikke havde startet, i et miljø, jeg kun overvågede af en anden grund. Det var fristende at lade den ligge som uvedkommende.

### What warrants review
Faldvagten er slået fra på netop den første kørsel efter en lang pause. Det er et bevidst valg, men det er også den kørsel, hvor et stort fald er mest sandsynligt.

### Future work
Rettelsen er merget, men ikke released. Første rigtige bevis kommer, når en leveringskørsel møder en forrige version, der er ældre end grænsen.

## Step 5: Oprydning i lokale worktrees

**Author:** main

### Prompt Context

**Verbatim prompt:** ja, list dem
**Interpretation:** Gennemgå alle worktrees i kundens repo og klassificér, hvilke der hører til mergede PR'er og kan fjernes.
**Inferred intent:** Rydde op uden at miste arbejde, der kun findes lokalt.

### What I did
Skrev et script, der for hvert worktree slog branch, PR-tilstand, ucommittede filer, upushede commits og forholdet til main op, og om den lokale HEAD var identisk med det commit, PR'en blev merget fra. 21 worktrees hørte til mergede PR'er og var rene. Efter brugerens ja fjernede jeg dem og deres lokale branches, og verificerede bagefter, hvad der var tilbage.

### Why
Squash-merge gør `git branch -d` ubrugelig som sikkerhedstjek, fordi branchen aldrig bliver en forfader til main. Sammenligningen med PR'ens head-commit er det tjek, der faktisk siger, om noget går tabt.

### What worked
`git worktree remove` uden `--force`, så et worktree med ucommittede eller usporede filer ville have nægtet. Ingen gjorde.

### What didn't work
Min første liste satte tre worktrees under "commits kun lokalt". De pegede i virkeligheden på præcis de commits, tre mergede PR'er var merget fra; de havde bare et andet branchnavn end PR'en, så opslaget på branchnavn fandt ingen PR. Jeg opdagede det, da de samme korte hashes stod i outputtet efter sletningen, og rettede det i næste svar. Jeg skrev også 33 worktrees, hvor der var 32.

### What I learned
At slå PR op på branchnavn overser worktrees, hvor agenten har arbejdet på en omdøbt eller midlertidig branch. Opslaget skal også gå på commit-hash.

### What was tricky
Intet ud over ovenstående.

### What warrants review
Brugeren valgte at beholde de resterende 11, også de seks, der var sikre at fjerne. Det er noteret, så spørgsmålet ikke stilles igen.

### Future work
Ingen.
