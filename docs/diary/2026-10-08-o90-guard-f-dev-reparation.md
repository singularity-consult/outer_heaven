# Diary: guard F dev-reparation - keys-spor-override og grænse-accept

SEGES-kunderepo (DLBR-DataEstate2026), branch med guard F. Dev mistede CDC-sletninger i et hul i kontroltabel-udtrækket, så en række CDC-sporede raw-tabeller har forældreløse live-rækker. To ændringer: en engangs-override der kører de berørte tabeller mod et nøglesnapshot, og en grænse-form for at acceptere guard F-huller, sat kun i dev, så dev kan blive ved med at køre efter release.

## Step 1: keys_track_override_entities + sync_meta_accept_gaps_ending_before

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** (saniteret) (lead-opgave, forkortet af hensyn til kundedetaljer) "Task A, one-off keys-track override: New widget `keys_track_override_entities` ... Require the name list to equal the run's scope exactly ... Task B, dev keeps running with guard F: ... `sync_meta_accept_gaps_ending_before` = ISO UTC timestamp; any gap whose END is at or before it is accepted ... Set it ONLY in the dev target of the job YAML(s) ... Update runbook section 10 + add a short repair runbook for dev ... Run the unit tests ... Report commits, files, test result, and open risks."
**Interpretation:** Policy-logik i den rene modul med unit tests, notebook-wiring i fase 1/2, jobparametre i YAML, runbook. Commit, ikke push.
**Inferred intent:** Fjern de forældreløse rækker én gang, og hold dev grøn under guard F uden at slække reglen for fremtidige huller eller for test/prod.

### What I did
Generaliserede `validate_override_scope` (parameternavn, konsekvenstekst, fejlklasse som keyword-args; guard C's besked uændret). Tilføjede `validate_keys_track_override`, `keys_track_override_track`, `keys_track_override_snapshot_problem`, `parse_accept_gaps_ending_before`, `gap_acceptance`, og `accept_gaps_ending_before` på verdict og fase-1-rapport. Notebook: to widgets, override anvendes i fase 1 FØR guard F samler landing-rødder, `build_watermark_track_keys` returnerer nu også cutoff. YAML: bundle-variabel med tom default, kun `targets.dev.variables` sætter værdien; delete-tasken sender keys-override tom. Runbook afsnit 10 opdateret, nyt afsnit 11. Commits f961657 og e7fadef.

### Why
Lighedskravet genbruges, fordi faren er den samme som ved guard C-overridet: en parameter der overlever sin beslutning. Grænse-formen fordi indledende huller har et andet slutpunkt pr. tabel og ikke kan listes i hånden.

### What worked
Tests 300 -> 344 passed med `python -m pytest --noconftest -q -p no:cacheprovider lighthouse/tests/write_tests/test_raw_delete_detection_policy.py`. `ruff check` (Python312\Scripts\ruff 0.14.0) rent. `py_compile` på notebook og modul rent.

### What didn't work
- Første testkørsel: 2 failed, `test_a_gap_ending_exactly_at_the_cutoff_is_accepted` fik `newest SYNC_META extract 2026-09-06T12:26:40Z is 32 d 00:33 old ... (staleness cannot be accepted)` - min egen testfixture brugte et fast "nu" langt efter sidste udtræk. Rettet med `now=times[-1] + timedelta(hours=1)`.
- Et stort bash-heredoc med testkoden fejlede: `/usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `''` og intet blev skrevet. Løst ved at skrive til scratchpad med Write og appende via Python med CRLF.
- Python312 og 310 har ikke pytest (`ModuleNotFoundError: No module named 'pytest'`); kun 313 har.

### What I learned
DAB-target-overrides af en enkelt task kræver merge-by-task_key, som ikke kan verificeres offline her; en bundle-variabel med target-værdi undgår helt at røre task-listen i targets. Keys-udtrækket skriver en fast filnavn pr. tabel (overskrives), så snapshot-cutoff er sidste skrivetid.

### What was tricky
Den daglige keys-udtræk dækker ikke CDC-tabellerne, så en eventuel gammel /Keys-fil er en rest. Den ville stadig indeholde de forældreløse nøgler og "reparere" intet mens den så grøn ud - derfor blokerer et snapshot over 36 t (og manglende snapshot) for override-objekter i stedet for at skippe. Også: guard C afviser først over 100.000 rækker, så en lille tabel hvis nøgler ikke joiner ville blive slettet helt; runbooken gør målingen før skrivning til et klart stop-kriterium.

### What warrants review
- DAB: `default: ""` og `targets.dev.variables` i en inkluderet fil er ikke valideret (`bundle validate` ikke kørt).
- Om notebook-params der ikke findes som widget i raw-load-notebooken ignoreres ved "Run now with different parameters" - ikke verificeret.
- Forretningsnøglen i dublet-tjekket i runbooken er antaget, ikke verificeret.

### Future work
Benny kører release, keys-udtræk, valgfri måling og reparationskørslen i dev. Ingen kodeopfølgning forventet, med mindre målingen viser nøgler der ikke joiner.
