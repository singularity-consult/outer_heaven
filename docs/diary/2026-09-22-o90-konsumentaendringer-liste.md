# Diary: Fra kontraktdiff til eksekverbar ændringsliste for konsumentlaget

Kundeprojekt hos SEGES, fortsættelse af `2026-09-17-o90-kontraktdiff-v2.md`. Et
enriched lag (o90) er skrevet om i en v2-udgave og skal erstatte det gamle ved en
omdøbning. Konsumenterne i curated- og integrationslaget peges ikke om: de bliver
hængende på det samme skemanavn og møder et andet indhold under det.

Kontraktdiffen fra september beskriver hvad der sker, fil for fil, i fire
revisioner. Den er bevidst ren diagnose — den foreskriver ikke. Det efterlader et
hul: nogen skal stadig oversætte diagnosen til de konkrete rettelser, der skal
laves i konsumentlaget, før omdøbningen kan ske.

Samtidig har grundlaget flyttet sig siden diffen blev skrevet. Tre ting er
kommet til: en fejl i CDC-sporets nøglesammenligning, der har holdt
sletteregistreringen tavst inaktiv for en gruppe tabeller; en reparation af et
lækkende vandmærke-prædikat, der har hentet en stor mængde manglende rækker hjem;
og en pukkel af ophobede sletninger, der blev synlig første gang nøglesættet var
komplet.

Leverancen i denne omgang er derfor ikke endnu et diagnosedokument, men en liste
en builder kan eksekvere fil for fil — sorteret efter arbejdets form, så det
mekaniske kan tages først og det, der kræver en forretningsbeslutning, ligger for
sig.

## Step 1: Afgrænsning, faktatjek og en korrigeret præmis

**Author:** main (lead)

### Prompt Context

**Verbatim prompt:** Opgaven kom i to dele. Først opdraget (forkortet, elisioner
markeret):

> "Dette er **den kritiske vej**. Punkt 5, som er at rette curated, bygger
> direkte på resultatet. […] Dokumentet er skrevet **før** de sidste dages
> arbejde, og dets største enkeltpost er nu forkert i undervurderende retning.
> […] **1. Gruppe C er større end dokumenteret.** Diffen siger at
> `dw_is_deleted` er strukturelt altid falsk i den gamle løsning for en gruppe
> tabeller […] Vi har siden fundet at **nitten CDC-tabeller stod som fungerende
> uden at være det** […] **Skel skarpt mellem tre virkninger**, for de kræver
> forskellige svar af konsumenten […] **Sig det, når du ikke kan afgøre
> retningen** frem for at gætte. […] Ingen kode ændres i denne opgave — det er
> punkt 5. Din leverance er dokumentet."

Derefter en kurskorrektion, efter at jeg havde stillet et spørgsmål om
dokumentets struktur (forkortet):

> "Benny har skåret igennem, og han har ret: **spørgsmålet om akser er det
> forkerte spørgsmål.** Jeg lod dokumentets indre struktur styre arbejdet. Drop A
> mod B. Opgaven er ikke at klassificere fund. Den er at producere **listen over
> konkrete ændringer, der skal laves i curated og integration, for at de virker
> mod den nye ø90-integration.** Dokumentet er et middel til den liste, ikke et
> mål. […] **Formatet skal kunne eksekveres.** For hver fil: sti, hvilke
> ændringer der kræves, og hvor i filen. Er ændringen usikker — fordi den
> afhænger af en forretningsbeslutning frem for en teknisk — så marker den som
> sådan i stedet for at vælge. […] **Sortér efter arbejdets form, ikke efter
> alfabet.**"

**Interpretation:** Diffen skal ikke omskrives for sin egen skyld. Den skal
levere råstof til en arbejdsliste, og listen er leverancen. Rettelser i diffen
selv begrænses til det, der er blevet påviseligt forkert — ikke omstrukturering.
Usikkerhed markeres frem for at blive gættet væk, fordi de beslutninger tilhører
Benny.

**Inferred intent:** Benny vil kunne sætte punkt 5 i gang uden selv at skulle
læse 968 linjers diagnose og udlede opgaven af den. Han vil have en liste, hvor
det mekaniske kan uddelegeres og det tvivlsomme ligger synligt og samlet til
hans egen afgørelse.

### What I did

Læste projektets statusfil (genoptagelsesafsnittet fra 2026-09-21 med
målingerne og deres kilder) og hele kontraktdiffen. Krydsede de tre nye
bevægelser mod diffens egen liste over de tabeller konsumenterne faktisk læser,
og mod de to spor sletteregistreringen kører ad. Verificerede læsningerne med et
grep over konsumentlaget frem for at stole på diffens egne optællinger.

Udledte hvilke af de læste tabeller der ligger på hvert spor, og hvilke af dem
der har et målt tal i dag. Lagde derefter opgaven i hænderne på én builder med
det materiale, i stedet for at lade builderen genudlede det.

Valget mellem at skrive listen ind i den eksisterende diff eller lægge den som et
selvstændigt dokument faldt på det sidste, med en kort revision af diffen ved
siden af. Begrundelsen står i selve leverancen.

### Why

Diffens største svaghed var ikke dens struktur, men at den var kvalitativ på et
punkt, hvor der nu findes tal. Og dens egen åbne post sagde det ligeud: hvor
mange rækker der vil bære sletteflaget i v2, er raws tal, og raw var ikke målt.
Netop det hul er nu delvist lukket. Det er dér revisionen har noget at bidrage
med — ikke i en ny inddeling af de samme fund.

At holde listen adskilt fra diffen følger diffens eget princip: den er diagnose
og foreskriver ikke. En arbejdsliste, der bliver hakket af og dør, har en anden
læser og en anden levetid end et evidensdokument, der skal kunne slås op om et
år.

### What worked

Krydsningen af de to lister — de tabeller konsumenterne læser mod de tabeller
bevægelserne rammer — gav med det samme et skarpere billede end opdraget
antydede. Flere af de største tal rammer tabeller, ingen konsument læser, mens
den tabel der læses allertiest nu har et målt tal, den ikke havde før. Det er den
slags, der kun kommer frem ved at lægge listerne oven på hinanden, og det tog få
minutter.

At læse statusfilen først, som opdraget bad om, var rigtigt. Den indeholdt både
målingerne og forbeholdene ved dem, og et af forbeholdene viste sig at være
afgørende for hvordan tallene må bruges.

### What didn't work

Jeg stillede det forkerte spørgsmål. Efter at have læst materialet formulerede
jeg et valg mellem to måder at organisere dokumentet på og bad om en afgørelse.
Det var et spørgsmål om dokumentets indre struktur, ikke om leverancen, og det
kostede en runde. Kurskorrektionen var berettiget.

Fejlen har en genkendelig form: jeg lod artefaktet, jeg var blevet bedt om at
revidere, definere opgaven, i stedet for at spørge hvad artefaktet skulle bruges
til. Opdraget sagde det faktisk i første linje — det næste punkt er at rette
konsumentlaget — og jeg læste det som kontekst i stedet for som formål.

### What I learned

To påstande, der lyder ens, kan tilhøre hvert sit lag og må ikke lægges sammen.
Diffens observation om at et sletteflag er strukturelt inaktivt, er en påstand om
det *gamle* lag og hvordan det skrives. Fundet om den brudte nøglesammenligning
er en påstand om *raw*, altså om kilden til det nye lag. Opdraget behandlede det
andet som en forstærkning af det første. Det er det ikke: de overlapper kun på de
få tabeller, der optræder begge steder, og for resten peger de hver sin vej.
Under v2 er det alene raws tal, der afgør hvad konsumenten ser — det gamle lags
inddeling fortæller kun, hvad tallet plejede at være.

Målte tal bærer en enhed, og enheden skal med. Tallene fra sletteregistreringen
er fund *pr. kørsel*, ikke den ophobede population af markerede rækker. De to
forveksles let, fordi de står i samme kolonne i en opsummering, og en
arbejdsliste bygget på den forveksling ville love præcision, den ikke har.

### What was tricky

Navnelighed mellem tabeller. Flere af de tabeller, bevægelserne rammer, har navne
der ligner navnene på tabeller, konsumenterne læser, uden at være dem. Diffen
havde selv fanget to af de forvekslinger og skrevet dem eksplicit ned, hvilket
sparede en fejl. Det er et godt argument for at skrive den slags ned, også når
det virker overflødigt i skrivende stund.

Dertil, som altid i dette projekt: det gamle lag læser fra en delt kilde, som
ikke findes i repoet, mens det nye læser fra vores eget raw. Alt hvad der er målt
på den ene side, siger derfor principielt intet om den anden, og det skal holdes
adskilt i hver eneste påstand.

### What warrants review

Krydsningen mellem de tre bevægelser og de læste tabeller er min egen udledning
fra to lister i statusfilen. Builderen er bedt om at verificere den mod repoets
egne metadata frem for at overtage den. Den er det bærende led i hele listen, så
går den galt, går resten med.

Sorteringen efter arbejdets form er et skøn. Grænsen mellem "mekanisk" og
"flytter et tal" er ikke skarp i alle tilfælde, og en post placeret som mekanisk,
der i virkeligheden ændrer et resultat, er den farligste fejl listen kan
indeholde — netop fordi den så bliver taget først og uden opmærksomhed.

### Future work

Den ophobede population af slettemarkerede rækker i raw er stadig umålt for de
læste tabeller. Det er én forespørgsel, og den hører i målepligten før
omdøbningen, ikke i denne opgave.

Punkt 5 — de faktiske rettelser i konsumentlaget — følger efter denne liste og
bruger den som input.

## Step 2: Listen skrevet, udledningen efterprøvet, fire ting rettet

**Author:** builder

### Prompt Context

**Verbatim prompt:** Opdraget fra lead (forkortet, elisioner markeret):

> "**Ingen kode ændres.** Kun dokumentation. […] **Ingen kørsler.** […] Alt du
> ikke kan afgøre fra repoet eller fra de målinger du får udleveret her, skal stå
> som umåligt med angivelse af hvad der skal måles. […] **Listen over de konkrete
> ændringer, der skal laves i `03_curated` og `04_integration` (plus to filer
> udenfor)** […] Sortering — efter arbejdets form, ikke alfabet. […] **Vælg ikke
> for Benny.** […] **Min udledning — VERIFICÉR den, overtag den ikke.** Jeg har
> krydset de tre bevægelser mod diffens liste over de 22 tabeller konsumenterne
> faktisk læser. Resultatet nedenfor er min udledning fra to lister i
> statusfilen, ikke en måling. Den er det bærende led i hele arbejdslisten, så
> efterprøv den mod repoets egne metadata […] **Verificér de 42 selv med grep**
> frem for at overtage diffens optælling."

Derefter en kurskorrektion midt i arbejdet, efter at overgangsplanen var ændret:

> "Overgangsplanen er ændret fra big-bang til to trin. […] **Trin 1: curated og
> integration peges på `o90_v2`**, mens den gamle stadig står og virker. […] Det
> afløser forudsætningen 'ingen konsument repointes', som både diffen og mit
> oprindelige opdrag hvilede på. […] **Rækkefølge-fælde til trin 2:** omdøbningen
> og omskrivningen af notebooks **skal deployes i samme vindue.** […] **Skriv en
> anbefaling ind, ikke en beslutning:** bør centralisering af skemanavnet være
> første opgave […] Læg argumenterne for og imod frem, begge veje, og lad Benny
> afgøre."

**Interpretation:** Producér arbejdslisten som selvstændigt dokument, verificér
hvert bærende tal mod repoet frem for mod de udleverede lister, og skriv rev. 5
af diagnosen kirurgisk. Alt, der afhænger af en forretningsbeslutning, beskrives
med begge udfald i stedet for at blive afgjort.

**Inferred intent:** Lead ved, at den udledning han sender med, er det svageste
led, og at den er svær at falsificere uden at gå i repoets metadata. Han vil have
den efterprøvet af nogen, der ikke har skrevet den.

### What I did

Læste begge grundlagsdokumenter helt, verificerede filantallet med grep, og
efterprøvede derefter sporfordelingen mod repoets egne metadata-seeds frem for
mod statusfilens lister. Skrev arbejdslisten med et indeks over alle filer, fem
klasser og en femkolonners række pr. ændring, og rettede diagnosedokumentet på
seks punkter uden at flytte et eneste fund-id.

Kurskorrektionen om totrins-overgangen kom, mens jeg sad i metadata-verifikationen.
Den tilføjede en klasse (repointeringen) og en beslutningspost om centralisering
af skemanavnet, og den afløste en forudsætning, der stod eksplicit i diagnosens
indledning.

Til sidst en selvgennemgang af mit eget dokument: en tælling af hver klasse mod
grep-tallet, og et lille script der tjekker at hver markdown-tabelrække har samme
antal kolonner som sin header.

### Why

Lead bad om verifikation frem for overtagelse, og den eneste måde at efterprøve
en sporfordeling på er at finde det sted, hvor sporet faktisk afgøres. Det viste
sig at være tre steder: funktionen der vælger spor, viewet der afleder flaget, og
den seed der navngiver den ene gruppe tabeller eksplicit. Statusfilens lister er
korrekte, men de er observationer af en kørsel; metadata er grunden til at
kørslen så sådan ud.

Klasseopdelingen fik en ekstra klasse forrest frem for at repointeringen blev
lagt i den mekaniske gruppe. Den mekaniske gruppe er defineret ved at tallet står
stille, og repointeringen flytter tallet — det er hele formålet med den. At
lægge den dér ville placere præcis den farligste slags post i den gruppe, der
tages først og uden opmærksomhed. Lead havde selv advaret mod netop det.

### What worked

Metadata-verifikationen bekræftede leads regnestykke og skærpede det samtidig.
Hans opdeling var aritmetisk rigtig, men den behandlede alt uden for CDC-sporet
som ét spor. Der er to, og forskellen mellem dem er ikke kosmetisk: det ene har
virket hele tiden ved konstruktion, det andet har haft et hul, der først lige er
lukket.

Scriptet, der tæller kolonner i markdown-tabeller, fandt en tabel jeg havde
brækket ved at indsætte en fodnote midt i den. Det er en fejl, der er usynlig i
råteksten og først dukker op, når nogen åbner dokumentet i en viewer. Den slags
er værd at tjekke maskinelt, når leverancen udelukkende er prosa og tabeller.

### What didn't work

Ingen kørsler fejlede, fordi der ikke blev kørt noget — det var en ufravigelig
ramme. Men to fejl i mit eget arbejde blev fanget i selvgennemgangen:

Den ene var den brækkede tabel ovenfor. Fodnoten stod mellem to rækker, hvilket
afsluttede tabellen og efterlod den sidste række som løs tekst.

Den anden var en SQL-forespørgsel, jeg havde skrevet ind i beslutningsafsnittet,
som ikke kunne køre. Jeg havde aliasset en tabel som `sis` og derefter refereret
til `sois.IncrementalFlag`, som ikke fandtes i forespørgslen overhovedet — og
kolonnen lå desuden på en helt anden tabel, end jeg havde antaget. Det var kun
fordi rammen forbød kørsler, at fejlen overlevede til selvgennemgangen; havde
jeg kunnet køre den, var den faldet med det samme. Rettet ved at slå kolonnerne
op i det view, der allerede samler dem, hvilket gjorde forespørgslen kortere og
samtidig lod den dække alle de læste tabeller i stedet for to.

Dertil tre tælle-uoverensstemmelser mellem indekset og de underliggende tabeller,
fundet ved at lægge kolonnerne sammen i hånden. Alle tre var min egen slendrian,
ikke uenighed om fakta.

### What I learned

En sammenligning er stærkere end en tidsserie, og totrins-planen gav den gratis.
Diagnosens målepligt forudsatte big-bang og bad derfor om målinger før og efter i
tid — hvilket blander daglig tilvækst og sæsonvariation ind i enhver forskel. Når
begge udgaver af laget står side om side, kan det samme job køres to gange samme
dag mod hver sin kilde, og forskellen er ren. Det er værd at lede efter den slags
vindue, når en migrering planlægges: muligheden for at måle er en egenskab ved
overgangsformen, ikke noget man tilføjer bagefter.

Og en klassificering skal have sin definition vendt imod sig selv. Da jeg havde
placeret repointeringen i den mekaniske gruppe, var det definitionen på gruppen —
ikke min mavefornemmelse — der afslørede fejlen. Klasser, der er defineret ved en
egenskab frem for ved en fornemmelse, kan falsificere deres eget indhold.

### What was tricky

Grænsen mellem "jobbet fejler, og rettelsen er neutral" og "jobbet fejler, og
rettelsen flytter et tal" var den sværeste. Fire poster ser ud som en ren
sletning af et prædikat, fordi en kolonne ikke længere findes. Men prædikatet
fjerner reelt rækker i dag, og den rettede udgave læser et langt større
datasæt — flytningen kommer af tabellens form i den nye udgave, ikke af hvilken
rettelse man vælger. De endte i den ikke-neutrale gruppe med den begrundelse
skrevet ud, fordi en læser ellers vil læse dem som trivielle.

Et andet sted trak diagnosen en konklusion for snævert: en typeændring var
beskrevet som at en kolonne skifter type i outputtet. Den samme kolonne bruges få
linjer længere nede i en betingelse, der afgør en kategoriværdi — så ændringen
flytter ikke bare en type, den flytter hvad rækkerne kategoriseres som. Det slags
fund kommer kun frem ved at læse hele filen og ikke kun den linje, fundet peger
på.

### What warrants review

Klassificeringen af de fire poster ovenfor er den ene ting at kigge efter. De er
argumenterede, men det er et skøn, og skønnet står skrevet ud i dokumentet, så
det kan modsiges.

Den anden er sporfordelingen. Jeg kunne placere alle de læste tabeller på nær én,
og den ene har to modstridende observationer om sig — den står ikke i den seed,
der navngiver sin formodede gruppe, men projektfilen noterer en egenskab, der kun
giver mening, hvis den hører til dér. Den er ført som en åben post med den
forespørgsel, der afgør den, skrevet ud.

### Future work

To tabeller har vandmærker, der ikke har rykket sig i henholdsvis fem måneder og
over to år. Begge læses af konsumenter. Er kilden stået stille, vil
sammenligningen i trin 1 vise en forskel, der ikke kommer af omlægningen — og den
vil blive tilskrevet omlægningen, hvis ingen ved det på forhånd. Det er ført som
en åben post, men det hører reelt hjemme i raw-sporet og ikke i konsumentlisten.

En håndfuld kildetyper kan ikke afgøres fra repoet og afgøres af én forespørgsel
mod metadatabasen. Den forespørgsel låser fire adskilte poster op på én gang og
bør køres, før nogen begynder at rette filer.
