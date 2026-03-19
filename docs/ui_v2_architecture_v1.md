# UI v2 Architecture v1

Status: Frozen for `TASK-UI-11`
Version: `v1`
Scope: `ui-v2/` P0 trackside shell

## Goals
- Ship a modern, fast, offline-friendly frontend shell that coexists with the legacy `ui/` prototype.
- Optimize for trackside scanning: one dominant instruction, clear did-vs-should structure, immediate route changes.
- Keep tooling light enough to run cleanly in WSL2 without framework churn.

## Stack
- Runtime: standards-based ES modules in the browser
- Tooling: Node scripts for `dev` and `build`
- Output: static files under `ui-v2/dist/`
- Data source: existing local API endpoints under `/import`, `/summary`, `/insights`, `/compare`, `/map`

Why this stack:
- no framework dependency is required to satisfy current route complexity
- dev/build workflow stays deterministic and WSL2-friendly
- route/state logic remains inspectable by the Python evaluation harness

## Route Model
- `import`: session selection and offline/local import entry point
- `summary`: lap cards and lap table
- `insights`: dominant top-1 coaching view with did/should/because/success check and map context
- `compare`: lap A vs lap B deltas and compare map
- `corner`: focused corner detail derived from the currently selected insight

Routing is hash-based for static hosting and offline portability.

## State Model
- One root `appState` object
- Durable keys:
  - `route`
  - `sessionId`
  - `source`
  - `loading`
  - `error`
  - `summary`
  - `insights`
  - `compare`
  - `trackMap`
  - `compareMap`
  - `selectedInsightId`
  - `selectedSegmentId`
  - `compareSelection.referenceLap`
  - `compareSelection.targetLap`
- Derived state:
  - top insight index
  - selected insight payload
  - corner detail payload

## Component Model
- App shell
  - header brand + route buttons + connection badge
- Import screen
  - import form
  - recent/offline notes
- Summary screen
  - summary card rail
  - lap table
- Insights screen
  - top-1 hero
  - did-vs-should stack
  - insight list
  - map panel
  - summary rail
- Compare screen
  - lap selectors
  - compare delta list
  - compare map
- Corner screen
  - selected-corner detail
  - rider action checklist
  - evidence/quality notes

## Visual System
- Look: warm pit-wall paper + telemetry cyan + signal orange
- Typography:
  - headings: squarer techno/sans stack for motorsport flavor
  - body: readable humanist sans stack
- Hierarchy:
  - top-1 hero is materially larger than secondary cards
  - did/should/because/success check are four fixed semantic blocks
  - risk tier, confidence, and gain live in a compact telemetry rail
- Motion:
  - screen transitions use short fade/slide
  - cards use stagger only on insights entry
- Color semantics:
  - `Primary`: telemetry cyan
  - `Experimental`: signal amber
  - `Blocked`: brake red
  - confidence chips reuse fixed palette across routes

## Interaction Rules
- Route changes must work from one click/tap without double activation.
- Insight selection updates:
  - selected card styling
  - map highlight
  - corner route payload
- Compare selector changes re-fetch compare/map data for explicit lap choices.
- `not_ready` and error responses must render in place with actionable text, never blank screens.

## Evaluation Implications
- The frontend harness must inspect:
  - route declarations and route buttons
  - explicit top-1 hero semantics
  - did-vs-should field rendering tokens
  - compare/corner route stability hooks
  - map legend/highlight semantics
  - interaction-binding tokens for route, compare, and insight selection

## Coexistence Rules
- Keep legacy `ui/` untouched as a fallback prototype during migration.
- New work lands in `ui-v2/`.
- Root `npm run build` targets `ui-v2` only.

## Deferred Items
- Framework migration beyond ES modules
- richer compare drill-down and corner mini-timeline
- virtualized tables and large-session performance tuning
