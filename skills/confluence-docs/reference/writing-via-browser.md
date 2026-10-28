# Teknik: skriv til Confluence via brugerens browser-session

Verificeret 2026-10-28 i SEGES' Confluence Cloud, gennem brugerens egen browser-session med Claude-in-Chrome-udvidelsen (i Edge). Der bruges intet API-token: kaldene køres som `fetch` fra en åben Confluence-side, så de arver brugerens session og rettigheder.

Alle stier nedenfor er relative til Confluence-instansen (`/wiki/...`). Kør dem fra en fane hvor Confluence allerede er åben.

## Før du skriver

- Claude Code auto-mode blokerer skrivninger til Confluence, indtil brugeren eksplicit i chatten har godkendt hvilke sider der må ændres. Få godkendelsen på side-niveau først.
- Rettighedstjek uden at ændre noget:

  ```js
  const r = await fetch('/wiki/api/v2/pages/<pageId>/operations');
  (await r.json()).operations.map(o => o.operation + ':' + o.targetType);
  ```

- Output fra `javascript_tool` der ligner tokens eller brugerdata, blokeres ("Cookie/query string data"). Returnér kun det nødvendige: status-kode, id, versionsnummer.

## Opret side

```js
const r = await fetch('/wiki/api/v2/pages', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Atlassian-Token': 'no-check'
  },
  body: JSON.stringify({
    spaceId: '<spaceId>',
    parentId: '<parentPageId>',
    status: 'current',
    title: '<titel>',
    body: { representation: 'storage', value: storageXml }
  })
});
const j = await r.json();
[r.status, j.id, j.version && j.version.number];
```

Forventet: `200` og et nyt side-id.

## Opdatér side

Hent den nuværende version, og send `version.number + 1`.

```js
const cur = await (await fetch(
  '/wiki/api/v2/pages/<pageId>?body-format=storage'
)).json();
const r = await fetch('/wiki/api/v2/pages/<pageId>', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'X-Atlassian-Token': 'no-check'
  },
  body: JSON.stringify({
    id: '<pageId>',
    status: 'current',
    title: cur.title,
    body: { representation: 'storage', value: storageXml },
    version: { number: cur.version.number + 1, message: '<hvorfor>' }
  })
});
r.status;
```

Forventet: `200`.

## Slet side

```js
(await fetch('/wiki/api/v2/pages/<pageId>', {
  method: 'DELETE',
  headers: { 'X-Atlassian-Token': 'no-check' }
})).status;
```

Forventet: `204`. Siden havner i space'ets papirkurv og kan gendannes derfra.

## Code-makro

```xml
<ac:structured-macro ac:name="code">
  <ac:parameter ac:name="language">sql</ac:parameter>
  <ac:parameter ac:name="linenumbers">true</ac:parameter>
  <ac:parameter ac:name="title">...</ac:parameter>
  <ac:plain-text-body><![CDATA[...]]></ac:plain-text-body>
</ac:structured-macro>
```

Python-sprogkoden er `py`.

## Vedhæftninger

REST-endpointet `/wiki/rest/api/content/<pageId>/child/attachment` fejler med `403 "XSRF check failed"` uanset header (både `X-Atlassian-Token: no-check` og `nocheck` er prøvet). Brug det ikke.

Virker i stedet: den klassiske formular.

1. Navigér til `/wiki/pages/viewpageattachments.action?pageId=<pageId>`.
2. Formularen har file-inputs `file_0` til `file_4`.
3. Sæt filerne:
   - **Filer genereret i browseren** (fx draw.io-XML eller en PNG tegnet på canvas): byg en `File` og sæt den via `DataTransfer` på `input.files`.

     ```js
     const dt = new DataTransfer();
     dt.items.add(new File([blob], '<filnavn>', { type: '<mediaType>' }));
     document.querySelector('input[name="file_0"]').files = dt.files;
     ```

   - **Lokale filer** (screenshots på disken): brug udvidelsens `file_upload`-værktøj på inputtet.
4. Indsend med `form.requestSubmit()` (ikke `form.submit()`, der springer formularens egne handlers over).

## Billede i side

```xml
<ac:image ac:width="860"><ri:attachment ri:filename="x.jpg"/></ac:image>
```

Vedhæft filen først. Screenshots tages i fuld opløsning (scale 1), beskæres til det relevante udsnit og kommer altid fra dev.

## draw.io-diagram

Vedhæft to filer:

- `<navn>` (uden filendelse), mediaType `application/vnd.jgraph.mxfile`, indhold: mxfile-XML.
- `<navn>.png`: preview. Kan tegnes på et canvas i browseren. Preview-PNG'en skal matche XML'en, ellers viser siden noget andet end editoren.

Indsæt makroen:

```xml
<ac:structured-macro ac:name="drawio" ac:schema-version="1">
  <ac:parameter ac:name="border">true</ac:parameter>
  <ac:parameter ac:name="viewerToolbar">true</ac:parameter>
  <ac:parameter ac:name="fitWindow">false</ac:parameter>
  <ac:parameter ac:name="diagramName"><navn></ac:parameter>
  <ac:parameter ac:name="simpleViewer">false</ac:parameter>
  <ac:parameter ac:name="width"><bredde></ac:parameter>
  <ac:parameter ac:name="diagramWidth"><bredde></ac:parameter>
  <ac:parameter ac:name="revision">1</ac:parameter>
</ac:structured-macro>
```

Diagrammet renderes korrekt, uden at nogen åbner draw.io-editoren.

## Azure-login

Udvidelsen har ikke rettighed på Microsofts login-side. Skal du tage screenshots fra ADF eller Databricks i dev, logger brugeren selv ind først.
