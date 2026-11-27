# Diary: Test- og valideringsstrategi for Data Vault efter refresh (Grundfos)

Benny havde refreshet core-data i tre nye Snowflake-miljøer (dev, test, ny prod) på en VaultSpeed-genereret Data Vault med et curated-lag ovenpå. Et gammelt prod-miljø i en separat konto kører alle kilder undtagen én ny kilde. Målet var en dokumenterbar strategi for tre spørgsmål: er objekterne deployet korrekt, er dataene i vaulten korrekte, og er curated-laget korrekt i data og struktur. Desuden skulle der laves scripts, som han kan køre mod miljøerne.

## Step 1: Strategi og kravliste til scripts

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** grundfos. Jeg har nu refreshet data i cores dev- test- og nyt prod miljø. I det gamle prod miljø kører alle vores kilder undtagen [kilde redigeret], og de er det, de tre andre miljøer skal måles mod. De tre andre miljøer indeholder gammel prods data og [kilde redigeret]. Hvordan verificerer jeg 1. at alle datavault-objekter, er korrekt deployet 2 at datavault objekter indeholder den korrekte data. 3 at det curated lage oven på datavault indeholder korrekt data og struktur. Giv mig en test- og validerings strategi, som jeg kan dokumentere, og samtidig fortæl mig hvad du skal bruge for at generere i de scripts jeg skal fyre af mod mijøerne. Vi er på snowflake, og datavault er bygget via VaultSpeed
**Interpretation:** En strategi med et facit pr. spørgsmål, plus en præcis liste over det input, der skal til, før scripts kan genereres.
**Inferred intent:** At kunne godkende de nye miljøer før go-live med noget, der kan dokumenteres over for kunden.

### What I did
Jeg læste projektets VaultSpeed-viden og status i command-deck, før jeg svarede. Den vigtigste pointe var, at gammel prod ikke kan være det eneste facit, fordi den mangler én kilde og selv har kendte fejl. Strategien fik derfor fire facit'er: den genererede DDL/ETL, de tre nye miljøer indbyrdes, gammel prod eksklusive den nye kilde, og pre-staging for den nye kilde. Jeg bad om seks ting, blandt andet hvordan refresh var lavet, og metadata-udtræk fra information_schema.

### Why
Uden et klart facit pr. tjek bliver enhver afvigelse en diskussion. Metadata gør det muligt at generere scripts, der passer til de faktiske kolonnenavne, i stedet for at gætte.

### What worked
Den eksisterende projektstatus pegede direkte på kendte afvigelser (satellitnøgler uden åben række, forældreløse link-nøgler, hardkodede ghost-hashes). De blev en del af strategien som et register over kendte sager, så de ikke bliver genopdaget som nye fejl.

### What didn't work
Intet fejlede i dette trin.

### What I learned
I en VaultSpeed-vault kan hash keys og ghost-hashes være forskellige mellem miljøer, hvis hash-konfigurationen er ændret (multi-master mod single master). Derfor sammenlignes forretningsnøgler og antal, ikke hash-værdier.

### What was tricky
At holde strategien kort nok til at kunne dokumenteres og samtidig præcis om, hvad der er facit for hvad.

### What warrants review
Om de fire facit'er holder, når de første resultater kommer.

### Future work
Ingen ud over næste trin.

## Step 2: Metadata-analyse og fund

**Author:** main

### Prompt Context

**Speaker:** Benny
**Verbatim prompt:** 1 jeg har opdateret data på alle miljæer samme dag, men forskellige tidspunkter. Data skal ikke være 1:1 2. gammel prod ligger adskilt. 3: alle miljøer har samme skema-struktur for hhv. datavault og curated_layer: [schemanavne redigeret]. 4. DDL/ETL er ens fra dev-test-prod i nyt platform. Gammel prod er der sket nogle ændringer i portering til nyt miljø, så der er ikke meningsfuldt at sammenligne med 5: Ja de er stadig ude. 6: Metafiler er her: [sti redigeret]  Kun kilderne [kildeliste redigeret] er relevante
**Interpretation:** Svar på de seks spørgsmål. Metadata ligger klar til analyse.
**Inferred intent:** Få konkrete fund nu og scripts til resten.

Opfølgende prompt (Benny, verbatim): "[referencetabel redigeret] er ikke relevant længere. Ift BDV er vi kun interesseret i LNA- og LAS-tabellerne. Jeg har lavet en "new_meta" fil i samme mappe"

### What I did
Jeg sammenlignede metadata-CSV'erne for de fire miljøer med et Python-script. Derefter brugte jeg den nye fil med curated-kolonner og GET_DDL til at krydstjekke, at alle tabeller, som ny prods views refererer til i vaulten, findes. Til sidst sammenlignede jeg curated-kolonner mellem gammel og ny prod.

### Why
Deploy-spørgsmålet kan langt hen ad vejen besvares uden at røre Snowflake, når metadata er udtrukket. Det sparer en kørselsrunde.

### What worked
- Dev, test og ny prod havde identisk vault-struktur ned på kolonne, type og rækkefølge. Det besvarede spørgsmål 1 for vaulten uden en eneste query.
- Referencetjekket på DDL lukkede en advarsel, jeg selv havde rejst: at business vault var skrumpet kraftigt. Ny prods views bruger kun to BDV-tabeller, og begge findes.

### What didn't work
Min første advarsel om datatypeskift mellem gammel og ny prod var for bred. Da jeg greppede i ny prods DDL, viste det sig, at ingen af de omtypede kolonner bruges i curated. Jeg trak advarslen tilbage i det næste svar.

### What I learned
- En liste over views siger intet om, hvorvidt de kører. Et view kan stå i information_schema og alligevel fejle, hvis det refererer til et objekt, der er fjernet. Et compile-tjek pr. view er nødvendigt.
- En kolonnesammenligning af curated fandt ting, som tabellisterne ikke viste: en fjernet flag-kolonne i to facts, en testkolonne lagt ind som kolonne 1 i en fact, og en hash key, der havde skiftet type.

### What was tricky
Benny mente, at det ikke var meningsfuldt at sammenligne strukturen med gammel prod. For vaulten holder det, men ikke for curated, hvor konsumenterne (Power BI) afhænger af kolonnerne. Det måtte siges direkte.

### What warrants review
Referencetjekket er kun på tabelniveau, ikke kolonneniveau. Compile-tjekket i scriptene er det, der faktisk bekræfter, at viewene kører.

### Future work
Benny skal tage stilling til fundene: den fjernede flag-kolonne, testkolonnen, den manglende LAS-tabel og typeskiftet på hash-nøglen.

## Step 3: Valideringsscripts bygget af builder

**Author:** main (opsummerer builder-agentens rapport)

### Prompt Context

**Speaker:** agent brief
**Verbatim prompt:** Briefen fra main bad om tre Snowflake Scripting-filer (vault-tjek, curated-tjek, relationstjek), et stdlib-Python-sammenligningsscript med tolerance og PASS/WARN/FAIL, og en README. Scope blev opdateret midt i bygningen med BDV-indsnævring og den nye metadatafil.
**Benny's own words:** none quoted in the brief
**Interpretation:** Scripts, der kan køre uændret i fire miljøer i separate konti, med resultaterne sammenlignet lokalt.
**Inferred intent:** Gentagelig validering uden cross-account-adgang.

### What I did
En builder-agent byggede et planner/executor-mønster i Snowflake Scripting. En INFORMATION_SCHEMA-query genererer én check-query pr. objekt. En løkke kører hver query isoleret i en EXCEPTION-blok. Resultaterne samles som JSON og returneres via FLATTEN, så der ikke kræves rettighed til at oprette temp-tabeller. `compare.py` sammenligner de tre nye miljøer indbyrdes og ny prod mod gammel prod eksklusive den nye kilde. Integritetsbrud tæller altid som FAIL, mens antal sammenlignes med 2 % tolerance.

### Why
Miljøerne ligger i separate Snowflake-konti, så sammenligningen må ske uden for Snowflake.

### What worked
`compare.py` kørte på de rigtige metadata og blev testet på syntetiske resultatfiler. Forælder-opslaget for link-nøgler (udledt af kolonnenavne, hvor det længste hub-præfiks vinder) blev simuleret offline, og alle nøgler fandt en forælder.

### What didn't work
Builderen rettede tre ting i egen kode under selvreview:
- `SQLERRM` blev brugt direkte i en konkatenering og blev ændret til først at blive tildelt en variabel.
- Rapporten henviste til en detaljefil, der ikke blev skrevet.
- Støj fra kolonnerækkefølge og VARCHAR-længder gav næsten 600 rækker og blev samlet til én WARN pr. objekt.

### What I learned
Rolle-nøgler og same-as-nøgler gør det generiske tjek af forældreløse link-nøgler skrøbeligt. Reglen bygger på en antagelse om, hvilken hub nøglen ligger i, og den antagelse kan kun bekræftes ved en kørsel.

### What was tricky
Curated-kolonnenavne har blandet casing ("hash key" mod "Hash Key"), så matchet mellem fact og dim måtte være case-insensitivt.

### What warrants review
SQL'en er aldrig kørt, fordi der ikke er Snowflake-adgang i sessionen. De mest usikre konstruktioner er en cursor erklæret i en nested blok inde i en løkke, `SELECT INTO` i en EXCEPTION-handler og dynamisk GET_DDL. Første kørsel i dev er den reelle syntakstest. Benny har ikke brugt scriptene endnu.

### Future work
- Afklar om ét dev-only view hører til en kilde uden for scope, og ekskluder det i givet fald.
- Kør scriptene i dev, test, ny prod og gammel prod, og kør derefter `compare.py`.
- Skriv strategien op som dokumentation.

Status er gemt i command-deck (commit `ba0d9dc`).
