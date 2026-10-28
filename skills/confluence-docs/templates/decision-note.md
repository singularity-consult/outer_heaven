# Skabelon: beslutningsnote

Bruges under Historik og beslutninger. En note beskriver én beslutning. Når beslutningen ændres, skrives en ny note, og den gamle får status "Erstattet af" med link. Gamle noter slettes ikke.

Status-label har tre værdier:

| Status | Farve i status-makroen |
|---|---|
| Gældende | `Green` |
| Erstattet af &lt;link&gt; | `Yellow` |
| Forkastet | `Red` |

## Markdown-version

```markdown
**Status:** Gældende  <!-- eller: Erstattet af [<titel>](<link>) / Forkastet -->
**Dato for beslutning:** <ÅÅÅÅ-MM-DD>
**Besluttet af:** <navn eller forum>

## Kontekst

<Problemet med konkrete navne: hvilken pipeline, tabel, miljø, hvad gik galt eller hvad krævede et valg.>

## Beslutning

<Valget i én sætning først.> <Derefter uddybning.>

## Alternativer

- **<alternativ>**: fravalgt fordi <grund>.
- **<alternativ>**: fravalgt fordi <grund>.

## Konsekvenser

- **Det lever vi med:** <ulempe eller omkostning>
- **Det låser fast:** <hvad der bliver svært at ændre senere>

## Ændringslog

| Dato | Ændring | Hvorfor | Af | Reference |
|---|---|---|---|---|
| <ÅÅÅÅ-MM-DD> | Noten oprettet | <hvorfor beslutningen skulle skrives ned> | <navn> | <PR / Jira-nøgle> |
```

## Storage format

```xml
<p>
  <strong>Status:</strong>
  <ac:structured-macro ac:name="status" ac:schema-version="1">
    <ac:parameter ac:name="colour">Green</ac:parameter>
    <ac:parameter ac:name="title">Gældende</ac:parameter>
  </ac:structured-macro>
</p>
<p><strong>Dato for beslutning:</strong> &lt;ÅÅÅÅ-MM-DD&gt;</p>
<p><strong>Besluttet af:</strong> &lt;navn eller forum&gt;</p>

<h2>Kontekst</h2>
<p>&lt;problemet, med konkrete navne&gt;</p>

<h2>Beslutning</h2>
<p><strong>&lt;valget i én sætning&gt;</strong></p>
<p>&lt;uddybning&gt;</p>

<h2>Alternativer</h2>
<ul>
  <li><strong>&lt;alternativ&gt;</strong>: fravalgt fordi &lt;grund&gt;.</li>
  <li><strong>&lt;alternativ&gt;</strong>: fravalgt fordi &lt;grund&gt;.</li>
</ul>

<h2>Konsekvenser</h2>
<ul>
  <li><strong>Det lever vi med:</strong> &lt;ulempe eller omkostning&gt;</li>
  <li><strong>Det låser fast:</strong> &lt;hvad der bliver svært at ændre&gt;</li>
</ul>

<h2>Ændringslog</h2>
<!-- Indsæt tabellen fra templates/changelog.md -->
```

Erstattet note: skift status-makroen til `Yellow` / `Erstattet` og sæt linket lige efter makroen:

```xml
<p>
  <strong>Status:</strong>
  <ac:structured-macro ac:name="status" ac:schema-version="1">
    <ac:parameter ac:name="colour">Yellow</ac:parameter>
    <ac:parameter ac:name="title">Erstattet</ac:parameter>
  </ac:structured-macro>
  af <ac:link><ri:page ri:content-title="&lt;titel på ny note&gt;"/></ac:link>
</p>
```

Forkastet: `colour` = `Red`, `title` = `Forkastet`.
