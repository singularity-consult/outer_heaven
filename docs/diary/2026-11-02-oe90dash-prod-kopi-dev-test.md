# Diary: oe90dash prod-kopi til dev og test (SEGES Data Estate)

Mål: en genkørbar kopi af de 8 tabeller, som Power BI-modellen `okonomiopfolgning` læser, fra prod til dev og test, og alle DASH-jobs i dev og test sat på PAUSED. Prod-schedules røres ikke. Benny har besluttet, at beskyttelsen kun er pause af schedules; manuelle kørsler kan trunkere, og så kopierer vi igen.

## Step 1: Afklaring af kopimekanisme og jobs

**Author:** outer_heaven:lead

### Prompt Context

**Verbatim prompt:** (saniteret) Opgave i SEGES-repoet DLBR-DataEstate2026: (1) Én-gangs-kopi af de 8 tabeller, som Power BI-modellen okonomiopfolgning læser, fra prod til dev og test. (2) Alle DASH-relaterede jobs skal være PAUSED i dev og test. Kopimekanisme skal afklares read-only (kan dev og test læse prod-kataloget?). Foretrukket: DEEP CLONE i en notebook, parametriseret med målmiljø, plus et manuelt job kun i dev- og test-targets. Ejerskab skal ende hos job-SP eller platformens admin-gruppe.
**Interpretation:** Undersøg read-only, om prod-kataloget er synligt fra dev og test, design kopien, find alle unpaused DASH-schedules i dev og test, og få en builder til at lave YAML og notebook.
**Inferred intent:** Power BI-rapporten skal kunne testes i dev og test mod prod-lignende data, uden at natlige test-jobs ødelægger kopien.

### What I did
Læste de fire DASH-workflow-filer og semantic model-partitionerne. Kørte read-only `databricks catalogs get`, `workspace-bindings get-bindings`, `grants get` og `tables list` mod dev, test og prod.

### Why
Kopimekanismen afhænger helt af, om en workspace kan se både kilde- og målkatalog.

### What worked
Partitionerne bekræfter præcis 8 kilder (7 i curated oe90dash, variansanalyse i enriched). Prodform og Økonomi er M-tabeller uden kilde.

### What didn't work
Prod-katalogerne er ikke tilgængelige fra dev eller test: `databricks catalogs get <prod-kataloget for curated> -p dev` gav `Error: Catalog '<prod-kataloget for curated>' is not accessible in current workspace`. Samme fra test. Prod-workspacet kan heller ikke se curated_dev, curated_test eller enriched_test. Den første agent-kørsel hang i 600 s under et af de senere CLI-kald, og worktree'en gik tabt; genoptaget i en ny worktree med `timeout 60` på hvert CLI-kald.

### What I learned
Alle kataloger er ISOLATED og bundet kun til eget workspace via Terraform i iac-repoet (`databricks_workspace_binding` pr. katalog). Alle miljøer deler samme metastore, så Delta Sharing mellem dem er ikke en vej (deling sker til en anden metastore). Bindingerne mellem kataloger og workspaces blev kortlagt. Curated oe90dash-tabellerne ejes af platformens admin-gruppe i alle tre miljøer; variansanalyse ejes af miljøets job-SP.

### What was tricky
DEEP CLONE kræver, at én workspace ser både kilde og mål. Den foretrukne løsning (job i dev og test) virker derfor først, når prod-katalogerne får en READ_ONLY-binding til dev og test og job-SP'erne får SELECT. Det er en beslutning for Benny, ikke noget koden kan løse.

### What warrants review
Om tabeller ejet af platformens admin-gruppe kan erstattes med `CREATE OR REPLACE` af job-SP'en. Gruppens medlemmer var ikke synlige fra workspace-API'et, så det er uverificeret.

### Future work
Beslutning om binding (READ_ONLY prod til dev/test, i IaC eller manuelt og midlertidigt).

## Step 2: Builder leverer pause, notebook og job (PR 203)

**Author:** outer_heaven:lead

### Prompt Context

**Verbatim prompt:** Du hængte i 600 s under read-only-tjekket af catalog bindings, og ingen af dine commits blev gemt. [...] Genoptag fra binding-tjekket. Giv hvert CLI-kald en timeout (fx `timeout 60 databricks ...`). Hvis et kald mod test eller prod hænger eller kræver interaktiv login, så spring det over, notér det som uverificeret, og byg resten (pause-YAML, clone-notebook og manuelt job kun i dev- og test-targets).
**Interpretation:** Byg resten selv om bindings-forudsætningen ikke er på plads, og markér den som åben.
**Inferred intent:** Få koden klar til release, så kun binding-beslutningen står tilbage.

### What I did
Oprettede ny worktree på den eksisterende branch og gav builderen kravene. Builderen satte tre test-schedules til PAUSED (master_oe90_dash, E2E_oe90_dash, UT_oe90_dash_master), tilføjede notebook `solutions/databricks/resources/clone_oe90dash_prod_to_env.py` og job `solutions/databricks/workflows/clone_oe90dash_prod_to_env.yml` kun i dev- og test-targets. Commit 6b2d9a0, PR 203 i kunderepoet. Jeg verificerede author, diff og PR-status bagefter.

### Why
Pause beskytter kopien mod natlige truncates; job uden schedule gør kopien genkørbar.

### What worked
`databricks bundle validate` gav "Validation OK!" for dev og test. Prod-output indeholder intet clone-job, og prod-schedules er stadig UNPAUSED. Timeout på hvert CLI-kald forhindrede ny hængning.

### What didn't work
Intet fejlede i dette step. Selve kopien er ikke kørt, fordi prod-katalogerne ikke er synlige fra dev og test.

### What I learned
Et miljøtjek mod lighthouse-konfigurationen i notebooken forhindrer, at en kørsel rammer et andet miljø end workspacet.

### What was tricky
Ejerskab: CREATE OR REPLACE og SET OWNER på Admin-ejede tabeller kræver at job-SP'en ejer tabellen eller er medlem af Admin-gruppen. Ikke verificeret.

### What warrants review
Ejerreglen i notebooken (Admin eller SP bevares, alt andet bliver Admin) og om grants overlever CREATE OR REPLACE.

### Future work
Binding-beslutning, derefter første kørsel i dev og kontrol af ejer og grants.

## Step 3: variansanalyse udeladt, kun 7 curated-tabeller

**Author:** outer_heaven:lead

### Prompt Context

**Verbatim prompt:** (saniteret) Ret PR #203: tag variansanalyse ud af kopien. Benny har besluttet, at enriched_<env>.oe90dash.variansanalyse ikke skal kopieres; dev og test bruger deres egne. Det er en referencetabel med under hundrede rækker i dev. enriched_prod bindes derfor ikke til dev/test; curated_prod er READ_ONLY-bundet til begge, og det er verificeret.
**Interpretation:** Notebook, kommentarer og PR-tekst skal kun dække de 7 curated-tabeller, og forudsætningstjekket må kun kræve curated_prod.
**Inferred intent:** Kun bind det katalog, der er nødvendigt, og lad referencedata være miljøspecifikke.

### What I did
Sendte rettelsen til samme builder. Ny commit 0cc2a1f på samme branch; PR-teksten er opdateret. Jeg verificerede author, ingen Co-Authored-By, PR head = 0cc2a1f, og at "variansanalyse"/"enriched" kun står i forklaringerne om udeladelsen.

### Why
Binding-beslutningen er truffet: kun curated_prod er bundet til dev og test.

### What worked
`databricks bundle validate` gav "Validation OK!" for dev og test. Laget med lag-abstraktionen blev fjernet som død kode.

### What didn't work
`gh pr edit 203` fejlede med "your authentication token is missing required scopes [read:project]". Builderen satte i stedet PR-teksten med `gh api -X PATCH repos/<org>/<repo>/pulls/203 -F body=@...`.

### What I learned
`gh pr edit` kræver read:project-scope, også når projects ikke bruges. `gh api` PATCH på pulls-endpointet virker uden.

### What was tricky
Intet ud over gh-scope-fejlen.

### What warrants review
SP-grants på curated_prod og job-SP'ens ret til CREATE OR REPLACE på Admin-ejede tabeller er stadig ikke verificeret.

### Future work
Release, første kørsel i dev og test, kontrol af ejer, grants og rækkeantal.
