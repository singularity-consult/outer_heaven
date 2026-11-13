# Diary: O90-69573, Flux gennem de generiske SqlServer-pipelines i ADF

Kundeopgave (SEGES, DLBR-DataEstate2026). De seks generiske SqlServer-extract- og InformationSchema-pipelines skulle læse fra Flux (Azure SQL) via den nye linked service `ls_asql_flux` i stedet for den connection-string-baserede `SqlServerDynamic`, med uændret meta-flow. Ingen lead-dagbog fandtes for opgaven ved handback, så builder oprettede denne fil.

## Step 1: Dataset, kildeskift, Fail If Empty og InformationSchema-rettelser

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** Opgave (Jira O90-69573, SEGES-kunderepo DLBR-DataEstate2026): Tilpas de eksisterende generiske SQL Server-pipelines i ADF, så de kan indlæse fra Flux (Azure SQL) via linked service `ls_asql_flux`, mens meta-DB'en bruges på samme måde som i dag. (Fuld kravliste fra lead: nyt AzureSqlTable-dataset, AzureSqlSource, Fail If Empty i begge controllere, defaults fra SEGESDW/NAV til Flux, rør ikke triggere/Deploy.ps1/SqlServerDynamic/DB2, validér offline, commit lokalt uden push.)
**Interpretation:** Kildesiden af seks pipelines skal pege på ét fast Flux-dataset; meta-opslag, watermark og ingest-log uændret; tom metadata skal fejle synligt.
**Inferred intent:** Få Flux ind i landing med den eksisterende auto-extracter-maskine uden at bygge nye pipelines.

### What I did
`git pull --ff-only` på `feature/o90-69571-flux-linked-service` (fast-forward til ADF Studio-gemningen af `ls_asql_flux.json`). Skrev et Python-transformscript i scratchpad, der indlæser og gemmer ADF-JSON i Studio-format (tab-indent, CRLF, ingen afsluttende newline; round-trip var byte-identisk før ændring). Scriptet:
- oprettede `dataset/ds_asql_flux.json` (AzureSqlTable på `ls_asql_flux`, parametre SchemaName/TableName),
- skiftede `SQLServer_DynamicDataset` til `ds_asql_flux` og SqlSource/SqlServerSource til AzureSqlSource i Object, Keys og InformationSchema Object,
- indsatte `If Is Empty` (IfCondition på `output.count`) med `Fail If Empty` (errorCode 404) mellem lookup og ForEach i begge Extract-controllere og i InformationSchema-controlleren, plus `SP Update Log Failed_2` på If'ens Failed-gren i Extract-controllerne,
- ændrede ConnectionType-filteret i InformationSchema-pipelinerne fra `SqlServer` til `AzureSqlDatabase`, ConnectionName-default til `FLUX`, fjernede NAV/SEGESDW-test-tabelnavne som TableName-default,
- strammede KEY_COLUMN_USAGE-joinet i INFORMATION_SCHEMA-forespørgslen (schema/tabel med i join).
Commit `bd393404` med author Benny Christiansen.

### Why
Dataset uden ConnectionName-parameter, fordi linked servicen er fast; ConnectionName lever videre i pipelines til meta, log og landing-sti. ConnectionType-filteret skulle snævres ind, fordi alle SqlServer-rækker i meta ellers ville blive læst fra Flux' server og skrevet under forkert SourceConnectionID.

### What worked
Byte-identisk round-trip gjorde diffen ren. Et offline checker-script (parse, referenceName, dataset- og childpipeline-parametre, dependsOn-scope, `activity('X')`-referencer, AzureSqlSource på AzureSqlTable) gav "OK" for de seks pipelines.

### What didn't work
Første kørsel flyttede lookup'en først i InformationSchema-controlleren for læsbarhed; diffen voksede til 99 linjer. Rullede tilbage med `git checkout -- solutions/data_factory/pipeline` og kørte uden flytningen (35 linjer). Checker-scriptet melder på hele factory'en `Execute Generate Pipeline Path omits required ObjectName for Generate Pipeline Path` i DB2-pipelines; det er eksisterende og uden for scope, og checkeren er strengere end ADF på dette punkt.

### What I learned
`GetExtractObjectsSqlServer` accepterede allerede AzureSqlDatabase, men InformationSchema-pipelinerne havde hårdkodet `ConnectionType = 'SqlServer'` begge steder; uden rettelsen ville Flux aldrig få kolonner i `utility.ExtractInformationSchema`, og proc'ens INNER JOIN ville give tomt resultat. Konventionen i meta er systemnavn med versaler (O90) og teknologi i ConnectionType.

### What was tricky
At få Failed i UpdateIngestLog: dependsOn med flere betingelser er AND, så en eksisterende log-aktivitet kunne ikke genbruges; det krævede en ny aktivitet på If'ens Failed-gren. Pipeline-status bliver Failed efter ADF's leaf-regel (skippet ForEach evalueres via fejlet forælder), men det er ræsonneret, ikke set.

### What warrants review
Kørsel i dev: InformationSchema Controller SqlServer, derefter Extract SqlServer Controller med ConnectionName FLUX; tjek at service principal ser tabeller i INFORMATION_SCHEMA, at watermark-forespørgslen virker, og at Fail If Empty giver Failed i ingest-loggen. Meta-rækken for Flux findes ikke i repoet; navnet FLUX er valgt, ikke afledt.

### Future work
Seed af meta.SourceConnections/SourceObjects for Flux. Eventuelt guard i InformationSchema Object for manuel kørsel med forkert navn (tom firstRow giver kryptisk fejl).

## Step 2: Meta-seed-scripts for Flux (O90-69572)

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** Opgave (Jira O90-69572, SEGES DLBR-DataEstate2026): Skriv T-SQL-seed-scripts, som Benny selv kører manuelt mod meta-DB'en i dev, så forbindelsen FLUX kan indlæses af de generiske SQL Server-pipelines. Du kører INTET mod nogen database. (Fuld opgavetekst med tabelliste, fire kendte huller og leverancekrav er givet af lead.)
**Interpretation:** Fire scripts i command-deck (privat, ikke commit): forbindelse, sikre objekter, objekter der venter på beslutning, verifikation. Hullerne skal afklares i koden og have forslag, ikke implementeres.
**Inferred intent:** Kunne køre Flux-udtræk i dev nu for de tabeller, der er sikre, uden risiko for at passwords forlader kilden, og give Benny et beslutningsgrundlag for resten.

### What I did
Læste meta-tabellerne, `meta.SourceObjectDefinitions`, `utility.ExtractInformationSchemaDefinitions`, `GetExtractObjectsSqlServer`, `GetExtractQueryDB2` (kolonnebeskæring), O90-seed-scriptet som mønster, pipelinerne Extract SQLServer Object/Controller og InformationSchema, `Copy Meta Data.json`, `IngestDefinitions` og raw-delete-detection (`choose_track`). Skrev `01_source_connection.sql`, `02_source_objects.sql` (13 tabeller), `03_afventer_beslutning.sql` (fire kontakter, alle 0) og `04_verifikation.sql` i `command-deck/seges/flux-bilagsdata/meta-seed/`. Syntaks-tjekket alle fire med ScriptDom `TSql160Parser` (0 fejl), linjelængde (alle <= 60) og ASCII.

### Why
02 indeholder kun tabeller, som den deployede proc kan udtrykke præcist. Alt med password-kolonner eller vindues-logik er isoleret i 03 bag kontakter, så 01+02 kan køres nu.

### What worked
En sqlite-genskabelse af viewets `SourceColumns`-join viste den faktiske semantik: ingen rækker = alle kolonner; en NULL-række plus navne = de navne udelades; kun navne uden NULL = objektet mister alle kolonner. Dermed kan password-kolonner udelades uden proc-ændring, og `SourceColumns` kopieres allerede til test/prod af Copy Meta Data, mens `SourceObjectColumnPruning` ikke gør.

### What didn't work
Intet fejlede i kørslerne. Første tjek af ikke-ASCII med `grep -nP '[^\x00-\x7F]'` gav `grep: -P supports only unibyte and UTF-8 locales`; skiftede til et Python-tjek.

### What I learned
`SourceObjectKeyColumns` bruges kun for objekter helt uden rækker i ExtractInformationSchema, så nøglen kommer reelt fra PK i kilden. Et glidende ExtractSQLFilter på en fuld tabel (IncrementalFlag=0) sender den på full-track i delete-detection, som vil markere alt uden for vinduet som slettet. RollingWindowDays på et dato-watermark giver "kolonne > max - N dage", tættest på kravet uden proc-ændring. Natkørsel med JobIsIncremental=false læser hele tabellen for ALLE incremental-objekter på forbindelsen, også store append-only tabeller.

### What was tricky
Case-følsom sortering kunne få både navne-join og LIKE til at misse en password-kolonne; vagterne bruger derfor LOWER(). O90-seedet nulstiller watermark ved genkørsel; her indsættes baseline kun på nye rækker.

### What warrants review
`04_verifikation.sql` trin 3, 4, 6 og 7 efter InformationSchema-kørslen. INSERT ... EXEC af proc'en (som laver SELECT INTO #temp) er kun parse-tjekket. KeyColumns afhænger af PK i kilden og er ikke set.

### Future work
Beslutning om proc-ændring for kolonneudtryk (Audit) og "Id > max ELLER vindue"; triggere for dag/nat findes ikke endnu; ugentligt nøgleudtræk mod delete-detection skal afstemmes.

## Step: GetExtractObjectsSqlServer udvidet til Flux, DB2 bevist uberørt (O90-69572)

### Prompt Context

**Verbatim prompt:** Opgave (SEGES DLBR-DataEstate2026, O90-69572/69573): Udvid meta-proceduren `GetExtractObjectsSqlServer` til Flux. Benny stiller ét ufravigeligt krav: DB2/Ø90-indlæsningen [...] må IKKE påvirkes. Det skal sikres og dokumenteres FØR noget ændres. (Fuld tekst: tre udvidelser, fase 1 konsekvensanalyse, fase 2 kun hvis alt er additivt og DB2-sikkert.)
**Interpretation:** Pruning (ExcludeOnly), kolonneudtryk og genlæsningsvindue i SqlServer-proc'en, uden at røre et eneste objekt DB2 læser eller skriver.
**Inferred intent:** Kunne seede alle 19 Flux-tabeller uden SourceColumns-særheden og uden at en JSON-kolonne i en audit-tabel lækker passwords, med bevis for at Ø90 er upåvirket.

### What I did
Fase 1: grep af alle læsere/skrivere. `GetExtractObjectsSqlServer` kaldes kun af de fire `Extract SQLServer*`-pipelines; de tre triggere peger på DB2-pipelines. `SourceObjectIncrementalSetup` skrives af DB2-pipelines (Single Object, Watermark Reset, Single Controller), læses af `GetObjectMetadataDB2` og `SourceObjectDefinitions` og kopieres af Copy Meta Data med fast kolonneliste. Derfor blev vinduet en NY tabel `meta.SourceObjectReReadSetup` i stedet for nye kolonner, og udtryk en ny tabel `meta.SourceObjectColumnExpressions`. Ingen eksisterende tabel eller view er ændret.
Fase 2: proc, to tabeller, Build Include, fire nye Copy/Merge-aktiviteter i Copy Meta Data (tekstindsat, eksisterende aktiviteter asserted identiske). Commits 2debf209 og a18ff51e. Nye/omskrevne scripts i command-deck: 03 (kontakter fjernet), 04 (tjek tilpasset), 05_db2_regression.sql, 01 (en kommentar).

### Validation (offline, syntetiske rækker)
- `dotnet build SSMS.sqlproj -c Release -p:NetCoreBuild=true` (uden flaget: MSB4278, SSDT-targets mangler). Gammel og ny: 0 fejl, samme 4 SQL71558-advarsler. Dacpac'en viste at SDK-projektet globber alle .sql (DB2SyncMetaTables og ColumnPruning har ingen Build Include, men er med).
- sqlpackage 170.5.96 i scratchpad. Publish mod LocalDB fejlede først: `Unable to load DLL 'Microsoft.Data.SqlClient.SNI.dll' ... (0x800700CE)` (stien for lang), derefter hang managed SNI over named pipe. Løsning: `/Action:Script` og `/Action:DeployReport` med `/TargetFile:<gammel dacpac>` (offline) og kør scripts med sqlcmd mod en egen LocalDB-instans `fluxreg`. DeployReport med standardindstillinger (som azure/sql-action): Create 2 tabeller + 3 check constraints, Alter 1 proc, ingen Drop, ingen Alerts.
- Gammel vs. ny proc på samme syntetiske data (O90 med Exclude- og IncludeOnly-pruning, SyncMeta, FLUX, en anden SqlServer-forbindelse): binær sammenligning af JSON pr. række for SourceObjectDefinitions, IngestDefinitions, EISD, EnrichedColumnTypeDefinitions, GetObjectMetadataDB2, GetExtractObjectsSqlServer, plus fil-diff af GetExtractQueryDB2-output. Første version gav forskel: STRING_AGG-kolonnerækkefølgen ændrede sig (Email, Name, Id blev til Email, Id, Name), fordi SELECT INTO med LEFT JOIN ændrede temp-tabellens indlæsningsrækkefølge. Omskrevet til de oprindelige `SELECT * INTO` + DELETE/ALTER/UPDATE. Det gav så `Cannot resolve collation conflict for string_agg operation` (tilføjet temp-kolonne får tempdb-collation); rettet med `COLLATE DATABASE_DEFAULT`. Derefter: 144 af 144 rækker identiske, kun modul-hashen for proc'en forskellig.
- Med Flux-rækker i de nye tabeller: DB2-output stadig identisk; kun de berørte FLUX-objekter ændret. Genererede SqlQuery kørt mod en syntetisk Flux-DB: top-level password-nøgler fjernet, ikke-JSON gav NULL, en nøgle under et indlejret objekt blev IKKE fjernet, vinduet fangede nyere rækker med gammelt Id.
- 01-04 kørt mod LocalDB: 03 stopper med 50039 før release, kører rent og idempotent efter. Første version af vagt 7a fejlede fejlagtigt (50032), fordi fulde objekter melder JobIsIncremental = 0 i begge kald; rettet til optælling. Negative tests: fjernet pruning gav 50033, fjernet udtryk gav 50034.
- 05 kørt før/efter med et simuleret vandmærkeskift imellem: første version gav falsk forskel i GetObjectMetadataDB2 (NewWatermarkQuery har vandmærket indbygget); den er nu taget ud af hashen. Derefter kun Modul-totalen forskellig; Modul uden SqlServer-proc'en ens.

### What warrants review
Copy Meta Data fejler (rødt Release Metadata, Prod springes over), hvis den køres før "Release Sql Database" har lavet tabellerne i dev og målmiljøet. De øvrige grene kører stadig. ADF-delen er kun tjekket som SQL mod LocalDB, ikke i ADF. Placering og stavemåde af password-nøglerne i audit-JSON'en, navnet på fremmednøglekolonnen i metadata-tabellen og ydeevnen af den korrelerede underforespørgsel er ikke set mod Flux.
