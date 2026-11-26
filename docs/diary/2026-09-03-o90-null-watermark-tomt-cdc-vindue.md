# Diary: Ø90 inkrementel extract — NULL-watermark når en tabel har nul rækker i sit CDC-/filtervindue

Den inkrementelle DB2-extract i kundens data-platform beregner sit næste watermark ved at
lade en metadata-procedure *generere* en SQL-tekst, som pipelinen så kører mod kilden. Den
genererede tekst spørger efter MIN og MAX af den inkrementelle kolonne og afleder to ting:
det nye watermark, og et `IsDone`-flag som styrer en Until-løkke i controlleren.

En aggregering over nul rækker giver NULL. Så bliver det nye watermark NULL, og flaget
beregnes som en lighed mellem to udtryk der begge er NULL — altså `NULL = NULL`, som i SQL
er NULL og ikke sandt. Pipelinen konverterer den værdi til boolean og vælter.

Det ramte under en daglig driftkørsel: én tabel ud af halvfjerds fejlede, resten kørte
grønt. Tabellen var nyligt tilføjet CDC-sporet og havde aldrig fået en eneste registrering
i CDC-metadatatabellen, så dens vindue var tomt hele vejen igennem — ikke bare på dagen.

Opgaven er robusthed frem for drift: den konkrete tabel er i mellemtiden taget helt af
CDC-sporet, fordi kildesystemets arkitekt bekræftede at den slet ikke producerer
registreringer. Men enhver nytilføjet tabel, og enhver tabel der aldrig ændres, vil ramme
det samme.

## Step 1: Verifikation af diagnosen, og de to fund der flyttede designet

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Opgave: ret en bug i `GetObjectMetadataDB2` der vælter Ø90-driftkørslen når en sync_meta-tabel har nul rækker i CDC-tabellen. En tidligere lead-session analyserede dette men kunne ikke levere kode, fordi dens worktree ved en fejl blev oprettet i et andet repo. Dens analyse er gengivet nedenfor, så du ikke skal genopdage den — men verificér selv frem for at tage den for gode varer. […] FIXET SKAL LIGGE I `GetObjectMetadataDB2.sql`, ikke i ADF-udtrykket. Når `MaxIncrementalColumn` er NULL, skal den genererede query returnere det gamle watermark uændret og `IsDone = TRUE` — 'intet at hente'. Et `coalesce` i `Set IsDone` ville skjule forskellen mellem 'ingen ændringer' og 'queryen fejlede' […] TJEK OGSÅ DEN ANDEN GREN […] Dæk begge, eller argumentér for hvorfor kun den ene er reel." Efterfulgt af en course correction der valgte variant (b) — returnér den rå, ujusterede sidst-indlæste værdi — og som meldte at den ramte tabel var taget af CDC-sporet, så opgaven ikke længere er en driftblokker.

**Interpretation:** Genverificér en nedarvet analyse frem for at bygge på den, fastlæg hvor
i den genererede SQL rettelsen hører hjemme, og afgør om begge grene af query-genereringen
er reelt eksponerede. Fixet skal ligge i den SQL der genererer teksten, ikke i det
pipeline-udtryk der forbruger den.

**Inferred intent:** En stille forkert værdi er dyrere end et højlydt nedbrud. Rettelsen
skal skelne mellem "der var intet at hente" og "beregningen fejlede", og den skelnen skal
ligge det sted hvor forskellen faktisk kendes — i genereringen — ikke maskeres et lag
længere ude med et coalesce.

### What I did

Læste den genererende procedure, metadata-viewet den trækker fra, søsterproceduren der
bygger selve extract-queryen, og de to pipeline-definitioner der forbruger dem. Sendte en
søgeagent i gang med at hente de præcise pipeline-udtryk ordret, mens jeg selv gennemgik
SQL-siden, så de to spor ikke overlappede.

Bekræftede årsagen i koden: den ydre SELECT i den genererede tekst afleder flaget som en
lighed mellem to udtryk der begge er NULL når kilden ikke gav rækker.

Fastslog dernæst tre ting den nedarvede analyse ikke havde med.

For det første: metadata-viewet tvinger dato-flaget til sand for alle tabeller der er
færdig-backfillede på CDC-sporet. Det betyder at netop den gren altid producerer
tekst-output, så en rettelse dér ikke kan give typekonflikt. Den anden gren kan derimod
producere rå numerisk output, og dér er typespørgsmålet reelt.

For det andet, og vigtigst: den aktivitet der skriver watermarket tilbage til metadata er
**ikke** betinget af flaget. Den er kun betinget af at kørslen er inkrementel, og den
ligger efter kopieringen. Så uanset hvad den genererede query returnerer som nyt watermark,
bliver det skrevet — også på en kørsel hvor intet blev hentet. Det gør "returnér det gamle
watermark" til et krav og ikke et designvalg: et tomt eller NULL-svar ville nulstille
watermarket.

For det tredje: den værdi proceduren i dag kalder "det gamle watermark" er ikke den gemte
værdi. Viewet lægger et rullende vindue til først, og det vindue er negativt for langt de
fleste tabeller. Skrev man den værdi tilbage, ville watermarket vandre bagud med vinduets
størrelse for hver tom kørsel — ubegrænset for en tabel der aldrig ændres. Aldrig fremad med
den nuværende opsætning, så intet datatab i dag; men konfigurationen der holder det
harmløst er en enkelt talværdi som ingen regel beskytter.

Lagde de to varianter frem med argumenter for og imod hver: den justerede værdi (ét sted at
rette, men indfører afdrift) mod den rå gemte værdi (watermarket står stille, men proceduren
skal læse en kilde mere). Anbefalede den rå værdi, fordi afdriftsvarianten sætter en fælde
der først springer den dag nogen ændrer en tilsyneladende harmløs indstilling.

### Why

Opgaven kom med en færdig analyse og en påstand om at en bestemt rettelsesplacering allerede
var fundet. Begge dele viste sig at holde, men ingen af dem dækkede det der faktisk afgør
designet: at tilbageskrivningen er ubetinget, og at den værdi man ville have skrevet tilbage
ikke er den man tror. De to fund kunne kun komme af selv at læse pipeline-definitionen og
viewet, i stedet for at bygge videre på referatet.

### What worked

At dele arbejdet i to spor der ikke rører de samme filer — søgeagenten på
pipeline-definitionerne, mig selv på SQL-laget — gav begge fund i samme runde uden at nogen
af os læste det samme to gange.

At lade beslutningen falde på ét spørgsmål med to navngivne varianter, hver med for og imod,
frem for en anbefaling præsenteret som eneste mulighed. Svaret kom retur med en begrundelse
der gjorde argumentet stærkere end mit eget: en anden tabel havde samme dag vist præcis den
fejlklasse, hvor et watermark stod i et forkert talformat og derfor stille hentede nul
rækker i det uendelige uden nogensinde at fejle.

### What didn't work

Intet blev bygget forkert i dette trin, fordi intet blev bygget endnu. Men den nedarvede
analyse var ufuldstændig på en måde der ville have givet en rettelse med en ny fejl i sig:
havde jeg taget "returnér det gamle watermark" bogstaveligt fra referatet, ville resultatet
have indført systematisk afdrift på hovedparten af de inkrementelle tabeller.

Et forsøg på at læse på tværs af to repoer med `git -C` blev afvist af isolationen i
worktreen: "Refusing to run it — a worktree-isolated agent's git operations must target its
own worktree." Det samme gjaldt `Write` mod en sti uden for arbejdstræet, og et heredoc-kald
faldt over sin egen afslutning. Isolationen var korrekt opførsel; det kostede et opdelt kald
og en omvej over scratchpad.

### What I learned

Når en procedure genererer SQL som et andet system kører, ligger fejlens årsag og fejlens
symptom i hver sin verden, og ingen af dem er der hvor stakken peger. Symptomet var en
type-konvertering i pipelinen; årsagen var SQL's tre-værdi-logik i en genereret tekst to lag
væk.

En "gammel værdi" i en metadata-kæde er sjældent én værdi. Her fandtes den i tre former —
som gemt i tabellen, som justeret af viewet, og som normaliseret af proceduren — og kun den
mellemste af dem havde et navn der antydede at den var justeret.

En rettelse der returnerer en værdi ind i en kæde skal returnere den i kædens format, ikke i
lagerets. Den gemte værdi kan være i et andet format end det pipelinen sender videre, og en
"rå" returværdi ville dermed bygge en ugyldig sammenligning længere nede.

### What was tricky

At holde fast i at en påstand om et kildesystems opbevaringsvindue ikke kan afgøres ved at
læse et repo. Den nedarvede analyse indeholdt et konkret måltal, og det var fristende at
viderebringe det som verificeret. Det er det ikke — det kan kun afgøres mod kilden — og det
ændrer i øvrigt ikke rettelsen, kun hvor ofte man ville være blevet ramt.

Ligeledes: om databasen accepterer en betinget udtryksform der blander en litteral med en
kolonne på den numeriske gren kan kun afgøres ved at køre den. Det skal stå i runbooken som
noget der ses efter på første kørsel, ikke som noget der ræsonneres om.

### What warrants review

Selve rettelsen er endnu ikke skrevet. Når den er, er de to steder en anmelder skal se på:
at den ikke tilføjer en kolonne til procedurens resultatsæt — søsterproceduren indsætter
resultatet i en tabelvariabel med et fast antal kolonner og vælter ved en ekstra — og at den
værdi der returneres ved nul rækker er normaliseret til samme format som den værdi der
returneres på den grønne sti.

### Future work

Den fulde-indlæsnings-gren af den genererede tekst navngiver sit resultat med en anden
versalisering end den pipelinen læser. Det er død kode i dag, fordi grenen aldrig nås på den
sti, men det er en inkonsistens der vil bide den dag stien ændrer sig. Ikke i denne
leverance.

Der ligger en forældet kopi af pipeline-definitionerne ved siden af de levende, med små
adfærdsforskelle. Den er ikke i vejen nu, men den gør enhver fremtidig søgning tvetydig.
