# Skabelon: ændringslog

Står nederst på hver side under overskriften "Ændringslog".

Regler:

- Kolonner: Dato | Ændring | Hvorfor | Af | Reference (PR / Jira-nøgle).
- Nyeste række øverst.
- Kun indholdsmæssige ændringer. Stavefejl og formatering ligger i Confluence' sidehistorik.
- "Hvorfor" er obligatorisk. En række uden begrundelse tæller ikke.

Begrundelse: Confluence har allerede versionshistorik, der viser hvad og hvornår. Loggens eneste merværdi er hvorfor-feltet. En række som "Opdateret trin 3" uden grund er støj.

Godt og dårligt eksempel på hvorfor-feltet:

- Dårligt: "Opdateret."
- Godt: "Trin 3 pegede på den gamle pipeline, der er nedlagt; nye udviklere genkørte den forkerte."

## Markdown-version

```markdown
## Ændringslog

| Dato | Ændring | Hvorfor | Af | Reference |
|---|---|---|---|---|
| <ÅÅÅÅ-MM-DD> | <hvad der ændrede sig i indholdet> | <hvorfor ændringen var nødvendig> | <navn> | <PR / Jira-nøgle> |
| <ÅÅÅÅ-MM-DD> | Siden oprettet | <hvorfor siden var nødvendig> | <navn> | <PR / Jira-nøgle> |
```

## Storage format

```xml
<h2>Ændringslog</h2>
<table>
  <tbody>
    <tr>
      <th><p>Dato</p></th>
      <th><p>Ændring</p></th>
      <th><p>Hvorfor</p></th>
      <th><p>Af</p></th>
      <th><p>Reference</p></th>
    </tr>
    <tr>
      <td><p>&lt;ÅÅÅÅ-MM-DD&gt;</p></td>
      <td><p>&lt;hvad der ændrede sig i indholdet&gt;</p></td>
      <td><p>&lt;hvorfor ændringen var nødvendig&gt;</p></td>
      <td><p>&lt;navn&gt;</p></td>
      <td><p>&lt;PR / Jira-nøgle&gt;</p></td>
    </tr>
  </tbody>
</table>
```

Ny række indsættes som første `<tr>` efter header-rækken.
