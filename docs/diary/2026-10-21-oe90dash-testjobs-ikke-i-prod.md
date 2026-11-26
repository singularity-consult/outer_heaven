# Diary: oe90dash test-jobs må ikke deployes til prod

SEGES DataEstate2026 (DAB-bundle). oe90dash unit test-jobs (master + 10 UT) og e2e-jobbet var defineret for alle targets inkl. prod. Unit tests trunkerer tabeller og skal efter dash-dokumentationen kun køre i dev og test. Målet var at fjerne dem fra prod uden at ændre den resolvede konfiguration i dev og test.

## Step 1: Flyt jobs fra top-level resources ind i targets.dev/test, udkommentér prod

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** (saniteret) Repo: C:\claudes_folder\repos\DLBR-DataEstate2026 (SEGES customer repo; Benny explicitly instructed this change). Create a NEW worktree + branch `feature/oe90dash-testjobs-ikke-i-prod` from `origin/main` (git fetch first). [...] Goal: the oe90dash test jobs must no longer be deployed to the prod target [...] move the job definitions from top-level `resources:` into `targets.dev.resources` and `targets.test.resources` (fully merged with each target's existing overrides, so each target's resolved job config is unchanged), and comment out the whole `targets.prod` block [...] Validation (mandatory, read-only) [...] Commit with author and committer [Bennys kunde-identitet] [...] `git push -u origin feature/oe90dash-testjobs-ikke-i-prod` (normal push). No PR, no deploy/release, no job runs.

(Prompten fra lead er forkortet med [...] her; den fulde tekst indeholdt også krav til diff-validering og rapport.)

**Interpretation:** Top-level jobs i en included yml deployes til alle targets; target-overrides kan kun merge. Løsningen er derfor at definere jobbene kun under dev og test.
**Inferred intent:** Prod skal være fri for jobs der kan TRUNCATE prod-tabeller, med en dokumenteret vej tilbage.

### What I did
Ny worktree `.claude/worktrees/oe90dash-testjobs-ikke-i-prod` fra origin/main (818ba3d). Baseline `databricks bundle validate -t {dev,test,prod} -p {dev,test,prod} -o json` (CLI v0.291.0) gemt i `%TEMP%\oe90dash_val`. Et lille Python-generatorscript byggede de nye filer ud fra originalteksten: hver target-override (name, email, job_clusters, schedule) beholdt ordret, og top-level `permissions`/`tasks`/`tags` lagt ind i dev med YAML-ankre og genbrugt i test og i den udkommenterede prod-blok via aliaser. Dansk header-kommentar forklarer hvorfor. Efter-validate i alle tre targets og en JSON-sammenligning (sort_keys, listerækkefølge bevaret). Commit 2bbba45 som Benny, pushet.

### Why
Kun ved at fjerne jobbene fra top-level resources forsvinder de fra prod. Ankre undgår at duplikere 11 tasklister og holder kommentarerne ét sted.

### What worked
DAB resolver plain YAML-ankre/aliaser på tværs af targets i samme fil fint. Resultat: dev og test 30 jobs før og efter, de 12 berørte jobs byte-identiske i resolved JSON, resten af bundlen identisk. Prod 30 til 18 jobs, præcis de 12 test-jobs fjernet, alle øvrige jobs uændrede.

### What didn't work
Kontrol af genaktivering: med prod-blokken midlertidigt afkommenteret var prod IKKE identisk med før. Sammenligningen gav `reenabled prod identical to before (whole bundle): False`, med diff i `job_clusters` for de 11 jobs med cluster: før havde prod `azure_attributes: {availability: SPOT_WITH_FALLBACK_AZURE, first_on_demand: 1}`, som var lækket ind fra DEV-cluster-variablen i top-level-definitionen via merge. Efter genaktivering får prod det rene PROD-cluster. Ikke replikeret, da prod alligevel er udkommenteret; noteret til Benny.

Også `grep -nP '[\x{2013}\x{2014}]'` fejlede med `grep: -P supports only unibyte and UTF-8 locales`; tjekket i Python i stedet.

### What I learned
Target-overrides i DAB dybde-merger new_cluster, så felter fra top-level cluster-variablen lever videre i andre targets. Eksempel: test-jobbenes cluster i prod havde spot-attributterne fra DEV-variablen.

### What was tricky
Relative notebook-stier (`../tests/...`) resolves relativt til filen, så flytning inden for samme fil er sikker. Arbejdskopien er CRLF (autocrlf=true), filerne skrevet som LF; git normaliserer. Flyttede originalkommentarer indeholdt 9 lange tankestreger, erstattet med bindestreg.

### What warrants review
`git show 2bbba45` i DLBR-DataEstate2026. Diff er stor (fuld omstrukturering), men den resolvede JSON er beviset. Deploy til prod vil få DAB til at slette de 12 pausede jobs i prod.

### Future work
Ved evt. genaktivering i prod: beslut om spot-attributterne skal med. Branch har ingen PR endnu.
