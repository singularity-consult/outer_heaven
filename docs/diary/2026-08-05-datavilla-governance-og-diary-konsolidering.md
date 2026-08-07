# Diary: Datavilla — miljøbeslutning, diary-konsolidering og deploy under to Azure-identiteter

Tre stykker arbejde der faldt ud af drift-opgaven uden selv at være byggearbejde: beslutningen om
at opgive multi-miljø, opdagelsen af at diaries om personlig økonomi lå i et offentligt repo, og
en teknik til at deploye mod ét Azure-tenant mens en anden session arbejder mod et andet.

De hører sammen fordi de alle handler om rammerne omkring projektet frem for om koden i det.

## Step 1: Multi-miljø udgår — og nedrivningen udskydes med en reminder

**Author:** main

### Prompt Context

**Verbatim prompt:** "en reminder besked ville være fint, dagligt batch bør køre midnat og jeg har
besluttet kun at have mit dev-miljø. Jeg er jo eneste bruger, så at lave noget direkte i et
produktionsmiljø (som så hedder \"dev\") er fuldt ud acceptabelt i dette, isolerede, scenarie"

Efterfulgt af: "lad ressourcer og terraform være for nu. Noter det og remind mig om tre måneder"

**Interpretation:** Blok 5 (multi-miljø bundle-targets) udgår af planen. Drift-opsætningen skal
bygges simpelt for dev alene. De ubrugte test- og prod-ressourcer skal stå indtil videre, men
beslutningen skal genbesøges.

**Inferred intent:** Han vil ikke betale kompleksitetsprisen for en miljøadskillelse han er den
eneste bruger af. Samtidig vil han ikke træffe nedrivningsbeslutningen i samme åndedrag — den skal
have lov at modne.

### What I did

Fjernede multi-miljø fra drift-opgavens rammer og verificerede hvad beslutningen efterlod:
`rg-datavilla-test` og `rg-datavilla-prod` står begge fuldt udbyggede med ni ressourcer hver —
Databricks workspace, to storage accounts, key vault, VNet, NSG og en access connector.

Oprettede en cloud-routine (`trig_01YQnRzNpL52M9JhLx5ZcUVw`) der fyrer 2026-11-05 kl. 08:00 UTC og
gengiver beslutningen, hvad der står i de to ressourcegrupper, argumentet for og imod nedrivning,
og at nedrivning skal køre plan-før-apply. Prompten er self-contained, fordi cloud-agenten hverken
har adgang til Azure eller lokale filer.

Skrev beslutningen ind i `command-deck/datavilla/status.md` sammen med routine-ID'et.

### Why

Argumentet mod at rive ned med det samme er ikke økonomisk — tomme storage accounts og en ubrugt
key vault koster småpenge, og et Databricks workspace uden kørende clusters brænder ingen DBU. Det
er at ressourcerne er ubrugt kompleksitet: de ligger i Terraform-state og dukker op i hver `plan`.

Men det argument bliver ikke svagere af at vente tre måneder, og Benny havde ikke lyst til at træffe
den beslutning midt i en drift-opgave. En reminder er den rigtige form: den koster intet nu og sikrer
at beslutningen ikke bare glider ud i glemsel.

### What worked

At skrive routine-prompten som ren gengivelse frem for som en opgave. Cloud-agenten kan ikke tjekke
noget som helst — den har hverken Azure-adgang eller repoet — så en prompt der bad den "undersøge
status" ville have produceret gætværk. Den bliver eksplicit bedt om ikke at undersøge noget.

Blast radius ved beslutningen er reelt lille, og det er værd at have skrevet ned hvorfor: raw er
append-only med SCD2, og enriched er en full-overwrite-projektion der altid kan genskabes fra raw.
Et uheld i "produktion" koster en gen-kørsel, ikke data.

### What didn't work

Intet fejlede i dette trin. Routinen blev oprettet i første forsøg.

### What I learned

**En reminder er et legitimt svar på en beslutning der ikke haster.** Fristelsen var at presse på
for en afgørelse, fordi ressourcerne står der og "burde" ryddes. Men beslutningen bliver ikke bedre
af at blive truffet hurtigt, og alternativet til at udskyde er ikke at beslutte — det er at glemme.

**IaC ændrer risikoprofilen ved at rive ned.** Normalt er "riv det ned" en énvejsdør. Med Terraform
er den ikke: en `apply` genskaber det hele. Det burde gøre nedrivning til det lette valg, og det er
værd at pege på når beslutningen tages om tre måneder.

### What was tricky

At holde routine-prompten fri for det den ikke kan vide. Den skal beskrive tilstanden som den var
5. august, ikke som den måtte være i november — ellers ville den påstå noget forældet med
selvsikkerhed. Løsningen var at datostemple beskrivelsen eksplicit i selve teksten.

### What warrants review

- Routinen er en engangs-affyring. Bliver den ikke besvaret i november, forsvinder den lydløst.
  `ended_reason: "run_once_fired"` betyder at den er kørt, ikke at nogen reagerede.
- `command-deck/datavilla/status.md` er det eneste sted beslutningen og dens begrundelse står samlet.

### Future work

- November: tag stilling til `rg-datavilla-test` og `rg-datavilla-prod`.
- Navngivningen er nu misvisende — et miljø der hedder "dev" er de facto produktion. Det er
  accepteret bevidst, men det vil læses forkert af enhver der kommer til projektet senere.

## Step 2: Diaries om personlig økonomi lå i et offentligt repo

**Author:** main

### Prompt Context

**Verbatim prompt:** "3: diary skal være hvor den altid har været - det er ikke et bevidst valg fra
min side i projektrepo"

Efterfulgt af, da fundet blev fremlagt: "Reglen du nævner er rigtige - men lige i dette tilfælde, og
hvis det udelukkende er finasielle relationer - så lad det ligge i outer_heaven"

**Interpretation:** Diaries hører i outer_heaven per skillen; at otte datavilla-diaries lå i
projektrepoet var ikke et valg. Efter fundet: flytningen skal ske alligevel, men kun hvis indholdet
er begrænset til finansielle relationer.

**Inferred intent:** Han vil have ét sted at lede efter diaries. Men han vil ikke publicere mere om
sin privatøkonomi end institutionsnavne — betingelsen er en reel gate, ikke en formalitet.

### What I did

Diary-skillen siger at diaries hører i outer_heaven, aldrig i projektrepoet. Men optællingen viste
to konkurrerende praksisser: 34 filer i outer_heaven, hvoraf otte handlede om datavilla, og otte
filer i datavilla-repoet — alle fra 23. juli og frem. Praksis havde skiftet undervejs uden at nogen
besluttede det.

Før flytning tjekkede jeg to ting. Først at `outer_heaven` er **PUBLIC** mens `datavilla` er privat.
Dernæst at Bennys egen memory-regel siger: *"Disse er personlige finansielle data → hører i lokal
memory, ikke i git (command-deck/outer_heaven)."*

Det gjorde flytningen til et spørgsmål om eksponering frem for om filplacering. Jeg scannede derfor
begge sæt for credentials, wallet-adresser, IBAN, kontonumre, beløbsmønstre og personnavne. De
eksisterende ti offentlige filer var rene: ingen credentials, kun secret-*navne* som
`kraken-privat-api-key`, og de beløb der fandtes var de syntetiske erstatninger (`12345.67`,
`9999.99`) fra tidligere purges. De otte i datavilla var også rene — ingen wallet-adresser, ingen
personnavne, og den ene IBAN var eksplicit dokumenteret som syntetisk (`DK0000000000000000`).

Det eneste reelle identifikatorfund var firmaets Pleo `company_id`, som teksten selv markerer som
non-secret config.

Efter Bennys betingede ja flyttede jeg de otte med `datavilla-`-præfiks som de øvrige, rettede en
krydshenvisning der pegede på den gamle placering, og fjernede originalerne fra datavilla i en
separat commit.

### Why

Skillens begrundelse for centralisering er god: diaries skal kunne læses i én sweep af
`work-style-insight`, og spredte filer kan ikke aggregeres. Men skillen er skrevet med kundeprojekter
i tankerne — "keeps customer repos clean" — og forudså ikke et projekt hvor projektrepoet er *mere*
privat end diary-repoet.

Derfor var det ikke nok at følge reglen. Betingelsen skulle verificeres først, og Benny stillede den
selv præcist: udelukkende finansielle relationer.

### What worked

At scanne før flytning frem for efter. Havde jeg flyttet først og tjekket bagefter, ville et fund
have krævet history rewrite på et offentligt repo — en helt anden operation end at lade være.

At bruge Bennys egen betingelse som konkret checkliste. "Udelukkende finansielle relationer" kunne
oversættes direkte til fem søgemønstre, og resultatet var afgørbart frem for et skøn.

### What didn't work

Intet teknisk fejlede. Men jeg lagde selv op til at appende det manglende trin til builderens
eksisterende diary-fil — hvilket ville have brudt skillens regel om ikke at redigere filer fra
tidligere sessioner. Fangede det ved at læse skillen ordentligt inden jeg skrev.

### What I learned

**En regel om placering kan skjule et spørgsmål om eksponering.** Skillen taler om hvor filer hører
hjemme, ikke om hvem der kan læse dem. I langt de fleste projekter falder de to sammen. Her gjorde
de ikke, og forskellen var kun synlig fordi repo-visibiliteten blev tjekket.

**"Det var ikke et bevidst valg" er ikke det samme som "det var forkert."** Builderne der begyndte at
skrive i datavilla-repoet ramte utilsigtet en placering der var mere forsigtig end reglen krævede.
Det er værd at bemærke inden man retter en afvigelse: afvigelsen kan være bedre end normen.

### What was tricky

At skelne mellem hvad der er følsomt og hvad der bare føles følsomt. Institutionsnavne — Kraken,
Koinly, Kronjylland, Revolut, Pleo, CorPay, e-conomic — er en profil over finansielle relationer,
men de er ikke credentials og ikke beløb. Den vurdering er Bennys, ikke min, og pointen var at
fremlægge den præcist nok til at han kunne træffe den.

### What warrants review

- Git-historikken i outer_heaven indeholder de ti oprindelige filer uanset hvad. Skulle noget
  vise sig at burde fjernes, kræver det history rewrite på et offentligt repo.
- Scanningen dækkede fem mønstre. Den fandt ikke noget, men fravær af hits er ikke bevis for at
  der intet er — kun at de mønstre jeg tænkte på ikke findes.

### Future work

- Overvej om diary-skillen skal have en eksplicit note om at tjekke repo-visibilitet når projektet
  rummer personlige data. Det er præcis den slags kant `improve-skill` findes til.

## Step 3: Deploy mod ét Azure-tenant mens en anden session arbejder mod et andet

**Author:** main

### Prompt Context

**Verbatim prompt:** "kør deploy nu med benny@singularityconsult.dk som aktiv axure account på dette
repo - jeg bruger bech@seges.dk i en anden claude terminal"

**Interpretation:** Deploy datavilla under Singularity-identiteten, uden at forstyrre den
SEGES-session der kører parallelt.

**Inferred intent:** Han vil have begge dele til at køre samtidigt. Den naive løsning — `az account
set` — ville have løst hans problem og skabt et nyt et andet sted.

### What I did

`az account set` er global: den skriver til `~/.azure/azureProfile.json` og påvirker enhver proces
på maskinen. Azure CLI har ikke per-terminal eller per-repo kontekst, så den oplagte kommando ville
have brækket den anden session midt i dens arbejde.

I stedet hentede jeg et Entra-token til den rigtige tenant uden at ændre noget:

```
export DATABRICKS_TOKEN=$(az account get-access-token \
  --subscription 83d6730c-6cac-45fe-b434-14aebbf109e5 \
  --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query accessToken -o tsv)
```

`--subscription` vælger konto uden at gøre den aktiv. Med `DATABRICKS_TOKEN` sat (og
`DATABRICKS_AUTH_TYPE=azure-cli` fjernet) bruger både CLI'en og Terraform-provideren det token
direkte. Verificeret begge veje: `databricks current-user me` svarede
`benny@singularityconsult.dk`, mens `az account show` fortsat svarede `bech@seges.dk`.

Alle efterfølgende deploys i sessionen kørte på den opskrift.

### Why

Problemet var reelt, ikke teoretisk. Tidligere i sessionen fejlede kald med:

```
IncorrectClaimException: Expected iss claim to be: https://sts.windows.net/4988b4cb-.../,
but was: https://sts.windows.net/ec009f06-.../
```

Og senere, da kontoen var skiftet igen:

```
AADSTS50020: User account '{EUII Hidden}' from identity provider
'https://sts.windows.net/52c45313-.../' does not exist in tenant 'Singularity Consult IVS'
```

Ingen af de to fejlbeskeder peger på det egentlige problem. De ligner adgangsfejl, men årsagen er at
den aktive konto hører til en anden kunde.

### What worked

Token-vejen løser problemet i den rigtige retning: i stedet for at ændre maskinens tilstand så den
passer til opgaven, giver den opgaven den identitet den skal bruge. Det gør også at to sessioner kan
arbejde mod hver sin tenant samtidigt uden at koordinere.

At verificere begge sider — hvem Databricks tror jeg er, og hvem `az` stadig peger på — frem for kun
den ene. Havde jeg kun tjekket at deployet virkede, ville jeg ikke vide om jeg havde ødelagt noget
for den anden session.

### What didn't work

Første forsøg på at uploade en notebook fejlede på noget helt andet:

```
Error: requirement failed: C:/Program Files/Git/Users/benny@singularityconsult.dk/zz_notif_test
is not absolute.
```

Git Bash oversætter Unix-lignende stier til Windows-stier før CLI'en ser dem. `MSYS_NO_PATHCONV=1`
løser det, og det rammer enhver Databricks-kommando der tager en workspace-sti som argument.

### What I learned

**`az account get-access-token --subscription` er den manglende brik for multi-tenant-arbejde.** Den
er ikke svær at finde, men den oplagte kommando er `az account set`, og den er destruktiv for andre
processer. Forskellen mellem "vælg konto for dette kald" og "gør denne konto aktiv" er hele pointen.

**Azure-fejlbeskeder om tenant-mismatch beskriver symptomet, ikke årsagen.** Begge de citerede fejl
ligner rettighedsproblemer. Genkender man ikke mønstret, bruger man tid på at tjekke roller og
grants i stedet for at kigge på `az account show`.

### What was tricky

Fristelsen til bare at køre `az account set` og skifte tilbage bagefter. Det ville have virket i de
fleste tilfælde — og fejlet præcis når den anden session lavede noget vigtigt i mellemtiden. En
løsning der virker "medmindre timingen er uheldig" er ikke en løsning i et miljø hvor to sessioner
kører side om side.

### What warrants review

- Tokenet er kortlivet (omkring en time). Til lange deploys skal det hentes forfra, ikke genbruges
  fra en tidligere kommando i samme session.
- Opskriften findes nu kun her og i `command-deck/datavilla/status.md`. Den hører reelt hjemme i
  projektets README, hvor den næste deploy vil lede.

### Future work

- Overvej at pakke token-hentningen i et lille script i `scripts/`, så deploy-opskriften er én
  kommando frem for tre eksporter der skal huskes i rigtig rækkefølge.
