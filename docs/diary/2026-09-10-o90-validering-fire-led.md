# Diary: Validering af Ø90-data mod kilden i fire led

Kundeprojekt hos landbrugets datafællesskab. Enriched-ombygningen (metadatadrevet, ~70
tabeller) er næsten færdig, og spørgsmålet der skal besvares før den kan shippes er hvordan
man overhovedet får en velbegrundet tillid til at data er rigtige — uden at bruge en uge på
det og uden at belaste et produktionskildesystem hårdt.

Opgaven kom som "vi validerer enriched mod DB2-kilden". Arbejdet her handler mest om at finde
ud af at den ramme var forkert, og hvad den rigtige er.

## Step 1: Kortlægning af hvad der allerede findes, og hvad valideringen faktisk er

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Benny vil have en konkret plan for hvordan Ø90-data valideres mod
DB2-kilden. Hans ord: 'Vi validerer enriched mod DB2-kilden. De kommer jo aldrig til at være
helt i sync. Det er vigtigt at finde balancen mellem rigtighed og hastighed — sådan at vi får
en god mavefornemmelse med data, men det skal også gå hurtigt at validere, da vi snart skal
have shippet det her.'"

**Interpretation:** Der skal leveres en udførbar plan, ikke en metodebeskrivelse: hvilke
tabeller, hvilke kolonner, hvilket tidsvindue, hvilke queries på begge sider, og hvad et
afvigende svar betyder. Shipping-presset er en reel begrænsning der skal skære i planen.

**Inferred intent:** Tillid til data før release, købt så billigt som muligt. Underforstået
at "hurtigt" ikke må betyde "overfladisk nok til at være vildledende" — deraf kravet om at
skrive ned hvad valideringen *ikke* beviser.

### What I did

Læste den eksisterende verifikationskode, afstemningskoden fra en tidligere leverance, og
ADF-lagets DB2-udtræk. Sendte to parallelle udforskningsagenter afsted: én på spørgsmålet
"hvordan udføres overhovedet en ad hoc-forespørgsel mod DB2 i denne løsning", én på "kan den
eksisterende afstemningskode genbruges".

Verificerede selv de fund der bar konklusioner, frem for at stole på referater: den lagrede
procedure der bygger udtræks-SQL'en, `IfCondition`-betingelsen omkring sletningen af
landing-filer, og de to diagnostik-artefakter der påstod at DB2-forbindelsen aldrig havde
virket.

Undervejs opdagede jeg at mit worktree stod på `main` og ikke på feature-branchen, så
halvdelen af den kode opgaven handlede om ikke eksisterede i checkouten. Nulstillede
worktree-branchen til feature-branchen og sendte en rettelse til begge kørende agenter med
besked om at gentage de læsninger der var fejlet.

### Why

Rammen "enriched mod DB2" indeholder to helt forskellige spørgsmål — fangede udtrækket
kilden, og afledte enriched raw korrekt — og de har vidt forskellig pris. At skelne dem var
en forudsætning for overhovedet at kunne skære i planen.

### What worked

At verificere referater mod kildefilerne. Begge agenter leverede fund der var rigtige i
substansen, men to af de vigtigste konklusioner ville have været forkerte hvis jeg havde taget
referatet for pålydende.

En diagnostik-linked-service beskrev DB2-forbindelsen som en åben fejl: "Used to test whether
a parameterised linked service behaves differently ... where Get NewWatermark Value has never
succeeded." Både den og en tilhørende diagnostik-pipeline var markeret "Delete once the
question is settled". Jeg konkluderede at forbindelsen kunne være blokeret, og stillede det
som spørgsmål frem for at bygge planen på det. Svaret var at spørgsmålet **blev** afgjort for
en uge siden, men noterne aldrig blev fjernet. Efterslæb i dokumentationen der læses som en
åben fejl af enhver der kommer forbi.

At stille spørgsmålet i stedet for at gætte var det rigtige træk, og det er en generel lære:
en kodekommentar der beskriver en tilstand er et øjebliksbillede med en udløbsdato, ikke et
faktum.

### What didn't work

Min egen første analyse af hvor valideringen skulle sættes ind var skæv, og worktree-fejlen
var delvist skyld i det. Jeg tog udgangspunkt i en ramme hvor kæden havde to led (raw og
enriched) og hvor kun det ene var udækket. Den viste sig at have fire.

Et forsøg på at køre `cd <worktree> && grep ...` gav tom output uden fejl, hvilket sendte mig
et kort stykke ned ad et forkert spor ("koden findes ikke i repoet"). Den rigtige forklaring
var branchen, ikke repoet.

### What I learned

**Landing-zonen akkumulerer.** Sletningen af landing-filer ligger inde i et `IfCondition` på
en `ReloadTableInFull`-parameter, ikke i den daglige sti. Kildens egne parquet-filer bliver
altså liggende, dateret pr. kørsel. Det betyder at sammenligningen "gjorde indlæsningen det
rigtige ved det kilden leverede" kan laves **række for række, gratis, uden at spørge
kildesystemet om noget som helst**. Det var det enkeltfund der ændrede planen mest.

**Fuld-load afgøres per objekt, ikke per kørsel.** Udtrækket beregner `RunIsIncremental` som
en AND mellem objektets eget flag og jobbets parameter. Et objekt der ikke er markeret
inkrementelt kører fuldt hver eneste dag, også under en inkrementel kørsel. De objekter har
dermed et komplet, friskt kildesnapshot liggende hver morgen.

**Der findes ingen vej til at få et aggregat *tilbage* fra kilden uden ny kode.**
Copy-aktiviteten lander filer; den eneste aktivitet der returnerer en værdi kører en query
hvis tekst genereres af en lagret procedure fra metadata. Den frie tekst man kan indsætte
lander i `WHERE`-positionen og kan ikke tilføje et `GROUP BY`. Til gengæld beviser en
eksisterende pipeline at en literal kilde-query *kan* sendes afsted og dens resultat landes —
så en generisk aggregat-pipeline er buildbar og lille.

**Den eksisterende afstemningskode fra en tidligere leverance kan ikke genbruges.** Den rører
aldrig den egentlige kilde: dens "kilde"-side er et ældre datawarehouse, staged til Delta af
en separat notebook. Det er en stor, uparametriseret fil; kun normaliseringen kan genbruges.

Det bedste i den fil var ikke det jeg blev bedt om at kigge efter. De tre renseregler
(padding, tom streng mod NULL, dato-sentinel) er der, men asymmetrisk anvendt og delvist
bundet til en enkelt kolonne. Det virkelig genbrugelige er et ordens-uafhængigt
kolonne-fingeraftryk bygget som bitvis XOR over en hash pr. række — det kan ikke overflowe som
en `SUM` kan, og det peger på *hvilken* kolonne der afviger uden et ekstra join. Altså styrken
fra et rækkeniveau-tjek til prisen af et aggregat.

**En verifikation der er skrevet er ikke en verifikation der er kørt.**
Verifikations-notebooken for enriched mod raw står eksplicit som UVERIFICERET i projektets
egen runbook: beslutningslogikken er enhedstestet, men det fulde outer join og
tidsrejse-pinningen har aldrig rørt en cluster. De "få sekunder på mange millioner rækker" der
cirkulerede som argument for at det led allerede var løst, stammede fra pilotens håndskrevne
joins, ikke fra notebooken.

### What was tricky

At holde fast i at "enriched mod DB2" var det forkerte spørgsmål, når det var sådan opgaven
blev stillet, og når rammen kom med en gennemarbejdet analyse vedhæftet. Analysen var god og
tre af dens fem punkter holdt; men dens grundpræmis — at det ene af to led allerede var dækket
gratis — var halvt forkert på to måder samtidig (notebooken har aldrig kørt, og der var fire
led, ikke to).

Den anden vanskelighed var at skelne mellem "dyrt" og "blokeret". Det er to helt forskellige
svar til en der skal shippe, og forskellen lå i en kodekommentar der var forældet.

### What warrants review

Kortet over de fire led og især **afgrænsningen**: hvad de fire led tilsammen ikke beviser. To
huller er identificeret og skal stå skrevet så de kan læses uden at grave — afkortning der sker
i selve udtrækket er usynlig i landing fordi filerne allerede er castet, og rækker kilden har
men aldrig sendte mangler ens i landing og i raw, så de to kan ikke afsløre hinanden.

Sidefund til oprydning: de to diagnostik-artefakter med forældede noter bør slettes eller
rettes. De sendte mig ned i en blindgyde, og de vil sende den næste samme vej.

### Future work

Planen skrives i projektets status-repo, ikke i kunderepoet, og bygges derefter af en
builder-teammate. Fire led, prioriteret efter pris: de tre gratis først, kilde-benet sidst og
snævrest. Alle kørsler udføres af kunden selv; builder skriver kode og runbook og deployer
intet.

## Step 2: Den sidste tabel, og to af de fire led bygget

**Author:** builder

### Prompt Context

**Verbatim prompt (saniteret):** "Repo: C:\claudes_folder\repos\DLBR-DataEstate2026. Branch: `feature/o90-enriched-v2`, seneste commit `9c2a3be`. Pull først. [...] **Fire buildere er døde på API-fejl i dette forløb.** Commit og push løbende. Efterlad aldrig ucommitteret arbejde i Bennys hovedarbejdstræ. [...] Opgave 1: stream-notebooken til METODETIDERALLE. Den eneste tabel der ikke er bygget. Knap to milliarder rækker, få promille ændret pr. døgn. [...] Opgave 2: valideringsled 2 — landing → raw. Planens afsnit 'Led 2'. Den billigste stærke kontrol vi har liggende ubrugt. [...] Opgave 3: valideringsled 4 — raw → enriched, værdier. Planens afsnit 'Led 4'. Lukker NULL-auditens blinde vinkel [...] **Deploy intet. Kør intet mod Databricks.**"

**Interpretation:** Tre selvstændige leverancer i samme aflevering: den ene tabel der ikke kunne køre gennem den generiske notebook, plus to nye verifikations-notebooks der skriver til en fælles resultattabel. Alt sammen kode plus runbook — ingen kørsel, intet deploy. Leaden havde allerede lagt de tre valg jeg skulle træffe selv frem som spørgsmål: merge-nøglen når `dw_valid_from` ikke findes, og om de afledte kolonner hører i enriched eller curated.

**Inferred intent:** Enriched-laget skal kunne shippes til test, og de to ting der mangler er dækning (den sidste tabel) og tillid (leddene). Advarslen om fire døde buildere er en instruks om arbejdsform, ikke om indhold: små commits, push efter hver, aldrig et halvt resultat i hovedarbejdstræet.

### What I did

Seks commits, pushet enkeltvis: `705d873` (append-only-tabellen), `0b1773b` (led 4), `c099048` (led 2), `f419a22` og `0fae526` (to fund fra mit eget review), `ef73b9d` (syv fund fra et uafhængigt review af diffen).

**Den append-only tabel.** Ny notebook `transform_enriched_o90_append_only.py` ved siden af den generiske. Jeg verificerede carve-out'en mod koden i stedet for at tage den på ordet, og den holder i tre led: `load_to_raw_general.py:154-159` skriver mønstret med `.outputMode("append").table(...)` uden MERGE, `:138-140` kalder kun `add_scd2_audit_columns` når `"scd2" in write_pattern`, og — det der egentlig afgør sagen — `raw_delete_detection.choose_track` springer `stream_append` over på linje 338, så `write.soft_delete` heller aldrig rører tabellen. Den er altså append-only i drift og ikke bare i hensigt, og det er forudsætningen for at en Delta-tabel overhovedet er en lovlig streaming-kilde.

Tre konsekvenser skulle håndteres hver for sig. Enriched bærer **to** dw-kolonner her, ikke fem: `dw_is_deleted` båret fra raw (strukturelt `false`, fordi delete-detektionen springer mønstret over — båret alligevel, fordi enriched er en tro afledning og ikke en vurdering af raws indhold) og `dw_processing_date`.

Merge-nøglen blev det spørgsmål jeg brugte længst tid på, og svaret er at der ikke er nogen. SCD2-vejen merger fordi raw *lukker* historikrækker og lukningen skal nå frem; her lukkes intet. Værre: `generic_upsert_type_1` kalder `dropDuplicates(primary_key_columns)` når der ikke er en sequence-kolonne (`lighthouse/write.py:830`), og raw kan — netop fordi den er append-only — lovligt have to rækker med samme forretningsnøgle hvis kilden har genleveret. En merge ville lægge dem sammen vilkårligt og efterlade enriched med færre rækker end raw, altså præcis den defekt `verify_enriched_o90.py` findes for at fange. Skrivningen blev en append; forretningsnøglen erklæres stadig på tabellen gennem `create_table`, fordi den dokumenterer kornstørrelsen og er det en afstemning joiner på.

Checkpoint frem for watermark blev skrevet ind som en **livscyklus** på kontrolrækken: `watermark_column_name = '_checkpoint'`, `watermark_value` altid NULL. Rækken siger dermed selv hvilken reparation der gælder for den, og runbook 16.5 har begge trin.

Spørgsmålet om de afledte kolonner (`PRTIMESTAMP`, `PRYEAR`, `PRMONTH`, `source_system`) besvarede jeg med et grep i stedet for med et princip, og svaret blev entydigt: **nul konsumenter i hele `solutions/`** for de tre første, og for den fjerde har curated allerede sin egen og rigere mapning fra `maskine` (`03_curated/o90/fact_metodetideralle.py:51-57`) som enricheds version ikke kender. Curated bygger oven i købet allerede selv den samme komposition (`:75`) og `year(prdato)` (`transform_fact_automatikker.py:222`). Så de hører i curated, de *er* i curated, og enricheds versioner er døde kolonner på knap to milliarder rækker.

Samme grep fandt den modsatte konklusion for `PRDATO`: netop fordi curated parser den med mønstret `'yyyy-MM-dd HHmmss'` og kalder `year()` på den, **skal** den være en DATE. Det blev en override i seed-scriptet med begrundelse og forfatter — ikke en gren i notebooken — i plain `numeric_yyyymmdd_to_date`-form, af samme paritetsgrund som SYSNR i leverance 2.

**Led 2 og led 4** blev to nye notebooks plus en fælles resultattabel `o90_v2_source_validation` med planens skema. Detaljerne om hvorfor led 2 måtte afvige fra planen står under "What didn't work".

### Why

Opgave 1 var det sidste hul i dækningen: 69 tabeller kørte, én kunne ikke, og grunden var strukturel frem for praktisk. Opgave 2 og 3 er tillidsdelen — og rækkefølgen i planen (3 → 2 → 4) er prisordnet, så de to gratis led var det rigtige sted at bruge tiden når led 1 kræver et ADF-deploy og belaster kildesystemet.

Hele vejen igennem var det styrende krav at en læring skal lande i reglen eller i overrides-tabellen med spor, aldrig som kode i én tabels notebook. Det er også derfor `PRDATO` blev en seed-række og ikke en `withColumn`.

### What worked

At verificere carve-out'en mod tre uafhængige steder i koden frem for ét. Det tredje sted — at delete-detektionen springer mønstret over — var det eneste der faktisk beviste at tabellen er append-only i *drift*; de to første viser kun at indlæsningen skriver append. Havde delete-detektionen kørt på den, havde streamingen været ulovlig uanset hvad skrivemønstret hed.

At lade et grep afgøre spørgsmålet om de afledte kolonner. Det principielle argument ("en beregnet kolonne er ikke en typekonvertering") var rigtigt, men det empiriske — nul konsumenter, og curated har allerede en bedre version — er det der kan fremvises.

Små commits med push efter hver. Fire buildere var døde undervejs i forløbet; jeg mistede ingenting.

### What didn't work

**Planens led 2 er forkert som skrevet, og jeg opdagede det først da jeg læste `lighthouse/write.py` for at bygge den.** Planen pinner raw-siden med `dw_file_name`: raws rækker med et givet filnavn skulle være de rækker filen blev til. Men `generic_upsert_type_2` stager en close og en update **kun** hvor mindst én attribut faktisk afviger (`write.py:842-856`) og en insert kun for nøgler målet ikke har (`:862-866`). En landing-række med uændrede værdier producerer **ingen raw-række overhovedet** og beholder filnavnet fra den kørsel den først ankom i. På en fuld-load-tabel er det normaltilfældet for ca. 99,7 % af snapshottet — et rækketal mod det pinnede filsæt havde meldt hver eneste tabel katastrofalt afvigende.

Jeg byggede den derfor som **indeholdelse** i stedet, hvilket er sandt i kraft af SCD2's konstruktion: hver landing-række skal findes som *en eller anden* rækkeversion i raw. For en fuld-load-tabel gælder den anden vej også, og de to sammen er en tovejs række-for-række-prøve. Afvigelsen er skrevet ind i runbook 17.2 og i notebookens header, så den næste der læser planen ikke tror koden er i uorden.

**Mit første udkast til led 4 blev fældet af en test der allerede lå der.** Jeg lagde de tre transformationsnavne ind i policy-modulet som en dict over "hvilke transformationer ændrer værdien":

```
FAILED lighthouse/tests/enriched_tests/test_enriched_o90_policy.py::
  test_neither_the_policy_module_nor_the_notebook_knows_that_time_is_special[policy]
E   assert 'time_of_day_to_hhmmss' not in '"""Decision..."\n        )'
```

Testen har ret. Viden om hvorvidt en transformation bevarer værdien hører i `enriched_transformations.py` ved siden af medlemmet selv, ikke i policy-modulet — og den blev samtidig bedre placeret: et nyt medlem af det lukkede sæt skal nu tage stilling, ellers rejser opslaget. Begge defaults er forkerte, og det står i koden hvorfor.

**Mit eget review fandt en tavs fejl i idempotensen.** Første udkast skrev både data og auditrækker inde i `foreachBatch` med `txnAppId`/`txnVersion`. Det er rigtigt for data og forkert for auditen: Delta husker det højeste `txnVersion` per `txnAppId` i **måltabellens egen** log, og den log overlever alt undtagen at tabellen droppes. Reparationen dropper enriched-tabellen, så datasiden er dækket — men audittabellen droppes aldrig. Efter en genopbygning havde dens txn-identitet stadig stået på batch 220, genopbygningens batch 0..220 var blevet genkendt som allerede anvendt, og den genopbyggede tabel havde stået helt uden måling. Tavst.

Auditrækkerne samles nu per batch-id i driveren — tildeling, ikke append, så en genkørt batch *erstatter* sin egen måling — og skrives én gang når streamen er terminet.

Samme indsigt afslørede at jeg havde skrevet noget forkert i runbooken: sletter man kun checkpointet og ikke tabellen, får man **ikke** godt tre milliarder rækker. Man får en kørsel der skriver ingenting og melder grønt, fordi `txnVersion` stadig står i loggen. Det er den bedre af de to fejl og stadig en fejl — og det er en anden fejl end den runbooken advarede mod. Rettet i 16.5.

**Et andet review-fund:** en tabel hvor hver eneste risikokolonne bar en konverterende transformation ville i led 4 melde `ok` uden at en eneste værdi var sammenlignet. Den melder nu `skipped`, hvilket er hele grunden til at en skipped-række overhovedet skrives ud.

**Og så det værste fund, som jeg ikke selv så — to gange.** Jeg sendte min egen diff til et uafhængigt review, og det fandt at led 2's indeholdelses-join ikke var null-sikkert:

```python
absent_in_raw = landing_aligned.join(raw_versions, compared_keys, "left_anti").count()
```

`join(other, ["a","b"], ...)`-formen kompilerer til `EqualTo`, ikke `EqualNullSafe`. `NULL = NULL` er unknown, så en landing-række med NULL i én eneste sammenlignet kolonne matcher aldrig sin identiske tvilling i raw og tælles som fraværende.

Det havde ikke været et kanttilfælde. Tjekket **fremstiller selv** NULL-værdier lige inden: hver blank-paddet DB2 `CHARACTER`-kolonne går gennem `NULLIF(..., '')` i min egen alignment, og O90 er fuld af dem. En korrekt tabel havde meldt afvigelse på næsten hver eneste række — altså præcis den "råber ulv"-fejl jeg selv havde skrevet en header om at undgå, indført af mig, i den samme fil.

Kodebasen kendte i forvejen forskellen: `verify_enriched_o90.py:264` bruger `eqNullSafe` for netop denne slags værdisammenligning, og kommentaren på `:248` forklarer hvorfor *nøgle*-joinet bevidst ikke gør. Jeg havde læst begge dele tidligere samme dag. Rettet med en håndbygget betingelse over aliasede frames; nøgle-joinet beholder almindelig lighed, med begrundelsen skrevet ind.

Reviewet fandt yderligere fem mindre ting, hvoraf de to der betød noget var at `derive_enriched_df`s påstand om at være den eneste udledning var blevet falsk da auditen flyttede ud af `foreachBatch` (`write_batch` havde fået sin egen kopi), og at en tom kørsel overskrev `dw_processing_date` i kontroltabellen, som betyder "den kørsel der sidst *rykkede* tabellen frem".

### What I learned

`generic_upsert_type_2`'s opførsel for en *uændret* kilderække er ikke intuitiv og er ikke dokumenteret noget sted: den producerer hverken close, update eller insert. Konsekvensen — at `dw_file_name` i raw peger på den kørsel rækken *først* ankom i, ikke den seneste der leverede den — er den slags detalje der får en ellers rigtig kontrol til at melde falsk alarm på 70 tabeller.

Delta's `txnAppId`/`txnVersion` beskytter mod mere end batch-retries: de gør også "jeg glemte at droppe tabellen" til en tavs no-op i stedet for en duplikering. Det er en bedre fejl, men den ser ud som en succes, og det skal en runbook sige.

At en invariant-test kan fange et *design*valg og ikke bare en regression. Testen der forbyder policy-modulet at kende til TIME var skrevet mod en helt anden bekymring og fangede alligevel at jeg var ved at lægge domæneviden det forkerte sted.

At mit eget review ikke er nok. Jeg læste diffen igennem og fandt to reelle fejl — og gik alligevel to gange forbi en tredje der havde gjort hele led 2 ubrugelig. Den var ikke skjult: `verify_enriched_o90.py` i samme mappe har `eqNullSafe` og en kommentar om hvorfor. Det der gjorde den usynlig for mig var at jeg havde skrevet begrundelsen for null-håndteringen ét sted (alignment-udtrykkene) og derfor følte spørgsmålet afklaret da jeg nåede til joinet. Et sæt friske øjne på diffen fandt den på under tre minutter. Det er argumentet for at gøre det til rutine og ikke til noget man gør når man er i tvivl — for i tvivl var jeg ikke.

### What was tricky

At afgøre hvilke aggregater der overhovedet *må* sammenlignes i led 4. Planen siger "SUM, MIN, MAX efter måltype", men et aggregat er kun bevis hvis det **forventes** at være ens — og UTC-blokken flytter hver eneste værdi med offsettet med vilje, så `MIN`/`MAX` på en UTC-korrigeret kolonne ville melde en korrekt tabel rød. En kontrol der råber ulv bliver slukket, så udvalget måtte gøres til en per-kolonne-beslutning ("hvad gjorde loaden ved værdien") frem for en per-type-tabel.

Rensningsreglen er forskellig i de to led, og forskellen er ikke et sjuskefejl: led 2 bruger `RTRIM` (planens regel — foranstillet whitespace kan være data, og ingen af siderne er renset af noget), led 4 bruger loadens eget `plan.clean_expression` med `TRIM`, fordi enriched-siden allerede *er* renset af loaden og de to skal gøres identiske. Begge steder står begrundelsen i koden.

Kodning og linjeskift. Runbooken er UTF-8 med CRLF, og en heredoc-baseret append fejlede (`unexpected EOF while looking for matching '`) — jeg endte med at skrive sektionerne til scratchpad og appende dem med et lille Python-script der konverterer til CRLF. Blobbene er `i/lf` overalt, verificeret med `git ls-files --eol`, og arbejdstræet er CRLF.

### What warrants review

Alle tre notebooks er **ukørte**. Beslutningslogikken bagved er dækket af 280 grønne enhedstests i `lighthouse/tests/enriched_tests/`, men joins, aggregater, `bit_xor(xxhash64())` mod rigtige parquet-filer, `TRY_CAST` ind i raws frosne typer, `txnAppId`-idempotensen og `maxBytesPerTrigger`-opdelingen på 50 GB er kun læst, ikke set køre.

Det tungeste enkeltpunkt er **prisen på led 2's indeholdelses-join**: en shuffle af landing mod hele raw på samtlige fælles kolonner. Gratis i den forstand at det ikke rører kildesystemet, ikke gratis i cluster-tid. Runbook 17.4 siger kør i etaper og tag de store til sidst, men tallet er ukendt til den første kørsel er gjort.

Og et åbent spørgsmål jeg ikke kunne lukke: `PRDATO`-override'n forudsætter at kolonnen faktisk bærer `yyyyMMdd`. Det er sandsynliggjort af den gamle transform og af to curated-konsumenter, men ikke målt mod data. Runbook 16.2(d) har forespørgslen, og den skal køres **før** første kørsel, fordi sentineltallet er det forventede `lost_count`.

`lighthouse/` uden for `lighthouse/tests/` er urørt — `git diff origin/main..HEAD -- lighthouse/ ':(exclude)lighthouse/tests/'` er tom.

### Future work

Led 1 (DB2 → landing) er ikke bygget. Den kræver en ny ADF-pipeline og er det eneste led der belaster kildesystemet; planens afsnit står uændret.

Workflow-yml til de to nye verifikations-notebooks og til den append-only tabel. Orkestrering bygges til sidst, efter stående aftale.

Per-kolonne-diagnosen i led 2 virker kun for fuld-load-tabeller, hvor de to sider er samme rækkesæt. For en inkrementel tabel giver indeholdelsen rækkeniveau-beviset, men ikke en pegepind på *hvilken* kolonne. Det kan bygges, men kræver et join per kolonne og blev fravalgt.

## Step 3: Nøglekolonner ændres aldrig — og et seed-script der aldrig kunne køre

**Author:** builder

### Prompt Context

**Verbatim prompt (saniteret):** "Repo: C:\claudes_folder\repos\DLBR-DataEstate2026 (SEGES customer repo; Benny explicitly instructed this). Branch feature/o90-enriched-v2, at 4d372ad (pushed). [...] NEW RULE decided by Benny: key columns are never changed in enriched v2. A column that is part of the declared key [...] keeps raw's value AND the rule-derived base type. No override (no TargetTypeName change, no TransformationName) may apply to a key column. [...] METODETIDERALLE was just stopped because its PRDATO override (decimal -> date) applied to a key column [...] Tasks: 1. Seed script [...] remove the METODETIDERALLE.PRDATO row and the KISOPL.<date column> row. Add a guard step [...] THROWs with the offending table.column list [...] 2. View [...] an override on a key column must not take effect [...] 3. Python guard [...] 4. Runbook [...] Add at the very top of the runbook a SHORT section 'Næste kørsler i rækkefølge' [...] Also record [...] the old hand-written enriched transforms used different keys than meta [...] This is an open question for Benny. Git: author `<navn> <mail>` [...] Commit and push [...] no force."

**Interpretation:** Den tredje nøgle-guard fra runbook 12.10 skal lukkes for overrides i alle tre lag der bærer typereglen: seed-scriptet (første linje), viewet (forsvar i dybden) og notebookene (når et gammelt view møder en ny notebook). Dertil runbook-oprydning og en ren registrering af nøgleforskelle, uden at afgøre dem.

**Inferred intent:** Benny skal kunne genoptage METODETIDERALLE og genopbygningen af dato-tabellerne uden at samme fejlklasse kan komme igen ad nogen vej, og han skal have ét indgangspunkt i en runbook han selv finder uoverskuelig.

### What I did

To commits på `feature/o90-enriched-v2`, pushet: `c452a37` (selve reglen i seed, view, policy, notebooks, tests, runbook) og `383e160` (commit-hashen skrevet ind i runbook 12.10, som ikke kan kende sin egen hash i samme commit).

Nøglekilden fandt jeg i viewet frem for at tage planens ord for den: `RuleBase` læser `utility.ExtractInformationSchema.KeySequenceNumber` direkte, og `SourceObjectDefinitions.pk_cols` læser samme kolonne gennem `ExtractInformationSchemaDefinitions`. Seed-guarden (STEP 1b) læser tabellen selv og ikke viewets output, fordi viewet beskærer kolonner og `pk_cols` ikke gør — en beskåret nøgle er stadig en nøgle. Testen er `ISNULL(KeySequenceNumber, 0) <> 0`, det præcise komplement af viewets eksisterende ikke-nøgle-test. STEP 2 sletter, inde i transaktionen og før upserten, enhver override på en nøgle for forbindelsen; 3a fik en `UNION ALL`-gren der viser en nøgle-override som alligevel står, så kontrakten om præcis tre resultatsæt holder.

I viewet blev det én betingelse i override-joinets `ON`: `AND ISNULL(RuleBase.KeySequenceNumber, 0) = 0`. Så falder `TargetTypeName`, `TransformationName`, `IsOverriddenFlag` og `UtcCorrectionFlag` tilbage til reglen på én gang. Note 8 i headeren forklarer det.

I Python fik `ColumnPlan` to nye felter, `base_target_type_name` og `base_transformation_name`, og `policy.validate_keys_are_unchanged` er en søskende til `validate_keys_are_uncleaned`. Den afviser tre ting på en nøgle: anden måltype end basis (case og mellemrum ignoreret), anden transformation end basis, og `IsOverriddenFlag = 1` — det sidste fordi en override på en nøgle, også en der gentager reglen, kun kan komme fra et view der er ældre end note 8. Kaldet står i begge notebooks lige efter den gamle guard.

Runbooken fik "Næste kørsler i rækkefølge" øverst (14 nummererede linjer med afsnitshenvisning), et nyt trin 4 i 16.5 der rydder halve auditrækker (tabelnavn og kolonner læst fra `CAST_NULL_AUDIT_TABLE_NAME`/`CAST_NULL_AUDIT_COLUMNS`), 12.10 med lukningen og to bekræftelsesforespørgsler, en ny 12.11 med de gamle transforms' nøgler mod meta-nøglerne, og 16.2/16.4/19 omskrevet til 16 dato-overrides og `int` på de to nøglekolonner.

Tests: `python -m pytest --noconftest -q -p no:cacheprovider --continue-on-collection-errors` gik fra 371 passed / 18 errors til **388 passed / 18 errors** (de 18 er de uændrede pyspark-importfejl).

### Why

En nøgle der skifter værdi eller type bryder to ting samtidig: `create_table` lægger `NOT NULL` på nøglen, og konverteringen giver NULL for `0`; og afstemningen joiner raw mod enriched på nøglen med ren lighed. Rensning var allerede blokeret af samme grund. Tre lag fordi de deployes hver for sig — seed køres manuelt, viewet med DACPAC, notebookene fra Git-mappen — og et af dem vil altid være bagud på et tidspunkt.

### What worked

Den lokale SQL Server. `sqllocaldb info` viste `MSSQLLocalDB`, og jeg byggede en engangsdatabase `o90_seed_harness` med de rigtige DDL'er for `ExtractInformationSchema` og `EnrichedColumnTypeOverrides`, minimale stubtabeller for de fire meta-tabeller viewene læser, og **de rigtige view-filer** deployet med `sqlcmd -i`. Det gav rød/grøn på viewet: HEAD-versionen gav `TargetTypeName = date, IsOverriddenFlag = 1` for begge nøglekolonner, den nye `int, 0`. Seed-scriptet i fire kørsler: 2 slettet / 17 indsat; genkørsel 0/0/0; payload med nøglerækker injiceret gav `Msg 50001 ... Aborted: the payload overrides key column(s) <skema>.METODETIDERALLE.<datokolonne> (KeySequenceNumber <n>), <skema>.KISOPL.<datokolonne> (KeySequenceNumber <n>)` med rækkeantallet uændret på 17; og en håndskrevet nøgle-override viste sig i 3a og blev slettet ved næste kørsel. Databasen blev droppet bagefter. Hverken meta-DB'en eller Databricks er rørt.

### What didn't work

Første kørsel af seed-scriptet i harnesset fejlede, og ikke på grund af min ændring:

```
sqlcmd -S "(localdb)\MSSQLLocalDB" -E -I -d o90_seed_harness -i seed_o90_enriched_type_overrides.sql
Msg 113, Level 15, State 1, ... Line 689
Missing end comment mark '*/'.
```

HEAD-versionen (`4d372ad`) gav samme fejl på linje 592. Årsagen stod i en kommentar leaden/builderen skrev i forrige commit: `a grep over 02_enriched/o90/*.py`. T-SQL-blokkommentarer nester, så `/*` i stien åbnede et andet niveau som blokkens egen `*/` kun lukkede. **17-rækkers-versionen af scriptet kunne altså aldrig parses** — dev-meta har kun SYSNR og PRDATO fra `65c1afd`. Rettet til `the .py files in 02_enriched/o90`, og en ny test (`test_seed_script_has_no_comment_opener_inside_a_comment`) er bekræftet rød mod HEAD-filen og grøn nu. Den eksisterende T-SQL-tokenizer i testene læser kommentarer fladt og kunne ikke se det.

Mindre ting: `sqlcmd` fra Git Bash svarede `Sqlcmd: The -E and the -U/-P options are mutually exclusive.` (miljøvariabler fra profilen), så harnesset kørte fra PowerShell. En heredoc med et Python-script til runbook-erstatningerne gav `unexpected EOF while looking for matching '` — scriptet blev skrevet til scratchpad og kørt derfra, samme løsning som i step 2. Og `Edit`-lignende replace på `ColumnPlan` fejlede først på `assert s.count(old)==1`, fordi `AuditRow` har de samme tre feltlinjer; ankeret måtte udvides med `data_type_name`.

Et selvfundet fejlskrift i 12.11: jeg skrev først at den gamle vej "skrev de fleste tabeller med `write.overwrite`". Et grep viste 35 med overwrite og 36 med upsert, og teksten blev rettet før commit.

### What I learned

T-SQL-kommentarer nester. En glob i en sti i en kommentar er nok til at gøre et helt script uparsbart, og ingen tekstbaseret test fanger det uden at modellere nestingen.

En lokal SQL Server med de rigtige view-filer og stubtabeller er billig og giver en reel verifikation af SQL-logik uden at røre kundens miljø. Den burde have været brugt ved forrige seed-ændring.

### What was tricky

Meta-nøglerne for de 70 tabeller står ikke i repoet. For 12.11 kunne jeg kun afgøre fire fra repoets egne filer (ESTED, KKONTI, MLKONTO, SYSNR-ikke-IDX); resten kom fra Bennys egne migreringsnoter uden for repoet, som leaden selv pegede på. De er markeret med kilde **U** og en forespørgsel mod `meta.IngestDefinitions` der erstatter dem. 48 tabeller med gammel nøgle `IDX` står som ikke afgørbare.

METODETIDER.PRDATO: den gamle transform har PRDATO i nøglen, noterne siger meta-nøglen er `SYNC_ID`. Rækken blev i payloaden, og runbooken siger at seed-guarden afgør det ved seed.

Hvad ignoreres, skal ignoreres helt: ved at lægge nøglebetingelsen i join'et bliver `UtcCorrectionFlag` for en TIMESTAMP-nøgle med en ignoreret override nu hvad reglen alene giver. Det er konsekvent, men det er en adfærdsændring og står i note 8.

### What warrants review

At `THROW` i STEP 1b og `DELETE` i STEP 2 opfører sig ens mod dev-meta som mod harnesset. Harnesset havde de rigtige DDL'er og views, men kun 24 katalogrækker. Kør trin 7–8 i "Næste kørsler" og læs PRINT-linjerne: forventet `deleted 1`, `inserted 16`.

`validate_keys_are_unchanged` fælder også en override der blot gentager reglen på en nøgle. Det er bevidst strammere end opgaven; spørg Benny hvis det skulle ramme en grøn tabel.

Tabellen i runbook 12.11 bygger for de fleste rækker på noter uden for repoet.

`git diff origin/main -- lighthouse ':!lighthouse/tests'` er 0 linjer.

### Future work

Gæld til overgangs-branchen: `METODETIDERALLE.PRDATO` og datokolonnen i nøglen på `KISOPL` forbliver `int` i o90_v2, og curated der læser dem som dato (`fact_metodetideralle.py:75`, `transform_fact_automatikker.py:222`, `transform_fact_ejerform.py:65,92`, `dim_personoplysninger.py:230`, `fact_interessentskab .py:57`) skal selv konvertere den dag de peges om.

Benny skal afgøre spørgsmålet i 12.11 om gamle nøgler mod meta-nøgler; forespørgslen står der.
