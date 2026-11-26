# Diary: Central fejlmail for alle jobs i kunde-dataplatformens bundle

Kunden har fået en dedikeret overvågnings-mailgruppe, og alle jobs i Databricks-bundlen skal sende fejlbeskeder dertil. I dag har kun 6 af 29 job-ressourcer mail, fordelt på tre forskellige adresser (en fælles teamadresse og to varianter af en ældre dashboard-overvågningsgruppe), og seks jobs der kører planlagt i prod har ingen alarm. Målet er én kilde til modtageren, så nye jobs ikke glemmer den.

## Step 1: Kortlægning, afgrænsning og beslutninger (lead)

**Author:** outer_heaven:lead

### Prompt Context

**Verbatim prompt:** "vi har nu fået en rigtig mailgruppe, som alle jobs skal sende fejlbeskeder til: [adresse udeladt, offentligt repo]"
**Interpretation:** Saml fejlnotifikation for alle bundle-jobs på den nye gruppe; afklar miljøer, eksisterende modtagere og mekanisme før bygning.
**Inferred intent:** Driftsalarmer skal nå de rette personer pålideligt, uden at hvert nyt job afhænger af at udvikleren husker det.

### What I did
Læste bundle-roden, de inkluderede variabelfiler og alle workflow-YAML'er på main og kortlagde med et lille pyyaml-script pr. job og target: schedule/trigger-status og notifikationer. Tjekkede bundle-referencen for en central mekanisme. Forsøgte at slå mailgruppen op i Entra ID read-only.

### Why
Briefen antog en blanding af job- og task-niveau; det skulle verificeres, og der skulle findes en mekanisme der fanger fremtidige jobs.

### What worked
Kortlægningen afslørede at alle eksisterende notifikationer er på job-niveau (ingen på task-niveau), mest i target-override-blokke, og at flere jobs kalder andre jobs via run_job_task (forælder/barn), hvilket giver dobbeltmails hvis begge mailer.

### What didn't work
`az ad group list --filter "startswith(displayName,'...')"` gav `ERROR: Insufficient privileges to complete the operation.` Gruppens evne til at modtage eksterne mails kan derfor kun afgøres ved en bevidst fejlet kørsel. En første worktree blev auto-ryddet fordi den var uændret; en ny blev oprettet på en navngiven gren.

### What I learned
Bundle `presets` har ingen nøgle for email-notifikationer, og YAML-anchors virker ikke på tværs af include-filer. Den eneste helt automatiske vej er en Python job_mutator, som kræver venv og en matchende databricks-bundles-pakke i CI. Alle targets kører `mode: production`, så dev-schedules kører rigtigt og ville støje.

### What was tricky
Afvejningen mellem automatik (mutator) og ingen ny teknologi i deploy-pipelinen. Valget faldt på en kompleks variabel pr. target plus en CI-vagt, der fejler ved PR hvis et job mangler referencen.

### What warrants review
At dev ikke får modtager, at test og prod gør, og at CI-vagten faktisk fanger et job uden referencen.

### Future work
Bevidst fejlet testkørsel for at bevise modtagelse (afgøres senere). Et parallelt nyt job på en anden gren skal tilpasses variablen før merge.

Beslutninger (produktejer): test og prod mailer, dev ikke; alle tre gamle adresser erstattes; variabel plus CI-vagt; mail på alle jobs inkl. børn; ingen duration-warning; no_alert_for_canceled_runs og no_alert_for_skipped_runs tages med.

## Step 2: Variabel, 29 jobs, CI-vagt og bevis pr. target (builder)

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** "OPGAVE: Saml fejlmail for alle Databricks-bundle-jobs på én modtager via en kompleks variabel pr. target + en CI-vagt." (fuld brief fra lead; adresser, stier og jobnavne udeladt her, offentligt repo)
**Interpretation:** Indfør én kompleks variabel med overvågnings-mailgruppen som modtager i test og prod og ingen i dev, brug den på job-niveau i alle 29 jobs sammen med no_alert-indstillingerne, fjern de tre gamle adresser og tilføj en vagt i PR-validate-workflowet. Kun `bundle validate`, ingen deploy.
**Inferred intent:** Én kilde til modtageren, og en PR kan ikke længere tilføje et job uden alarm.

### What I did
Tog et baseline-udtræk af den resolvede bundle (`databricks bundle validate -t <t> --profile <t> -o json`) for dev, test og prod før ændringen. Tilføjede variablen med gruppen som default og en override til `{}` under `targets.dev.variables` i bundle-roden. Indsatte `email_notifications: ${var...}` plus `notification_settings` lige efter `name:` i base-blokken for 17 jobs; for de 12 test-jobs, der kun defineres under targets med YAML-anchors, i både dev- og test-blokken. Hardkodede target-overrides blev slettet, en prod-only `notification_settings` på ét integrationsjob blev konsolideret ind i base, og de udkommenterede prod-blokke for test-jobs fik variabel-referencen i stedet for den gamle adresse, så en genaktivering bliver korrekt. Ændringerne blev lavet med et lille Python-script, der bevarer CRLF i arbejdskopien. Vagten er et pyyaml-script, der kaldes fra validate-workflowet efter `actions/setup-python@v5` og `pip install pyyaml==6.0.2`. Én commit, author sat eksplicit med `git -c user.name=... -c user.email=...`.

### Why
Default = gruppen betyder, at et fremtidigt target (eller en glemt override) mailer i stedet for at være tavs; kun dev skal aktivt fravælge. Vagten flytter "husk mailen" fra hukommelse til PR-checket.

### What worked
`workflow_failure_notifications: {}` som target-override accepteres af validate og resolver til `email_notifications: {}` på alle 29 dev-jobs; test har gruppen på 29 af 29, prod på 17 af 17 (test-jobs deployes bevidst ikke til prod). Et diff af baseline mod ny resolved JSON, med de to notifikationsfelter fjernet, viste nul forskelle i øvrige felter på alle tre targets: ændringen rører kun notifikationer. Vagten var grøn på grenen, rød på scratch-kopier med (a) manglende reference i base og i et target-only test-job, (b) hardkodet adresse i en prod-override og på task-niveau, og (c) det parallelle nye job fra en anden gren, som blev grønt med en fire-linjers rettelse.

### What didn't work
Ingen validate- eller vagt-fejl på den rigtige gren. Én egen fejl undervejs: et inline Python-kald fra Git Bash med en `/c/Users/...`-sti gav `FileNotFoundError: [Errno 2] No such file or directory: '/c/Users/.../scratchpad/base_dev.json'`, fordi Windows-Python ikke forstår MSYS-stier inde i en Python-streng (kun i argv bliver de oversat). Løst ved at `cd` til scratch og bruge relative stier.

### What I learned
En kompleks variabel kan overstyres til et tomt map pr. target, og et tomt `email_notifications` på job-niveau er gyldigt; der er ikke brug for `on_failure: []`. Variabel-overrides under `targets.dev.variables` i bundle-roden og i en inkluderet workflow-fil merges uden konflikt. Prod-workspacet indeholder færre jobs end dev/test, så "alle jobs" skal tælles pr. target, ikke globalt.

### What was tricky
Test-jobfilerne har ingen base-blok og genbruger tasks via anchors, så referencen skulle stå i hver target-blok. Vagtens dækningsregel: for et job med base-blok kræves referencen i base, fordi base deployes til alle targets, også targets som filen ikke nævner. For target-only jobs kræves den i alle target-blokke. Det er en smule strengere end briefens formulering ("base ELLER alle target-blokke"); bevidst valg. Lokal CLI er 1.21.0, CI kører 1.22.1.

### What warrants review
At dev ikke mailer (også det daglige master-job, som før mailede fra dev med den gamle teamadresse: en tilsigtet adfærdsændring). At vagtens strenghed for base-jobs er ønsket. At validate-workflowets nye steps faktisk kører på GitHub-runneren; det er kun simuleret lokalt med Python 3.12 og den pinnede pyyaml.

### Future work
Det parallelle nye job skal skifte sin hardkodede blok til variabel-referencen før merge, ellers bliver vagten rød. Bevidst fejlet kørsel i test for at bevise at gruppen modtager mail fra workspacet.
