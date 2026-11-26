# Diary: Ø90 posteringer — AQE's broadcast-konvertering slået fra i stedet for en større driver

Det tunge enriched-trin i Ø90-dashboardets posteringspipeline har fejlet periodisk i
produktion med at driverens `maxResultSize` sprænges. Stacktracen peger hver gang på
`BroadcastExchangeExec.$anonfun$relationFuture$1` → `Collector.collect`: det er build-siden
af en broadcast join der collectes til driveren, ikke manglende worker-ressourcer.

Årsagen er et kendt AQE-mønster. AQE beslutter i runtime at broadcaste ud fra
**komprimeret** shuffle-størrelse, men collecter **ukomprimerede** rows. Data med mange
gentagne strenge komprimerer ekstremt godt, så en relation kan måle langt under tærsklen
komprimeret og flere GiB ukomprimeret. Ligger den på vippen, flipper planen fra dag til
dag — hvilket forklarer præcis hvorfor fejlen er periodisk og ikke konstant.

Det første plaster var hardware: en dedikeret prod-driver med `maxResultSize: 8g`. Det holdt
en periode og fejlede så igen, nu på 8,1 GiB mod 8 GiB. Dermed er hardware-ruten udtømt —
Spark har `MAX_BROADCAST_TABLE_BYTES` hardkodet til 8 GB i `BroadcastExchangeExec`, og
ingen driverstørrelse på Azure flytter den grænse. Denne leverance er derfor den varige
rettelse: forbyd AQE at vælge broadcast overhovedet, og giv i stedet eksplicitte hints til
de lookups der reelt er små nok.

## Step 1: Implementering af conf-fladen og broadcast-hintet

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt (saniteret):** "Implementér en præcist afgrænset rettelse i kunderepoet […] PROD-jobbet
`Master oe90 dash`, trin `load_to_enriched_posteringer`, fejler periodisk med:
`org.apache.spark.SparkException: … Total size of serialized results of 128 tasks (8.1 GiB)
is bigger than spark.driver.maxResultSize 8.0 GiB` […] Rettelsen er at forhindre AQE i at
vælge broadcast, og i stedet give eksplicitte broadcast-hints til de lookups der reelt er
små. […] **Ændring 1** — slå AQE's broadcast-konvertering fra […] Placér den efter
parametrene men FØR den første `spark.sql()`/`spark.table()`-kald. […] **Ændring 2** —
eksplicitte broadcast-hints i fase 3 […] `SELECT /*+ BROADCAST(pt, ott, niv1) */` […]
**Hvad du IKKE må gøre:** Rør ikke `assetbundlevariables.yml`. […] Rør ikke
`master_oe90_dash.yml`. Fjern ikke `.display()`-kaldene […] Ændr ingen SQL-logik, ingen
joins, ingen kolonner. […] Branch fra `main`, IKKE fra den nuværende release-branch. […]
Commit-forfatter SKAL være `<navn> <mail>`. […] Push branchen. Opret
IKKE en PR uden videre. […] Hvis du opdager at noget i briefen ikke passer med den faktiske
fil […] så STOP og rapportér i stedet for at improvisere."

**Interpretation:** To kirurgiske ændringer i én notebook: to `spark.conf.set`-linjer i
parametercellen og ét SQL-hint efter `SELECT` i fase 3's store join, plus en kort begrundelse
i den omkringliggende markdown. Alt andet i repoet er fredet, inklusive den støjende
`.display()`-oprydning og den store driver, som først må rulles tilbage når fixet er
verificeret i prod. Branch fra `main`, commit som Benny, push uden PR.

**Inferred intent:** Flytte rettelsen fra hardware-sporet, som er kørt tør, til plan-sporet,
uden at ændre en eneste række i outputtet. Ændringen skal være så lille og læsbar at den kan
reviewes på øjemål og rulles tilbage isoleret, og den skal kunne deployes uafhængigt af
release-branchen der allerede er i luften.

### What I did

Læste kontekstnoten og hele notebooken igennem før jeg rørte noget, og verificerede at
briefens beskrivelse af filen holdt — den gjorde: parametercellen så ud som beskrevet, den
første `spark.table()`-kald ligger efter den, og de tre hint-mål havde de aliaser briefen
antog (`pt`, `ott`, og `niv1` som uden alias matcher temp-viewets navn).

Branchede fra `main` frem for fra den kørende release-branch, lagde de to conf-linjer ind
efter `raw`-variablen i parametercellen med en dansk kommentar der forklarer hvorfor begge
nøgler er nødvendige, og satte `SELECT /*+ BROADCAST(pt, ott, niv1) */` på fase 3's join.
Begrundelsen for hintet lagde jeg som et afsnit i markdown-cellen lige over joinet, hvor
filen i forvejen dokumenterer join-kæden — det passede bedre til husstilen end en SQL-kommentar
inde i strengen.

Commit med eksplicit `--author="<navn> <mail>"`, kun den ene fil, og
den utrackede `.claude/`-mappe holdt udenfor. Pushet uden PR.

### Why

Begge conf-nøgler skal sættes, ikke kun den ene. Databricks' AQE-broadcast styres af
`spark.databricks.adaptive.autoBroadcastJoinThreshold`, mens `spark.sql.autoBroadcastJoinThreshold`
kun rammer den statiske planlægning. Sætter man kun den statiske, konverterer AQE stadig i
runtime og fejlen er uændret. Det er den fælde hele rettelsen står og falder med, og derfor
står den skrevet ud i kommentaren i koden frem for kun i kontekstnoten.

Hintet er ikke pynt. Når tærsklen er slået fra, gælder det for *alle* joins i planen, også
de tre bittesmå opslagstabeller på 4–10 rækker. Uden hint ville de falde til sort-merge join
med fuld shuffle af hele posteringstabellen på hver af dem — en rettelse der fjerner
driver-nedbruddet ved at gøre jobbet langsomt nok til at være et nyt problem.

### What worked

Verifikationen var billig og entydig. `git diff main --stat` gav præcis én ændret fil, og
`python -m py_compile` på notebooken gik igennem uden fejl. Jeg tjekkede også at filen stadig
dekoder som UTF-8 uden BOM, da både kommentarerne og markdown-cellen indeholder æ/ø/å — en
mangled encoding ville have været den slags fejl der først dukker op på clusteret.

Repoets git-identitet stod allerede korrekt som Bennys kunde-identitet, og der
er hverken commit-template eller aktive hooks der kunne skyde attribution ind. Jeg satte
`--author` eksplicit alligevel og verificerede bagefter med et grep efter
`claude|co-authored|anthropic|generated with|<forkert konto>` i commit-beskeden. Tomt.

### What didn't work

Én selvforskyldt fejl, fanget i mit eget diff-review. Da jeg satte hintet ind, matchede jeg
på `CAST(p.ejendommeid AS STRING)  ` inklusive to af de mellemrum der holder `AS ejendommeid`
i den kolonneopstilling filen bruger hele vejen igennem. Erstatningen tog dem med, så den
første linje i select-listen faldt to tegn ud af flugt med de 40 andre. Rent kosmetisk, men
det ville have stået i diffet som en uforklarlig ændring på en linje der ikke var en del af
opgaven. Rettet med en opfølgende edit der lagde de to mellemrum tilbage; det endelige diff
viser linjen som uændret kontekst.

Jeg kunne ikke verificere lokalt at `spark.conf.set` accepterer `-1` som Python-`int` frem
for strengen `"-1"` — `pyspark` er ikke installeret på maskinen:

```
ModuleNotFoundError: No module named 'pyspark'
```

Der findes heller ingen anden `spark.conf.set` i repoet at læne sig op ad; mit grep fandt kun
mine egne to nye linjer. Se "What warrants review".

### What I learned

Der er en hård grænse her man ikke kan købe sig ud af. `MAX_BROADCAST_TABLE_BYTES` er 8 GB
hardkodet i `BroadcastExchangeExec` (plus 512 mio. rækker), så over den fejler jobbet uanset
driverstørrelse. Det gør hardware-plastret til en ren udsættelse med præcis én fordobling i
sig, hvilket er nøjagtig hvad forløbet viste: 4 GiB → 8 GiB driver → fejl igen på 8,1 GiB.

Detaljen om komprimeret måling mod ukomprimeret collect er hele forklaringen på at fejlen er
*periodisk*. En relation der ligger på vippen mellem de to tal flipper plan fra dag til dag
afhængigt af hvor godt dagens data komprimerer. Det er værd at genkende næste gang noget
fejler "af og til" med en broadcast i stacktracen.

`niv1`-joinet har ingen equi-nøgle — det er en ren `BETWEEN` — og bliver derfor
BroadcastNestedLoopJoin uanset tærsklen. Hintet ændrer ikke *om* der broadcastes der, kun at
valget bliver eksplicit i planen. Det er en pointe der er let at misforstå som at hintet
"omgår" den tærskel man lige har slået fra.

### What was tricky

Fristelsen til at gøre lidt mere end opgaven. Notebooken har fire `.display()`-kald,
som hver giver en ekstra evaluering af de samme aggregeringer pr. kørsel, og temp-viewene
caches ikke. Det ligger lige for at rydde op mens man alligevel er inde i
filen, men briefen fredede det eksplicit, og med god grund: fixet skal kunne verificeres i
prod uden at der er en anden ændring at forveksle effekten med.

Den anden var at ramme det rigtige sted til begrundelsen. Filen dokumenterer sig selv tungt i
markdown-celler med tabeller over join-kæden, så en SQL-kommentar inde i den 80 linjer lange
query-streng ville have været det forkerte sted at forklare noget der handler om hele planen.

### What warrants review

Tre ting, i prioriteret rækkefølge.

**Kør jobbet og bekræft at broadcasten er væk.** Det er den eneste rigtige validering, og den
kan kun laves i target-miljøet. Jeg har ikke kørt Databricks-jobs eller deployet noget. Det
der skal ses efter i Spark UI er at `BroadcastExchange` ikke længere optræder over de store
joins i fase 3, og at de tre hint-mål stadig broadcastes.

**Typen på `-1`.** Linjerne står som `spark.conf.set("…", -1)` med Python-`int` som briefen
angav. Jeg vurderer det som sikkert — `RuntimeConfig.set` er annoteret `Union[str, int, bool]`
i Spark 3.4+, og Scala-siden har en `set(String, Long)`-overload — men jeg har ikke kunnet
køre det. Er der tvivl, er `"-1"` som streng en risikofri ændring, og fejlen ville i givet fald
vise sig i første celle på første kørsel, ikke halvvejs inde i jobbet.

**Performance-regressionen der ikke er hintet væk.** Tærsklen på `-1` rammer hele planen, og
kun tre af de tretten joins har fået hint. `fy`, `metadata`, `opsaetninger`, `produktionsgren`,
`ejendomme`, `kontolinier`, `opgavetype`, `liniestyringer` og `niv2` bliver alle sort-merge
joins nu, også dem der før blev broadcastet legitimt. Det er den tilsigtede pris — det var
netop dér den store relation kom fra — men den første prod-kørsel skal sammenlignes på
varighed, ikke kun på om den lykkes. `niv2` er den at holde øje med: den er equi på `cvrnr`
plus `BETWEEN`, så skæve cvr-fordelinger giver skæve partitioner.

### Future work

Et duplikat-tjek på join-nøglen for de to tabeller der joines på `ejendommeid` alene udestår
stadig.

Den store driver og `maxResultSize: 8g` står bevidst urørt indtil fixet er verificeret i prod.
Når det er sket, er der en oprydning i at rulle den tilbage til default-clusteret — men først
da, og som en selvstændig ændring.

`.display()`-oprydningen og et muligt `RANGE_JOIN`-hint på `niv2` ligger begge som separate,
mindre opgaver der ikke skulle blandes ind her.
