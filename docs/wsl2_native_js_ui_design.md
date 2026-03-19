# WSL2-Native Runtime and Modern JavaScript UI Design

Date: 2026-03-08
Repo: `aimSoloAnalysis`
Status: design intake

## Purpose
Define the path to make Aim Solo Analysis run natively and comfortably inside WSL2, and to upgrade the current UI from a small static JavaScript page into a frontend architecture capable of meeting the repo's explicit UI-excellence and trackside-speed requirements.

This design treats these as one initiative because they are coupled:
- if the local runtime is still partially Windows/PowerShell-centric, frontend iteration stays awkward
- if the frontend remains a thin static page, UI excellence will stay under-specified and difficult to verify

## Problem Statement
The repo currently has a functioning local Python backend and a small static UI under `ui/` (`index.html`, `app.js`, `styles.css`). That is sufficient for early MVP exploration, but it is too weak for the product bar now described in:
- `UX_SPEC.md`
- `REQUIREMENTS_BASELINE.md`
- `BUILD_PLAN.md`

At the same time, the planner/bootstrap workflow still assumes PowerShell for repo-state refresh (`tools/update_bootstrap.ps1`), which is not runnable in the current WSL2 environment because `pwsh` is absent. That is a concrete operating gap for day-to-day development and AI planning.

## Goals
1. Make the project comfortably operable from WSL2 without depending on PowerShell.
2. Preserve local/offline-first development and runtime.
3. Upgrade the UI to a modern JavaScript application architecture that supports high-quality trackside UX.
4. Improve frontend testability, route structure, component reuse, and evaluation-harness integration.
5. Keep the migration incremental enough that working backend/API paths are not destabilized unnecessarily.

## Non-Goals
1. No cloud deployment redesign.
2. No requirement to move the backend away from Python/FastAPI.
3. No real-time telemetry streaming in this initiative.
4. No XRK decode parity work in this initiative.
5. No UI framework migration purely for fashion; the goal is product/UX capability, not novelty.

## Current State Summary

### Backend
- Python codebase for ingest, storage, analytics, and API.
- FastAPI app in `api/app.py`.
- SQLite persistence.
- Evaluation tooling already exists for backend and frontend.

### Frontend
- Static frontend in `ui/`:
  - `ui/index.html`
  - `ui/app.js`
  - `ui/styles.css`
- Current UI can support basic route shell and flow demos, but it does not provide the architecture needed for:
  - stronger information hierarchy
  - richer interaction states
  - composable screen-level reuse
  - high-confidence visual and interaction testing
  - sustained UX iteration at the level implied by the requirements

### Runtime / Planner Tooling
- Repo instructions require `pwsh -File tools/update_bootstrap.ps1`.
- In the current WSL2 environment, `pwsh` is not installed.
- This creates planner friction and means bootstrap state cannot be refreshed using the repo's preferred toolchain.

## Why the UI Change Is Needed Even Though the UI Is Already JavaScript
Strictly speaking, the current UI is already JavaScript. The actual issue is not language; it is frontend architecture maturity.

Current UI characteristics:
- static HTML shell
- hand-managed DOM updates
- limited state organization
- likely growing coupling between screens and shared logic

That is acceptable for an early prototype, but not for a product with requirements like:
- rapid trackside comprehension
- top-1 recommendation visual dominance
- clear "did vs should" interactions and evidence displays
- consistent confidence/risk semantics
- route-level robustness for import -> summary -> insights -> compare
- future at-home deep-analysis expansion

So the real target is:
- modern JavaScript frontend architecture
- componentized stateful UI
- better testability and route modeling
- better long-term UX leverage

## Design Recommendation

### Recommendation 1: Make the toolchain WSL2-native first
Do not keep a split mental model where some planning/dev flows assume Windows PowerShell while implementation runs in Linux.

The repo should have a native WSL2 path for:
- bootstrap refresh
- API startup
- frontend startup
- evaluation commands
- planner task execution

### Recommendation 2: Keep backend Python, replace the static UI with a modern JS app
The backend does not need a language rewrite. The correct move is:
- keep Python/FastAPI backend and analytics pipeline
- replace the current static UI with a real JavaScript frontend app

### Recommendation 3: Prefer SvelteKit + TypeScript for the UI rewrite
Why SvelteKit over React or continuing vanilla JS:
- lower boilerplate than React for a small local tool
- easier to build expressive, fast-feeling UI with less ceremony
- good fit for route-driven local apps
- strong ergonomics for state + derived UI + transitions
- easier to keep components readable for AI-assisted iteration
- easier to host locally from static or dev server flows

If TypeScript feels too heavy, plain JavaScript is possible, but TypeScript is recommended because the app is becoming multi-screen, data-rich, and API-contract-heavy.

## WSL2-Native Design

### Objectives
1. No planning-critical PowerShell dependency.
2. One documented Linux/WSL2 command path for common tasks.
3. Clear filesystem/path strategy for CSV imports and artifacts.
4. Stable browser access from Windows to the WSL2-hosted local app.

### Tooling Changes

#### Replace `tools/update_bootstrap.ps1` with a native equivalent
Use a native bootstrap refresh command:
- `python3 tools/update_bootstrap.py`

Why Python rather than Bash:
- repo already depends on Python
- cross-platform path handling is easier to keep correct
- avoids separate shell portability issues
- easier to test in CI/local pytest if desired

PowerShell can remain as a compatibility wrapper if desired, but the canonical planner path should be the native script.

#### Standardize startup commands
Document canonical native commands such as:
- backend: `PYTHONPATH=. uvicorn api.app:app --reload --host 0.0.0.0 --port 8000`
- frontend dev: `npm run dev -- --host 0.0.0.0 --port 4173`
- backend eval: `PYTHONPATH=. python3 tools/eval_backend.py`
- frontend eval: `PYTHONPATH=. python3 tools/eval_frontend.py`
- planner refresh: `python3 tools/update_bootstrap.py`

#### Path strategy
The runtime should explicitly support:
- WSL-native repo paths
- imported files under Linux-visible paths
- optional `/mnt/c/...` file selection when source CSVs remain on Windows

Recommendation:
- support reading CSVs from `/mnt/c/...` directly for convenience
- but use WSL-native artifact/cache/output paths under the repo or configured Linux data dirs

#### Browser access model
Run backend and frontend inside WSL2 and access them from the Windows browser using localhost-mapped ports.

This is the simplest operator model:
- compute stays in WSL2
- browser stays on Windows if desired
- no mixed Windows/Python runtime needed
- Windows browser targets: `http://localhost:4173` for the frontend dev server and `http://localhost:8000` for the backend API

## Modern JS UI Design

### Product Direction
The UI must serve two different but related modes:
1. trackside quick-insight mode (P0)
2. at-home deeper analysis mode (P1)

The rewrite should prioritize P0, but the architecture must not block P1.

### UX Principles
1. The UI should feel immediate and high-signal under time pressure.
2. Primary focus must be obvious without reading all cards.
3. "Did vs should" must be visually first-class, not buried in prose.
4. Confidence, risk, and expected gain must be consistently encoded.
5. The route flow import -> summary -> insights -> compare must be stable, not fragile.
6. Offline/local status must be clear but not visually dominant.

### Route Model
Recommended frontend routes:
- `/import`
- `/summary/[sessionId]`
- `/insights/[sessionId]`
- `/compare/[sessionId]`
- `/corner/[sessionId]/[cornerId]`

These match the build plan and current mental model.

### Core Screen Architecture

#### 1. Import Screen
Purpose:
- ingest a CSV quickly
- confirm track + direction
- confirm rider/bike context
- launch analysis with confidence

Key UX requirements:
- drag/drop or file select
- recent imports
- explicit track direction selection
- clear analyze CTA
- clear loading/progress states

#### 2. Summary Screen
Purpose:
- orient the rider/coach in seconds

Key UX requirements:
- best lap prominence
- valid-laps filter
- quick alerts
- one-tap transition into compare or insights

#### 3. Insights Screen
Purpose:
- deliver the top next-session coaching recommendations

Key UX requirements:
- top 1 visually dominant
- max 3 surfaced at once
- clear `Action`, `Evidence`, `Estimated gain`
- explicit confidence and risk framing
- clear corner identity
- selected insight drives map/highlight state

#### 4. Compare Screen
Purpose:
- inspect where time is gained/lost and why

Key UX requirements:
- stable lap selectors
- track overlay
- delta trace
- segment table
- fast switching without visual confusion

#### 5. Corner Detail Screen
Purpose:
- let the rider inspect one corner with enough evidence to act

Key UX requirements:
- corner mini-map
- entry/apex/exit framing
- rider vs target framing
- success-check cues when available

## Frontend Architecture Recommendation

### Stack
- SvelteKit
- TypeScript
- Vite (via SvelteKit)
- lightweight CSS architecture using design tokens and scoped component styles

### Why this stack fits the repo
- The current app is local-first and route-oriented.
- API contracts are stable enough to support a typed client.
- The evaluation harness can be strengthened around predictable selectors and page states.
- The UI needs more structure, not more backend complexity.

### App Structure
Suggested structure:

```text
ui-v2/
  src/
    lib/
      api/
      components/
      stores/
      utils/
      types/
    routes/
      import/
      summary/[sessionId]/
      insights/[sessionId]/
      compare/[sessionId]/
      corner/[sessionId]/[cornerId]/
    app.html
    app.css
```

### API Client Contract
Create a typed API client that wraps:
- `/import`
- `/summary/{session_id}`
- `/insights/{session_id}`
- `/compare/{session_id}`
- `/map/{session_id}`

If current endpoints are missing UI-critical payload structure, adjust backend responses deliberately rather than letting the frontend compensate with ad hoc transformations everywhere.

## UI Excellence Requirements Mapped to Architecture

### Top-1 recommendation dominance
This should not be a styling afterthought.

Architectural implication:
- insights route needs explicit component hierarchy for:
  - primary insight
  - secondary insights
  - evidence panel
  - map/highlight synchronization

### Did-vs-should clarity
Architectural implication:
- insight data contract should carry distinct fields for:
  - `did`
  - `should`
  - `because`
  - `success_check`
- UI should render these as structured slots, not freeform concatenated text

### Confidence/risk consistency
Architectural implication:
- a shared semantic-badge component should render:
  - confidence
  - risk tier
  - blocked/experimental semantics where needed

### Trackside responsiveness
Architectural implication:
- frontend should cache recent session payloads locally in memory/session store
- route transitions should not fully reset global selector context
- expensive map/compare payloads should load progressively

## Migration Strategy

### Phase 1: WSL2-native tooling baseline
Deliver:
- native bootstrap refresh script
- native run commands documented
- path/runtime docs updated
- planner workflow no longer depends on `pwsh`

This should happen first because it improves every later iteration.

### Phase 2: Freeze frontend API contract for rewritten UI
Before the UI rewrite, freeze or at least explicitly document:
- import response contract
- summary payload
- insights payload
- compare payload
- map payload
- not-ready and error states

Without this, the frontend rewrite will drift into guesswork.

### Phase 3: Create new frontend alongside current UI
Do not rewrite in place.

Recommended approach:
- keep `ui/` as legacy prototype temporarily
- add `ui-v2/` as the new app
- serve it separately until core routes are ready

This de-risks the change and lets evaluation harnesses compare old vs new behavior during migration.

### Phase 4: Port trackside P0 screens in order
Recommended order:
1. Import
2. Summary
3. Insights
4. Compare
5. Corner Detail

Reason:
- that matches the core trackside flow
- insights can be designed correctly only once summary/session-selection semantics are stable

### Phase 5: Upgrade evaluation harnesses for UI quality
The existing frontend harness should evolve from simple route/behavior checks into:
- critical flow checks
- payload/render contract checks
- timing and responsiveness checks
- top-1 dominance and did-vs-should surface checks

## Risks

### Risk 1: rewriting the UI before freezing payload shape
If the UI contract is not frozen first, the frontend will encode unstable assumptions and churn.

### Risk 2: doing a framework migration without a UX contract
The framework itself does not create UI excellence. The UX contract still needs to be explicit.

### Risk 3: keeping Windows-specific planner tooling while moving the app to WSL2
That would preserve the exact friction this initiative is supposed to remove.

### Risk 4: overbuilding P1 before P0 trackside quality is excellent
The product bar says trackside quality matters first. P1 should not dilute that.

## Recommended Task Priority After This Design

### Highest priority
1. Native WSL2 bootstrap and run tooling
2. Freeze did-vs-should payload contract
3. Implement deterministic coaching copy policy and evidence plumbing
4. Add golden behavior tests and scorecard gating for coaching quality
5. Freeze and design the modern JS frontend API/UX contract

### Why this order
- WSL2-native tooling removes current operating friction immediately
- the did-vs-should payload contract is the core product contract for the UI
- frontend excellence depends on a stable insight contract
- scorecard gating is needed so the rewrite improves product quality instead of only aesthetics

## Proposed New Task Sequence

### Platform / Tooling
- `TASK-PLAT-01`: Replace PowerShell bootstrap with native Python bootstrap refresh tool for WSL2/Linux
- `TASK-PLAT-02`: Document and validate native WSL2 run/eval workflow for backend, frontend, and planner operations

### Product contract
- keep existing priority on `TASK-P0-09` through `TASK-P0-14`
- those tasks are now even more important because they define the UI contract the rewrite depends on

### UI design and migration
- `TASK-UI-10`: Freeze frontend API/payload contract for import/summary/insights/compare/map for the rewritten UI
- `TASK-UI-11`: Design modern trackside JS UI architecture and visual system for P0 flow
- `TASK-UI-12`: Scaffold `ui-v2/` SvelteKit app and wire route shell
- `TASK-UI-13`: Implement Import + Summary in `ui-v2`
- `TASK-UI-14`: Implement Insights route with top-1 dominance and structured did-vs-should rendering
- `TASK-UI-15`: Implement Compare + Corner Detail routes and upgrade frontend eval harness

## First Recommended Dispatch
If only one new task is dispatched first, it should be:

`TASK-PLAT-01`: Replace PowerShell bootstrap with native Python bootstrap refresh tool for WSL2/Linux

Reason:
- it removes immediate planner/dev friction
- it unblocks cleaner repo operation from WSL2
- it is relatively self-contained
- it reduces future coordination overhead for every subsequent task

## Second Recommended Dispatch
After native tooling is in place, dispatch:

`TASK-P0-10`: Freeze top-insight did-vs-should payload contract

Reason:
- the frontend rewrite should not start before this contract is explicit
- this is the most important interface between analytics output and UI excellence

## Recommendation
Treat the initiative as:
1. WSL2-native tooling normalization
2. coaching-contract hardening (`TASK-P0-09` to `TASK-P0-14`)
3. modern JS frontend rewrite on top of that contract

That sequencing is the highest-leverage path and best aligned with the repo's stated product requirements.
