# Diary: Portering af fire o90-tabeller fra gammel platforms raw til eget raw-lag

Fire o90-tabeller (MLKONTO, POSTEXT, METODETIDER, METODETIDERALLE) skal flyttes fra den gamle platforms raw-lag, som vi læser gennem Delta Share, ind i DLBR-DataEstate2026's eget raw-lag. De er de sidste fire efter en runde hvor 22 andre tabeller blev flyttet.

Pointen med porteringen er ikke at skrive i raw-tabellen. Den er at lægge en fil i landing der ser ud præcis som en førstegangs full load fra ADF, og så lade platformens egen loader bygge tabellen. Så møder næste ADF-kørsel en tabel loaderen selv har lavet: nøgler fra meta, `_checkpoints` og `_schemas` etableret, write pattern anvendt som metaen foreskriver.

Alle fire skal blive på `IsBackfillCompleted = 0`. Vippes det til 1, skifter kilden til kildens SYNC_META med begrænset retention, og så starter et ur som forrige runde brugte to dage på at slippe ud af.

## Step 1: Grundlag, kildelæsning og designafklaring

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Byg en Databricks-notebook plus runbook der porterer fire o90-tabeller fra gammel platforms raw (Delta Share) ind i DLBR-DataEstate2026's eget raw-lag. Designet er FÆRDIGT — det står nedenfor. Din opgave er at få det bygget og verificeret, ikke at gentænke det." Briefen indeholdt tabeloversigt med SourceObjectID, skema, spor, write pattern, nøgler og filtre, et afsnit "Verificeret grundlag (genudled det ikke)", en femtrins fremgangsmåde, en liste over ting jeg selv skulle afgøre, og ét punkt markeret "En ting du skal undersøge, ikke antage": hvor `dw_key_columns` kommer fra.

**Interpretation:** Designet ligger fast og skal ikke genåbnes. Jeg skal finde ud af hvor `dw_key_columns` skrives, træffe de udestående implementeringsvalg (placering, parametrisering, stiudledning, idempotens, verifikation), og sætte en builder på at bygge notebook og runbook.

**Inferred intent:** At undgå at porteringen efterlader en tabel der afviger fra det ADF leverer bagefter. Den eksplicitte `dw_key_columns`-opgave er ikke nysgerrighed — det er en mistanke om at en usporet kolonne kan vælte første inkrementelle kørsel.

### What I did

Jeg læste loaderen `solutions/databricks/01_raw/load_to_raw_general.py` og fandt at landing-stien bygges som `f"{config.landing_location}/{source_path}"`, hvor `source_path` kommer fra metaens `extra_fields`. Det bekræfter at stien skal læses fra meta og ikke hardkodes, og at AutoLoader læser rekursivt ned gennem de daterede undermapper.

Så fulgte jeg kolonnerne. `lighthouse/config/base_configuration.yml` definerer platformens egne tekniske kolonner: `dw_created_date`, `dw_modified_date`, `dw_is_deleted`, `dw_valid_from`, `dw_valid_to`, `dw_is_current`, `dw_processing_date`, `dw_file_name`. Den gamle platforms raw bruger andre navne — `dw_valid_from_date`, `dw_valid_to_date`, `dw_is_deleted_in_source`, plus `hash`. Navnene overlapper kun delvist, hvilket er hele grunden til at de gamle tekniske kolonner skal droppes frem for at bæres med.

Meta-databasen var utilgængelig hele sessionen, så jeg læste skemaerne gennem Unity Catalogs REST-API i stedet, som ikke kræver compute. Det viste sig at være mere oplysende end en skemaliste normalt er. I den nye raw (raw-kataloget i dev, tabel `o90.dapostext`) ligger tabellen med `dw_created_date`, `dw_key_columns` og `_rescued_data` på position 36-38 — altså *før* `dw_file_name` på position 39. Rækkefølgen afslører oprindelsen: de tre står før de kolonner lighthouse selv tilføjer, fordi de allerede lå i filen da AutoLoader læste den.

Det pegede på ADF, og der lå de. `solutions/data_factory/pipeline/Extract DB2 Single Object.json:234-246` har en `additionalColumns`-blok på Copy Activity med `dw_created_date` sat til `@utcNow()` og `dw_key_columns` sat til `@activity('Get Object Meta Data').output.firstRow.KeyColumns`. Formatet bygges i `solutions/sql_database/meta/Views/SourceObjectDefinitions.sql` som citerede kolonnenavne aggregeret og pakket i kantparenteser — altså `["IDX"]`, ikke `IDX`, og ikke den strippede `keys`-variant fra `IngestDefinitions`-viewet, som fjerner både anførselstegn og parenteser.

Dernæst SCD2-sammenligningen. `lighthouse/write.py:584-596` udleder attributterne som "alle kolonner i måltabellen minus en eksplicit exclude-liste". Exclude-listen indeholder `dw_created_date`, `dw_modified_date`, `dw_is_deleted`, `dw_valid_from`, `dw_valid_to`, `dw_is_current`, `dw_file_name` og `dw_processing_date`. Den indeholder ikke `dw_key_columns`.

Jeg lagde valget frem for Benny som to veje: droppe alt `dw_*` som designet sagde, eller spejle ADF nøjagtigt. Han valgte at spejle, og skærpede princippet til at parquetten skal indeholde præcis det en førstegangs full load fra ADF ville lægge i landing — hverken mere eller mindre.

Han rettede samtidig et forslag jeg havde stillet. Jeg foreslog at bære gammel raws `dw_created_date` med, fordi den allerede er en streng og dermed typemæssigt passer. Det er forkert, og han begrundede det med at kolonnen er `SequenceOrderByColumn` i metaen. Jeg verificerede begrundelsen i koden frem for at tage den på ordet: `lighthouse/write.py:888-895` sætter `dw_valid_from = col(sequence_column)` når der er en sequence-kolonne. Bæres gammel platforms værdier med, arver hver porteret række et `dw_valid_from` fra dengang *de* hentede rækken. Det er historik ad bagvejen, stik imod beslutningen om at historikken starter forfra.

Til sidst verificerede jeg de fire kildeskemaer gennem samme REST-vej. Forretningskolonnerne tæller 35, 34, 7 og 10, hvilket stemmer med briefens tal.

### Why

Briefen bad eksplicit om ikke at genudlede det verificerede grundlag, og det holdt jeg mig til: kolonnesæt og datatyper genkontrollerede jeg ikke. Men den bad lige så eksplicit om at *undersøge* `dw_key_columns` frem for at antage, og den undersøgelse kunne ikke stoppe ved "findes ikke i repoets skrivevej". Den observation var allerede gjort i briefen. Værdien lå i at finde ud af hvad der så skriver den, og svaret lå uden for Databricks.

### What worked

Unity Catalogs REST-API som erstatning for compute. Da meta-databasen faldt ud, var kolonne*rækkefølgen* i en eksisterende måltabel det der pegede på ADF — en ren skemalæsning uden en eneste kørt query. Det er en billigere diagnostik end at starte en klynge.

At læse `write.py` selv frem for at stole på et referat. En søgeagent rapporterede exclude-listen uden `dw_file_name` og `dw_processing_date`. Havde jeg taget det for gode varer, ville jeg have konkluderet at `dw_file_name` er en SCD2-attribut, og dermed at hver ADF-levering versionerer hver række, fordi filnavnet skifter hver gang. Det ville have været en opsigtsvækkende og helt forkert konklusion om et system der kører i produktion.

### What didn't work

Meta-databasen var utilgængelig hele sessionen. Første forsøg gav:

```
Exception calling "Open" with "0" argument(s): "Cannot open server '<sql-server-dev>'
requested by the login. Client with IP address '<klient-IP>' is not allowed to access the
server."
```

Firewallen tillod ikke den IP jeg kom fra. Jeg gættede ikke på indholdet af `meta.SourceObjectDefinitions.KeyColumns` eller `SequenceOrderByColumn`, men lod i stedet notebooken læse begge fra meta ved kørsel og fejle højlydt hvis `SequenceOrderByColumn` ikke er `dw_created_date`. Det gør leverancen selvverificerende frem for afhængig af et opslag jeg ikke kunne foretage.

Worktreet forsvandt midt i arbejdet ved et døgnskifte og blev gendannet under et nyt navn. Stien `.claude/worktrees/agent-a5faed54e5171db31` blev til `agent-a1211670421e919c3`, og en kommando fejlede med `cd: ... No such file or directory`. Samme branch og indhold, så intet arbejde gik tabt, men absolutte stier fra før skiftet er døde.

### What I learned

Kolonnerækkefølgen i en Delta-tabel er et spor om hvor kolonnerne kom fra. Alt før `dw_file_name` lå i filen; alt fra `dw_file_name` og frem blev tilføjet af lighthouse. Det gjorde det muligt at skelne ADF's bidrag fra platformens uden at læse en eneste række data.

Der findes to forskellige repræsentationer af nøglekolonnerne i metaen, og de ser ens nok ud til at kunne forveksles. `SourceObjectDefinitions.KeyColumns` giver `["IDX"]`, mens `IngestDefinitions.keys` stripper anførselstegn og parenteser væk til `IDX`. ADF skriver den første ind i `dw_key_columns`. Vælger man den anden, får hver porteret række en værdi der afviger fra alt hvad ADF leverer bagefter — og eftersom kolonnen er en SCD2-attribut, koster det en falsk version på hver eneste række.

### What was tricky

Fælden er tavs i begge ender. `dw_key_columns` optræder ikke i repoets skrivevej, så en kodesøgning finder intet, og en portering der dropper den fejler ikke — den lykkes, og regningen forfalder først ved første inkrementelle kørsel, hvor hele det porterede datasæt lukkes og genåbnes. På POSTEXT er det hele det porterede datasæt.

`dw_created_date` er den samme fælde spejlvendt. Kolonnen står på SCD2-exclude-listen, hvilket ser ud som om dens værdi er ligegyldig. Det er den ikke, for den er samtidig sequence-kolonne og styrer `dw_valid_from`. En kolonne kan altså være irrelevant for versionsdetektionen og alligevel afgøre hvad tidsstemplet på versionen bliver.

### What warrants review

`lighthouse/write.py:584-596` og `888-895` er de to steder der bærer hele designet. Den første afgør hvilke kolonner der overhovedet må afvige mellem en porteret række og en ADF-leveret; den anden afgør hvad `dw_valid_from` bliver sat til.

Formatet på `dw_created_date` skal verificeres mod faktiske værdier i en eksisterende raw-tabel, ikke gættes. Kolonnen er en streng der implicit castes til timestamp, så et afvigende format bider først downstream.

### Future work

`source_path` udledes to steder som ikke er garanteret at give det samme. ADF's sink-dataset bygger mappen som `tolower(ConnectionName)/TableName`, mens `IngestDefinitions`-viewet bygger `source_path` som `DefaultRootFolder` hvis den er sat, ellers `LOWER(ConnectionName)`, plus tabelnavnet. Er `DefaultRootFolder` sat på et objekt, peger ADF og loaderen på hver sin mappe. Det gælder alle tabeller, ikke kun de fire, og er ikke opstået med denne opgave.
