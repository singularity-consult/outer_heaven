# Diary: DLBR SHIR — flyt VM-install til storage-downloads (firewall TLS-inspektion)

SEGES DataEstate2026 IaC. SHIR-VM'ens `installGW` CustomScriptExtension stod `Failed` fordi
`gatewayInstall.ps1` downloadede gateway-MSI fra go.microsoft.com og JRE fra javadl.oracle.com —
firewallens TLS-inspektion dræber begge udgående downloads. Opgaven: gendan den rene gamle
adf_shir-struktur (params + aktiv IRInstall-extension), men afvig kun i VM-install-laget ved at
hente alt fra storage (`stdlbrshirdiag`/`adfshir`) via en kortlivet SAS genereret on-the-fly i workflowet.
Main er sandheden for al øvrig infra.

## Step 1: Workflow-revert, bicep re-aktivering, ps1-omskrivning

**Author:** builder (outer_heaven:builder)

### Prompt Context

**Verbatim prompt:** "Du implementerer et stykke IaC-arbejde i en SEGES-kunderepo. Al kontekst er verificeret. Lav ændringerne, validér dem, men COMMIT/PUSH IKKE — stop og rapportér tilbage med diffs til review." (efterfulgt af fuld spec: repo/branch, scoping-princip "Main er sandheden pånær hvad der installeres på selve VM'en", verificeret rodårsag, referencemønster i dataestatedlbr-IaC/solutions/adf_shir, 5 låste beslutninger, 5 konkrete ændringer, hårde constraints, 3 åbne punkter at flagge).

**Interpretation:** Gendan det rene reference-mønster (artifacts-location + SAS + aktiv IRInstall), flyt alle VM-downloads til storage, revert workflow-hacks, slet orphan-scripts, rør ikke main-infra. Ingen commit/push.

**Inferred intent:** Få SHIR-redeploy til at lykkes bag firewallen uden langtids-secrets og uden at beskadige den kørende node, mens al ikke-VM-infra forbliver mains sandhed.

### What I did
- `deploy_adf_shir.yml`: fjernede den ucommittede push-trigger (hardcoded til feature-branchen) og `|| 'dev'`-defaults; env-guarden er bevaret kommenteret som på main (main selv har den kommenteret — så "gendan guard" = match main, ikke uncomment).
- `template_adf_shir.yml`: skrev om til mains minimale mønster (checkout + azure/login + arm-deploy) og tilføjede ét step "Generate short-lived artifacts SAS" der minter en 2t container-SAS (`New-AzStorageContainerSASToken -Permission rl -Protocol HttpsOnly`), masker den (`::add-mask::`), og sender den som `_artifactsLocationSasToken` til arm-deploy. Fjernede alle imperative hacks (Get-names, Diagnose-TLS, Re-register-SHIR, Reset-VM-password, DB2-install). Beholdt 2026-repoets egne navne (`secrets.ARM_*`, `vars.AZURE_RESOURCE_GROUP_NAME`).
- `main.bicep`: tilføjede `_artifactsLocation` (default `https://stdlbrshirdiag.blob.core.windows.net/adfshir/`), `@secure() _artifactsLocationSasToken`, `installForceUpdateTag string = utcNow()`, og `var scriptURL = '${_artifactsLocation}gatewayInstall.ps1?${_artifactsLocationSasToken}'`. Slettede den døde inline `listServiceSAS`-kommentarblok. Re-aktiverede `IRInstalltemplate` og passer artifactsLocation/SAS/forceUpdateTag ind. Lod `serviceEndpoints` (Microsoft.Sql + Microsoft.Storage) og al øvrig infra urørt.
- `nested/IRInstall.bicep`: tilføjede params `artifactsLocation`, `@secure() artifactsLocationSasToken`, `forceUpdateTag`; satte `forceUpdateTag` på extensionen; udvidede `commandToExecute` til `-gatewayKey ... -ArtifactsLocation ... -ArtifactsLocationSasToken ...` (i protectedSettings, krypteret).
- `nested/VMtemplate.bicep`: urørt — beholdt `computerName`-truncate-fix.
- `gatewayInstall.ps1`: tilføjede params `$ArtifactsLocation`/`$ArtifactsLocationSasToken`; ny `Get-ArtifactUrl`+`Download-Artifact`; fjernede ubrugte `Download-Gateway`; MSI hentes nu som `IntegrationRuntime.msi` fra storage; `Install-Gateway` bruger nu `$gwPath` i msiexec-arg i stedet for hardcoded `gateway.msi`; JRE skrevet helt om (Temurin ZIP → ryd `C:\Java` idempotent → `Expand-Archive` → find `bin\java.exe` → `JAVA_HOME` = runtime-roden, PATH opdateret kun hvis ikke til stede); DB2 ODBC tilføjet (hent `db2cli.zip`, extract til `C:\`, idempotent registry-registrering med samme nøgler som det fjernede pipeline-step).

### Why
Firewall-TLS-inspektion dræber kun de interne internet-downloads, ikke stien til storage (det er sådan fileUris allerede henter ps1'en). Ved at flytte MSI/JRE/DB2 til storage-downloads gennem den kortlivede SAS forbliver flowet download→install→register intakt, og den kørende SHIR beskadiges ikke før register-trinnet. `forceUpdateTag=utcNow()` opfylder kravet om at extensionen kører på hvert dev-deploy.

### What worked
- Read-only git (`git --no-pager diff`, `git show origin/main:...`) virker fint og bekræftede at branchens committede `deploy_adf_shir.yml` allerede er identisk med main; kun den ucommittede ændring skulle revertes.
- Reference-mønsteret i `dataestatedlbr-IaC/solutions/adf_shir` matchede 1:1 det ønskede (params, scriptURL, IRInstall med listAuthKeys i protectedSettings).

### What didn't work
- `git checkout -- .github/workflows/deploy_adf_shir.yml` (PowerShell) blev nægtet af sandboxen ("Permission to use PowerShell has been denied") — git-checkout vurderes destructive. Workaround: revert via Edit-tool i stedet (ren additiv diff, så det var sikkert).
- Sletning af orphan-scripts blev blokeret: både `Remove-Item ... install_db2cli.ps1 diagnose_tls.ps1` (PowerShell) og `rm` (Bash) nægtet af sandboxen. KAN IKKE slettes herfra — overladt til Benny som manuelt trin. Filerne er nu ubrugte (deres logik er flyttet ind i gatewayInstall.ps1 hhv. fjernet fra workflowet).
- `bicep build`/`az bicep build` kunne ikke køres: ingen bicep-binær på maskinen (`Glob **/bicep.exe` = intet) og både Bash og PowerShell exec nægtet. Bicep er IKKE lintet lokalt — kun manuel syntaks-gennemgang.

### What I learned
- Main's `deploy_adf_shir.yml` har env-guarden (`if:`) kommenteret ud allerede. "Gendan env-guarden (dev kun fra main)" i spec'en kan derfor ikke betyde uncomment, for så ville branchen afvige fra main i ikke-VM-lag. Korrekt fortolkning: match mains tilstand (guard kommenteret). Flagget til Benny.
- Bash-tool'et på denne maskine mangler `:` i git-revspec-stier (`origin/main:path` blev til `origin\main;path`). PowerShell `git show 'origin/main:path'` virker.

### What was tricky
- Temurin er ZIP, ikke Oracle's silent `.exe`. Den udpakker til en versioneret undermappe (fx `jdk8u492-b09-jre`), så `JAVA_HOME` kan ikke hardcodes — jeg finder `bin\java.exe` rekursivt og afleder roden. Idempotens løst ved at rydde `C:\Java` før extract; risiko: hvis en aktiv copy-activity låser java.exe under redeploy kan extract delvist fejle (flagget).
- SAS som `@secure()` param ført ind i en non-secure `var scriptURL` og videre til non-secure module-param: Bicep-warning (samme som reference-mønsteret). SAS havner uundgåeligt i extensionens *public* `settings.fileUris` (plaintext på ressourcen) — kun protectedSettings er krypteret. Kortlivet SAS (2t) begrænser blast radius.

### What didn't work (none beyond above)
Intet yderligere.

### What warrants review
- `template_adf_shir.yml`: SAS-overførsel til arm-deploy `parameters`-strengen — SAS indeholder `&`/`=`; verificér at arm-deploy parser `_artifactsLocationSasToken="<token>"` korrekt (alternativ: parametErfil). Kræver et faktisk dev-run.
- `gatewayInstall.ps1` JRE/DB2-blokke: kun verificerbare ved kørsel på VM'en. Tjek tracelog under `C:\WindowsAzure\Logs\Plugins\Microsoft.Compute.CustomScriptExtension\`.
- Deploy-SP'ens storage-rettigheder på `stdlbrshirdiag` (krav for `Get-AzStorageAccountKey`) — IKKE verificerbart fra repoet; ingen role-assignment i koden. BLOKERENDE hvis manglende.

### Future work
- Slet `infrastructure/adf_shir/install_db2cli.ps1` og `diagnose_tls.ps1` (sandbox blokerede sletning her).
- Afklar parameters.json vnet/subnet-prefixes (10.192.112.0/24) — ren infra, main er sandhed; revert eller behold? Benny beslutter.
- Overvej parametErfil frem for CLI-override til SAS hvis arm-deploy-parsing driller.
- Når DB2-driveren senere skal opgraderes: registry-registreringen er idempotent, men selve dll-overskrivning kan fejle hvis driveren er i brug under redeploy.

## Step 2: Merge main, review af builder-output, beslutninger, commit & push

**Author:** main

### Prompt Context

**Verbatim prompt:** "først rebase main ind i denne branch - ÆNDRE INTET I MAIN" (efterfulgt af afklaringer undervejs: "main er sandheden pånær hvad der installeres på selve VM (IR, DB2 Driver, JME)", svar på tre review-beslutninger, "Yes" til commit, "push it").

**Interpretation:** Bring mains sandhed ind i branchen uden at røre main, review builderens arbejde selvstændigt frem for at stole på rapporten, afgør de tre åbne punkter på verificeret grund, og ship (commit + push) når Benny giver ok.

**Inferred intent:** Stå på fast grund før et dev-deploy: branchen skal være main + kun VM-install-laget, koden skal være verificeret (ikke antaget), og historikken må ikke ødelægge andres arbejde.

### What I did
- Vurderede rebase vs merge: branchen var 27 foran / 20 bagud main, og main havde lige fået sit eget SHIR-subnet-arbejde (PR 16, de-6487) i `adf_shir/main.bicep`. Valgte **merge** frem for rebase (rebase = force-push på delt branch + replay af 27 commits hvoraf mange rører den fil main superseder). Stashede den ucommittede push-trigger-hack, `git merge --no-ff --no-commit origin/main` → **auto-merge uden konflikt** (mains `serviceEndpoints` og branchens edits lå i forskellige regioner). Commit `4ded489`, main urørt.
- Reviewede builderens fem filer selv via `git diff` frem for at stole på rapporten. Bekræftede: bicep-wiring korrekt, `gatewayInstall.ps1` storage-downloads + Temurin-ZIP-håndtering + idempotent DB2 + bevaret `Register-Gateway`, template tilbage til rent mønster.
- Gjorde det builderen ikke kunne pga. sandbox: **slettede** de to orphan-filer (`install_db2cli.ps1`, `diagnose_tls.ps1`) og **lintede bicep** (`az bicep build` → exit 0, kun `no-hardcoded-env-urls`-warning på `core.windows.net`-URL'en).
- Fangede en utilsigtet artefakt: `az bicep build` efterlod `main.json` (kompileret ARM) som jeg var ved at stage; bekræftede via `git log -- main.json` (tomt) at den aldrig var committet, og fjernede den før commit.
- Committede de 7 ændringer som `3547210` med korrekt identitet `Benny Christiansen <bech@seges.dk>`, og pushede til `origin/feature/shir-fixes-shared-deploy` (fast-forward, ingen force).

### Why
"Main er sandhed pånær VM-install" gjorde merge til det rigtige værktøj og gav et enkelt resolutions-princip. Selvstændigt review frem for tillid til builder-rapporten er Bennys norm (vær aldrig skråsikker uden verifikation). De tre beslutninger skulle afgøres på fakta, ikke antagelser.

### What worked
- Merge auto-resolverede rent — bekræftede at merge-valget over rebase var rigtigt, og at konflikt-overfladen (kun `main.bicep`) var triviel fordi ændringerne lå i forskellige regioner.
- **Live-verifikation af subnet-spørgsmålet** afgjorde beslutning #2 hårdt: `az network vnet list -g SHARED` viste at `vnet-dlbr-shir` faktisk er `10.192.112.0/24` (subnet `.0/27`, bastion `.32/27`) — præcis branchens `parameters.json`-værdier. Mains `main.bicep`-defaults (`10.163.134.x`) er stale. Så her er branchen sandheden, ikke main — params skal blive.
- `az` var logget ind som `bech@seges.dk` på rette sub (`DLBR DataEstate`), så read-only Azure-opslag (VNet, extension-state, blobs) kunne afgøre tvivl undervejs.

### What didn't work
- Push afvist første gang: `! [remote rejected] ... refusing to allow an OAuth App to create or update workflow .github/workflows/deploy_adf_shir.yml without workflow scope`. Aktiv gh-konto var desuden `singularity-consult` (forkert for en segesdk-repo). Løst ved at Benny kørte `gh auth switch -u bechseges; gh auth refresh -h github.com -s workflow` interaktivt (kun han kan), hvorefter pushet lykkedes som `bechseges`.
- Role-assignment-opslag for at verificere SP'ens `listKeys`-rettighed fejlede gentagne gange med `(MissingSubscription)` selv med sat kontekst — sandsynligvis fordi kontoen ikke må læse RBAC. Efterladt til at blive afgjort ved første dev-run.

### What I learned
- `git ls-files <path>` viser index-indhold, ikke HEAD — en fil jeg lige havde `git add`'et fremstod som "tracked" selvom den aldrig var committet. `git log -- <path>` (tomt) er den korrekte test for "var den nogensinde i repoet".
- Konto-nøgle-SAS (`Get-AzStorageAccountKey`) kræver `listKeys`/Contributor — ikke `Storage Blob Data Reader` som jeg fejlagtigt sagde tidligere. Pragmatisk er det dog mere robust, fordi deploy-SP'en der i forvejen deployer i RG `SHARED` næsten helt sikkert har Contributor; user-delegation-SAS ville kræve en data-plane-rolle der måske ikke findes.

### What was tricky
- At skelne "branch-divergens der skal smides væk" fra "branch-værdi der er den reelle sandhed". `parameters.json`-subnettet så ud som ren infra-divergens (og dermed kandidat til revert under "main er sandhed"), men live-VNet'et viste det modsatte. Lektien: verificér mod miljøet før man kalder noget for stale.

### What warrants review
- Første dev-deploy er den reelle verifikation af tre uafklarede risici: (1) deploy-SP'ens `listKeys`-adgang på `stdlbrshirdiag` — fejler steppet `Generate short-lived artifacts SAS` med AuthorizationFailed hvis manglende; (2) om 905 MB-MSI'en faktisk er installerbar (`msiexec` på VM'en); (3) om SAS'ens `&`/`=` parser rent gennem arm-deploy `parameters`-strengen.

### Future work
- Kør dev-deploy (`gh workflow run deploy_adf_shir.yml --ref feature/shir-fixes-shared-deploy -f environment=dev`) og bekræft: SHIR online + registreret til `id-dlbr-shir`, gateway+JRE+DB2 installeret, admin-credentials uændrede.
- Den committede `bec-systemate`-identitet på commit `1834c96` (subnet-params) er forkert pr. Bennys regler, men ligger i historikken; ikke rettet (ville kræve history-rewrite).
