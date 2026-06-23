# Diary: Grundfos Indian-address cleaning PoC (deterministic heuristic)

A decision-grounding proof-of-concept (NOT production) for the Grundfos
IIR-matching project. Goal: show how far pure stdlib + pandas heuristics,
anchored in M1's already-canonicalized geography (city/state/pin), get us at
cleaning and partly structuring 500 Indian address lines — before deciding
whether a heavier tool (libpostal / LLM) is worth the investment.

## Step 1: Build and validate the PoC

**Author:** builder

### Prompt Context

**Verbatim prompt:** Lav et PROOF-OF-CONCEPT (beslutningsgrundlag, IKKE
produktion) der renser og delvist strukturerer 500 indiske adresselinjer fra
Grundfos-dataene, forankret i den sikre geografi vi allerede har kanoniseret.
Formålet er at VISE Benny hvor langt vi når med ren, deterministisk heuristik +
kendt geografi, før vi beslutter om vi skal investere i et tungere værktøj
(libpostal/LLM). [Plus: repo grundfos-iir-matching, branch feat/base-files,
git-ignored scratch/poc_address_parse.py + output/poc_address_parse.csv, pure
Python stdlib+pandas, no libpostal, sample 500 = ~170 IIR + ~170 promoter + ~160
awardee with seed=42, remove known geo + admin noise + landmarks, extract floor
+ house/plot, hit-rate report, 15 before/after examples, honest assessment.]

**Interpretation:** Standalone script in scratch/, never touching the M1
pipeline modules, that samples 500 addresses deterministically, strips redundant
known geography and administrative/landmark noise, isolates floor and
house/plot codes into their own fields, and emits an inspectable per-row CSV
plus a concrete hit-rate report to stdout.

**Inferred intent:** Benny wants a defensible read on whether deterministic
regex + known geography is "good enough" for address structuring, or whether the
problem genuinely needs libpostal/LLM. The deliverable is the evidence (numbers
+ side-by-side examples), not production code.

### What I did
Wrote `scratch/poc_address_parse.py` (pure stdlib + pandas) and generated
`output/poc_address_parse.csv` (500 rows, 13 columns in the exact required
order). The pipeline per address: normalize whitespace/commas, strip known
geo (pin/city/state as whole words), remove admin noise, extract landmarks,
extract floor, then grab a leading house/plot code — in that order so admin
prefixes ("Registered, ...") are cleared before the anchored house-code match.
Sampling uses `random_state=42` per slice (170 iir / 170 promoter / 160
awardee), only rows with non-empty `addr_line1_raw`. Report prints per-field
hit-rates broken down by source/role, avg token reduction, an over-stripped
(empty-remainder) rate as a failure signal, and 15 hand-picked hard cases.
Skipped the optional PROJECT_DISTRICT join — it lives under OneDrive (read-only
customer source) and district was explicitly optional; keeping the PoC
self-contained avoided reaching outside the worktree.

### Why
The whole point is to demonstrate the ceiling of deterministic heuristics, so
the report leads with concrete per-source numbers (formats differ wildly: IIR
short fragments vs PD comma-salad strings) and shows raw→fields→remainder side
by side so Benny can judge quality himself.

### What worked
Geography removal and admin-noise stripping on promoter strings are strong:
admin noise removed on 91.8% of promoters (they almost all start
"Registered,"/"Head Quarter,"/"Corporate,"). House/plot extraction on awardee
hits 56.9%. Final numbers: floor 23.8%, house/plot 38.6%, landmark 12.0%, admin
35.4% overall; avg token reduction 2.5 (8.4→5.9).

### What didn't work
First run had two real bugs caught in self-review, both with verbatim repros:
1. House/plot regex catastrophically over-grabbed. For
   `Plot Number 2B and 2C Biotech Park Phase II` the greedy value
   `[A-Za-z0-9/\-&. ]*?` ran to end-of-string (no comma terminator on IIR
   lines), so the whole line became the "code" and `cleaned_remainder` was
   empty. IIR empty-remainder rate was 15.9%.
2. `PSP House` was wrongly tagged as admin noise: the loose police-station
   abbreviation pattern `p\.?\s*s\.?\s*...` matched "P"+"S" in "PSP", then
   `[^,]*` ate " House". Diagnosed with
   `[m.group(0) for m in _ADMIN_RE.finditer('PSP House, ...')]` → `['PSP House']`.

Fixed both: introduced a tight `_CODE` token (digit runs / 1-2 letter prefixes
with `-`/`/` separators, joined by and/&/comma) and a lookahead
`(?=,|$|\s[A-Za-z])` so the code stops before descriptive words; required the
dotted form `p\.\s*o\.`/`p\.\s*s\.` so acronyms like PSP don't fire. After fix:
"Plot Number 2B and 2C" stops before "Biotech Park", PSP admin matches `[]`,
IIR empty-remainder dropped to 5.9% / overall 2.4%.

### What I learned
The two PD roles and IIR are almost different problems: PD strings are
comma-delimited with a reliable admin prefix (heuristics shine), while IIR lines
often have no commas at all, which breaks any "up to next comma" assumption and
makes the leading-code grab the riskiest stage. The honest ceiling for pure
heuristics is "noise removal yes, true field structuring no".

### What was tricky
Anchored leading-code extraction with no comma terminator: had to bound the code
by token shape + a lookahead rather than by a delimiter, or it eats the street.
Balancing that against still catching multi-code plots ("2B and 2C") took the
`(?:and|&|,)`-joined repetition.

### What warrants review
`scratch/poc_address_parse.py` regexes `_HOUSE_RE`/`_CODE` (lines ~88-119) and
`_ADMIN_RE` (lines ~116-141) are the judgement calls. Known residual misses,
visible in the 15 examples and worth a reviewer's eye: "New Delhi" leaves orphan
"New" when only "Delhi" is the canon city (geo-variant gap); "8 B" splits into
house "8" + remainder "B"; "Block no. 758" not extracted (Block not in marker
list, defensible). Validate by re-running `python scratch/poc_address_parse.py`
from repo root and reading the stdout report + the CSV.

### What I learned about reliability (for the handback)
Reliable: known-geo removal, admin-prefix stripping on promoters, leading
plot/door/survey codes with explicit markers. Unreliable: `cleaned_remainder` as
a clean street/locality (still holds sub-localities, building names, village/PO
fragments), landmark recall (only ~12%, many landmarks lack a keyword), and any
IIR line without commas. This is exactly where libpostal/LLM would win:
component-level labelling (house/road/suburb/city) instead of subtractive
cleaning.

### Future work
If Benny greenlights deeper work: (a) build a city/state variant map so
"New Delhi"/"Greater Noida" tails strip cleanly; (b) benchmark libpostal on the
same 500 to quantify the gap; (c) treat IIR and PD with separate pipelines
rather than one shared one.

## Step 2: Clean over IIR line1 + line2 combined (not just line1)

**Author:** builder

### Prompt Context

**Verbatim prompt:** Udvid et eksisterende PoC-script så
adresse-støjreduktionen behandler adresselinje 1 OG 2 samlet (i stedet for
kun linje 1). [Plus: STOP ved støjreduktion (ingen libpostal/LLM, ingen
felt-strukturering); genbrug rense-pipelinen 1:1, ændr kun INPUT; for IIR byg
kombineret = line1 + ", " + line2 hvis line2 ikke tom, kør HELE pipelinen på
den; PD uændret (line2 tom); behold raw_line1/raw_line2 separat men
floor/house/landmark/admin/remainder beregnet over kombineret for IIR; samme
13 kolonner; samme 500-stikprøve seed=42; hit-rater pr. felt og source; VIGTIGT
FØR/EFTER for IIR kun-line1 vs line1+2 (landmark-% , tom-rest-%, gns.
token-reduktion); 10 fulde før/efter-eksempler hvor line2 reelt bidrog; ærlig
note om tom-rest-raten 5.9% gik op eller ned.]

**Interpretation:** Only the input composition changes. The cleaning logic
(`parse_address`) stays byte-for-byte the same — I just feed it a combined
string for IIR. Keep line1/line2 as separate output columns, but every derived
field is now computed over the combined string for IIR. Add a FØR/EFTER section
quantifying what line2 buys, plus 10 examples where line2 mattered.

**Inferred intent:** Benny has decided to stop at noise reduction and wants
evidence on a narrow question: does folding IIR's 85%-filled line2 (area/colony,
but also noisy) into the cleaned picture improve it or mostly add noise?

### What I did
Added `combine_lines(raw_line1, raw_line2)` which appends line2 with a comma
when present and collapses to line1 when line2 is empty (so PD — 0% line2 — is
untouched). Renamed `parse_address`'s first param `raw_line1`→`raw_address` and
fed it the combined string in `run()`. `run()` now also runs a PARALLEL
line1-only parse for IIR rows and returns it as a second frame (not written to
disk) purely to power the FØR/EFTER comparison. Fixed the token-reduction
baseline in `block()` to measure against the actual cleaned input
(`combine_lines(...)`) rather than `raw_line1`, otherwise IIR reduction would be
computed against the wrong, shorter baseline. Added `_report_line2_effect()`
(the FØR/EFTER table) and `_print_line2_examples()` (10 IIR rows where line2
changed the remainder, landmark, or admin output). Output is the same 13
columns in the same order; 500 rows, 170 IIR confirmed via pandas re-read.

### Why
The deliverable question is purely "line2 in vs out", so the report had to put
the two parses side by side on identical rows. Keeping a separate line1-only
parse in memory (rather than re-deriving from the CSV) makes the comparison
exact and row-aligned.

### What worked
The change was genuinely small because the pipeline reused 1:1 — only the input
string and the report changed. FØR/EFTER numbers (n=170, line2 filled 87.1%):
empty-remainder DROPPED 5.9%→3.5% (−2.4pp), landmark-removal rose 2.9%→7.6%
(line2 carries "Opposite To Itpl"-style landmarks the pipeline now catches),
avg remainder tokens 4.0→6.6 (the added area/colony content). Examples 1-8 and
10 show area/colony correctly preserved (e.g. "Lalgadi Malakpet",
"Institutional Area Sector 32", "Bavdhan", "Hosur Main Road Adugodi" appended
to the remainder); example 9 shows line2 "Opposite To Itpl" correctly removed
as a landmark instead of polluting the remainder.

### What didn't work
Nothing broke. First and only run produced the expected report and a clean
CSV — no errors, no over-strip regressions. Stated explicitly per the
all-sections rule: this step had no failures.

### What I learned
The honest answer to Benny's question: for IIR, line2 makes the picture BETTER,
not noisier. The empty-remainder rate went DOWN (5.9%→3.5%), which is the
opposite of the over-strip risk one might fear from adding more input — because
line2's area/colony survives the pipeline and fills remainders that were empty
on line1 alone. The added tokens are mostly useful locality, and the genuine
noise in line2 (city repeats, landmarks) is removed by the same admin/landmark
stages. The one caveat: "MIDC, MIDC, Bhosari" (example 7) shows a duplicated
token line2 can re-introduce, which dedup of geo-variants would clean.

### What was tricky
The token-reduction baseline. The original `block()` measured reduction against
`raw_line1`; left unchanged, IIR's combined remainder would be compared to a
baseline that never included line2, making "reduction" meaningless. Switching
the baseline to `combine_lines(...)` per row was the load-bearing fix so the
ALL/iir blocks report a coherent raw→remainder number.

### What warrants review
`combine_lines` (the only input change) and the two new report functions
`_report_line2_effect` / `_print_line2_examples` in
`scratch/poc_address_parse.py`. The cleaning regexes are untouched from Step 1.
Validate by re-running `python scratch/poc_address_parse.py` from repo root and
reading the FØR/EFTER table and the 10 line2 examples. Note example 8 ("Dhun
Building (I floor)") — "I floor" is NOT extracted because `_FLOOR_RE` requires a
digit; pre-existing behaviour, not introduced here.

### Future work
Geo-variant / duplicate-token dedup would clean the "MIDC, MIDC" and
"New Delhi"→orphan-"New" residue now slightly more visible with line2 folded in.
That remains out of scope per the explicit "stop at noise reduction" decision.
