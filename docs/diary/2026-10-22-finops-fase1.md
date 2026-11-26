# Diary: FinOps fase 1 (budget-alarmer og job-tags på kundens data-platform)

FinOps fase 1 på kundens Azure-/Databricks-platform: Terraform-budgetter (miljøbudget inkl. Databricks managed RG, ufiltreret totalbudget inkl. et større kapacitetskøb uden RG) med alarmer til tech lead alene, plus rettede `project`-tags på to Databricks-jobs. To feature-branches pushet, ingen PR, ingen plan/apply/deploy.

## Step 1: Budget-alarmer i IaC-repoet og job-tags i bundle-repoet

**Author:** builder

### Prompt Context

**Verbatim prompt:** (lead-brief, saniteret til rollebeskrivelser) "Benny (tech lead på DLBR DataEstate-platformen) har udtrykkeligt bedt om FinOps fase 1 i to SEGES-repos. Lav ændringerne, validér dem, commit og push KUN feature-branches. Ingen PR, ingen apply/deploy/release, intet mod main." Opgave A: alerts-modulet i IaC-repoet (modtagere som tfvars-liste med kun tech lead, subscription-scoped miljøbudget filtreret på `<Env>` + `databricks-rg-<Env>`, ufiltreret totalbudget kun i prod-kørslen, Actual >= 100 % og Forecasted >= 95 %, fjern udkommentering af modulet, robust action group-logik). Opgave B: `project`-tag på to jobs i bundle-repoet.
**Interpretation:** Genaktivér et dødt alerts-modul så det faktisk kan applyes, uden at røre andre moduler, og ret to tags.
**Inferred intent:** Få synlighed på månedsforbruget (især et større kapacitetskøb uden RG, som intet RG-budget kan fange) før regningen overrasker.

### What I did
Lavede worktrees fra frisk `origin/main` i begge repos. Omskrev `modules/alerts` (alerts.tf, variables.tf), aktiverede `module "alerts"` i main.tf, opdaterede root variables.tf og de fire tfvars. Verificerede Azure-fakta read-only med `az`: managed RG'er hedder `databricks-rg-<Env>`, cost-data rapporterer RG-navne med små bogstaver, den eksisterende action group i Azure er ikke Terraforms (andet navn og RG end locals), og Terraforms egen action group er aldrig oprettet. I bundle-repoet tilføjede/rettede jeg to tag-linjer og kørte `databricks bundle validate` mod dev/test/prod.

### Why
Budget på RG-niveau kan ikke se Databricks-VM-omkostning (ligger i managed RG) eller et større kapacitetskøb uden RG. Subscription-scoped budget med `ResourceGroupName`-filter løser det første, et ufiltreret totalbudget det andet.

### What worked
- `terraform validate` grøn efter `init -backend=false`.
- Evaluering af tfvars-afledte værdier via `terraform console` i en scratch-kopi uden backend.tf gav entydige budgetnavne, korrekt count (kun prod = 1) og RG-filtre pr. miljø.
- `databricks bundle validate -o json` bekræftede de resolvede tags i prod.

### What didn't work
- `git worktree add ... /c/claudes_folder/...` med `MSYS_NO_PATHCONV=1` sat: git tog stien bogstaveligt og oprettede worktrees i `C:/c/claudes_folder/...`. Rettet med `git worktree move` til Windows-stier (`C:/claudes_folder/...`) og fjernede de tomme mapper.
- `az databricks workspace list` fejlede: "The command requires the extension databricks ... EOFError: EOF when reading a line". Brugte `az resource list/show` i stedet.
- `az resource show --ids $id` uden `MSYS_NO_PATHCONV` fik stien konverteret til `C:/Program Files/Git/subscriptions/...` ("invalid ResourceId value").
- `terraform console` i worktree'et efter `init -backend=false`: "Backend initialization required". Løst med scratch-kopi uden backend.tf.
- `plantimestamp()` findes ikke i `terraform console` ("There is no function named \"plantimestamp\""); testede formatet med `timestamp()` i stedet. `validate` accepterer den i konfigurationen.

### What I learned
- `terraform fmt -recursive -check` fejler på næsten alle filer i IaC-repoet, så `fmt -recursive` ville have reformatteret andre moduler. Kørte kun `fmt` på `modules/alerts`.
- Budget-startdato i fortiden accepteres kun inden for den aktuelle time grain, så den hardcodede februar-dato ville have fejlet ved apply. Erstattet af første i måneden ud fra `plantimestamp()` + `ignore_changes`.
- Release-workflowet kører dev -> test -> prod sekventielt, men den gamle "opret i dev, læs via data i andre miljøer"-logik ville stadig få en isoleret test/prod-plan til at fejle.

### What was tricky
- Action group-designet: valgte én action group pr. miljø i miljøets egen RG i stedet for én fælles i den delte RG. Fjerner rækkefølge-afhængigheden helt, men er en designændring lead/tech lead skal kvittere for.
- iac_dev-tfvars brugte samme budgetnavn som dev og peger på samme RG; med subscription-scope ville navnet kollidere. Omdøbt, men budgettet overlapper stadig dev's.

### What warrants review
- Første `terraform plan` pr. miljø: forvent 1 action group + 1 budget (prod: + totalbudget), ingen ændringer i andre moduler.
- Om budget-filteret matcher RG-navne med små bogstaver (sat via `lower()`, ikke verificeret mod API).
- iac_dev-budgettet (lavt beløb, samme RG som dev) vil alarmere med det samme hvis den kørsel nogensinde applyes.

### Future work
- Tech lead skal bekræfte totalbudgettets beløb (FORSLAG i prod.tfvars).
- Overvej at oprydde ubrugte locals (`shared_action_group_name`) og den manuelle action group i Azure.
- RG'er uden for miljøerne (den delte RG, integrations-RG) fanges kun af totalbudgettet.

## Step 2: Én fælles action group i den delte RG

**Author:** builder

### Prompt Context

**Verbatim prompt:** (lead-besked, saniteret) "Benny har besluttet at ændre action group-designet ... Ny model: én fælles action group i den delte RG i stedet for én pr. miljø. Brug navnet fra `local.shared_action_group_name` og short name højst 12 tegn. ... Gruppen må kun oprettes i ét miljøs kørsel ... opret gruppen i det miljø, der applyes FØRST ... De andre miljøer må IKKE bruge et `data`-opslag på gruppen ... Byg i stedet resource-ID'et som en streng ... Kør `terraform fmt` kun på `modules/alerts` og de filer, du ændrer ..."
**Interpretation:** Tilbage til delt gruppe, men uden data-opslag, så plan ikke fejler på tværs af states.
**Inferred intent:** Én modtagerliste ét sted, og ingen skrøbelig rækkefølge ved plan.

### What I did
Læste release-workflowet: dev, test og prod er separate kald af et genbrugt workflow (plan-job + apply-job), kædet med `needs`, så dev er applyet før test planlægges. Gruppen oprettes i dev-kørslen (`count` på `action_group_owner_environment`, default "dev"); andre miljøer bygger ID'et ud fra subscription-ID, RG og navn. Fjernede per-miljø-gruppen og dens variabler, tilføjede kommentarer om state-ejerskab og destroy, og en tfvars-kommentar om at kun dev's modtagerliste virker. Commit 3c2df34 pushet.

### Why
Benny ville have én gruppe. Konstrueret ID i stedet for data-opslag gør plan i test/prod uafhængig af om gruppen findes.

### What worked
`terraform validate` grøn. `terraform console` i scratch-kopien viste samme konstruerede ID for test, prod og iac.

### What didn't work
- `terraform fmt` på main.tf, variables.tf og tfvars omformaterede hele filerne (main.tf 253 linjer diff), fordi repoet ikke var fmt-formateret på main i forvejen. Rullede tilbage med `git checkout --` og lavede de små ændringer igen. Kun `modules/alerts` er formateret; modul-blokken i main.tf er tjekket med `terraform fmt -check` på en udtrukket kopi.
- `terraform validate` fejlede første gang med "...but that provider isn't available ... terraform init", fordi jeg havde slettet `.terraform.lock.hcl` efter forrige validate. Ny `init -backend=false` løste det.

### What I learned
Et reusable-workflow-kald med `needs` venter på hele det kaldte workflow, inkl. apply-jobbet.

### What was tricky
Uden data-opslag fanger plan ikke en manglende gruppe; fejlen flyttes til apply i test/prod, hvis dev ikke er applyet.

### What warrants review
Om budget-API'et afviser et ikke-eksisterende contact group-ID ved apply, og om Azure returnerer ID'et med anden casing (fx `microsoft.insights`), hvilket kan give evig diff på `contact_groups`. Begge kan kun ses ved første plan/apply.

### Future work
Ingen ud over Step 1's.
