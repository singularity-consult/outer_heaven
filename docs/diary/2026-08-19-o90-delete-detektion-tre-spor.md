# Diary: Delete-detektion pr. tabel i stedet for pr. koersel

SEGES-kundearbejde, branch `feature/o90-raw-delete-detection`. En Databricks-notebook
detekterer slettede raekker i raw-laget ved at bygge det aktuelle noeglesaet fra kilden og
anti-joine raws current-raekker imod det. Den 17. august koerte den og indsatte ~87,8 mio.
falske slette-raekker i ni raw-tabeller. Det blev rullet tilbage 19/8 via Delta
time-travel-restore, men fejlen stod uaendret i koden. Opgaven er at rette den foer
delete-tasken igen faar lov at koere.

Diariet er sanitiseret efter samme konvention som `2026-08-11-o90-raw-delete-detection-scope.md`:
ingen tabel-, skema- eller servernavne fra kilden, ingen datavaerdier. Rollebeskrivelser i
stedet. Talstoerrelser om vores egen fejl beholdes, da de er vores, ikke kundens.

## Step 1: Kravafklaring — to fejl fundet i selve planen

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Benny har godkendt at I retter delete-detektionen for [kilden] i
SEGES-repoet DLBR-DataEstate2026. Laes foerst planen — den er skrevet i dag paa baggrund af
verificerede udtraek, ikke gaetvaerk [...] Den 17/8 koerte delete-tasken i
`ingest_o90_raw_full` og indsatte **87.815.183 falske slette-raekker** i ni raw-tabeller.
[Den stoerste transaktionstabel] alene fik 57,7 mio. [...] Sporet skal afgoeres **pr. tabel
ud fra metadata**, ikke af et widget. Tre spor plus en skip-liste [...] Overvej en guard C:
Afvis koerslen hvis noeglesaettet daekker under en taerskel af raws current-raekker. Det er
den eneste guard der ville have fanget 17/8-fejlen. Diskuter taersklen med Benny frem for at
vaelge den selv. [...] Udfordr praemisserne hvis noget ikke holder — Benny vil hellere
korrigeres end have medhold."
(forkortet, og kilde-objektnavne erstattet med rollebeskrivelser; fuld ordlyd i sessionen)

**Interpretation:** Planen var detaljeret og bygget paa verificerede udtraek, saa fristelsen
var at gaa direkte til implementering. Men opgaven bad eksplicit om at praemisserne blev
udfordret, og to af dem holdt ikke.

**Inferred intent:** Det underliggende maal er ikke "ret filvalget" men "goer det umuligt for
denne notebook at masse-slette igen". Enhver antagelse i designet der kun holder saa laenge
en konfiguration andetsteds er rigtig, er derfor selv en del af fejlen.

### What I did

Laeste planen, koden paa feature-branchen, og de to verificerede CSV-udtraek. Sendte en
read-only research-agent efter metadata-viewet, lighthouse-adapteren, `write.soft_delete()`,
job-definitionen og raw-loaderen, mens jeg selv gennemgik CSV'erne og git-historikken.

Fandt tre ting der aendrede kravene:

1. **Planens sync_meta-konstruktion ville have udloest en stoerre masse-sletning end 17/8.**
   Planen antog at kildens CDC-kontroltabel kun indeholder sletninger og foreslog et rent
   anti-join imod alle dens noegler. To ting modsagde det: operationstypen indgaar i
   tabellens egen primaernoegle, og den genererede inkrementelle udtraeks-query joiner
   `INNER JOIN` tilbage til den levende entitetstabel — hvilket kun giver mening for raekker
   der stadig findes. Kontroltabellen er altsaa en fuld change log. Benny koerte den query
   jeg bad om: tre fjerdedele af raekkerne var `INSERT`/`UPDATE`, ikke `DELETE`. Planens
   snippet ville have flaget dem alle som slettede paa tvaers af 29 tabeller.

2. **Reduktionen til "seneste operation pr. noegle" kan ikke bygges som beskrevet.**
   Rodaarsagen viste sig at vaere et tabt `ExtractSQLFilter` i 2026-metaen — gammel loesning
   filtrerer til `DELETE` ved *udtraekket*, ikke i notebooken. Men naar det filter genskabes,
   findes der ingen `INSERT`-raekker i raw at reducere imod, saa en genindsat noegle kan ikke
   opdages inde i kontroltabellen. Den maa i stedet detekteres mod entitetens egen
   raw-raekke: er den aendret senere end sletningens tidsstempel, lever noeglen.

3. **Samme sammenligning er ogsaa den tidsafgraensning planen bad om separat.** De to krav
   er ét krav. Det halverede et stykke af specifikationen.

Derudover: `get_latest_file_path` returnerer én fil. Er et fuldt snapshot skrevet som flere
part-filer — hvilket parallel kopiering goer — er "nyeste fil" ét fragment. Det er 17/8's
fejlklasse et niveau laengere nede, og planen daekkede den ikke. Kravet blev aendret til at
laese nyeste daterede *mappe*.

### Why

Alle tre spor skriver gennem den samme destruktive primitiv. En fejl i inputkonstruktionen
bliver derfor til slettede raekker, ikke til en exception. Derfor er det inputsiden der skal
gennemgaas raekke for raekke, ikke skrivesiden.

### What worked

At bede om praecis to SQL-queries frem for at gaette paa operationskolonnens vaerdidomaene.
`git grep` fandt ingen reference til den i hele repoet, saa den kunne kun afgoeres i data.
Svaret kom som konkrete tal og afgjorde sagen paa én runde.

At laese commit-beskrivelsen paa den commit der indfoerte den fejlende widget. Den forklarede
*hvorfor* metadata-vejen blev forladt 7/8 — en bekymring for at en opstroems framework-sync
lydloest kunne tabe feltet — og den bekymring var gyldig. Uden den kontekst ville jeg have
foreslaaet praecis den loesning der allerede var afvist én gang, uden at kunne adressere
indvendingen.

### What didn't work

Min foerste rodaarsagsanalyse ramte ved siden af. Jeg konkluderede at filteret manglede i
notebooken; det manglede i metaen. Forskellen er ikke akademisk: filtreres der foerst i
notebooken, traekkes der fortsat fire gange for mange raekker ud af kilden hver dag. Jeg blev
korrigeret og kravet blev delt i to — meta-rettelsen som primaer, notebook-filteret som
defensivt lag.

Foerste forsoeg paa at laese maalfilen fejlede: worktreen var branchet fra `main`, mens
arbejdet ligger paa feature-branchen, saa filen fandtes ikke. Loest med
`git reset --hard origin/feature/o90-raw-delete-detection` efter at have bekraeftet at
worktree-branchen var tom.

Diariet kunne ikke skrives til outer_heaven-klonen: worktree-isolationen afviser writes uden
for worktreen, mens diary-skillen kraever at diarier ligger i outer_heaven og aldrig i
kundens repo. Konflikten blev ikke omgaaet — filen blev lagt i scratchpad og overdraget til
Benny.

Jeg regnede en deadline forkert og byggede et argument paa den. Jeg tog raw-lagets kopi af
kontroltabellen som den holdbare optegnelse og konkluderede at retentionsvinduet lukkede et
doegn tidligere end antaget — og at en bestemt koersel derfor hastede. Begge dele var forkert.
Landing-laget er det holdbare: filerne bliver liggende i storage, og en fil dér var tre dage
friskere end raws kopi og overlappede den uden hul. Retentionsuret sidder desuden paa
udtraekket fra kildesystemet, ikke paa det trin der flytter landing til raw — saa den koersel
jeg udpegede som hastende kunne slet ikke redde noget. Laeringen er ikke "tjek landing ogsaa",
men at jeg sluttede fra det lag jeg tilfaeldigvis havde tal paa, i stedet for at spoerge hvilket
lag der faktisk er holdbart, og hvilket trin der faktisk skriver til det.

### What I learned

En "guard" der validerer kolonner beskytter ikke mod en fejl i raekker. De to eksisterende
guards tjekkede at noeglesaettet var ikke-tomt og at primaernoeglekolonnerne var til stede.
Et inkrementelt delta bestaar begge: det er en gyldig, ikke-tom fil med korrekte kolonner.
Kriteriet skulle vaere daekning, ikke form.

Den mere generelle udgave: 7/8-beslutningen om at flytte valget fra metadata til et
job-parameter var korrekt begrundet, men den flyttede beslutningen til det forkerte
granularitetsniveau — ét valg for hele koerslen i stedet for ét pr. tabel. Én forkert vaerdi
blev dermed til 87,8 mio. raekker. Granularitet er en sikkerhedsegenskab, ikke kun et
designvalg.

### What was tricky

At skelne mellem hvad der ejes af kunden og hvad der synkes fra et opstroems framework.
Rettelsen kraevede to metadatafelter som ingen af de eksisterende lag eksponerede. Det
afgoerende spoergsmaal — er metadata-viewet vores eller synket? — kunne jeg ikke afgoere selv
og maatte stille. Svaret (viewet er kundens egen tilpasning, framework-mappen er ikke) gjorde
en ellers afvist loesning gyldig igen.

Guard C's taerskel var heller ikke en ren specifikationsopgave. En fast procentsats rammer
skaevt i begge ender: 5 % af den stoerste tabel er millioner af raekker, 5 % af en lille tabel
er en normal dags sletninger. Den endelige regel kombinerer derfor andel og absolut antal.

### What warrants review

Ikke noget kode endnu — dette step er kravafklaring. Ved review af implementeringen:
konstruktionen af slettesaettet for hvert af de tre spor, og at beskyttelsen mod
genindsaettelse er implementeret paa source-siden frem for ved at filtrere maaltabellen.
Skrivningen selv laeser maaltabellen internt, saa en filtrering udefra ville ikke virke.

### Future work

Enriched-laget laeser kildens kontroltabel fra det gamle estate over Delta Share, selvom
2026 har sin egen raw-kopi. Noteret, bevidst ikke bygget paa, og uden for scope her.

Et friskt udtraek af kildens kontroltabel skal koeres foer retentionsvinduet lukker. Det er en
koerselsopgave for Benny, ikke en byggeopgave, og den afhaenger ikke af denne rettelse.

## Step 2: Fix, guards, tests, runbook

**Author:** builder (outer_heaven:builder sub-agent)

### Prompt Context

**Verbatim prompt:** Opgaven kom fra lead-agenten som en fuldt specificeret
kravliste (K1-K9) med filer i scope, filer der ikke måtte røres, en
beslutningstabel for sporvalg, testkrav og runbook-krav. Kernen, ordret fra
briefen: *"Rodårsag: `key_source`-widget'en er ét valg for hele kørslen. Jobbet
sender `key_source: "full_snapshot"` med `meta_where_clause: "connection_name =
'o90'"` — altså alle 67 objekter, også de 45 inkrementelle. For dem peger
`source_path` på tabelroden, og `get_latest_file_path` kører `max()` på øverste
niveau mellem undermapperne `Full/` og `Incremental/` og går kun ned i vinderen.
Findes `Incremental/`, vinder den altid → nøglesættet blev et delta → alt urørt
blev anti-joinet væk."* Og selvreview-kravet: *"kan nogen sti gennem koden ende
med at kalde `soft_delete()` med et nøglesæt der ikke er kildens fulde sandhed
for netop den tabel? Det er den ene fejl der betyder noget."*

**Interpretation:** Byg om, så hvert objekt klassificeres i præcis ét spor ud fra
sin egen metadata, tilføj lag af beskyttelse der fejler højlydt frem for stille,
og lever metadata-ændringerne som scripts der ikke køres af mig.

**Inferred intent:** Gøre klassen af fejl umulig, ikke bare den konkrete
forekomst — og gøre en kørsel læsbar bagefter uden at skulle gentage den.

### What I did

Skrev notebooken om til to faser. Fase 1 klassificerer hvert objekt i scope i
`full`, `sync_meta`, `watermark` eller `skip(<grund>)` — sekventielt, kun
metadata- og katalogopslag. Fase 2 bygger nøglesættet, kører guards og skriver.
Adskillelsen betyder at et objekt ikke kan forsvinde stille: kørslen kaster til
sidst hvis noget i scope ikke fik et spor.

Lagde al beslutningslogik i et almindeligt Python-modul ved siden af notebooken,
uden pyspark-import på modulniveau. Det var det, der gjorde tests mulige
overhovedet — se "What was tricky". Modulet indeholder sporvalget, guard
C-tærsklerne som navngivne konstanter, mappe-resolveren, samt de to
DataFrame-transformationer der afgør hvilke nøgler der overlever (pyspark
importeres inde i de to funktioner).

Guards: A (tomt nøglesæt), B (nøglenavne kan resolves mod raw-målet — flyttet fra
et efter-tjek til forrest i funktionen), C (dækning < 95 % **og** > 10.000
rækker der ville blive markeret; begge betingelser, fordi en ren procentsats
rammer skævt i begge ender). Afviste tabeller samles og navngives i én exception
til sidst, så én kørsel rapporterer om alle tabeller.

Beskyttelse mod genindsættelse lagt på source-siden — `soft_delete()` læser selv
måltabellen, så en target-side-filtrering ville være virkningsløs.

Metadata-leverancerne: en kolonne tilføjet til metadata-viewet, og et idempotent
SQL-script der genskaber et filter der var gået tabt under seeding. Begge
leveret, ingen af dem kørt.

Tests i to filer: ren beslutningslogik (46 tests, kører lokalt) og Spark-adfærd
(kan kun køre med Databricks Connect). Plus en runbook i kundens repo.

### Why

Widget'en var symptomet; den egentlige fejl var at én beslutning blev truffet ét
sted for 67 objekter med tre forskellige former. Alt andet i opgaven — guards,
den højlydte metadata-validering, exception på uklassificerede objekter — er
lag der gør den samme klasse af fejl synlig næste gang.

### What worked

At flytte den rene logik ud i et modul. Det gav 46 tests der kører på 0,03
sekunder uden cluster, herunder en fake-filsystemtest der reproducerer præcis
den mappestruktur der udløste hændelsen (en `Full/`-mappe ved siden af en langt
nyere delta-mappe) og beviser at resolveren ikke kan gå det forkerte sted hen.

At descende mappetræet **efter navn** i stedet for efter modification time.
Nul-paddede datodele sorterer kronologisk, og det fjerner hele klassen af
"nyeste skrivning vandt" på én gang. En test dækker specifikt et backfill, hvor
en ældre datomappe er skrevet senest.

### What didn't work

Første forsøg på at køre den eksisterende testsuite lokalt fejlede før collection:

```
$ python -m pytest lighthouse/tests/write_tests/test_generic_type_2_upsert.py -x -q
ImportError while loading conftest '...\lighthouse\tests\conftest.py'.
lighthouse\tests\conftest.py:2: in <module>
    from lighthouse.helpers.spark import get_spark_session
lighthouse\helpers\__init__.py:1: in <module>
    from .dbutils import *
lighthouse\helpers\dbutils.py:1: in <module>
    from pyspark.sql import SparkSession
E   ModuleNotFoundError: No module named 'pyspark'
```

Ingen pyspark lokalt (Python 3.14; framework-suiten kører mod Databricks Connect
i CI). Workaround: `pytest --noconftest <fil>` på den rene testfil, som ikke
importerer pyspark. Det virker, men betyder at halvdelen af testene aldrig er
set køre af mig.

En af mine egne guard C-tests var forkert skrevet:

```
$ python -m pytest --noconftest lighthouse/tests/write_tests/test_raw_delete_detection_policy.py -q
E       assert False is True
E        +  where False = <function rejects_for_coverage ...>(989999, 1000000)
1 failed, 38 passed in 0.08s
```

Jeg havde valgt et fixture hvor dækningsbetingelsen ikke var opfyldt, og testede
derfor ikke den grænse jeg troede. Koden havde ret, testen tog fejl. Rettet til
et fixture hvor kun den absolutte grænse varierer, plus en ekstra test der
eksplicit fastholder at *begge* betingelser skal være opfyldt.

To resolver-tests fejlede først på en efterladt detalje:

```
E       AssertionError: assert '...Full/2026/08/17/' == '...Full/2026/08/17'
```

`dbutils.fs.ls` rapporterer mappestier med afsluttende skråstreg. Det er reel
adfærd og både `ls` og parquet-læsning accepterer den, så testen var forkert,
ikke koden.

### What I learned

Den vigtigste opdagelse kom af at læse frameworkets upsert-kode i stedet for at
stole på signaturen. Den sanitizer de nøgle- og attributnavne den får (kun
lowercase), og tjekker dem derefter mod måltabellens kolonner med et
**case-sensitivt** `in`. Konsekvensen: skrivestien virker kun hvis måltabellens
kolonner allerede er lowercase — hvilket de er, fordi indlæsningen skriver
gennem samme sanitizer. Men metadata staver nøglerne som kildesystemet gør
(uppercase), så de to sider hang kun sammen fordi Spark resolver join-kolonner
case-insensitivt. Det var en tilfældighed, ikke et design.

Jeg ændrede derfor koden til at resolve metadatas nøglenavne mod måltabellens
faktiske stavning forrest, og bruge målets stavning hele vejen igennem. Det
gjorde også mine egne Spark-tests korrekte: min første udgave byggede
testtabeller med uppercase kolonner og ville have kastet `TypeError` inde i
frameworket — en rød test der intet havde med opgaven at gøre.

Anden ting: en tidsstempel-kolonne der ikke er et tidsstempel er farligere end
en der mangler. `x > NULL` er NULL, rækken falder ud af det beskyttede sæt, og
beskyttelsen er slået fra uden et eneste signal. Det er nu et højlydt typetjek.

### What was tricky

Testplaceringen. Briefen bad om tests under framework-repoets testmappe, men
mappens `conftest.py` importerer pyspark ved collection, så *ingen* test der
lægges under den, kan køre lokalt — heller ikke en ren en. Jeg lagde dem
alligevel dér (så CI samler dem op) og dokumenterede `--noconftest`-kaldet i
runbooken som den lokale vej. Det er en pragmatisk løsning, ikke en pæn.

Valget mellem tidligste og seneste skrivetidspunkt som snapshot-cutoff tog
uforholdsmæssigt lang tid. Jeg endte på det tidligste: jo senere cutoff, jo
færre raw-rækker beskyttes. At udskyde en sletning til næste kørsel er billigt;
en falsk sletning er ikke.

Import af sidemodulet fra en Databricks-notebook er den ene ting jeg ikke kan
verificere herfra. Repoet bruger mønsteret andre steder, og bundle-syncen tager
mappen med, men om `os.getcwd()` peger det rigtige sted i det konkrete workspace
kan kun en kørsel afgøre.

### What warrants review

Det ene spørgsmål der betyder noget — kan nogen gren nå `soft_delete()` med et
delvist nøglesæt — gennemgik jeg gren for gren. Full- og watermark-sporene
skipper frem for at falde tilbage når mappen mangler eller er tom; CDC-sporet
starter fra raws egne nøgler og kan derfor kun slette for lidt, aldrig for
meget; guard A og C står imellem. Restrisiko: et delvist skrevet snapshot
(extract kører stadig) kan give en dækning lige over 95 % og dermed slippe forbi
guard C. Det er iboende i "læs den nyeste mappe"-designet og afbødes af
rækkefølgekravet i runbooken, ikke af kode.

En anden ting værd at se på: hvis entitetsnavnet i CDC-kontroltabellen ikke
matcher metadatas, bliver slettesættet tomt, og sporet bliver et stille no-op med
dækning 1,0. Ufarligt for data, men usynligt ud over at oversigten viser 0
sletninger.

### Future work

Watermark-sporet er skrevet men skipper alt i praksis, fordi nøgleudtrækket ikke
kører endnu. Det er kun dækket af unit-tests og bør køres igennem for alvor, når
udtrækket findes. Derudover: raw-tabellen bag CDC-sporet indeholder stadig ~5,9
mio. rækker der ikke burde have været hentet; filteret i metadata stopper kun
nye. En oprydning er ikke lavet.

## Step 3: Uafhængigt review — og hullet jeg selv havde efterladt

**Author:** builder (outer_heaven:builder sub-agent)

### Prompt Context

**Verbatim prompt:** Ingen ny prompt fra lead. Jeg havde selv sat en
review-agent på diffen med ét primært spørgsmål, ordret: *"Can ANY path through
the code end up calling `write.soft_delete()` with a `source_keys_df` that is not
the source's full truth for that particular table? Trace every branch."*
Rapporten kom efter afleveringen af Step 1.

**Interpretation:** Behandl fundene som rigtige indtil det modsatte er vist, og
ret det der reelt kan gøre skade.

**Inferred intent:** Et selvreview af egen kode har en blind vinkel; den skulle
lukkes af nogen der ikke havde skrevet den.

### What I did

Reviewet svarede "ja" på hovedspørgsmålet — ikke ad 17/8-ruten, men ad en anden.
Guard C målte nøglesættets **størrelse**, ikke dets **overlap** med måltabellen.
Og størrelse er præcis hvad et ødelagt nøglesæt beholder: læses en nøglekolonne
tilbage med en anden type end måltabellen har, joiner sættet til ingenting, mens
dækningen aflæses som 1,0000 og hver eneste række er på vej til at blive
markeret slettet. Samme skadesomfang som hændelsen, ad en rute ingen af mine tre
guards kunne se.

Guard C tæller nu det faktiske anti-join. Det koster en tredje `count()` pr.
tabel; briefen tillod to, men den aritmetik de to understøttede betyder ikke det
guarden har brug for at den betyder.

Typemismatchet forebygges nu også, ikke bare opdages: nøglerne castes til
måltabellens egne typer. Derudover rettet: to kildeobjekter kan kollapse til ét
`entity_name` og blive parret på tværs (rejser nu), guard A og B afsluttede
kørslen med exit 0 (blokerer nu), mappe-resolveren sorterede ikke-nul-paddede
datonavne som tekst (`["10","9"]` valgte september), fil-listningen slugte alle
exceptions inklusive rettighedsfejl, og i SQL-scriptet sammenlignede
idempotens-guarden under databasens case-insensitive collation.

### Why

Fundene handlede alle om at fejl blev usynlige. Det var netop det hele opgaven
gik ud på at forhindre, så de var ikke til forhandling.

### What worked

At stille review-agenten ét skarpt spørgsmål frem for at bede om en generel
gennemgang. Det primære fund kom direkte af det spørgsmål og var ikke noget jeg
selv fandt på to gennemlæsninger.

At jeg havde lagt logikken i et testbart modul betød at hvert fund kunne lukkes
med en test frem for med et argument. Testantallet gik fra 46 til 55.

### What didn't work

Reviewet fandt også at fire af mine Spark-tests ikke kunne bestå, fordi de
byggede testtabeller med uppercase kolonner. Det havde jeg selv fundet og rettet
timer forinden — men kun fordi jeg tilfældigvis læste frameworkets upsert-kode.
To uafhængige veje til samme fund er et dårligt tegn for hvor let det var at
overse.

Jeg fik desuden skrevet et kinesisk tegn ind midt i en commit-besked
(`those two支持ed`) og måtte amende den. Ingen skade, men værd at bemærke.

### What I learned

Et guard-kriterium skal måle den handling det beskytter imod, ikke en proxy for
den. "Nøglesættet har rimelig størrelse" lignede en fornuftig proxy for
"nøglesættet er troværdigt" og var det ikke. Den eneste rigtige måling var den
samme join som skrivestien selv laver.

Og: to uafhængige inferenser af samme skema er to skemaer. Måltabellens skema
blev udledt én gang og gemt; snapshot-læsningen udleder på ny over én mappe.
Hvor de er uenige, promoverer Spark stille begge sider til en fælles type i
joinet og matcher intet.

### What was tricky

At afgøre hvilke fund der var reelle. Reviewet leverede en prioriteret liste,
men et par af punkterne var teoretiske for dette datasæt (NULL i primærnøgler,
translitterede entitetsnavne). Dem skrev jeg ind som kendte begrænsninger i
runbooken i stedet for at bygge maskineri til dem. Balancen mellem "ret alt" og
"ret det der kan ske" er ikke givet på forhånd.

### What warrants review

Den tredje `count()` pr. tabel er en bevidst afvigelse fra briefen og bør
godkendes eksplicit. På de største tabeller er det et ekstra fuldt anti-join.

Beskyttelses-unionen (K6) lægges ind i nøglesættet *før* guard C måler, så
dækningstallet delvist indeholder rækker der kom fra måltabellen selv. Det er
efter min vurdering det rigtige at måle — det er hvad skrivestien faktisk vil
gøre — men det er værd at være enig om.

### Future work

Nøglesættet materialiseres omkring fem gange pr. tabel (guard A, guard C's to
counts, frameworkets egne debug-counts, og selve merge'en) uden caching. Det er
korrekthedsneutralt, men reelt spild på store tabeller.

## Step 4: Materialisér nøglesættet én gang

**Author:** builder (outer_heaven:builder sub-agent)

### Prompt Context

**Verbatim prompt:** *"Du flagger selv at `source_keys_df` bygges ~5 gange pr.
tabel uden caching. Det er en større omkostning end den tredje count vi lige har
accepteret. Den største tabel i estatet har ~114,7 mio. rækker — dér er
forskellen mellem én og fem materialiseringer reel. Krav: cache eller persistér
`source_keys_df` når det er bygget, og frigiv det igen når tabellen er
færdigbehandlet — også når tabellen afbrydes af guard A, guard C eller en
exception."* Med to ting jeg blev bedt om at vurdere frem for at antage: valget
mellem `cache()` og `persist(MEMORY_AND_DISK)`, og om `raw_current_df` har samme
problem.

**Interpretation:** Ret den omkostning jeg selv havde noteret som future work,
og træf de to valg på et grundlag frem for på vane.

**Inferred intent:** Lukke opgaven — det var sidste krav — uden at åbne nye
adfærdsændringer.

### What I did

Begge frames caches nu, og begge frigives i en `finally` der dækker samtlige
udgange: guard B's return, sporbyggerens "ingen nøglekilde"-return, guard A,
guard C, exception-grenen og normal gennemførelse. Frames samles i en liste
efterhånden som de persisteres, og `finally` løber listen igennem — det var
lettere at få rigtigt end indlejrede try/finally, og det kan ikke komme ud af
trit når der senere tilføjes en guard.

Vurderingen af `raw_current_df` gav mere end forventet. Den var ikke bare "det
samme problem": den blev bygget **tre gange** på tre forskellige steder — én
gang til guard C's count, én gang til guard C's anti-join, og én gang inde i
hver sporbygger til beskyttelses-unionen (og CDC-sporet læser sin to gange
internt). Jeg samlede den til én projektion pr. tabel, bygget ét sted og sendt
med ind i sporbyggerne. Projektionen er lige så vigtig som cachen: frames
reduceres til nøglekolonnerne plus ét tidsstempel, og den brede tabel har langt
flere kolonner end det, som ingen downstream bruger.

Valget mellem `cache()` og `persist(MEMORY_AND_DISK)` er ikke kosmetisk, hvilket
jeg troede indtil jeg slog det op: i PySpark 3.4+ betyder `cache()`
`MEMORY_AND_DISK_DESER`, altså deserialiserede objekter på heapen. Jeg valgte
den serialiserede variant og skrev begrundelsen i koden — sættet kan nå
størrelsesordenen af den største tabel, fire tabeller kører samtidig, og det
læses en håndfuld gange, ikke hundredvis. Så kompakt lagring der spiller ud på
disk slår hurtig deserialisering; en eviction ville koste en fuld genlæsning.

### Why

Fem materialiseringer af et sæt der på den største tabel har ~114,7 mio. rækker
er dyrere end den tredje count vi lige havde diskuteret, og på snapshot-sporene
betyder en genberegning ikke bare et scan, men en ny parquet-læsning plus et nyt
beskyttelses-join.

### What worked

At samle de persisterede frames i en liste og frigive dem ét sted. Det gjorde
det trivielt at verificere dækningen: seks udgange, én oprydning, ingen af dem
kan glemmes.

At blive bedt om at *vurdere* frem for at vælge. Havde jeg bare skrevet
`cache()`, havde jeg ramt den fede variant uden at opdage det.

### What didn't work

Ingen fejlslagne kørsler denne gang — ændringen er ren refaktorering plus
caching, og de rene tests rører den ikke. Det er samtidig svagheden: **intet af
dette er verificeret i drift.** De 55 tests er stadig grønne, men de tester
beslutningslogikken, ikke hukommelsesadfærden. Om `MEMORY_AND_DISK` faktisk er
det rigtige niveau, og om unpersist frigiver hurtigt nok til at fire samtidige
tabeller ikke træder på hinanden, kan kun en kørsel afgøre.

### What I learned

`cache()` og `persist()` er ikke synonymer i PySpark længere, og forskellen er
netop relevant i det tilfælde hvor man cacher: store frames. Værd at huske til
næste gang.

Og: når man leder efter unødige materialiseringer, er den rigtige første
bevægelse at spørge hvor mange gange en frame *bygges*, ikke hvor mange gange
den læses. Her var svaret tre steder for den ene frame, hvilket cachen alene
ikke ville have løst — to cachede kopier af samme projektion er stadig to.

### What was tricky

At holde ændringen inden for det aftalte. Sammenlægningen af de tre
raw-projektioner ændrer signaturerne på alle tre sporbyggere, og det ligner mere
end "tilføj caching". Jeg vurderede det som nødvendigt for at kunne cache
overhovedet — man kan ikke dele en cache mellem tre uafhængigt byggede frames —
men det er en større diff end kravet lyder til.

### What warrants review

Signaturændringen på de tre sporbyggere: de tager nu en færdigbygget frame ind i
stedet for et tabelnavn. Adfærden er uændret, men det er den slags ændring hvor
en overset call-site ville vise sig først i drift.

Og storage level-valget. Begrundelsen står i koden, men den bygger på et skøn
over hvor stort nøglesættet bliver, ikke på en måling.

### Future work

Ingen nye. De to punkter fra Step 3 står stadig: watermark-sporet er kun dækket
af unit-tests indtil nøgleudtrækket kører, og kontroltabellen i raw indeholder
stadig rækker der ikke burde have været hentet.

---

**Tilføjelse til samme arbejdsgang: objekttallet i runbooken.**

Jeg havde selv flaget at runbooken indeholdt et objekttal jeg vidste var
forkert, men lod det stå fordi leveringsomfanget var snævert defineret. Det var
den forkerte afvejning, og lead korrigerede den med en begrundelse der holder:
et forkert tal i et dokument nogen læser *under* en kørsel er værre end en
manglende oplysning. At respektere scope er ikke en grund til at lade et kendt
forkert tal blive stående — det rigtige træk havde været at rette det og
oplyse om det, ikke at spørge først.

Fordelingen er nu målt i metaen efter seed-scriptet er kørt: 70 objekter,
fordelt 22 på full-sporet, 29 på CDC-sporet og 19 på watermark-sporet. Skrevet
ind som målt tal, og forbeholdet om at "tallene ikke er verificeret" er fjernet,
fordi det ikke længere er sandt for fordelingen. Til gengæld skrev jeg præcist
det forbehold der *stadig* gælder: selve kørslens output er ikke set endnu, så
hvor mange objekter der ender som skrevet afhænger af hvad der er landet. Det
var værd at bruge et øjeblik på — et forbehold der er bredere end virkeligheden
lærer læseren at ignorere forbehold.

Tre steder skulle rettes, ikke ét. Ud over selve fordelingen også
eksempel-optællingslinjen i afsnittet om oversigten. Den skrev jeg om fra et
opdigtet konkret eksempel til en form med pladsholdere plus den invariant der
faktisk kan kontrolleres: tallene skal summere til 70, mindst de 19
watermark-objekter står som skippet, og afvist/blokeret/fejlet skal alle være 0.
Bedre end et eksempel jeg ikke kan stå inde for.

Det tredje sted rørte jeg bevidst *ikke* mekanisk. Beskrivelsen af hændelsen
nævner 67 objekter, og det er korrekt for det tidspunkt. Jeg beholdt tallet og
gjorde i stedet tidsangivelsen eksplicit ("i scope dengang"), så en læser ikke
læser det som en modsigelse af de 70 længere nede. Lead bad specifikt om at det
blev vurderet frem for rettet, og vurderingen faldt ud til at beholde det.

En sidste detalje jeg fangede ved gennemlæsning: mit udkast skrev at skip af
kontroltabellen og af det append-only objekt kom "oveni" fordelingen, hvilket
kunne læses som 70 + 2. De ligger inde i de 70. Rettet, fordi det er præcis den
slags tvetydighed der får nogen til at tro at oversigten ikke stemmer.

Om at et objekt endeligt bliver på watermark-sporet: det er nu afgjort på data
frem for på oplysning — et friskt udtræk dækkende tre døgn indeholder stadig
præcis 29 entiteter i kontroltabellen, og objektet er ikke blandt dem. Skrevet
ind i runbooken som kontekst ved klassifikationen. Der er ikke bygget noget på
det: sporet læses fra metadata, og der er ingen navne i koden.
