# Phase 4 — Pre-implementation audit of Phase 1–3

STOP-before-implementing audit, as required by the Phase 4 spec. No Phase
1–3 file was modified to produce this. Every claim below was checked
against the actual repository and/or a live test run in this session
(not recalled from memory) — see the "how verified" note under each
section. Sections 16–17 flag the specific points that need your decision
before any Phase 4 code touches them.

## 1. Project architecture

```
/android   Expo/React Native client — interface only, no AI logic
/backend   FastAPI service (backend/app/*) — the actual intelligence
/agent     AIProvider abstraction (Claude today) + coding-agent interface
/memory    schema.sql + migrations/0002_phase2.sql + 0003_phase3.sql
/tools     cross-cutting tool *specifications* (name/schema/permission)
/prompts   versioned prompt templates
/docker    docker-compose.yml (Postgres + backend)
/docs      ARCHITECTURE.md, DECISIONS.md, PHASE_1/2/3.md (this file: 4)
```
145 Python files, 21 backend/agent test files. `backend/app` has 25
subpackages (api, audit, auth, business, capabilities, communication,
context, cost, db, escalation, evaluation, events, health, knowledge,
learning, memory, orchestrator, permissions, planner, policy, proactive,
profile, suggestions, tasks, tools, wallet, ws).

**The one finding that reframes everything else in this audit:** there is
no persistent host anywhere in Phase 1–3. The backend is a normal FastAPI
process, started manually (`uvicorn` / `docker compose up`), that runs
only while something keeps it running — there is no systemd unit, no
cloud deployment, no always-on VM. Phase 4's "24/7 operating mode,"
"background workers," "daily/weekly review," and "continuous operation
without a new user command" all assume the backend process stays alive
indefinitely. That's true of the code Phase 4 will add (an
`asyncio`/APScheduler loop *can* run forever inside the process) but not
of anything today — nobody has deployed this backend anywhere it would
actually stay up between your sessions. I can build "runs forever while
the process is up" as code; I cannot make the process itself always be
up — that's a hosting decision (your own server, a cloud VM, a
persistently-running Docker host) that has to happen outside this repo.
Everything below assumes Phase 4 delivers the *capability* to run
continuously; actually running continuously, unattended, is a deployment
step for you, not a line of code.

## 2. Phase 1 summary

Stub-first monorepo: `StubOrchestrator`/`StubPlanner` (deterministic, zero
external deps), in-memory `WorkingMemory`/`ShortTermMemory`/`LongTermMemory`,
in-process `EventBus`, `ToolRegistry` with two real SAFE tools
(filesystem read, project inspection) and three SENSITIVE placeholders
(`GitHubTool`, `BrowserTool`, `WebSearchTool` — all raise
`NotImplementedError` on purpose, correct metadata, no real integration).
`PermissionLevel.SAFE/SENSITIVE` + `ConfirmationManager` is the entire
Phase 1 security model. Android app is a thin Expo/RN client talking to
the backend over REST + WebSocket only.

## 3. Phase 2 summary

Postgres-backed (`postgres_store.py`) replaces the in-memory stores
*behind the same interfaces*. Adds: `knowledge` (11 categories, trigram+
difflib dedup), `profile`/`projects`/`goals`/`interests`/`workflows`
(soft references, not FK-enforced — deliberate, see DECISIONS.md),
`suggestions` queue, `ProactiveLearningEngine` (manual-invoke only, no
scheduler — off by default), `CostTracker`, persisted `tasks` lifecycle,
deterministic `EvaluationEngine` (no second Claude call to grade the
first), `AuditLogger` (wildcard `EventBus` subscriber → `audit_log`
table), `ClaudePlanner`/`ClaudeOrchestrator` (falls back to the Phase 1
stub pair on any failure), `ModelRouter` with `fast`/`primary`/`fallback`
roles. Single gate: `claude_ready = pool is not None and
settings.jarvis_use_claude and bool(settings.anthropic_api_key)` — one
global boolean, checked once at process startup in `deps.py`, turns the
*entire* Phase 2 (and now Phase 3) stack on or off as one unit. No
partial/hybrid state exists today.

## 4. Phase 3 summary

Centralized `PolicyEngine.evaluate(PolicyRequest) -> ALLOW/DENY/ASK`
(`backend/app/policy/engine.py`), reusing `ConfirmationManager` for the
ASK path (no second approval mechanism). Five `AutonomyLevel`s
(`LEVEL_1_SUGGEST` … `LEVEL_5_SAFE_AUTOMATION`, int enum, stored in the
existing `preferences` table). New domains, each a `Tool` — not a second
orchestrator path: `wallet` (real internal ledger, GREEN/YELLOW/RED,
weekly/monthly/per-transaction limits, **no real payment rail**),
`communication`+`escalation` (real classification/policy/audit, actual
transmission is `NotConfiguredChannelAdapter` → `NotImplementedError`),
`business` (ideas/customers/opportunities/experiments/revenue + a
deterministic opportunity-scoring formula), `capabilities` (real,
unauthenticated GitHub repo search — network-blocked in this sandbox's
proxy, not a code defect), `health` (live self-diagnostics, honest
`NOT_CONFIGURED`/`NOT_TESTED` everywhere nothing real exists yet).
Android gained `JarvisCore` (9-state visual identity), real on-device TTS
(`expo-speech`), and a command-center dashboard + 7 new screens.

## 5. Existing AI/model architecture

`agent/provider/base.py`'s `AIProvider` (`stream()`/`complete()`) is the
only thing the backend depends on — never the `anthropic` SDK directly.
`ModelRouter` (`agent/provider/router.py`) holds three roles
(`fast`/`primary`/`fallback`), each a `ClaudeProvider` at a different
model tier, with retry/timeout and same-family fallback. `FakeProvider`
is the deterministic test double used by the entire backend test suite.
This is a real, working single-provider router — there is no
multi-provider comparison, no cost/quality evaluator, no "pick a
different vendor" path. Phase 4's "Model Engine" (evaluator, cost
optimizer, multi-model consensus) is new work built *on* this interface,
not a replacement of it.

## 6. Existing tool architecture

`backend/app/tools/base.py`: `Tool` (dataclass, `name`/`description`/
`input_schema`/`permission_level`, abstract `execute(**kwargs)`) +
`ToolRegistry` (flat dict, `register`/`get`/`list`, no categories, no
versioning, no health/usage stats, no dependency graph). 5 Phase 3 tools
in `phase3_tools.py`, 5 Phase 1 tools (2 real SAFE + 3 `NotImplementedError`
SENSITIVE placeholders) in `filesystem.py`/`project_inspection.py`/
`placeholders.py`. Every field Phase 4 §"Tool Registry" wants (health
checks, latency, cost, fallback, discovery, versioning) is genuinely
absent today — this is net-new, additive metadata on top of the existing
`Tool` dataclass, not a redesign of it.

## 7. Existing agent architecture

**There is no "Agent" concept anywhere in the codebase** (confirmed:
`grep -rn "class.*Agent" backend/app` returns nothing). `/agent` is the
model-provider package (`AIProvider`), unrelated to Phase 4's "Agent
Runtime"/specialized agents (Research Agent, Coding Agent, etc.). Phase
4's entire Agent Runtime, orchestration, delegation, and performance
tracking is genuinely new — there is nothing to conflict with, but also
nothing to build on except the tool/policy/event primitives underneath.

## 8. Existing memory architecture

Three interfaces (`WorkingMemory`/`ShortTermMemory`/`LongTermMemory`),
one in-memory implementation (Phase 1 fallback + tests) and one Postgres
implementation (Phase 2 default). `LongTermMemory.search` is naive
substring/trigram matching — no embeddings, no vector search.
`pgvector`'s column is present in `schema.sql` but commented out
(documented upgrade path, never enabled). No episodic/procedural/
strategic/predictive memory categories exist — `knowledge` (11
categories) is the closest thing, plus `profile_facts`. Phase 4's memory
taxonomy (episodic, procedural, strategic, predictive, decision, failure,
success…) is new schema + new tables, layered beside the existing three,
not a replacement.

## 9. Existing database architecture

28 tables across three idempotent, additive SQL files (`IF NOT EXISTS`/
`ON CONFLICT` throughout, verified applicable to a fresh DB and safe to
re-run):
- `schema.sql` (3): `working_memory`, `short_term_memory`, `long_term_memory`
- `migrations/0002_phase2.sql` (12): `knowledge`, `profile_facts`,
  `preferences`, `projects`, `goals`, `interests`, `workflows`,
  `suggestions`, `tasks`, `audit_log`, `token_usage`,
  `knowledge_relationships`
- `migrations/0003_phase3.sql` (13): `policies`, `approvals`,
  `capabilities`, `contacts`, `communications`, `escalation_events`,
  `wallet_accounts`, `wallet_transactions`, `business_ideas`,
  `customers`, `opportunities`, `experiments`, `revenue_records`

No ORM — raw SQL via `asyncpg`. Convention is a new numbered migration
file per phase (`0004_phase4.sql`), never editing prior files in place —
matches the pattern DECISIONS.md documents for why Phase 2 did this.

## 10. Existing automation architecture

None, deliberately. `ProactiveLearningEngine.run_cycle()` is
manually-invoked, makes zero Claude calls, and is off by default
(`feature_proactive_learning=False`). `WorkflowDetector` only *recognizes*
a repeated tool-call sequence after the fact — it doesn't execute
workflows, branch, loop, or schedule anything. No cron/APScheduler
dependency exists anywhere (`grep -rn "apscheduler\|cron\|scheduler"` —
one doc comment, zero code). Phase 4's Scheduler/Task Queue/Workflow
Engine/Background Agents are 100% new infrastructure.

## 11. Existing phone/device capabilities

None. The Android app is Expo/RN with `expo-speech` for real
text-to-speech (verified: bundles, not verified on a physical
device/emulator — none available in this sandbox). No STT, no wake
word/VAD, no contacts/SMS/calls/calendar/camera/clipboard/accessibility
integration — `docs/PHASE_3.md`'s NOT_TESTED/NOT_IMPLEMENTED table is
exhaustive on this point and still accurate. `CommunicationChannelAdapter`
is the one designed seam for wiring in a real transport later; nothing
calls a real Android or telephony API today.

## 12. Existing APIs/integrations

REST (`backend/app/api/*.py` + `phase3_routes.py`) + WebSocket
(`backend/app/ws`), bearer-token gated. External integrations: Claude API
(real, working), GitHub — two *different* things, worth keeping distinct:
`GitHubTool` (`github.create_issue`, write, `NotImplementedError`
placeholder) vs. `capabilities.github_search` (read-only repo search,
real `httpx` call, code is correct, blocked by *this session's own proxy*
only — 403 on `api.github.com/search/*`, confirmed by direct `curl`,
while `api.github.com` root returns 200). No email, calendar, CRM,
payment, or messaging integration exists.

## 13. Existing authentication/permissions

Auth: **one static bearer token** (`JARVIS_API_TOKEN`, compared with `==`
in `app/auth/dependency.py`), explicitly documented as a placeholder
("swap for real OAuth/session auth later"). No users, no roles, no
per-user anything — every API call is "the one owner," full stop.
Permissions: `PermissionLevel.SAFE | SENSITIVE` — two values, no
read/write/execute/financial/external granularity. `PolicyEngine` (Phase
3) adds risk classification (GREEN/YELLOW/RED) and autonomy levels on
top, but only for wallet/communication/capability actions specifically —
ordinary tool calls still only see SAFE/SENSITIVE.

## 14. Existing tests

Verified live in this session (Postgres running locally):
```
backend: 127 passed, 1 skipped   (7.1s)
agent:    11 passed               (0.4s)
```
The 1 skip is the GitHub-search network test (sandbox proxy block, not a
bug). With Postgres made deliberately unreachable, 40 pass and 88 skip
cleanly — no crashes, confirming graceful degradation actually works, not
just on the happy path. 21 test files total; every one except
`test_phase3_routes.py` constructs services directly rather than booting
the app (documented in `app/deps.py`'s module docstring as the intended
pattern) — `test_phase3_routes.py` is the deliberate exception that boots
the real FastAPI app + lifespan.

## 15. Existing technical debt

All pre-existing and already self-documented (not new findings, no hidden
`TODO`/`FIXME`/`XXX` anywhere — confirmed by grep):
- Static bearer token (no real auth) — §13.
- Two-value permission model — §13.
- No vector/semantic search — substring/trigram only, `pgvector` column
  present but disabled — §8.
- Soft (non-FK) references from goals/interests/workflows to projects —
  deliberate, documented tradeoff (DECISIONS.md), not an oversight.
- No scheduler/background execution — §10.
- Global, process-wide `claude_ready` gate instead of per-user/session —
  fine for a single-owner Phase 1–3, a real constraint for Phase 4 (§17).
- No real communication transport, no real payment rail, no MCP registry,
  no browser automation, no coding-agent execution — all explicit
  `NotImplementedError`/`NOT_CONFIGURED`, never faked.

## 16. Phase 4 dependencies (net-new infrastructure Phase 4 needs before its higher-level engines can work)

- **Scheduler / background task runner** — nothing exists; needed for
  Task Engine, 24/7 mode, daily/weekly review, monitoring.
- **Agent Runtime** — nothing exists; needed for every specialized-agent
  feature.
- **Sandboxed execution environment** — nothing exists; required before
  any self-coding/self-update capability can safely run generated code
  against the live system (see §17, this is the sharpest edge in the
  whole spec).
- **Snapshot/rollback tooling for code changes** — beyond git itself,
  nothing automates "snapshot → apply → verify → rollback" today.
- **Extended capability/tool metadata schema** (risk class, resource
  cost, health/usage stats, dependency graph) — additive fields on top of
  the existing `Tool`/registry, not a redesign.
- **Real communication channel adapter(s)** — `NotConfiguredChannelAdapter`
  is the seam; an actual provider (email/SMS/etc.) is still not connected.
- **Vector/semantic search** — pgvector column exists but is disabled;
  needed for Knowledge Engine's semantic/hybrid search.
- **Monitoring/observability beyond structured logs** — no metrics, no
  traces, no health-score aggregation across subsystems.
- **A place to actually run continuously** — see §1. Not a code
  dependency, but a real one.

## 17. Phase 4 conflicts (need your decision before I touch anything)

These are the only points where Phase 4 as specified doesn't just extend
Phase 3 cleanly — I'm asking before assuming an answer, per your own
protocol:

**(a) Two different "autonomy level" scales already both claim the name.**
Phase 3 shipped `AutonomyLevel` (1 Suggest, 2 Prepare, 3 Ask, 4 Execute
Approved, 5 Safe Automation) wired directly into `PolicyEngine`, stored
in the `preferences` table, covered by tests. This Phase 4 spec defines a
*different* 6-level scale (0 Observe … 5 Human-Gated) with different
semantics and explicitly says not to default to human-gated. These don't
map 1:1, and conflating them risks silently changing what an existing
stored autonomy level means for wallet/communication actions that are
already policy-gated. **My proposed resolution** (not yet applied):
introduce Phase 4's scale as a distinct, additively-named concept (e.g.
`AutonomyMode` for the new continuous-loop/engine posture) that composes
*with* Phase 3's existing `AutonomyLevel` for actions PolicyEngine
already governs, rather than replacing or renumbering the enum Phase 3
tests and the `preferences` table already depend on. Confirm this is the
right call before I add it.

**(b) Self-coding/self-update is qualitatively different from anything in
Phase 1–3.** Nothing in this codebase has ever modified its own source
while running, and — per §16 — no sandbox or snapshot/rollback tooling
exists yet to do it safely. Your spec's own Self-Update Protocol requires
exactly that tooling *before* any autonomous code change.

**RESOLVED — confirmed by user 2026-09-02:** self-modification always
requires explicit human confirmation before anything is applied to the
running system, regardless of autonomy level or mode. This is not "human
gated" in the everyday sense the spec wants to avoid (ordinary tool use,
research, wallet transactions within limits, communication within policy
all proceed autonomously as designed) — it's specifically that "Jarvis
edits its own running backend code" is carved out as permanently
confirmation-required. Implemented as `backend/app/selfcode`: every
self-modification is a stored `SelfModificationProposal` (diff + reason +
risk + test plan + rollback plan) that must go through
`ConfirmationManager` and be explicitly approved before an `applied_at`
timestamp is ever set — the policy engine hard-codes this (not merely
defaults to it) so no autonomy-level setting can bypass it.

**(c) Permission-model extension approach.** Extending `PermissionLevel`
(SAFE/SENSITIVE) with the richer scopes Phase 4 wants (read/write/
execute/financial/external/risk-class) touches every existing `Tool`
subclass's constructor call. I'll do this additively (new optional
fields with defaults matching current SAFE/SENSITIVE behavior, so no
existing tool, test, or stored data changes meaning) rather than
replacing the enum — flagging so the approach itself is visible before
the diff lands, not asking you to approve each field.

None of the above should be read as "Phase 4 is blocked" — (a) and (c)
have a clear additive path I'll take unless you object; (b) is the one
place I'm asking you to actually choose, since it's a real safety
tradeoff and the spec itself calls for the protective tooling to exist
first.

## 18. Missing infrastructure

Covered concretely in §16; the two categories worth restating plainly:
nothing that runs on a timer or in the background exists yet (§10), and
nothing that lets generated code run against a copy of the system before
it touches the real one exists yet (§17b). Everything else Phase 4 lists
(capability registry richness, agent runtime, knowledge graph, prediction/
decision engines, economic analytics, business OS breadth, command
center) is buildable additively on the existing event bus / tool registry
/ policy engine / Postgres store pattern already proven across Phase 1–3.

## 19. Recommended implementation order

Your own 4A–4AE order is sound and I'll follow its shape; folding it into
what's actually buildable incrementally here:

1. **4A (done — this document).**
2. **4B–4E: Core Orchestrator extension, Capability Registry, Tool
   Registry extension, Permissions/Resource/Autonomy** — additive schema
   + services, no existing behavior changes. Foundation everything else
   composes on.
3. **4F–4H: Agent Runtime, Task Engine, Workflow Engine** — the biggest
   genuinely-new subsystem (§7); needs the scheduler from §16 to be real
   rather than manually-invoked.
4. **4I–4K: Memory Engine extensions, Knowledge Graph, Research Engine**
   — extends existing knowledge/memory tables; semantic search stays
   substring-based until an embedding source is chosen (same open item
   Phase 1–3 already left documented).
5. **4L–4N: Learning, Prediction, Decision Engines** — statistics/
   heuristics first (matches the existing non-LLM classifier pattern in
   `communication/classifier.py` and `business/scoring.py`), not a second
   Claude call standing in for every judgment.
6. **4O–4T: Self-Diagnostics → Self-Healing → Self-Coding → Self-Testing
   → Self-Update → Self-Improvement** — in that order specifically,
   because each one is the previous one's prerequisite, and 4Q
   (Self-Coding) is gated on §17(b) being resolved and real sandbox/
   snapshot tooling existing, not just planned.
7. **4U–4V: Economic Engine, Business OS** — extends Phase 3's wallet/
   business modules; still no real payment rail unless you decide
   otherwise (§17 doesn't touch this — Phase 3's stance stands).
8. **4W: Communication/Phone/Device layer** — still needs a real
   transport provider; the seam (`CommunicationChannelAdapter`) already
   exists.
9. **4X–4Z: Monitoring, Security, Command Center** — surfaces everything
   above; mostly Android + REST work once the engines exist.
10. **4AA–4AE: continuous operation, strategic intelligence, digital
    twin, advanced discovery, autonomous evolution** — depend on
    everything before them being real and tested, and on §1's hosting
    decision for "continuous" to mean anything beyond "runs all session."

## 20. Risks

- **Self-modifying code with no sandbox yet** — the single largest risk
  in the spec; addressed by the boundary proposed in §17(b).
- **Runaway resource/API spend** from autonomous research/learning/agent
  loops — Phase 2's `CostTracker` exists but has no hard circuit-breaker
  today; Phase 4's Resource/Economic engines need one before "continuous"
  autonomy is safe to enable by default.
- **Prompt injection via autonomous web research** — the spec explicitly
  calls this out (treat external content as data); nothing in Phase 1–3
  parses untrusted web content yet, so this defense has to be built in
  from the start of the Research Engine, not retrofitted.
- **Autonomous external communication** — Phase 3's policy gate already
  covers this for the one channel type that exists; every new channel
  Phase 4 adds needs to go through the same gate, not a shortcut.
- **Complexity/maintainability** — 30 named subsystems is a lot of
  surface; the "primitives → tools → capabilities → agents → workflows"
  composition rule in your spec is the right mitigation and I'll hold to
  it rather than adding one-off modules per subsystem name.
- **False sense of "24/7"** — see §1; building the code without deploying
  it somewhere persistent would look done while not actually running
  unattended.

## 21. Estimated complexity by subsystem

Rough sizing (S = additive/contained, M = new service + schema, L =
genuinely new subsystem with real design risk, XL = the two hardest
problems in the whole spec):

| Size | Subsystems |
|---|---|
| **S** | Capability Registry metadata, Notification Engine, Audit Engine (extends existing `AuditLogger`), Analytics Engine, Documentation Engine, Long-Term Strategy Engine (memory extension) |
| **M** | Core Orchestrator extension, Permissions/Resource/Autonomy extension, Task Engine, Memory Engine extensions, Prediction Engine (heuristic first), Decision Engine, Economic Engine (extends Phase 3 wallet), Business OS breadth, Monitoring/Observability, Command Center (mostly Android+REST) |
| **L** | Agent Runtime, Workflow Engine, Knowledge Graph, Research Engine (with injection defense), Learning Engine, Self-Diagnostics, Self-Healing, Communication/Phone/Device layer (needs a real provider), Security Engine hardening |
| **XL** | Self-Coding/Self-Testing/Self-Update (needs sandbox+snapshot infra first, §17b), true continuous 24/7 operation (needs a real host, §1) |

---

**Nothing in Phase 1–3 was modified to produce this audit.** I'm holding
here for your decision on §17 before writing any Phase 4 code — (a) and
(c) I'll proceed with additively unless you say otherwise; (b) is the one
I actually need an answer on.
