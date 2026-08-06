# Diary: Datavilla — enriched-laget lukket og flyttet til serverless

Blok 2 (enriched) manglede `enriched:`-blokke for ti kilder, og de jobs der var triggeret lå
halvfærdige: fire grønne, to fejlede, otte aldrig kørt. Denne opgave lukkede laget helt — først ved
at kollapse de 18 per-system enrich-jobs til ét, så ved at flytte det ene job til serverless, og
til sidst ved at bevise det live og merge det.

Byggedetaljerne er dokumenteret trin for trin af builderen i
`2026-08-02-datavilla-enriched-remaining-sources.md` (fem trin, ~74 KB). Denne fil dækker det
builderen per definition ikke kunne skrive: hvad der skete efter dens sidste commit.

## Step 1: Deploy, live-bevis, verifikation og merge

**Author:** main

### Prompt Context

**Verbatim prompt:** "ja, merge og push. Hvor langt er vi lige nu?" (efter en forudgående "YES" til
spørgsmålet "Skal jeg køre deploy og derefter trigge jobbet?")

**Interpretation:** Benny godkendte den destruktive deploy, og efter grøn kørsel og verifikation
skulle arbejdet merges til master og pushes. Derefter ville han have et samlet statusbillede.

**Inferred intent:** Han ville ikke have flere delrapporter — han ville have laget lukket og et
troværdigt overblik over hvor projektet faktisk står. Underforstået at "grøn kørsel" ikke er nok;
tallene skal holde mod raw.

### What I did

Deployet skete i tre runder, fordi de to første afdækkede fejl.

Første runde deployede den classic-baserede samling (18 jobs → 1). `bundle plan` viste præcis
`2 to add, 0 to change, 36 to delete, 36 unchanged` — de 36 sletninger var 18 enrich-jobs med
tilhørende permissions, de 36 uændrede var ingest-jobbene. Planen blev læst igennem før apply,
netop fordi den var destruktiv.

Anden runde deployede serverless-varianten og trigged run `738961088735741`. Den kørte 27,5 minutter
og fejlede fuldstændigt: 117 iterationer, alle røde. 117 = 39 sources × 3 forsøg, altså retries der
fungerede efter hensigten mod en fejl der ikke var transient.

Tredje runde deployede `.cache()`-fixet og trigged run `202397189629227`. Den blev grøn: 39/39
iterationer på 15,6 minutter, ingen retries brugt, median 71 s per source og max 320 s.

Verifikationen var to uafhængige pas. Rækketal: jeg genererede SQL ud fra repoets egen
`current_strategy()` så hver kilde blev tjekket med sin egen semantik — `scd2_current` for 30 kilder,
`append_latest_per_key` og `append_latest_batch` for 7, `snapshot_all` for 2. Resultat: 39 tabeller,
387.417 rækker, nul afvigelser. Typning: 41 kolonner med `try_cast`-baserede transforms, hvor
non-null-count blev sammenlignet mellem raw og enriched. Nul tab.

Merge var fast-forward (`git merge --ff-only`), seks commits fra `664ae7a` til `f547312`, pushet til
origin. Bagefter ryddede jeg branch og worktree, plus fire ældre merged branches.

### Why

Deploy og jobkørsel er mains rolle, ikke builderens — det står i `src/databricks.yml` linje 8, og
den arbejdsdeling har holdt gennem hele projektet. Builderen bygger og tester offline; kun main har
den kontekst og de rettigheder der skal til for at røre dev.

Verifikationen blev bygget på repoets egen `current_strategy()` frem for håndskrevet SQL, fordi
current-view betyder tre forskellige ting afhængigt af `history`. Et håndskrevet filter ville have
været mit gæt på semantikken, ikke motorens. Da hele pointen var at kontrollere motoren udefra,
skulle sammenligningen bruge den samme definition af "gældende række" som motoren selv.

### What worked

`bundle plan` viste sig at være det rigtige værktøj før en destruktiv deploy. Det er ikke noget jeg
plejer at række efter — jeg tjekkede først om kommandoen fandtes — men den gav præcis den
bekræftelse der manglede: at ingest ikke blev rørt.

Fast-forward-merge frem for merge-commit holdt historikken lineær, og `git rev-list master ^branch`
bekræftede at branchen var ren efterkommer inden.

At generere verifikations-SQL fra config i stedet for at skrive den i hånden fangede en fejl jeg
ellers ville have overset: koinly-kildernes raw-kolonner har mellemrum (`Sent Amount`) og bliver
snake_case'et i enriched. Min første version brugte raw-navnet mod enriched-tabellen og fejlede med
`UNRESOLVED_COLUMN`. Fixet var at bruge repoets egen `to_snake_case()` — igen: brug motorens
definition, ikke din egen.

### What didn't work

Den første serverless-kørsel fejlede på hver eneste iteration:

```
engine.py:108   cleansed = cleansed.cache()
[NOT_SUPPORTED_WITH_SERVERLESS] PERSIST TABLE is not supported on serverless compute. SQLSTATE: 0A000
```

Jeg havde forudsagt den forkerte fejl. Inden kørslen skrev jeg at tre ting blev testet samtidig, og
at 8 samtidige iterationer mod `_ops.run_log` var den mest sandsynlige kandidat til at vælte. Det
var det ikke — iterationerne nåede aldrig så langt. Concurrency-risikoen er stadig utestet.

SQL-verifikationen faldt undervejs på en afbrudt forbindelse, fordi jeg sendte alle 39 subqueries i
én statement. Løsningen var at køre i bidder på fire-fem med retry. Trivielt, men det kostede tid.

To gange fejlede Databricks-kald med en fejl der ikke lignede sin årsag. Første gang var
`FileNotFoundError [WinError 2]` fra Python-subprocess, fordi `az` på Windows er `az.cmd` og ikke
findes for `subprocess.run`. Anden gang var HTTP 400 med:

```
IncorrectClaimException: Expected iss claim to be: https://sts.windows.net/4988b4cb-.../,
but was: https://sts.windows.net/ec009f06-.../
```

Bennys `az`-context var skiftet til SEGES-tenanten midt i sessionen. Ingen af de to fejl siger noget
om det egentlige problem, og begge kostede et par forsøg at læse rigtigt.

En agent døde undervejs på `API Error: Response stalled mid-stream` umiddelbart efter at have
kvitteret på opgaven. Jeg tjekkede worktreen for reddet arbejde før genstart — den var ren, så der
var intet at hente, men vanen er rigtig.

### What I learned

**Retries betaler tre gange for den samme lektion når fejlen er deterministisk.** `max_retries: 2`
blev sat for at overleve `AZURE_QUOTA_EXCEEDED_EXCEPTION`, som er ægte transient. Mod en
kode-inkompatibilitet gjorde de 39 fejl til 117 og kørslen tre gange så lang, uden nogen chance for
at hjælpe. Det er ikke et argument mod retries, men på en første kørsel af en ny compute-model kunne
`max_retries: 0` have givet samme information på en tredjedel af tiden.

**`for_each` isolerer per iteration.** Jeg påstod undervejs at en fejl i iteration 38 ville koste
hele kørslen. Det er forkert, og beviset lå allerede i vores egne data: det fejlede kraken-job havde
én iteration SUCCESS og én FAILED i samme run.

**Et `job_cluster` lever hele job-runnet ud.** Jeg advarede om at autotermination på 10 minutter
kunne rive clusteret ned mellem for_each-iterationer. Det gælder idle-tid, og et for_each med
`concurrency: 1` er ikke idle. Bekymringen var ubegrundet.

**Predictive optimization lukkede et åbent spørgsmål uden arbejde.** `DESCRIBE TABLE EXTENDED` viste
`Type = MANAGED` og `Predictive Optimization = ENABLE (inherited from METASTORE)`. Den daglige
full-overwrite rydder altså op efter sig selv. Det var billigere at slå op end at designe en
retention-strategi.

### What was tricky

Den egentlige friktion var at holde styr på hvad der var bevist og hvad der var påstået. Builderen
leverede en liste over hvad den ikke kunne verificere offline; kørslen bekræftede det meste, men
ikke alt, og et par ting på listen blev bekræftet af noget helt andet end det der stod. At holde den
bogføring ærlig — særligt at blive ved med at sige at omkostningen er uverificeret, når alt andet
blev grønt — krævede mere opmærksomhed end selve verifikationen.

Dertil kom en asymmetri i tallene der ser ud som datatab men ikke er det: `kraken_tradeshistory`
viser 158 i enriched hvor raw har 316. Raw er append-only med to batches, og current-view for append
er seneste batch. Samme forhold på `kraken_balance`. Det skulle forklares aktivt, ellers ligner det
en fejl.

### What warrants review

- Verifikations-scriptene ligger i scratchpad, ikke i repoet. `verify.sql` og `nullcheck.sql`
  genereres fra config og er reproducerbare, men de er ikke versionerede. Hvis samme kontrol skal
  køres efter hver enrich-ændring, hører de hjemme i `scripts/`.
- Concurrency-antagelsen er stadig utestet på det punkt der betød noget: at 8 samtidige iterationer
  kan skrive til `_ops.run_log` og køre `CREATE SCHEMA IF NOT EXISTS` uden at kollidere. Den grønne
  kørsel beviser at det virkede én gang, ikke at det er sikkert.
- Omkostningen mod loftet på 200-500 DKK/md er uverificeret. To kørsler er brugt, hvoraf den ene
  fejlede alle 117 iterationer. Første måneds faktura er det eneste rigtige svar.

### Future work

- Overvej `max_retries: 0` som default ved første kørsel af en ny compute-model, og hæv den når
  laget er bevist.
- Flyt verifikationen ind i repoet som et script, så "enriched matcher raw" kan køres som en
  kontrol frem for at blive genopfundet.
- De otte `.cache()`-steder i `write/` er den kendte blocker hvis ingest nogensinde skal på
  serverless. `write/scd2.py` er den svære, fordi `staged` og `changed` hver især konsumeres mere
  end én gang.
