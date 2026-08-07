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

## Step 3: Deployet fejlede på ét værdiformat — den afsluttende skråstreg på trigger-URL'en

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt (åbningen; den fulde opgavebesked specificerede desuden arbejdssted, det
præcise fix, testkravene, lektien der skulle skrives ned og rammerne):**

> "Kirurgisk fix. Deployet fejlede på ét værdiformat — hele resten af drift-opsætningen er inde i
> master og virker."

**Interpretation:** Step 2's arbejde er merged og korrekt på alt andet end én ting: den genererede
`file_arrival.url` manglede en afsluttende skråstreg, og Databricks' backend afviste alle tre
filankomst-triggere ved deploy. Opgaven var at tilføje skråstregen ét sted, ikke at røre
`LandingConfig.drop_root()` som Auto Loader-læsningen deler, og at lukke hullet med en test der
rammer det *emitterede* YAML.

**Inferred intent:** Selve fixet er en linje. Det der faktisk skulle leveres var værnet mod at det
sker igen, plus en ærlig nedskrivning af hvorfor de offline-checks der blev kørt i Step 2 ikke
kunne fange det.

### What I did

Læste `_trigger_url()` i `src/scripts/generate_jobs.py`, `LandingConfig.drop_root()` i
`src/datavilla/config.py` og de eksisterende trigger-tests, før jeg rørte noget. Tilføjede
skråstregen som allersidste led i `_trigger_url()`, efter de to eksisterende guards, så
`return url` blev til `return f"{url}/"`. Guards sammenligner mod `volume_root`, som selv er uden
skråstreg; hvis normaliseringen var lagt før dem, ville `url.startswith(f"{volume_root}/")` skifte
betydning. Docstringen fik afsnittet om hvorfor skråstregen bor her og ikke i `drop_root()`, og
FILE_JOB_TEMPLATE fik en tilsvarende kommentar, så skråstregen står forklaret i det emitterede
YAML og ikke ligner noget man må rydde op i.

`drop_root()` er ikke rørt. Den har en anden kaldende: Auto Loader-læsningen, hvis checkpoint- og
schema-mapper er nøglet på de skråstregsløse stier der kører i produktion i dag.

Tre tests. Den eksisterende
`test_file_arrival_trigger_url_is_the_drop_root_never_the_volume_root` strippper nu skråstregen én
gang og sammenligner de strukturelle påstande mod den skråstregsløse config-værdi, plus en ny
`url != f"{volume_root}/"` fordi volume-roden med skråstreg er præcis samme fejl i en ny stavemåde.
Ny `test_every_emitted_file_arrival_url_ends_with_a_slash` går gennem `_all_jobs()` og påstår
skråstregen på hvert job der overhovedet bærer en trigger, ikke bare de tre kendte filer. Ny
`test_the_trailing_slash_is_added_by_the_generator_not_by_drop_root` fastholder arbejdsdelingen:
`drop_root()` skal ende uden skråstreg, `_trigger_url()` skal returnere præcis den sti plus én.

Regenererede job-YAML'erne (`python scripts/generate_jobs.py`), som ændrede de tre
`ingest_*.job.yml` for fil-drops. Commit `2ce3b17` på `trigger-url-fix`. Ikke pushet.

### Why

Fejlen kostede ikke data, men den kostede halvdelen af designet: workspacet endte med ét job med
schedule og nul med trigger. `daily_pipeline` blev oprettet og kører, så API-siden er i drift mens
fil-drop-siden aldrig nåede frem. Det er den værste slags delvis-deploy, fordi den ser ud som en
succes hvis man kun kigger på det job der kom igennem.

Placeringen af skråstregen er hele beslutningen. At normalisere inde i `drop_root()` ville have
været én tegns forskel i kode og en fuld re-ingest i drift, fordi Auto Loaders checkpoints flytter
med stien for hver eneste fil-drop-kilde. Fixet skulle derfor ligge oven på afledningen og ikke i
den.

### What worked

Koblingen fra Step 2 holdt under fixet. Fordi trigger-stien allerede blev afledt gennem
`drop_root()` og ikke skrevet i hånden, var der præcis ét sted at gribe ind, og de to guards
kunne blive stående uændret. Havde stien været hardcodet i tre YAML-filer, havde dette været tre
redigeringer og en fjerde der blev glemt næste gang.

Rød/grøn blev bekræftet frem for antaget: jeg satte midlertidigt returværdien tilbage til `url`
og kørte suiten. Fem tests fejlede, herunder den nye artefakt-guard:

```
FAILED tests/test_generate_jobs.py::test_every_emitted_file_arrival_url_ends_with_a_slash
FAILED tests/test_generate_jobs.py::test_the_trailing_slash_is_added_by_the_generator_not_by_drop_root
FAILED tests/test_generate_jobs.py::test_file_arrival_trigger_url_is_the_drop_root_never_the_volume_root
FAILED tests/test_generate_jobs.py::test_committed_jobs_are_up_to_date
FAILED tests/test_generate_jobs.py::test_drift_check_covers_the_daily_job
5 failed, 470 passed in 13.40s
```

Med fixet på plads: `python -m pytest` giver `475 passed in 9.44s`, og
`python scripts/generate_jobs.py --check` svarer `job resources are up to date` med exit 0.

### What didn't work

Deployet i Step 2, ordret:

```
Error: cannot update job: Invalid file arrival trigger configuration URL: must end with '/'
```

Den ramte alle tre filankomst-jobs, og hele deployet med dem. Den genererede værdi var
`/Volumes/datavilla_${var.env}_landing/economic/incoming/files` uden afsluttende skråstreg.

Selve dette step havde ingen fejlslagne forsøg ud over den bevidste rød/grøn-verifikation. Det er
værd at notere frem for at lade linjen stå tom: fixet var kendt på forhånd, og det svære var
teksten omkring det, ikke koden.

### What I learned

**Struktur-validering er ikke værdi-validering.** I Step 2 blev `databricks bundle schema` brugt
som erstatning for at kunne deploye, og den gjorde faktisk sit arbejde: den bekræftede feltnavne,
nesting, required fields og enums, og alt det var korrekt. `wait_after_last_change_seconds`-gulvet
på 60 sekunder kom endda derfra, fordi schemaet dokumenterer det minimum i feltets beskrivelse.
Men schemaet ved at `url` er en `string`. Det ved ikke *hvilke* strings backenden accepterer. Den
regel findes kun i backendens validering, og derfor kunne fejlen kun dukke op ved deploy.

Konsekvensen for hvordan jeg skriver offline-checks: et schema-check er et argument for at
strukturen er rigtig og ingen som helst dækning på værdiformater. Når et deploy ikke er muligt, er
den ærlige rapportering "struktur verificeret, værdier uverificerede" og ikke "valideret".

**Testen skal ramme artefaktet, ikke funktionen.** Springet mellem `_trigger_url()`s returværdi og
det emitterede YAML var præcis der fejlen slap igennem. Der var allerede en test på trigger-URL'en,
og den var grøn hele vejen, fordi den påstod at funktionen og configen var enige med hinanden.
Begge var enige om en værdi backenden ville afvise. Den nye guard læser det YAML der faktisk bliver
deployet.

### What was tricky

At `volume_root` er skråstregsløs gør rækkefølgen inde i `_trigger_url()` betydningsbærende. Guarden
`url.startswith(f"{volume_root}/")` skal se den unormaliserede værdi; normaliserer man først, tester
man noget andet end det man tror. Det er skrevet ind i docstringen, fordi den næste der rydder op i
funktionen ellers med rimelighed vil flytte linjen op.

Den eksisterende test havde `assert not ops.startswith(f"{url}/")` som "ops ligger ikke under
drop-roden". Med skråstregen i `url` blev det `.../files//` og påstanden vilkårlig. Rettet til
`assert not ops.startswith(url)`, hvilket nu er den korrekte formulering netop fordi `url` ender på
skråstreg. Sådan en assertion fejler ikke når den bliver forkert, den bliver bare meningsløs, og
det er den slags der overlever et refactor uden at nogen opdager det.

### What warrants review

- `_trigger_url()` i `src/scripts/generate_jobs.py` (~linje 1084): læs docstringen sammen med
  rækkefølgen af guards og normaliseringen. Det er hele beslutningen om hvor skråstregen bor.
- `test_every_emitted_file_arrival_url_ends_with_a_slash` i `src/tests/test_generate_jobs.py`. Den
  er den egentlige leverance i denne runde; vurder om dens dækning (alle jobs med trigger, ikke de
  tre kendte filnavne) er den rigtige bredde.
- Diffen på de tre `src/resources/ingest_*.job.yml` er én tegns ændring på `url` plus en kommentar.
  Alt andet i dem skal være uændret.
- **Andre værdiformat-krav som schema-validering heller ikke ville fange.** Jeg har kigget efter
  dem og ikke bygget noget om. Det jeg fandt, i rækkefølge efter hvor sandsynligt det er at bide:
  wildcards eller glob-mønstre i `file_arrival.url` understøttes ikke af Databricks, og vores stier
  er bogstavelige i dag, men intet værn forhindrer en fremtidig `pathGlobFilter`-agtig stump i at
  havne der. En sti der ikke eksisterer i volumet endnu er den anden: et deploy kan gå igennem og
  triggeren aldrig fyre, hvilket er tavs fejl frem for højlydt. Værdierne i `daily_pipeline` er
  derimod allerede backend-verificerede, fordi det job faktisk blev oprettet: cron-udtrykket
  `0 0 0 * * ?`, `timezone_id` og notifikations-mailen har været gennem den samme validering der
  afviste triggerne.

### Future work

- Efter deploy: bekræft at de tre triggere faktisk er oprettet i workspacet, og at der nu er tre
  jobs med trigger frem for nul. Det er den eneste måde at lukke denne runde.
- Bekræft at triggeren fyrer ved at lægge en fil i drop-mappen. At deployet accepteres beviser kun
  at værdiformatet er rigtigt, ikke at file events virker på det volume. Volume-typen (managed
  eller external) fra Step 2 er stadig uafklaret og afgør det.
- Overvej et lille værn mod wildcards i `_trigger_url()` hvis en fremtidig kilde nogensinde får
  brug for at pege triggeren et mere specifikt sted hen. Ikke bygget nu, fordi der ikke er noget
  der peger den vej endnu.

## Step 4: Triggerne deployede PAUSED — og eftersynet af hele fejlklassen

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt (åbningen; den fulde opgavebesked specificerede desuden arbejdssted, det
præcise fix, testkravene, det målrettede eftersyn af fejlklassen, diary-kravet og rammerne):**

> "Fix plus et målrettet eftersyn. Tredje gang i denne opgave at noget deployer grønt uden at
> virke — se sektionen om fejlklassen, den er hele pointen."

**Interpretation:** Skråstreg-fixet fra Step 3 er merged, deployet gik igennem, og alle tre
filankomst-triggere står nu i workspacet med korrekt sti og 60s debounce — men `PAUSED`. Fixet er
at sætte `pause_status: UNPAUSED` eksplicit i trigger-blokken og genbruge den begrundelse der
allerede stod på `daily_pipeline`s schedule, så den ikke findes i to udgaver. Oveni: gennemgå de
genererede jobs for andre felter hvor en *udeladelse* giver en default der stille slår noget fra,
og rapportere frem for at rette.

**Inferred intent:** Selve fixet er ét felt. Det der skulle leveres er dels værnet mod at samme
form for fejl slipper igennem igen, dels en systematisk gennemgang af hvor ellers i de 20 jobs vi
har arvet en default vi ikke kan navngive. Tre grønne deploys i træk der ikke virkede er ikke tre
uheld, det er et mønster i hvordan der bliver valideret.

### What I did

Læste `FILE_JOB_TEMPLATE` og `DAILY_JOB_TEMPLATE` i `src/scripts/generate_jobs.py` sammen med de
eksisterende trigger-tests, og bekræftede først feltets plads i schemaet frem for at antage den:
`databricks bundle schema` viser `pause_status` som søskende til `file_arrival` under `trigger`
(`jobs.TriggerSettings`), enum `["UNPAUSED", "PAUSED"]`. Det betyder otte mellemrums indrykning —
præcis samme dybde som feltet har under `schedule:`, hvilket er grunden til at én renderet blok kan
dække begge templates.

Begrundelsen blev trukket ud i én konstant, `ARMED_BLOCK`, med værdien i `PAUSE_STATUS_ARMED`.
Schedule-blokken i `DAILY_JOB_TEMPLATE` mistede sin egen kopi af argumentet og sin hårdkodede
`pause_status: UNPAUSED`-linje; begge templates render nu `{armed}`. `_render()` og
`_render_daily()` fylder det samme felt.

To nye tests, begge på det *emitterede* YAML. `test_every_emitted_trigger_is_armed_not_paused`
går gennem `_all_jobs()` og påstår `UNPAUSED` på hvert job der overhovedet bærer en trigger, ikke
på de tre kendte filnavne. `test_no_generated_job_emits_a_paused_schedule_or_trigger` scanner hver
`pause_status:`-linje i hver planlagt fil på tekstniveau, med et gulv på fire (tre triggere plus
schedulen) så den ikke kan blive tavs ved at felterne forsvinder helt. Den eksisterende
`test_daily_job_is_scheduled_at_midnight_local_and_armed` fik en linje der binder schedulen til
samme konstant.

Regenererede job-YAML'erne med `python scripts/generate_jobs.py`, hvilket ændrede de tre
`ingest_*.job.yml` for fil-drops og `daily_pipeline.job.yml`. Commit `6ac4a17` på
`trigger-unpause`. Ikke pushet.

Til eftersynet dumpede jeg `databricks bundle schema` til en fil og krydsede den mod det
genererede: et lille script sammenligner properties på `resources.Job` og `jobs.Task` med hvad de
20 jobs faktisk sætter. Det er dét der producerer listen under *What warrants review*. Ingen
`bundle validate`, intet deploy, ingen jobs kørt.

### Why

Feltet var ikke sat forkert, det var slet ikke der, og det er en anden slags fejl. En forkert værdi
bliver afvist eller opfører sig synligt forkert; et manglende felt bliver udfyldt af en default man
aldrig har set, og her er den default `PAUSED`. Resultatet var den værst mulige tilstand: tre jobs i
workspacet, med rigtig sti og rigtig debounce, der ser fuldstændig korrekte ud og aldrig fyrer.

Grunden til at begrundelsen skulle samles ét sted er at fejlen bogstavelig talt bestod i at den kun
stod ét af de to steder den gælder. Argumentet på schedulen — "a PAUSED schedule that someone has to
remember to unpause is the same as no schedule" — er ordret sandt om en trigger, og den der skrev
det havde allerede tænkt tanken færdig. Trigger-blokken 400 linjer længere oppe i samme fil arvede
den ikke. To kopier af én begrundelse er to begrundelser.

### What worked

Rød/grøn blev bevist begge veje frem for antaget, som ved URL-fixet. Med `{armed}` fjernet fra
trigger-blokken og YAML'erne regenereret:

```
FAILED tests/test_generate_jobs.py::test_every_emitted_trigger_is_armed_not_paused
FAILED tests/test_generate_jobs.py::test_no_generated_job_emits_a_paused_schedule_or_trigger
2 failed, 61 passed in 6.09s
```

med beskeden fra artefakt-guarden:

```
AssertionError: ingest_economic: trigger has pause_status=None; a trigger without an explicit
UNPAUSED deploys PAUSED and never fires
assert None == 'UNPAUSED'
```

Derefter blev trigger-blokken sat tilbage og schedule-blokken fjernet i stedet, for at bevise at
den anden halvdel også er dækket:

```
FAILED tests/test_generate_jobs.py::test_daily_job_is_scheduled_at_midnight_local_and_armed
FAILED tests/test_generate_jobs.py::test_no_generated_job_emits_a_paused_schedule_or_trigger
2 failed, 61 passed in 6.18s
```

Med begge på plads: `python -m pytest` giver `477 passed in 11.01s`, og
`python scripts/generate_jobs.py --check` svarer `job resources are up to date`.

At generatoren er deterministisk gjorde eksperimentet risikofrit: efter hver midlertidig ændring
gendannede en regenerering filerne byte-identisk, bekræftet med `git diff --stat` før og efter.

### What didn't work

Min første formulering af kommentaren var faktuelt for skråsikker, og jeg fangede den først under
selv-reviewet. Jeg skrev "Databricks defaults a MISSING pause_status to PAUSED" som om mekanismen
var kendt. Det er den ikke — der er mindst to kandidater, og den ene fandt jeg først bagefter:
`src/databricks.yml` sætter `mode: development` på dev-targetet, og den mode pauser hver schedule
og trigger der ikke selv siger noget. Databricks CLI'ens egen skabelontekst, fundet som streng i
binæren (v0.291.0), siger det direkte: *"Any job schedules and triggers are paused by default."*
Hvilken af de to mekanismer der reelt pausede triggerne kan jeg ikke afgøre herfra, og kommentaren
i koden siger nu netop det, plus at remediet er det samme uanset.

Samme binær gav et fund jeg ikke gik efter: `presets.trigger_pause_status: UNPAUSED` er ikke en vej
udenom, for CLI'en afviser den i development mode med

```
target with 'mode: development' cannot set trigger pause status to UNPAUSED by default
```

Det er skrevet ind i konstanten, så den næste der vil "forenkle" fire felter til én preset ved hvad
der sker.

Ingen kommandoer fejlede i denne runde ud over de bevidste røde kørsler ovenfor.

### What I learned

**Alle tre fejl i denne opgave har haft samme form: grønt deploy, ingen fejlmeddelelse, virkede
ikke.** Det er skarpere og mere brugbart end "struktur er ikke værdi", som var lektien efter Step 3,
fordi den formulering kun dækker den ene af dem.

1. `bundle schema` validerede struktur, ikke værdiformat — URL'en manglede en skråstreg, og
   backenden afviste den først ved deploy.
2. Feltet blev udeladt, og den default der udfyldte det slog funktionen fra — denne fejl.
3. Det tredje tilfælde er noteret men ikke ramt endnu: peger en trigger på en sti der ikke findes,
   fyrer den bare aldrig, tavst.

Fællesnævneren er at **fraværet af en fejl ikke er bevis for at noget virker.** Nummer 1 gav i det
mindste en fejlmeddelelse ved deploy. Nummer 2 og 3 giver intet overhovedet: jobbet står der, det
ser rigtigt ud, og den eneste indikator er data der ikke dukker op. Den slags opdages af den der
undrer sig over et tal, ikke af et check.

Det ændrer hvad jeg leder efter, når jeg ikke kan deploye. Ikke "er felterne rigtige" men "hvilke
felter har vi undladt, og hvad bliver de udfyldt med". `databricks bundle schema` er faktisk god
til præcis det, fordi den lister de felter vi ikke sætter — den kan bare ikke sige hvad defaulten
er, og det er den anden halvdel af spørgsmålet.

**En default man ikke kan navngive, skal skrives eksplicit.** Ikke fordi den nødvendigvis er forkert,
men fordi en læser ellers ikke kan se forskel på "vi har valgt dette" og "vi tænkte ikke over det".
`max_concurrent_runs: 1` står eksplicit på `daily_pipeline` med et helt afsnit om nonce-sekvenser;
de øvrige 19 jobs har samme værdi, usagt, fordi det tilfældigvis er defaulten.

### What was tricky

Indrykningen bar hele designet. At `pause_status` ligger på otte mellemrum *både* som felt under
`schedule:` og som søskende til `file_arrival:` under `trigger:` er det der gør én fælles konstant
mulig; havde dybderne været forskellige, skulle blokken have været renderet med variabel indrykning
og så var "én konstant" blevet til en hjælpefunktion og et argument. Det er verificeret i schemaet
og ikke gættet ud fra hvordan YAML'en ser ud.

Tekst-testen der scanner `pause_status:`-linjer skal kun ramme felter, ikke kommentarer — og
kommentaren indeholder ordet PAUSED flere gange, netop fordi den forklarer defaulten. `startswith`
efter `strip()` løser det, men det er den slags detalje der gør en test vilkårlig hvis den bliver
skrevet lidt anderledes næste gang.

Rækkefølgen i selv-reviewet var den egentlige gevinst: fixet var færdigt og grønt *før* jeg fandt
`mode: development` i `databricks.yml`, og det fund ændrede en kommentar jeg allerede havde skrevet
med for stor sikkerhed. Havde jeg committet efter grøn test i stedet for efter selv-review, stod
der nu en forkert forklaring i fire genererede filer.

### What warrants review

- `ARMED_BLOCK` og `PAUSE_STATUS_ARMED` i `src/scripts/generate_jobs.py` (~linje 230). Vurder om
  konstanten siger det rigtige om mekanismen — den er bevidst forsigtig, fordi jeg ikke kan afgøre
  om det var dev-mode-presetten eller Jobs-API'ets egen default der pausede triggerne.
- **Den vigtigste kontrol før noget andet: virker fixet overhovedet på dev-targetet?**
  `src/databricks.yml:53` sætter `mode: development`, og den mode pauser schedules og triggere "by
  default". Om en *eksplicit* `pause_status` i ressourcen overlever presetten, kan jeg ikke afgøre
  offline, og `bundle validate` var uden for rammerne. Der findes et gratis, læse-kun svar i
  workspacet: `daily_pipeline` har haft eksplicit `UNPAUSED` hele tiden og er deployet under samme
  mode. Står dens schedule som aktiv — eller findes der en automatisk kørsel omkring midnat i dens
  run-historik — så vinder eksplicitte værdier over presetten, og dette fix armer triggerne. Står
  den derimod som pauset, er fixet virkningsløst, og den rigtige løsning er en beslutning om
  `databricks.yml` (droppe development mode for dev-targetet), ikke om generatoren. Bemærk at
  `presets.trigger_pause_status: UNPAUSED` ikke er en udvej: CLI'en afviser den i development mode.
- **`queue` — udeladt på alle 20 jobs, og `daily_pipeline`s egen kommentar påstår det modsatte.**
  Kommentaren over `max_concurrent_runs: 1` siger at et overlappende run "must QUEUE behind the
  running one, not race it". Uden `queue: {enabled: true}` bliver det run efter al sandsynlighed
  *skippet*, ikke køet. Enten mangler feltet, eller også lover kommentaren noget jobbet ikke gør;
  begge dele skal rettes, og det er samme fejlklasse som denne commit handler om. For de tre
  triggede jobs er konsekvensen konkret: lander en upload mens jobbet kører, droppes kørslen.
  Filerne går ikke tabt — de bliver liggende i volumet, og Auto Loader tager dem næste gang jobbet
  kører — men næste gang er først ved næste upload, hvilket for et månedligt e-conomic-eksport kan
  være uger, og enriched projicerer imens en rå-tabel uden dem. Jeg har bevidst ikke sat feltet:
  defaulten er uverificeret herfra, og pointen er netop ikke at gætte. Anbefaling: sæt
  `queue: {enabled: true}` eksplicit på de tre trigger-jobs og på `daily_pipeline`, uanset hvad
  defaulten viser sig at være.
- **`timeout_seconds` — job-niveau udeladt på alle 20, task-niveau kun sat ét sted.** De 900s ligger
  på `daily_pipeline`s indre for_each-task; hverken fil-drop-iterationerne, per-system-ingest-jobbene
  eller enrich-iterationerne har nogen. Udeladt betyder ingen grænse. På et *trigget* job er det
  værre end det lyder: hænger en kørsel, og næste trigger enten skippes eller køer bag den for evigt,
  så en hængende Auto Loader-stream bliver til permanent tavshed. Anbefaling: et loft pr. job-shape,
  men det kræver et tal og dermed en beslutning — jeg vil ikke gætte det ind.
- **`max_concurrent_runs` — sat på `daily_pipeline`, usagt på de 19 andre.** Værdien er den vi vil
  have; det er kun begrundelsen der mangler. Samme klasse, modsat fortegn.
- **`max_retries` — 0 overalt undtagen enrich-iterationerne.** For et fil-drop betyder én forbigående
  fejl at det subject ikke bliver ingested før næste upload, af samme grund som queue-punktet.
- **`health` og `notification_settings` — udeladt overalt.** Ingen varsling på run-varighed. Det
  hænger sammen med queue-punktet på én måde der er værd at tjekke i samme ombæring:
  `no_alert_for_skipped_runs` defaulter til `false`, hvilket *kan* betyde at et skippet run alligevel
  sender on_failure-mail. Er det tilfældet, er det droppede run larmende frem for tavst, og queue
  rykker ned i prioritet. Er det ikke, står punktet hvor det står.
- Diffen på de fire genererede `*.job.yml` er ét felt plus kommentaren, og på `daily_pipeline`
  desuden flytningen af det gamle afsnit ind i blokken. Alt andet skal være uændret.

### Future work

- Efter deploy: bekræft i workspacet at de tre triggere står som aktive og ikke pausede. Det er den
  eneste måde at lukke denne runde, og den er billigere end den forrige, fordi tilstanden kan ses
  direkte på jobbet.
- Læg derefter en fil i drop-mappen og se at der faktisk starter en kørsel. Deployet beviser kun at
  feltet blev accepteret; at file events virker på volumet er stadig ubevist, og volume-typen
  (managed eller external) fra Step 2 er stadig uafklaret.
- Tag stilling til `queue` og til `timeout_seconds` som en samlet lille runde frem for enkeltvis.
  De hører til samme fejlklasse og har samme remedie: skriv defaulten eksplicit, eller ret den
  kommentar der påstår noget andet.
- Denne diary-fil er stadig **ucommittet** i `outer_heaven` (`git status` viser den som modificeret,
  388 tilføjede linjer og nul slettede). Opgavebeskeden sagde "Step 1-3 er ucommittet", men det
  holder ikke helt: `git show HEAD:docs/diary/2026-08-03-datavilla-drift-scheduling.md` indeholder
  Step 1 og Step 2 — de blev committet i `f54d034` ("diary: samle datavilla-diaries i
  outer_heaven"). Det ucommittede er altså **Step 3 og Step 4**. Nul sletninger i diffen bekræfter
  at intet i Step 1-3 er rørt af denne runde.

## Step 5: `queue` sat eksplicit — samme fejlklasse, fanget før deployet, og de første driftstal

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt (åbningen; den fulde opgavebesked specificerede desuden de fem jobs feltet skulle
sættes på, kommentar-rettelsen, testkravene, nattens driftstal og de uændrede rammer):**

> "Dit fund nr. 1 er godkendt til at komme med i denne commit. Deployet venter på det —
> pause-fixet går ikke ud alene, fordi vi ved der er en fejl mere, og vi har allerede brugt to
> deploy-runder på at opdage den slags én ad gangen."

**Interpretation:** Fund nr. 1 fra eftersynet i Step 4 — `queue` udeladt på alle 20 jobs — skal
bygges nu og ikke afvente en beslutningsrunde, og den løgnagtige kommentar over
`max_concurrent_runs: 1` skal rettes samtidig. Feltet skal sættes på de jobs der kan starte uden et
menneske: `daily_pipeline`, de tre filankomst-triggede og `enrich_all`, som kaldes af
`run_job_task`. Tests på det emitterede YAML, rød/grøn bevist begge veje.

**Inferred intent:** At samle to fejl af samme form i ét deploy frem for at bruge en deploy-runde
per fund. Det er en direkte konsekvens af fejlklassen fra Step 4: når man ved at defaults kan slå
ting fra i stilhed, er "vi tager den næste gang" en beslutning om at deploye noget man allerede har
mistanke til.

### What I did

Trak `queue: {enabled: true}` ud i én konstant, `QUEUE_BLOCK`, med begrundelsen renderet ind i
YAML'en på samme måde som `ARMED_BLOCK` fra Step 4 — seks mellemrums indrykning, fordi `queue` er et
job-niveau-felt og søskende til `tasks:`. Den renderes ind i tre af de fem job-shapes:
`DAILY_JOB_TEMPLATE`, `FILE_JOB_TEMPLATE` og `ENRICHED_JOB_TEMPLATE`.

De to øvrige shapes — `JOB_TEMPLATE` (jdbc) og `EXTRACTION_JOB_TEMPLATE` (per-system API) — fik den
ikke. Opgaven gav mig valget og bad om en begrundelse: **det koster ingen kompleksitet at lade være**,
fordi de fem shapes allerede er hver sin template, så der er hverken en gren eller en undtagelse at
indføre. Argumentet i blokken handler om tab man ikke opdager, og de 15 jobs startes kun ved at et
menneske trykker Run Now — det menneske ser afvisningen. At sætte feltet der ville hæfte en
begrundelse på jobs den ikke gælder for, og den næste læser skulle så selv regne ud at den ikke
gælder.

Kommentaren over `max_concurrent_runs: 1` er skrevet om. Den påstod at et overlappende run "must
QUEUE behind the running one, not race it" — en konfiguration der ikke fandtes. Nu siger den hvad
hvert af de to felter faktisk gør: `max_concurrent_runs` afviser det andet run, og kun
`queue.enabled` afgør om "afvist" betyder køet eller droppet. Den peger eksplicit på den anden
halvdel og siger at fjerner man køen, bliver afsnittet en løgn igen.

Tre tests, alle på det emitterede YAML. Den vigtigste detalje er at medlemskabet **udledes af
artefaktet** frem for af filnavne: `_unattended_job_keys()` samler jobs med `schedule`, jobs med
`trigger`, og jobs som et andet jobs `run_job_task` peger på (regex mod
`${resources.jobs.<key>.id}`). Den sidste er den der fanger `enrich_all`, som hverken har schedule
eller trigger. Testen påstår desuden at dette sæt er **identisk** med det sæt der får
fejl-mail — det er samme kriterium, og hvis de to nogensinde skilles ad, er en af dem blevet sat i
hånden i stedet for efter regel. En modsat test holder de 15 manuelle jobs fri af feltet, og en
tredje påstår at et genereret job der overhovedet taler om kø, også indeholder feltet.

Regenererede YAML'erne. Commit `6ab93ca` på `trigger-unpause`, oven på `6ac4a17` fra Step 4. Jeg
valgte bevidst **ikke** at amende ind i Step 4's commit, selvom opgaven sagde "denne commit": den
commit er allerede rapporteret og læst, og en squash ved merge er lead's beslutning frem for min.

### Why

Beslutningen om at sætte feltet frem for at undersøge defaulten først er den samme som ved
`pause_status`, og den er værd at skrive ned som et princip: **når en default ikke kan verificeres
herfra, er det argumentet for at skrive den, ikke imod.** Prisen ved at tage fejl er asymmetrisk på
en måde der afgør sagen — tager jeg fejl, køer vi et run der alligevel ville være kørt; tager jeg
ikke fejl og lader være, mister vi en upload uden at nogen får besked.

Grunden til at kommentaren skulle rettes i samme ombæring er at den var farligere end det manglende
felt. Et manglende felt er en tom plads; en kommentar der beskriver en konfiguration der ikke findes,
fortæller den næste læser at spørgsmålet er afklaret. Havde eftersynet i Step 4 kun kigget på felter
og ikke på hvad kommentarerne påstår, var den blevet stående som dokumentation for noget der ikke var
sandt.

### What worked

Rød/grøn blev bevist **tre gange, én pr. shape**, fordi de tre jobs bliver fanget ad tre forskellige
veje og et enkelt bevis derfor ikke ville dække udledningen. Fjernet fra fil-drop-templaten:

```
AssertionError: ingest_economic can start without a human, so a run refused for concurrency
disappears unless queue.enabled is set explicitly
assert None == {'enabled': True}
1 failed, 65 passed in 6.97s
```

Fjernet fra `enrich_all` — det interessante tilfælde, fordi det job hverken har schedule eller
trigger og kun fanges via `run_job_task`-udledningen:

```
AssertionError: enrich_all can start without a human, so a run refused for concurrency
disappears unless queue.enabled is set explicitly
1 failed, 65 passed in 6.63s
```

Fjernet fra `daily_pipeline`, hvor begge guards fyrer, herunder den der fanger præcis den fejl der
blev rettet:

```
FAILED tests/test_generate_jobs.py::test_every_unattended_job_queues_instead_of_dropping_a_run
FAILED tests/test_generate_jobs.py::test_the_daily_concurrency_comment_matches_what_is_actually_set
AssertionError: daily_pipeline.job.yml
assert 'queue:\n        enabled: true' in '# GENERATED by scripts/generate_jobs.py ...'
2 failed, 64 passed in 5.85s
```

Med alt på plads: `python -m pytest` giver `480 passed in 10.80s`, og
`python scripts/generate_jobs.py --check` svarer `job resources are up to date`.

**Første rigtige driftsbevis.** Natten før denne runde kørte `daily_pipeline` kl. 00:00 dansk tid med
`trigger=PERIODIC` og SUCCESS hele vejen: `ingest_api_sources` 14/14 kilder på 27,5 minutter,
`enrich` via `run_job_task` → `enrich_all` 39/39 iterationer på 16,2 minutter, i alt 43,7 minutters
wall-clock. `_ops.run_log` viser 342.110 rækker læst fra landing, 668 nye i raw (SCD2-dedup gjorde
resten til no-op) og 387.549 i enriched. Estimatet for ingest-delen var ~25-30 cluster-minutter, og
den faktiske blev 27,5 — hvilket er det tætteste denne opgave er kommet på at kunne verificere noget
mod virkeligheden frem for mod et schema. Kæden schedule → ingest → `run_job_task` → enrich virker i
praksis, ikke bare på papir.

Det lukker også det åbne spørgsmål fra Step 4 empirisk: samme deploy, samme workspace, samme
`mode: development` — `daily_pipeline` med eksplicit `pause_status: UNPAUSED` kom ud **UNPAUSED**,
mens de tre triggere uden feltet kom ud **PAUSED**. Eksplicit slår preset'en, og pause-fixet er
dermed ikke virkningsløst. Det er skrevet ind i `generate_jobs.py` ved konstanten, så næste læser
ikke skal gætte igen.

### What didn't work

Ingen kommandoer fejlede utilsigtet i denne runde. Det tætteste er en formulering jeg selv fangede
inden commit: den fælles `QUEUE_BLOCK` sagde først "1: stated outright on the daily job **below**",
hvilket kun er sandt i én af de fire filer den renderes ind i — i `ingest_economic.job.yml` er der
intet "below". Rettet til "1, whether stated outright (the daily job) or inherited as the default
(every other job here)". Det er en fælde ved præcis det mønster Step 4 indførte: når én blok
renderes flere steder, må dens tekst ikke pege på sin egen placering.

### What I learned

**Et eftersyn skal også læse kommentarerne, ikke kun felterne.** Fejlen i `daily_pipeline` fandtes i
to udgaver: et manglende felt og en kommentar der påstod at feltet var der i ånden. Den første kunne
findes ved at krydse `databricks bundle schema` mod det genererede — det var sådan jeg fandt den. Den
anden kunne kun findes ved at læse hvad teksten lover og sammenligne med hvad specen sætter. Den
slags "dokumentations-drift" er samme fejlklasse som resten af opgaven: den ser rigtig ud, den fejler
ikke, og den er forkert.

**Asymmetrisk pris er et bedre beslutningskriterium end sikkerhed.** Jeg kunne ikke verificere
Databricks' default for `queue` herfra, og i Step 4 lod jeg det stå som et åbent spørgsmål til lead.
Det var for forsigtigt. Når den ene fejl koster et unødvendigt køet run og den anden koster en tabt
upload, er spørgsmålet om defaulten irrelevant for beslutningen — den skal skrives eksplicit uanset
svaret. Verifikationen er stadig værd at lave, men den er ikke det der blokerer.

**Udled testens medlemskab af artefaktet, ikke af en liste.** `enrich_all` har hverken schedule eller
trigger og ville aldrig være fanget af en test der spurgte efter dem; den fanges fordi udledningen
også følger `run_job_task`-referencer. Havde jeg i stedet skrevet de fem jobnavne ind i testen, ville
den have været grøn og alligevel værdiløs den dag et sjette job bliver kaldt af et andet.

### What was tricky

At `queue` og `max_concurrent_runs` kun giver mening sammen, men bor to forskellige steder — og at
kun det ene er sat på fire af de fem jobs. Blokken skulle derfor kunne læses både på
`daily_pipeline`, hvor begge felter står, og på et fil-drop-job, hvor grænsen er en usagt default.
Det er løst i teksten ("1, whether stated outright or inherited as the default") frem for ved at
sætte `max_concurrent_runs` eksplicit overalt, fordi det sidste er et selvstændigt fund fra Step 4
som lead ikke har taget stilling til endnu.

Testen `test_the_daily_concurrency_comment_matches_what_is_actually_set` er den mest skrøbelige af de
tre, fordi den påstår noget om tekst frem for om struktur: den siger at et job der nævner kø også skal
indeholde feltet. Den er med, fordi det var præcis dén uoverensstemmelse der stod i repoet i to
måneder, men den er formuleret bredt nok til at en omskrivning af kommentaren ikke vælter den.

### What warrants review

- `QUEUE_BLOCK` i `src/scripts/generate_jobs.py` (~linje 276) og de tre steder den renderes. Vurder
  særligt afgrænsningen: fem jobs får feltet, femten gør ikke. Argumentet er "hvor er et droppet run
  tavst", og det er samme kriterium som fejl-mailen bruger.
- `_unattended_job_keys()` i `src/tests/test_generate_jobs.py`. Det er den egentlige leverance i
  denne runde — vurder om de tre veje ind (schedule, trigger, `run_job_task`-mål) er udtømmende. Jeg
  kender ikke en fjerde i dag, men `continuous` ville være en hvis den nogensinde bliver taget i brug.
- Den omskrevne kommentar over `max_concurrent_runs: 1` i `daily_pipeline.job.yml`. Læs den sammen
  med queue-blokken over den og vurder om den nu beskriver virkeligheden frem for hensigten.
- De øvrige fund fra Step 4 står uændrede og ubesluttede: job-niveau `timeout_seconds` (udeladt på
  alle 20), task-niveau timeout (kun på `daily_pipeline`s indre task), `max_concurrent_runs` usagt på
  19 jobs, `max_retries` 0 uden for enrich, og `health`/`notification_settings` udeladt overalt.

### Future work

- Nattens kørsel gav ét datapunkt til de to udestående knapper: 27,5 minutter for ingest-delen og
  16,2 for enrich. Ét punkt er ikke en grænse, så `timeout_seconds` og `max_retries` er bevidst ikke
  bygget ind. Efter en uges kørsler kan spredningen ses i `_ops.run_log`, og så kan et loft vælges på
  data frem for på fornemmelse.
- Bekræft efter deploy at de fem jobs faktisk står med kø slået til, og at de tre triggere står som
  aktive. Det er stadig kun deployet der kan bevise begge dele.
- At køen rent faktisk holder et run tilbage frem for at droppe det, kan først ses ved et rigtigt
  overlap — enten en upload midt i en kørsel eller en manuel start af `enrich_all` under det daglige
  batch. Det er ikke værd at fremprovokere; det bliver observeret næste gang det sker af sig selv.
- Diary-filen er stadig ucommittet i `outer_heaven`: Step 1-2 ligger i `f54d034`, mens Step 3, 4 og
  nu 5 kun findes i working tree.

## Step 6: Notifikationen bevist på en engangs-kopi frem for på produktionen

**Author:** main

### Prompt Context

**Verbatim prompt:** "billig!" (valg mellem to måder at teste fejlnotifikationen: en billig
engangs-kopi af strukturen, eller en invasiv test hvor en rigtig secret ødelægges midlertidigt)

**Interpretation:** Byg et midlertidigt job der replikerer notifikations-strukturen, kør det, og
bekræft at mailen kommer — uden at røre secrets, data eller eksisterende jobs.

**Inferred intent:** Benny ville have vished om at alarmen virker, men ikke betale for den med en
brudt kilde og en 43-minutters kørsel. Underforstået: hvis den billige test afviser mekanismen,
har vi lært det samme uden at have ødelagt noget.

### What I did

Byggede et engangsjob `ZZ notif-test` der replikerede den ene ting der var i tvivl: en `for_each`
med to inputs hvor den ene fejler, en `email_notifications.on_failure` udelukkende på den ydre task,
og en efterfølgende task med `run_if: ALL_DONE`. Ingen notifikation på job-niveau overhovedet — det
skulle netop vises at være utilstrækkeligt.

Iterationerne kørte en syntetisk notebook der kaster en exception når dens parameter er `fail`.

Resultatet:

```
JOB-RESULTAT: SUCCESS_WITH_FAILURES | The job run succeeded with 1 failed task
  fanout   FAILED
  after    SUCCESS
```

Benny bekræftede at mailen kom. Job og notebook blev slettet bagefter, og fraværet verificeret med
`databricks jobs get` og `workspace get-status` — begge svarer nu "does not exist".

### Why

Alternativet var at sætte en dummy-værdi på en secret i `kv-datavilla-dev`, køre `daily_pipeline`
og gendanne bagefter. Det ville have testet den faktiske opsætning frem for en kopi, men kostede en
fuld kørsel og efterlod en kilde brudt indtil gendannelsen — med den risiko at gendannelsen glemmes
og natten fejler.

Det der var i tvivl, var ikke datavillas konfiguration; den kunne læses. Det var Databricks' adfærd:
fyrer en task-level notifikation når en enkelt for_each-iteration fejler, i et run der samlet
klassificeres som succes? Det spørgsmål besvares lige så godt på en kopi som på produktionen.

### What worked

Kopien bekræftede builderens analyse i Step 4 præcist, og det var mere end mailen. Runnet kom ud som
`SUCCESS_WITH_FAILURES` — altså ville en job-level `on_failure` ikke have fyret. Kommentaren i
`daily_pipeline` der forbyder at "rydde op" i task-placeringen er dermed ikke et forsigtighedshensyn,
men en dokumenteret nødvendighed.

At bygge testen som et separat job frem for at ændre et eksisterende betød at oprydningen var
fuldstændig: to sletninger, og workspacet er tilbage på 20 jobs.

### What didn't work

`databricks workspace import` fejlede først med:

```
Error: requirement failed: C:/Program Files/Git/Users/benny@singularityconsult.dk/zz_notif_test is not absolute.
```

Git Bash oversætter en Unix-lignende workspace-sti til en Windows-sti før CLI'en ser den. Løsningen
er `MSYS_NO_PATHCONV=1`. Det rammer enhver Databricks-kommando der tager en workspace-sti som
argument, ikke kun import.

### What I learned

**Et spørgsmål om platformens adfærd behøver ikke stilles til produktionen.** Fristelsen var at teste
på den rigtige opsætning, fordi det er den der skal virke. Men det der var ukendt, var generisk
Databricks-semantik, og den kan isoleres. Skelnen mellem "jeg tvivler på min konfiguration" og "jeg
tvivler på platformen" afgør hvor testen hører hjemme.

**`SUCCESS_WITH_FAILURES` er en selvstændig tilstand**, ikke bare en beskrivelse. Den tæller som
succes for job-level notifikationer og som fejl for task-level. Et design der blander de to lag vil
tie i præcis den situation hvor alarmen betyder mest.

### What was tricky

Fristelsen til at kalde testen tilstrækkelig var større end den burde være. Kopien beviser Databricks'
adfærd, ikke at `daily_pipeline`s egen notifikation er korrekt konfigureret — det hviler stadig på at
have læst den emitterede YAML. De to ting skal holdes adskilt, også når begge peger samme vej.

### What warrants review

- Testen er slettet og efterlader intet spor i repoet. Skal den kunne gentages efter en fremtidig
  ændring af notifikations-designet, skal den bygges igen fra denne beskrivelse.
- Det er stadig kun bevist for `for_each`-tasks. Fejler en almindelig task i `daily_pipeline`, er
  adfærden formodentlig den samme, men det er ikke set.

### Future work

- `queue`s virkning er stadig ubevist og kræver et ægte overlap. Ikke værd at fremprovokere.
- Ved næste ændring af notifikations-opsætningen: gentag denne test frem for at stole på at den
  stadig gælder. Den koster ét lille spinup.
