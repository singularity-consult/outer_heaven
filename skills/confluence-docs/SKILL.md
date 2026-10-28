---
name: confluence-docs
description: Reference for writing developer documentation in Confluence for the customer SEGES (the Data Estate platform), covering guides, onboarding, rules and pitfalls, decision notes, and lookup pages. Use this whenever you write, restructure, or change a developer page in SEGES' Confluence. Covers the page structure (index page plus purpose-grouped subpages), the two page types (guide and decision note), the mandatory change log, the quality bar (full-resolution dev screenshots, code macros, concrete names), ready-to-send storage-format templates, and the verified browser-session technique for writing pages and attachments.
---

# confluence-docs

Udvikler-dokumentationen for SEGES' Data Estate-platform bor i Confluence. Skillen er referencen for hvordan siderne struktureres, hvordan de ser ud, og hvordan de skrives teknisk. Kvaliteten er som et færdigt produkt: en side der publiceres, skal kunne bruges af en ny udvikler uden at spørge nogen.

## Hvornår skillen bruges

- Når du skriver en ny udviklerside: guide, onboarding, regel, beslutningsnote eller opslag.
- Når du ændrer eller omstrukturerer en eksisterende side i udvikler-sektionen.
- Når du skal vedhæfte screenshots eller draw.io-diagrammer til en side.

Arkitektur- og indlæsningssider findes allerede. Link til dem frem for at gentage indholdet.

## Struktur: indeks plus undersider grupperet efter formål

Hovedsiden "Arbejdsgange for udviklere" er et indeks. Den forklarer kort hvad sektionen dækker og giver en anbefalet læserækkefølge for en ny udvikler. Den indeholder ikke selv vejledning.

Undersiderne grupperes efter formål, ikke efter teknologi. En side om at genkøre en ADF-pipeline hører under Arbejdsgange, ikke under "ADF".

1. **Onboarding**: adgange, værktøjer, første dag, første ændring.
2. **Arbejdsgange (how-to)**: konkrete opgaver trin for trin.
3. **Regler og faldgruber**: hvad du kan og ikke kan, og hvorfor.
4. **Historik og beslutninger**: beslutningsnoter.
5. **Opslag**: miljøer, navngivning, ordliste.

## To sidetyper

- **Guide** (`templates/guide.md`): hvordan du gør noget. Bruges til Onboarding, Arbejdsgange og Regler og faldgruber.
- **Beslutningsnote** (`templates/decision-note.md`): hvorfor vi valgte som vi gjorde. Bruges til Historik og beslutninger. En guides "Hvorfor gør vi det sådan" linker hertil i stedet for at gentage argumentationen.

Opslagssider er tabeller og lister uden fast skabelon, men de slutter også med ændringslog.

## Ændringslog på hver side

Hver side slutter med en ændringslog (`templates/changelog.md`). Confluence har allerede versionshistorik, så loggens eneste merværdi er **hvorfor**. Derfor:

- Nyeste række øverst.
- Kun indholdsmæssige ændringer. Stavefejl og formatering ligger i sidehistorikken.
- "Hvorfor" er obligatorisk. En række uden begrundelse tæller ikke.

## Kvalitetskrav

- **Screenshots**: altid fuld opløsning (scale 1), beskåret til det relevante udsnit, altid fra dev-miljøet, aldrig prod.
- **Kode**: altid i Confluence' code-makro med korrekt sprog. Verificeret: `sql`, og `py` for Python. Andre sprogkoder: tjek i makroens sprogliste før brug.
- **Konkrete navne**: skriv det rigtige pipeline-, tabel- og miljønavn frem for "pipelinen" eller "kildetabellen".
- **Ingen lang tankestreg** (em/en dash) i teksten. Brug kolon, komma, punktum eller parentes.
- **Sprog**: dansk.
- **Links frem for gentagelse**: eksisterende arkitektur- og indlæsningssider linkes, ikke kopieres.
- **Diagrammer**: draw.io-makro med vedhæftet XML og preview-PNG der matcher hinanden.

## Filer i skillen

- `templates/guide.md`: guide-skabelon, markdown og storage format.
- `templates/decision-note.md`: beslutningsnote-skabelon, markdown og storage format.
- `templates/changelog.md`: ændringslog, markdown og storage format.
- `reference/writing-via-browser.md`: verificeret teknik til at oprette og opdatere sider, vedhæfte filer og indsætte draw.io via brugerens browser-session.

Storage-format-snippets i skabelonerne kan sendes direkte som `body.value` med `representation: "storage"`.

## Tilladelse før skrivning

Læs gerne frit. Skriv, opdatér eller slet aldrig en Confluence-side uden at Benny i chatten har godkendt præcis hvilke sider der må ændres. Rettighedstjek uden ændring er beskrevet i teknik-referencen.
