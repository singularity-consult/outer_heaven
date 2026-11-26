# Diary: midlertidigt job der genbygger curated-fakta mod ny kalenderdimension (DLBR DataEstate)

Kalenderdimensionen i den fælles curated-zone er genopbygget med nye surrogatnøgler. To ubrugte løsninger har fakta, hvis kalender-id'er nu matcher numerisk men peger på forkerte datoer, fordi deres jobs blev slettet før skiftet. Målet er ét midlertidigt, manuelt job, der genbygger fakta med den eksisterende kode, kørt dev, test, prod, og derefter slettet igen.

## Step 1: afklaring og krav (lead)

**Author:** lead

### Prompt Context

**Verbatim prompt:** "lad os lave nogle midlertidige jobs, der kan genkøre dem, med ny cal-dimension"
**Interpretation:** Genskab de slettede integration-jobs midlertidigt, så de berørte curated-fakta kan genbygges mod den nye kalenderdimension.
**Inferred intent:** Få data i Databricks til at holde op med at pege på forkerte datoer, uden at genoplive løsninger som permanent drift.

### What I did
Læste de slettede job-YAML'er fra commit før sletningen, notebooks for de tre løsninger, lighthouse-helperen der slår surrogatnøgler op, nuværende workflows og semantiske modeller samt projektets statusfil. Afgrænsede, hvad der kan genkøres uden kodeændring, og rangerede beslutninger til Benny.

### Why
"Genkør" holder kun, hvis koden stadig kører mod nuværende main. Det skulle afgøres pr. løsning før noget bygges.

### What worked
Fakta skriver datoer som `*_key` og slår `*_id` op mod den aktuelle kalenderdimension ved skrivning, så en ren genkørsel retter id'erne uden kodeændring.

### What didn't work
Read-only tjek i dev kunne ikke køres: `databricks warehouses list -p dev` gav "A new access token could not be retrieved because the refresh token is invalid." Første forsøg på at kæde flere `git show` i én kommando blev afvist af worktree-isoleringen; enkeltkommandoer virkede.

### What I learned
En tredje, center-specifik løsning kan ikke genkøres: den gamle YAML peger på en omdøbt notebook, `fact_bilag` bruger kolonnenavne, som o90-fakta ikke har længere, og den afhænger af en o90-dimension, der fejler på main. De semantiske modeller er import mode og har ikke været refreshet siden jobbene blev slettet, så rapporterne viser gamle men konsistente data; fejlen findes kun i Databricks.

### What was tricky
Den gamle brancheanalyse-YAML indeholdt en task, som nu ejes af et andet job (brugerdatabase), og en reference-task uden kalenderrelation. Begge skal ud for ikke at få to skrivere eller udvide scope.

### What warrants review
At jobbet ikke har schedule i nogen target, og at kun curated-notebooks for automatisk kontering og brancheanalyse er med.

### Future work
Oprydnings-PR der sletter jobfilen efter grøn prod. Den center-specifikke løsning kræver en separat reparation, hvis den nogensinde skal genbygges.

Beslutninger (Benny 26/10): kun Databricks-tabeller, den center-specifikke løsning ude, ingen PBI-refresh, dev -> test -> prod, tab af historik før 2024 i én kildetabel accepteret, ét job `tmp_rebuild_calendar_ids` uden schedule, ingen -2 Åben.

## Step 2: jobfil bygget og valideret (builder)

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** "Opret én ny fil `solutions/databricks/workflows/tmp_rebuild_calendar_ids.yml` med ét job, nøgle og name `tmp_rebuild_calendar_ids`. Formål: manuel, midlertidig genbygning af curated-fakta for automatisk_kontering og brancheanalyse mod den nye `global.dim_calendar` (fakta slår `calendar*_id` op ved skrivning, så genkørsel retter dem). Jobbet slettes igen i en senere PR." (uddrag af leads brief; resten var kravene K1-K3, validering og commit-regler)
**Interpretation:** Én DAB-jobfil efter repoets workflow-konvention, med de 5 automatisk kontering-tasks og 13 brancheanalyse-curated-tasks fra commit før sletningen, prefixet `ak_`/`ba_`, uden schedule, med fejl-mail på jobniveau, valideret med `bundle validate`.
**Inferred intent:** En sikker, ikke-schedulet knap Benny kan trykke på i hvert miljø, som ikke kan starte af sig selv og er nem at slette igen.

### What I did
Skrev jobfilen i leads worktree efter konventionen fra leverandørbilag-jobbet (job_cluster pr. target-variabel, Developers CAN_MANAGE, tags) og tog task-sæt og `depends_on` fra de slettede YAML'er via `git show af4bc621^:...`. Targets sætter kun name og job_clusters. Verificerede at alle 18 notebook-stier findes på disk, og sammenlignede task-grafen maskinelt mod de gamle YAML'er med et lille Python-script (prefix påført, de to udeladte tasks fjernet): 18 mod 18, identisk. Kørte `databricks bundle validate -t dev --profile dev` (CLI v1.21.0): "Validation OK!". Inspicerede det resolvede job via `-o json`: 18 tasks, ingen schedule, email_notifications og tags som forventet. Én commit i kunderepoet med Bennys seges-identitet, ingen trailers.

### Why
Task-grafen er det eneste, der skal være rigtigt for at genkørslen giver korrekte fakta; derfor diff mod kilden i stedet for øjemål. Ingen schedule, fordi jobbet aldrig må køre af sig selv i prod.

### What worked
Den maskinelle diff af `depends_on` bekræftede også leads antagelse: ingen af de 13 curated-tasks afhang af de to udeladte tasks (brugerdatabase-enrichment og kredse). `grep -n schedule` på filen rammer kun kommentaren øverst.

### What didn't work
`databricks bundle validate -t prod --profile dev` fejlede på auth som ventet: "Error: cannot resolve bundle auth configuration: the host in the profile (...) doesn't match the host configured in the bundle (...). The profile "prod" has host=... that matches host in the bundle. To select it, pass "-p prod"". Jeg prøvede ikke `-p prod`, fordi briefen kun tillod prod-validate uden prod-auth. Prod- og test-target er derfor kun valideret strukturelt via dev og ved at targets er identiske bortset fra cluster-variablen.

### What I learned
FinOps-tagget `project` er én værdi pr. job, så et job der genbygger to løsninger kan ikke tagges retvisende for begge. Jeg valgte `project: global`, fordi omkostningen udløses af kalendermigreringen og det samme tag bruges af jobbet der bygger kalenderdimensionen; det holder også tag-værdierne til eksisterende projekter frem for at opfinde en midlertidig værdi.

### What was tricky
Bundle-roden er repo-roden, ikke den indlejrede bundle under resources; kun den ydre inkluderer workflows-mappen. CLI-versionen på PATH er 1.21.0, mens en parallel gren pinner 1.20.0 pga. et uafklaret problem med 1.21.0; validate gik igennem på 1.21.0, men det siger intet om deploy-adfærd.

### What warrants review
Tag-valget (`global` frem for et midlertidigt projektnavn). At fejl-mail ligger på jobniveau og ikke gentages i targets. At jobbet ikke er kørt nogen steder: det er kun valideret, ikke deployet eller eksekveret.

### Future work
Benny deployer via release-workflowet og kører jobbet manuelt dev, test, prod. Oprydnings-PR sletter filen efter grøn prod.
