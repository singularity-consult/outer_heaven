# Skabelon: guide

Bruges til Onboarding, Arbejdsgange og Regler og faldgruber. Erstat alt i `<...>`. Fjern ikke sektioner; skriv hellere én sætning end at udelade en overskrift.

## Markdown-version

~~~markdown
> **Formål:** <én sætning om hvad guiden får dig til at kunne>
> **Målgruppe:** <fx ny udvikler på Data Estate, data engineer der deployer>
> **Forudsætninger:** <adgange, værktøjer, links til andre sider>

## Hvornår bruger du denne guide

<Situationen der udløser guiden, med konkrete navne. Hvornår du IKKE skal bruge den.>

## Trin for trin

1. <Trin med konkret navn på pipeline, tabel eller miljø.>

   ```sql
   SELECT COUNT(*) FROM <katalog>.<skema>.<tabel>;
   ```

2. <Næste trin.> Screenshot fra dev, fuld opløsning, beskåret:

   ![<beskrivelse>](<fil>.png)

## Sådan ved du at det virkede

<Forventet output eller tjek: rækkeantal, status i monitoren, en forespørgsel og dens forventede resultat.>

## Faldgruber

> **Advarsel:** <det der har bidt os før, og hvad du gør i stedet>

## Hvorfor gør vi det sådan

<To til tre sætninger. Link til beslutningsnoten: [<titel>](<link>).>

## Ændringslog

| Dato | Ændring | Hvorfor | Af | Reference |
|---|---|---|---|---|
| <ÅÅÅÅ-MM-DD> | Siden oprettet | <hvorfor siden var nødvendig> | <navn> | <PR / Jira-nøgle> |
~~~

## Storage format

Sendes som `body.value` med `body.representation = "storage"`. Titlen sendes i `title`, ikke i body.

```xml
<ac:structured-macro ac:name="info" ac:schema-version="1">
  <ac:rich-text-body>
    <p><strong>Formål:</strong> &lt;én sætning&gt;</p>
    <p><strong>Målgruppe:</strong> &lt;målgruppe&gt;</p>
    <p><strong>Forudsætninger:</strong> &lt;adgange, værktøjer, links&gt;</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h2>Hvornår bruger du denne guide</h2>
<p>&lt;situationen, med konkrete navne&gt;</p>

<h2>Trin for trin</h2>
<ol>
  <li>
    <p>&lt;trin&gt;</p>
    <ac:structured-macro ac:name="code" ac:schema-version="1">
      <ac:parameter ac:name="language">sql</ac:parameter>
      <ac:parameter ac:name="linenumbers">true</ac:parameter>
      <ac:parameter ac:name="title">&lt;titel på kodeblok&gt;</ac:parameter>
      <ac:plain-text-body><![CDATA[SELECT COUNT(*) FROM <katalog>.<skema>.<tabel>;]]></ac:plain-text-body>
    </ac:structured-macro>
  </li>
  <li>
    <p>&lt;trin&gt;</p>
    <ac:image ac:width="860"><ri:attachment ri:filename="<fil>.png"/></ac:image>
  </li>
</ol>

<h2>Sådan ved du at det virkede</h2>
<p>&lt;forventet output eller tjek&gt;</p>

<h2>Faldgruber</h2>
<ac:structured-macro ac:name="warning" ac:schema-version="1">
  <ac:rich-text-body>
    <p>&lt;det der har bidt os før, og hvad du gør i stedet&gt;</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h2>Hvorfor gør vi det sådan</h2>
<p>&lt;kort begrundelse&gt; Se <a href="&lt;link til beslutningsnote&gt;">&lt;titel&gt;</a>.</p>

<h2>Ændringslog</h2>
<!-- Indsæt tabellen fra templates/changelog.md -->
```

Bemærk:

- Inde i `CDATA` skrives koden råt (ingen `&lt;`). Uden for `CDATA` skal `<` og `>` i tekst escapes.
- Python-kode bruger `<ac:parameter ac:name="language">py</ac:parameter>`.
- `ri:filename` skal matche en vedhæftning på siden. Vedhæft først, indsæt billedet bagefter.
