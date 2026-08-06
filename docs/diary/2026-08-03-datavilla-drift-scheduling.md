# Diary: Datavilla — sætte platformen i egentlig drift (scheduling + triggere)

Datavilla's Blok 1 (raw) og Blok 2 (enriched) virker ende-til-ende på ægte data i dev, men
**intet er i drift**: 0 af 19 jobs har `schedule`, `continuous` eller `trigger`, og
afhængigheden ingest→enrich er eksplicit ikke wired (jobgeneratoren skriver selv
"DEPENDENCY (flagged, not wired here)"). Denne opgave er at designe og bygge selve
drift-opsætningen, før curated/Blok 3.

Arbejdet foregår i worktree `.claude/worktrees/datavilla-drift` på branch
`drift-opsaetning` i `C:\claudes_folder\repos\datavilla`.

## Step 1: Kravafklaring — fire designbeslutninger og tre fund der væltede antagelser

**Author:** lead

### Prompt Context

**Verbatim prompt (åbningen; den fulde opgavebesked var lang og er forkortet her — den
resterende del specificerede repo-sti, verificeret situation, kildeoversigt, de fem punkter
der skulle forfines, tekniske rammer og regler):**

> "Forfin kravene til at sætte datavilla-platformen i egentlig DRIFT. Du implementerer ikke
> selv — du forfiner, udfordrer Bennys antagelser, og kører builderen når kravene er skarpe."

**Interpretation:** Jeg skulle lede kravafklaringen, ikke implementere: læse koden, udfordre
de foreslåede rammer med konkrete tal, stille ét spørgsmål ad gangen, og først sætte en
builder i gang når beslutningerne var skarpe.

**Inferred intent:** Undgå at bygge en drift-opsætning på antagelser der ikke holder. Benny
havde en model i hovedet (dagligt batch over alle kilder); opgaven var at teste den mod hvad
repoet og Databricks faktisk gør, frem for at kode den som beskrevet.

### What I did

Læste repoet før jeg dannede holdninger: `scripts/generate_jobs.py` (de fire job-shapes og
argumenterne bag dem), `databricks.yml`, `config.py`, `autoload.py`,
`write/autoloader.py`, `enriched/reader.py`, `runlog.py`, `infra/cluster_policy.tf`,
`infra/budget.tf` og README. Kørte config-loaderen direkte for at få den faktiske
kilde→job-fordeling frem for at tælle filer i hånden.

Fem beslutninger blev truffet undervejs, hver som ét spørgsmål med trade-offs stillet op:

1. **Job-shape for det daglige batch.** Ét delt classic-cluster med et `for_each` over
   API-kilderne, i stedet for en orkestrator der kalder de eksisterende per-system-jobs.
2. **Scope.** Startede som "14 API + 21 fil-drop = 35 kilder", endte som 14 efter at
   filankomst-triggere kom på bordet.
3. **Fil-drop-kilder flyttes til filankomst-triggere** på de tre eksisterende jobs.
4. **Enrich-scope: alle 39 kilder dagligt** (option A af tre).
5. **Kun dev-miljø.** Blok 5 (multi-miljø targets) udgår som en separat beslutning.

Verificerede tre ting undervejs som ikke kunne afgøres fra hukommelsen: at filankomst-triggere
virker mod UC volumes, hvad predictive optimization gør ved daglige full-overwrites, og hvordan
Databricks klassificerer et run hvor en task fejler men en downstream `run_if: ALL_DONE`-task
lykkes.

Oprettede worktree og branch, og skrev denne diary. Selve implementeringen er ikke påbegyndt —
den ligger hos builderen.

### Why

Rammen jeg fik indeholdt to præmisser der ikke holdt ved eftersyn, og begge ville have kostet
noget hvis de var gået direkte i kode. Compute-argumentet for det daglige batch var bygget på et
budgetloft der var hævet dagen før, og "fjerner et manuelt skridt" blev fremhævet som det der
adskilte to modeller — hvilket det ikke gjorde, fordi begge modeller fjerner skridtet. At få
det frem før byggeriet er hele pointen med et kravafklaringstrin.

### What worked

At køre repoets egen config-loader frem for at tælle job-filer gav den præcise fordeling
(14 API-kilder fordelt på 11 jobs, fordi tre systemer har to kilder hver) og gjorde
compute-regnestykket konkret nok til at være en beslutning i stedet for en fornemmelse.

Repoet er usædvanligt velkommenteret, og kommentarerne bar reelle argumenter, ikke bare
beskrivelser. `generate_jobs.py` forklarer hvorfor enriched-laget blev kollapset til ét job og
hvorfor det kører serverless, inklusive den kvote-fejl der tvang det frem. Det gjorde det muligt
at forstå tidligere beslutninger uden at spørge, og at se hvilke der stadig var åbne.

At stille ét spørgsmål ad gangen med for/imod holdt tempoet oppe — fem beslutninger på fem runder,
og to af dem endte et andet sted end udgangspunktet.

### What didn't work

Ingen fejlede kommandoer i dette trin — der blev ikke skrevet kode. Men to ting gik skævt:

Worktreen forsvandt under mig midt i arbejdet. Den første
(`.claude/worktrees/agent-ad11d28808a4a3844`) var en rigtig git-worktree; den blev erstattet af
`agent-a2a29656facf8bc17`, som **ikke** var registreret i `git worktree list` og manglede
`docs/`. Reads mod den første sti fejlede med "File does not exist" efter skiftet. Jeg opdagede
det ved at `git worktree list` fra hovedrepoet kun viste hovedrepoet selv. `EnterWorktree`
kunne ikke bruges herfra:

    EnterWorktree cannot create a worktree from a subagent with a cwd override
    (isolation: "worktree" or explicit cwd) — it would mutate the parent session's
    process-wide working directory.

Løsningen var at oprette worktreen med git direkte
(`git worktree add ".claude/worktrees/datavilla-drift" -b drift-opsaetning`) og give builderen
stien som `cwd` i stedet.

### What I learned

**Databricks klassificerer "Succeeded with failures" som succes.** Det er det vigtigste fund i
hele trinnet. Dokumentationen er ordret: *"A job that has been completed in a Succeeded with
failures state is considered to be in a successful state. To be notified when jobs have been
completed in this state, you must select Success when you configure notifications."* Og
`jobs.on_success` er *"Sent when a run stops and is completed in a successful or succeeded with
failures state."* Konsekvensen: den kombination vi havde aftalt — `run_if: ALL_DONE` på
enrich-tasken plus job-niveau `on_failure` — er et **stille fejldesign**. Når en PSD2-consent dør,
fejler ingest-tasken, enrich kører alligevel og lykkes, runnet klassificeres som succes, og der
kommer ingen mail. Præcis den fejlmode notifikationen fandtes for at fange. Fixet står i samme
dokument: læg `on_failure` på **tasken**, ikke på jobbet.

**Filankomst-triggere passer bedre til den eksisterende jobstruktur end forventet.** Triggeren er
en job-egenskab, og de tre fil-drop-jobs findes allerede og er allerede rigtige. Ændringen er en
`trigger`-blok på hver, ikke en ny job-shape. Det gjorde den model til *mindre* arbejde end det
daglige batch den erstattede, hvilket vendte min anbefaling.

**En tidsplan ved midnat dansk tid er ufarlig her, af en grund der ikke er indlysende.** Midnat
Europe/Copenhagen er 22:00 eller 23:00 UTC — begge på den *foregående* UTC-dato. Sommertid flytter
timen, aldrig UTC-datoen, så der er ingen sæsonbetinget forskydning i hvilken dag der hentes. Og
DST-skiftene sker 02:00-03:00 lokalt, så et midnats-cron rammer aldrig en time der mangler eller
optræder to gange.

### What was tricky

**Self-trigger-fælden.** Auto Loader-checkpointet ligger på `{volume_root}/_ops`, altså *inde i*
volume-roden. Filankomst-triggere læser rekursivt ned gennem alle undermapper. En trigger på
volume-roden ville derfor se hver kørsels egne checkpoint-filer som nye filer og gentrigge sig
selv i ring — classic cluster efter classic cluster, i døgndrift. Stien skal være
`landing.drop_root(env)`, som er søskende til `_ops`. Koden kender allerede disciplinen for
Auto Loader-læsningen og siger det i en kommentar i `config.py`; triggeren skal have samme.

**Scope-spørgsmålet og shape-spørgsmålet var koblede,** og det var ikke tydeligt fra
opgavebeskrivelsen. Med ét delt cluster går marginalprisen for en ekstra kilde mod nul, så
"hvilke kilder kører dagligt" bliver næsten ligegyldigt — mens det med en orkestrator over
per-system-jobs koster et fuldt cluster-spinup pr. kilde-system. Rækkefølgen af spørgsmål måtte
vendes om, så shape kom først.

**Enrich-scope skiftede betydning undervejs.** Da fil-kilderne flyttede til triggere, holdt
fil-kilderne op med at være passagerer i det daglige enrich og blev i stedet grunden til at det
skal feje bredt — det daglige enrich er nu det eneste der overhovedet enricher dem.

### What warrants review

Ingen kode at reviewe endnu. Det der skal efterses når builderen er færdig:

- At trigger-stien er `drop_root`-mønsteret og ikke volume-roden, på alle tre fil-jobs. Det er
  det eneste sted hvor en fejl bliver dyr i drift frem for bare forkert.
- At `on_failure` sidder på ingest-**tasken** i det daglige job, ikke kun på jobniveau.
- Om en task-niveau-notifikation på den ydre `for_each`-task faktisk fyrer når en *iteration*
  fejler. Det er den naturlige læsning, men det kan kun bekræftes på en rigtig kørsel.
- Om en tom `availableNow`-stream returnerer på sekunder på et UC single-user cluster. Kunne ikke
  afgøres offline.
- Om landing-volumes er managed eller external (ingen `databricks_volume`-ressource findes i
  `infra/`), og om predictive optimization er slået til på kontoen eller katalogget. Begge er
  workspace-observationer, ikke kodeændringer.

### Future work

- Landing-mapperne vokser monotont (upload-kontrakten er en ny dateret mappe pr. upload). Uden
  file events er loftet for en filankomst-trigger 10.000 filer i den overvågede understi. Langt
  ude i fremtiden ved nuværende uploadtempo, men det er et loft og ikke en degradering.
- Per-kilde cost-attribution findes stadig ikke for enrich-laget; den ærlige proxy er at fordele
  jobbets omkostning efter `duration` pr. iteration i `_ops.run_log`. Uændret fra Blok 2.
- Diary-placeringen er drevet: outer_heaven har datavilla-entries frem til 2026-07-20, hvorefter
  otte entries er skrevet i datavilla's eget `docs/diary/`. Skill'en er entydig om at
  outer_heaven er det rigtige sted, så denne entry ligger her. De otte er ikke flyttet — det er
  ikke min beslutning at tage.

## Step 2: Implementering — femte job-shape, filankomst-triggere og den notifikation der ellers aldrig ville fyre

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt (åbningen; den fulde opgavebesked var lang og er forkortet her — resten
specificerede arbejdssted, baggrund, de otte kravsektioner og reglerne):**

> "Byg drift-opsætningen for datavilla: scheduling, filankomst-triggere og fejl-notifikationer.
> Kravene nedenfor er færdigforhandlet med Benny — de er ikke til genforhandling, men sig fra
> hvis noget er teknisk umuligt eller selvmodsigende frem for at improvisere."

**Interpretation:** Kravene var lukkede og gennemargumenterede fra Step 1. Min opgave var at
implementere dem præcist, skrive argumenterne ind i artefakterne selv (husets stil), teste
offline, og flage de tre ting der kun kan afgøres på en rigtig kørsel frem for at gætte.

**Inferred intent:** Step 1 havde fundet to fælder — self-trigger-løkken og
"Succeeded with failures"-klassifikationen — som begge er usynlige indtil de koster noget i
drift. Implementeringen skulle gøre dem strukturelt umulige at genintroducere ved et uheld, ikke
bare undgå dem én gang.

### What I did

Læste `src/README.md`, `scripts/generate_jobs.py`, `config.py`, `databricks.yml` og den
eksisterende testfil før jeg rørte noget, og kørte config-loaderen for at bekræfte fordelingen
med data frem for filtælling: 39 kilder, 14 extraction, 3 fil-drop-grupper, 11 extraction-grupper,
4 jdbc. Det matchede lead'ens tal.

Femte job-shape i generatoren: `DAILY_JOB_TEMPLATE` → `resources/daily_pipeline.job.yml`.
Navnet er bevidst **ikke** `ingest_*` — det præfiks betyder "ét job pr. kilde-SYSTEM" overalt
ellers i repoet, og testens `_ingest_plan()` selekterer den familie på præfikset, så et
`ingest_daily` ville have væltet `assert len(plan) == 18` af den forkerte grund. Jobbet kører de
14 extraction-kilder serielt på ét delt `CLUSTER_BLOCK`-cluster (`timeout_seconds: 900` pr.
kilde), og derefter en `run_job_task` mod `enrich_all` med `run_if: ALL_DONE`. Midnat
Europe/Copenhagen, UNPAUSED, `max_concurrent_runs: 1`.

`FILE_JOB_TEMPLATE` fik en `trigger.file_arrival`-blok. Stien udledes ved at kalde
`LandingConfig.drop_root(ENV_VAR_REF)` — samme funktion Auto Loader-læsningen bruger — med
`${var.env}` som env, så den emitterede sti er miljø-agnostisk og ikke kan drifte fra det
læseren overvåger. Den gamle kommentar om at jobbet "is deliberately NOT scheduled: it is
triggered after an upload" er rettet til at beskrive filankomst-triggeren.

Notifikationer: ny bundle-variabel `notification_email` i `databricks.yml`, refereret af alle
genererede jobs via `NOTIFICATION_EMAIL_REF`. Task-niveau `on_failure` på `ingest_api_sources`
med doc-citatet skrevet ind i den genererede YAML, job-niveau `on_failure` som backstop på det
daglige job, samt job-niveau på de tre fil-jobs og `enrich_all`.

To generator-side guards i en ny `_trigger_url()`: alle kilder i en gruppe skal resolve til
SAMME drop root, og den skal ligge strengt UNDER volume-roden. Og en guard i `plan()`: hvis der
findes extraction-kilder men ingen enrichede, rejses en fejl frem for at emittere et dagligt job
hvis `${resources.jobs.enrich_all.id}` ikke kan resolve ved deploy.

15 nye tests. Opdaterede `src/README.md` med et "Drift"-afsnit. Regenererede alle job-YAML'er og
committede dem (generatoren ejer dem) som `3e32d84` på `drift-opsaetning`.

### Why

Kravet var eksplicit om at argumenterne skulle stå i artefakterne, ikke kun i commit-beskeden —
og det er ikke kosmetik her. Begge fælder ser ud som noget man ville "rydde op" i: en trigger på
volume-roden ser mere generel ud end en på en undermappe, og en notifikation på jobbet ser
pænere ud end en på en task. Uden argumentet ved siden af er begge oplagte kandidater til en
velmenende forenkling der genintroducerer fejlen.

Derfor er begge også bundet af tests frem for kun kommentarer. En kommentar kan slettes i samme
commit som ændringen; en test kan ikke.

### What worked

**`databricks bundle schema` gav en rigtig offline-validering jeg ikke havde regnet med.**
Kravet forbød `bundle validate|deploy`, men `bundle schema` er hverken — den dumper CLI'ens egen
JSON-schema uden at røre et workspace. Jeg skrev en lille rekursiv validator (resolver `$ref` og
vælger object-grenen af hver `oneOf`, da den anden gren er `${var.x}`-strengmønsteret) og kørte
alle 20 genererede jobs plus `databricks.yml` igennem den:

    OK: every generated job field name/enum matches the Databricks bundle schema

Det er langt stærkere end en øjenkontrol: den fanger feltnavne-tastefejl, forkert nesting,
manglende required-felter og forkerte enum-værdier. Jeg kontrollerede bagefter at enum-checket
ikke var tomt — `PauseStatus` har `enum: ["UNPAUSED", "PAUSED"]` og `RunIf` har
`["ALL_SUCCESS", "ALL_DONE", "NONE_FAILED", ...]`, så både `UNPAUSED` og `ALL_DONE` er verificerede
enum-medlemmer og ikke antagelser.

Samme dump gav et konkret fund: `wait_after_last_change_seconds` er dokumenteret med *"The
minimum allowed value is 60 seconds"*. De 60 sekunder lead'en valgte er altså **gulvet**, ikke et
rundt tal — det kan hæves, aldrig sænkes. Det står nu ved konstanten.

**At bevise drift-checket frem for at asserte det.** Jeg nøjedes ikke med en test der siger at
filen er med i `plan()`; jeg manipulerede og slettede den committede fil og kørte checket:

    $ printf '\n# tamper\n' >> resources/daily_pipeline.job.yml
    $ python scripts/generate_jobs.py --check
    job resources are OUT OF DATE — run: python scripts/generate_jobs.py
      - out of date: daily_pipeline.job.yml
    exit=1

    $ rm resources/daily_pipeline.job.yml && python scripts/generate_jobs.py --check
      - missing: daily_pipeline.job.yml
    exit_after_delete=1

Begge veje fanges, og filen blev genskabt bagefter (`exit_restored=0`).

At `str.format`-mønsteret i generatoren allerede var gennemtænkt gjorde `${var.env}`-stien
gratis: format-ARGUMENTER genskannes ikke, så en sti med `${...}` kan sendes ind som værdi uden
firdoblede tuborgklammer. Det var allerede etableret af `CLUSTER_BLOCK`.

### What didn't work

Ingen fejlede tests og ingen fejlslagne implementeringsforsøg — kravene var skarpe nok til at
det gik i første hug. To kommandoer fejlede undervejs, begge miljø-støj:

    $ databricks bundle schema > "$TMPDIR/bundle_schema.json"
    /usr/bin/bash: line 1: /bundle_schema.json: Permission denied
    exit=1

`$TMPDIR` var tom i Bash-toolet, så omdirigeringen ramte roden. Løst ved at skrive til en
eksplicit absolut sti.

    $ python -c "import jsonschema"
    ModuleNotFoundError: No module named 'jsonschema'

`jsonschema` findes ikke i miljøet, så schema-valideringen måtte skrives i hånden (~40 linjer).
Det var faktisk en fordel: den håndskrevne walker rapporterer sti-præcise fejl som
`daily_pipeline.job.yml:daily_pipeline.tasks[1]: UNKNOWN FIELD ...`, hvilket er nemmere at læse
end en jsonschema-traceback.

Endelig ramte jeg første udkast forbi på et kommentar-detaljeniveau: debounce-kommentaren sagde
"One e-conomic export unzips to ~20 files", men samme template renderes ind i de to Koinly-jobs,
hvor Koinly er én CSV pr. år. Fanget ved at læse den genererede YAML for alle tre jobs frem for
kun `ingest_economic`. Omskrevet til at dække begge dialekter.

### What I learned

**Forbuddet mod `bundle validate` udelukker ikke al schema-validering.** Grænsen der gav mening
at trække var "rører det et workspace?" — ikke "står ordet bundle i kommandoen". `bundle schema`
er ren lokal output fra CLI-binæren. Det er en generel lære for offline-arbejde mod Databricks:
CLI'en bærer sin egen schema, og den kan bruges som en gratis linter for genereret bundle-YAML.

**Task-niveau `email_notifications` er lovligt på den YDRE `for_each`-task.** Schemaet bekræfter
at `Task` har både `for_each_task` og `email_notifications` som søskende-felter, så konstruktionen
er strukturelt gyldig. Det siger intet om *hvornår* den fyrer — se nedenfor — men det udelukkede i
det mindste at jeg havde bygget noget der slet ikke ville deploye.

**Generatorens navngivningskonventioner bærer testlogik.** `_ingest_plan()` selekterer på
`startswith("ingest_")` og asserter derefter classic-cluster-kontrakten med et hårdt `== 18`. At
et jobnavn dermed er en del af testkontrakten er ikke åbenlyst før man vælger et navn der
kolliderer. Det er værd at kigge efter i andre generatorer med præfiks-baseret selektion.

### What was tricky

**At bevise at det daglige jobs cluster er det SAMME cluster og ikke en kopi.** En kopi ville
være usynlig i alle øjenkontroller og først vise sig når `CLUSTER_BLOCK` ændres og kun 18 af 19
jobs følger med. Løst ved at sammenligne det daglige jobs cluster-spec mod kraken-jobbets,
modulo `custom_tags`:

    assert dict(daily, custom_tags=None) == dict(reference, custom_tags=None)

**En reel svaghed jeg fandt ved self-review, som kravene ikke dækker.** `max_concurrent_runs: 1`
serialiserer kun runs af det daglige job. De 11 per-system `ingest_*`-jobs findes stadig som
manuelle debug-enheder og ingesterer de SAMME kilder — så at starte `ingest_kraken` i hånden
mens det daglige job kører, sætter to processer på én Kraken-nøgle, altså to uafhængige
nonce-sekvenser. Præcis den fejl `concurrency: 1` forhindrer INDEN i et run. Databricks har
ingen cross-job mutex der kan udtrykke det. Det er en accepteret operationel begrænsning, ikke
en fejl i kravene, men den var uskreven, så jeg skrev den ind ved `max_concurrent_runs` med
mitigeringen (kør ikke per-system-jobs omkring midnat, eller pause schedulen først).

**At skrive assertion om fravær af notifikationer.** Det var fristende at give alle 18 jobs
`on_failure` "for konsistens", men de har hverken schedule eller trigger, så de kører kun når et
menneske starter dem — og det menneske kigger allerede på kørslen. Mail om et run man selv står
og ser på er støj, og støj er hvordan en rigtig alarm bliver ignoreret. Det er nu en test
(`test_manually_run_ingest_jobs_are_not_wired_to_email`), så "tilføj det overalt" skal være en
beslutning frem for en refleks.

### What warrants review

- `src/resources/daily_pipeline.job.yml` er den nye fil — læs den hele vejen igennem, den er
  eneste sted hvor både ALL_DONE-argumentet og notifikations-fælden står samlet.
- `_trigger_url()` i `src/scripts/generate_jobs.py` og
  `test_file_arrival_trigger_url_is_the_drop_root_never_the_volume_root`. Det er værnet mod
  self-trigger-løkken og det eneste sted en fejl bliver dyr i drift frem for bare forkert.
- Den nye `ValueError` i `plan()` når extraction findes uden enriched. Den er dækket af en test
  der monkeypatcher `load_all_sources`, men det er en gren der aldrig rammes i praksis — vurder
  om den er værd at beholde eller er over-engineering.
- Overvej om schema-validatoren skal blive en permanent test. Jeg gjorde det bevidst **ikke**:
  den kræver at `databricks`-binæren er installeret, og repoets testsuite er "offline, no
  cluster". At indføre en CLI-afhængighed i unit-testene er en reel omkostning der ikke var
  bestilt. Scriptet er dog trivielt at genskabe fra denne diary hvis det ønskes.

Tre ting kan stadig kun afgøres på en rigtig kørsel, og er flaget i artefakterne frem for gættet:
om en task-niveau-notifikation på den ydre `for_each`-task faktisk fyrer når en enkelt ITERATION
fejler; om en tom `availableNow`-stream returnerer på sekunder på et UC single-user cluster (14
serielle iterationer er kun billige hvis en kilde uden nye data er hurtig — `_ops.run_log.duration`
pr. iteration svarer på det ved første kørsel); og om landing-volumes er managed eller external.

### Future work

- Første rigtige kørsel bør bevidst brække én kilde (fx en forkert vault-secret-reference) for at
  bekræfte at task-niveau-notifikationen fyrer på en enkelt fejlet iteration. Indtil det er set,
  er stilhed ikke bevis for at alt virker.
- Mål `duration` pr. iteration i `_ops.run_log` efter første nat og afgør om det serielle
  for_each koster mærkbart på tomme kilder. Hvis det gør, er svaret ikke at hæve `concurrency`
  (det genintroducerer nonce-problemet), men at gøre en tom stream billigere.
- Tjek volume-typen i workspacet og slå file events til hvis de er external — det fjerner
  10.000-fil-loftet for triggere, som landing-mapperne vokser monotont imod.
- `src/README.md`'s indledning siger stadig "This is Blok 0 ... og Blok 1", hvilket har været
  forældet siden Blok 2 landede. Ikke rettet her (uden for scope), men det er drift i
  dokumentationen.
