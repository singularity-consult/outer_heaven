# Diary: ai-agents-mcp-typescript over på Anthropic SDK

Benny følger Coursera-kurset "AI Agents with Model Context Protocol & TypeScript" (Jules White). Kurskoden (klon af `juleswhite/ai-agents-mcp-typescript` i `C:\claudes_folder\repos\ai-agents-mcp-typescript`) kalder OpenAI og rå `fetch`. Målet var at alle LLM-kald går gennem `@anthropic-ai/sdk`, mens kursets struktur (PERCEIVE->DECIDE->ACT->OBSERVE, kommentarer, konsol-output) bevares, så videoerne stadig kan følges. Ingen commits, ingen push.

## Step 1: Omskrivning af LLM-kald og offline-validering

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** Arbejd direkte i C:\claudes_folder\repos\ai-agents-mcp-typescript (frisk klon af https://github.com/juleswhite/ai-agents-mcp-typescript, Coursera-kursuskode; Benny har eksplicit bedt om at den tilpasses). Ingen worktree, ingen commits, ingen push. Rør ikke MCP-server-/test-filer ud over hvad der er nødvendigt. MÅL: Alle LLM-kald skal gå via det officielle Anthropic TypeScript SDK (`@anthropic-ai/sdk`) i stedet for OpenAI / rå fetch. [...resten af lead-briefen: tre kaldsteder llm.ts / expense-agent.ts / self-prompting-server.ts, claude-opus-5 default med ANTHROPIC_MODEL-override, haiku-4-5 med temperature 0 til klassifikation, fallbacks kun hvis det typecheck'er, .env.example, README, tsc + ikke-LLM tests, rapport på dansk.]
**Interpretation:** Udskift OpenAI/fetch med SDK'et i de tre navngivne filer plus alle andre OpenAI-referencer, uden at ændre agent-filerne i 01, og bevis det med tsc, eksisterende tests og hvad der ellers kan køres uden API-nøgle.
**Inferred intent:** Benny vil kunne køre kursets eksempler på sin Anthropic-konto og samtidig lære det rigtige tool_use/tool_result-mønster.

### What I did
Baseline først: `npm install` + `npx tsc --noEmit` på den urørte kode i alle tre `code/`-mapper gav exit 0, så der var ingen præeksisterende typefejl. Derefter `npm uninstall openai` (02, 03) og `npm install @anthropic-ai/sdk@latest` (01, 02, 03), som gav `^0.128.0`.

`01-intro-to-mcp-agents/code/llm.ts` er omskrevet til én `AnthropicProvider` med `new Anthropic()` og `client.beta.messages.create` med `betas: ["server-side-fallback-2026-07-01"]` + `fallbacks: "default"`. Det eksporterede interface (`Message`, `Tool`, `ToolCall`, `LLMResponse`, `LLMProvider`, `createLLMFromEnv`) er bevaret, så `agent.ts`, `workspace-agent.ts` og `agent-with-learning.ts` er uændrede. `Message.content` er udvidet til `string | null`. En `toConversation`-hjælper springer tomme/null-beskeder over, slår samme-rolle-beskeder sammen og fejler tydeligt hvis samtalen ikke starter og slutter med user. `import "dotenv/config"` ligger nu i `llm.ts`, fordi `agent-with-learning.ts` manglede det. `refusal` og `max_tokens` kaster tydelige fejl.

`02-failing-forward/code/src/expense-agent.ts` bruger nu Messages API med rigtige blokke: hele `response.content` appendes som assistant-turn, alle `tool_result` for en turn samles i én user-besked, `is_error` sættes ved MCP `isError`, ved en exception fra `callTool` eller ved `status: "failed"`, og loopet kører på `stop_reason === "tool_use"` med `pause_turn` håndteret. Typerne er SDK'ets `Anthropic.Beta.*`, fordi fallbacks kræver beta-namespacet.

I 03 er `self-prompting-server.ts` flyttet til `claude-haiku-4-5` med `temperature: 0` og `max_tokens: 1024`. To ekstra kaldsteder dukkede op, som briefen ikke nævnte: `validate-at-source-server.ts` (samme mønster, også Haiku) og `test-all.ts` (et fuldt agent-loop, nu med Opus 5 og fallbacks). Uden dem havde 03 ikke kunnet kompilere efter at `openai` var fjernet. Til sidst `.env.example` i hver code-mappe og fire minimale rettelser i `README.md`.

### Why
Lead-briefen bad om SDK-kald, rigtige tool_use-blokke i 02 og en lille model i 03. `validate-at-source-server.ts` og `test-all.ts` skulle med, fordi målet var "alle LLM-kald" og fordi pakkefjernelsen ellers ville brække builden.

### What worked
`npx tsc --noEmit` gav exit 0 i alle tre mapper efter ændringerne (også `npm run typecheck` i 01). `npm run test-server` i 01 endte med "ALL TESTS PASSED!", exit 0. `npm test` i 02 er en server-demo uden LLM og gav exit 0.

Den mest værdifulde check var en lokal mock af `POST /v1/messages` (node, scratchpad), som SDK'et blev peget på via `ANTHROPIC_BASE_URL`. Den loggede hver request og viste:
- 01 `agent.ts`: `/v1/messages?beta=true`, header `anthropic-beta: server-side-fallback-2026-07-01`, `fallbacks: "default"`, model `claude-opus-5`, `max_tokens` 16000, ingen temperature/thinking, system som separat felt, tools med `input_schema`, og i andet kald en strengt alternerende user/assistant/user-samtale.
- 02 `expense-agent.ts` med to parallelle tool_use (get_expense_categories + submit_expense med ugyldig kategori): andet kald havde hele assistant-content og én user-besked med begge tool_results; ids matchede, og `is_error: true` sad kun på den fejlede.
- 03: Haiku-kald med `temperature: 0`, uden beta-header; et ```json-indpakket svar blev parset korrekt i begge servere.
- Refusal-mock: begge agenter stopper med "Claude declined ... (refusal, category: cyber)".

### What didn't work
Mine Python-patchscripts, sendt via bash-heredoc, skrev `"\\n"` ud som et rigtigt linjeskift i TS-filen. `npx tsc --noEmit` i 02 fejlede med `src/expense-agent.ts(74,97): error TS1002: Unterminated string literal.` (plus følgefejl). Det skete igen i `self-prompting-server.ts`. Jeg rettede det med Edit og brugte Edit-værktøjet til de efterfølgende ændringer.

Mit første verifikationsscript fejlede på stier og encoding: `FileNotFoundError: ... '/c/Users/.../r01.jsonl'` (Windows-Python forstår ikke MSYS-stier; løst med `cygpath -w`), og derefter `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81` (løst med `encoding="utf-8"`).

`npm test` i 03 kan ikke køre uden nøgle: `Error: ANTHROPIC_API_KEY not found in .env file` (samme guard som originalen havde for OPENAI_API_KEY).

### What I learned
`@anthropic-ai/sdk` 0.128.0 typer `fallbacks` som `Array<BetaFallbackParam> | 'default'`, og `AnthropicBeta` indeholder `'server-side-fallback-2026-07-01'`, så fallbacks typecheck'er rent. Uden credentials fejler `new Anthropic()` ikke ved konstruktion, men først ved kaldet: "Could not resolve authentication method. Expected one of apiKey, authToken, credentials, config, or profile to be set."

### What was tricky
Arbejdskopien er CRLF (`core.autocrlf=true`), men mine scripts skrev LF. Jeg normaliserede de berørte filer til CRLF, så diffen ikke bliver hele filen.

### What warrants review
- `llm.ts` `toConversation`: den trimmer beskedtekst og slår samme-rolle-beskeder sammen. Det er bevidst defensivt og ikke nødvendigt for de nuværende agenter.
- 02 sætter `is_error` på `status: "failed"`. Det er et semantisk valg; Failing Forward-pointen (instruktioner i fejlsvaret) er bevaret, fordi content stadig er hele JSON-svaret.
- `test-all.ts` bruger Opus 5 som test-agent (ikke Haiku), så en fuld `npm test` i 03 koster mere end før. Kan sænkes med `ANTHROPIC_MODEL`.

### Future work
- Live-kørsel med rigtig nøgle er ikke sket: ingen agent, ingen fallback og ingen Haiku-klassifikation er set mod det rigtige API.
- `max_tokens`-grenen er ikke mock-testet (samme kodeform som refusal-grenen, som er testet).
- Præeksisterende: `agent-with-learning.ts` henviser til `npm run agent-learn`, som ikke findes i 01's package.json.
