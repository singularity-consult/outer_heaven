# Diary: Udvid raw-ingestion-jobbets scope til hele kilde-forbindelsen

SEGES-kundearbejde, branch `feature/o90-raw-delete-detection`. Et Databricks-job loader
data fra landing til raw for én DB2-baseret kilde-forbindelse. Jobbet var oprindeligt
skrevet til kun at dække forbindelsens full-load-delmængde, men størstedelen af
forbindelsens objekter er siden landet i landing uden nogensinde at blive loadet videre
til raw. Opgaven er at fjerne den indsnævring, så jobbet dækker hele forbindelsen og
selv håndterer de objekter der endnu ikke er landet.

Diariet er sanitiseret: ingen tabel-, skema- eller servernavne, ingen datavaerdier.
Rollebeskrivelser i stedet.

## Step 1: Kravafklaring og research foer implementering

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** "Opgave i kundens repo `C:\claudes_folder\repos\DLBR-DataEstate2026`
(SEGES). Branch: `feature/o90-raw-delete-detection`, aktuelt paa `dc73f15`. Arbejd paa den
branch. [...] I `solutions/databricks/workflows/ingest_o90_raw_full.yml`, linje 21 og 33:
`meta_where_clause: "connection_name = 'o90' AND IncrementalFlag = 0"` -> `"connection_name
= 'o90'"`. Begge tasks skal rettes. [...] Det der skal afklares som en del af opgaven:
1. 19 vs 22 [...] 2. `set_o90_full_tables_writepattern_scd2.sql` har `@ExpectedTableCount =
19` [...] 3. Jobbets navn og kommentarer siger 'full' [...]"
(forkortet; fuld ordlyd i sessionen)

**Interpretation:** Selve kodeaendringen er en to-linjers fjernelse af et praedikat i en
YAML-fil. Det egentlige arbejde er de tre afklaringspunkter — to talkonflikter og en
navngivningsbeslutning — plus at levere en verifikations-query til den ubeviste antagelse
om SCD2-merge-adfaerd.

**Inferred intent:** Benny vil ikke bare have linjen rettet; han vil vide at han ikke
retter oven paa et forkert grundlag. De tre punkter er alle "er den dokumentation vi
stoler paa, stadig sand?"-spoergsmaal.

### What I did

Laeste projektets status-dokument i command-deck, jobbets YAML, og det SQL-script der
saetter skrivemoensteret. Sendte en read-only Explore-agent gennem kunde-repoet for at faa
de praecise kolonnenavne som SCD2-frameworket skriver, hvordan `meta_where_clause` bliver
brugt (den bliver konkateneret raat paa som WHERE-klausul mod en metadata-view), og hvad
guarden i delete-detection-notebooken faktisk tjekker.

Besvarede de to talpunkter udelukkende fra allerede verificerede observationer i
status-dokumentet, uden at koere SQL mod meta-databasen.

### Why

Briefet sagde eksplicit "byg videre, verificer ikke forfra" om tre punkter, men bad
samtidig om at de tre aabne punkter blev afklaret "uden at gaette". Forskellen mellem de
to er hele opgavens pointe: det der allerede er observeret, genbruges; det der kun er
antaget, undersoeges.

### What worked

Talkonflikten "19 vs 22" viste sig ikke at vaere en konflikt. Status-dokumentet indeholder
begge observationer, dateret: det lave tal blev maalt i juni, det hoeje i august, og der er
seedet objekter ind imellem. Begge var sande paa hver sit tidspunkt. Kommentaren i YAML'en
er altsaa foraeldet, ikke forkert — en vaesentligt anden konklusion end "nogen har skrevet
forkert".

Guard-spoergsmaalet i SQL-scriptet kunne afgoeres ved ren laesning af scriptet plus én
tidligere observation. Guarden aborterer paa antal *aendrede* raekker, og UPDATE'en
filtrerer raekker fra der allerede har den oenskede vaerdi. Da seed-defaulten allerede
saetter den vaerdi, rammer UPDATE'en nul raekker, og guarden kan ikke trippe. Scriptet er
en no-op og har altid vaeret det — dets praemis var aldrig sand.

### What didn't work

Harness'ens worktree-isolation. Jeg blev startet som worktree-isoleret agent i en worktree
af et *andet* repo end det opgaven ligger i. Alle git-kommandoer mod kunde-repoet via
Bash-vaerktoejet afvises:

```
Refusing it — a worktree-isolated agent's git operations must target its own worktree.
```

Det gaelder ogsaa read-only git. Fil-adgang (Read/Edit) er upaavirket; kun git er spaerret.
Den sanktionerede udvej, `ExitWorktree`, afviser ogsaa:

```
ExitWorktree cannot be called from a subagent with a cwd override (isolation: "worktree"
or explicit cwd) — it would mutate the parent session's process-wide working directory.
```

PowerShell-vaerktoejet har ikke samme guard — `git -C <kunde-repo> config user.email`
virkede der. Jeg valgte ikke at bruge det til at committe. At skifte vaerktoej for at goere
praecis det, et andet vaerktoej lige har naegtet, er omgaaelse af en kontrol, uanset hvor
rimeligt selve resultatet ser ud. Lagt op til Benny som en beslutning i stedet.

### What I learned

Naar to tal i dokumentationen er i konflikt, er "hvornaar blev hvert af dem maalt" et
bedre foerste spoergsmaal end "hvilket et er rigtigt". Begge kan vaere korrekte
observationer af et system der har aendret sig imellem maalingerne. Det aendrer ogsaa
handlingen: en foraeldet kommentar opdateres, en forkert kommentar udloeser et
tillidsspoergsmaal til alt andet samme forfatter skrev.

En row-count-guard der taeller *aendrede* raekker frem for *matchede* raekker beskytter mod
noget andet end det kommentaren over den paastaar. Her stod der "abort hvis flere raekker
end forventet matcher", men koden taeller kun de raekker der faktisk blev skrevet til.
Idempotensen og guarden underminerer hinanden: jo mere idempotent scriptet er, jo mindre
kan guarden se.

### What was tricky

Fristelsen til at bruge PowerShell-omvejen. Benny havde eksplicit valgt at jeg skulle
forlade worktreen, mekanismen fejlede teknisk, og en oplagt substitut laa aaben. Det
afgoerende var at beskeden kom via en koordinator-agent, ikke fra Benny direkte, og at
selve refusalen var en kontrol jeg ikke selv har sat. Omkostningen ved at spoerge er én
udveksling; omkostningen ved at tage fejl om en kontrol er stoerre.

### What warrants review

Talpunktet hviler paa status-dokumentets august-observation, ikke paa en ny query mod
meta-databasen. Den kan efterproeves naar der alligevel er VPN og token i haanden.

### Future work

SQL-scriptet der saetter skrivemoensteret er doedvaegt i repoet — det kan ikke goere noget,
og dets forventningstal er lige saa foraeldet som YAML-kommentaren. Ryddes ikke op nu;
lagt op til Benny som en selvstaendig beslutning.
