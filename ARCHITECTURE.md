# Project Greenlight — Architecture

*Solar interconnection applications, reviewed by an agent, approved by a human.*

---

## 1. The thesis, stated as an architectural constraint

> **The LLM handles ambiguity. Deterministic code handles arithmetic. A human holds authority.**

This is not a design preference to be honored by prompting. It is enforced
structurally:

| Concern | Owner | Enforcement |
|---|---|---|
| Reading messy PDFs into typed facts | LLM | Every field carries `{doc, page, quote}` provenance or it is rejected |
| Judging whether a discrepancy is material | LLM | Rubric-scored, and the *detection* of the discrepancy is deterministic |
| Running the technical screens | Code | `services/screens/` may not import the Anthropic SDK — asserted by a test |
| Deciding the next investigative step | LLM | Bounded tool loop with a step budget and cost ceiling |
| Choosing the disposition | LLM proposes, **code can veto** | Any FAIL or INCONCLUSIVE screen makes `INITIAL_REVIEW_PASS` unreachable, whatever the model said |
| Sending anything to an applicant | Human | The terminal tool writes a `pending_review` draft. There is no send path in the agent's tool set. |

The interesting claim of this project is not that an agent can review an
application. It is that **you can bound what the agent is allowed to be wrong
about.**

---

## 2. System shape

An application packet arrives. Five stages run; stage 4 is the agentic one.

```
  ┌──────────────────────────────────────────────────────────────────┐
  │ 0. INTAKE                                          deterministic │
  │    PDFs → page-indexed text + SHA-256 + stable page anchors      │
  └────────────────────────────┬─────────────────────────────────────┘
                               ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ 1. EXTRACTION                                              LLM   │
  │    Per-document → typed ApplicationFacts.                        │
  │    Every field: value + doc_id + page + verbatim quote.          │
  │    No provenance → field is dropped, not guessed.                │
  └────────────────────────────┬─────────────────────────────────────┘
                               ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ 2. RECONCILIATION                            code finds, LLM judges│
  │    Code: which fields disagree across documents? what's missing? │
  │    LLM:  is this disagreement material? (7.6 vs 7.68 kW = no;    │
  │          missing spec sheet = yes; 7.6 vs 9.9 kW = yes)          │
  └────────────────────────────┬─────────────────────────────────────┘
                               ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ 3. SCREENS                              PURE DETERMINISTIC CODE  │
  │    CA Rule 21 (PG&E) §G.1 Initial Review, Screens A–M, as a flow.│
  │    Each returns PASS|FAIL|INCONCLUSIVE|NOT_APPLICABLE|SKIPPED:   │
  │      inputs used · formula · computed value · threshold · cite   │
  │    Same inputs → same answer, forever. Unit-tested to the digit. │
  └────────────────────────────┬─────────────────────────────────────┘
                               ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ 4. AGENT LOOP                                    LLM + tools     │
  │    Given screen results and materiality flags, decide what to    │
  │    check next. Re-run screens under mitigations. Search the      │
  │    rulebook. Pull provenance. Terminate with a proposal.         │
  │    Hard step budget · cost ceiling · full trace persisted.       │
  └────────────────────────────┬─────────────────────────────────────┘
                               ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ 5. GUARDRAILS, THEN THE HUMAN GATE          deterministic, then  │
  │    Number-faithfulness · citation validity · disposition veto.   │
  │    Draft lands in `pending_review`. Engineer approves/edits/     │
  │    rejects with every claim linked to its evidence. Only then    │
  │    does anything leave the building.                             │
  └──────────────────────────────────────────────────────────────────┘
```

---

## 3. Stage 3 — the deterministic screen engine

This is the load-bearing wall. It is ordinary Python with no model in it.

### Source: one pinned tariff edition

**PG&E Electric Rule No. 21, Advice Letter 7692-E, effective 2025-08-29**
(290 pages). The URL and SHA-256 live in
`domains/interconnection/rules/manifest.json`; `scripts/fetch_rules.py`
refuses a file whose hash has changed. In this edition the tariff sheet number
equals the PDF page number, so a citation is `Rule 21 §G.1.j, Sheet 151`.

We chose Rule 21 over FERC SGIP because rooftop solar and batteries at
California's investor-owned utilities are interconnected under this
CPUC tariff. SGIP covers FERC-jurisdictional (wholesale) interconnection.

### Where screens sit in the tariff's process

```
Interconnection Request
   │
   ▼
§E.5 COMPLETE AND VALID?  (Sheet 70)  ── no ──► DEFICIENCY_NOTICE
   │ yes                                        reasons in writing; applicant has
   ▼                                            10 business days to cure (Sheet 70)
§G.1 INITIAL REVIEW, Screens A–M  (Sheets 140–154)
   │                                            results due within 15 business days
   ├── all pass ───────────────────────────────► INITIAL_REVIEW_PASS  (§F.1.b, Sheet 78)
   │
   ├── any fail ───────────────────────────────► SUPPLEMENTAL_REVIEW_REQUIRED
   │                                            "technical reason, data and analysis"
   │                                            in writing (§F.2.a, Sheet 83), plus any
   │                                            mitigations found (§G.1, Sheet 140)
   │
   └── a screen needs utility-only input ──────► NEEDS_ENGINEER_DETERMINATION
       or judgment the tariff leaves to
       "Distribution Provider practice"

§G.2 SUPPLEMENTAL REVIEW, Screens N–P  (Sheets 154–161)  ── out of scope for automation
§G.3 DETAILED STUDY, Screens Q–R        (Sheets 161–163)  ── out of scope
```

Every disposition corresponds to a written notice the tariff itself requires,
so the drafted letter has a legal anchor, not just a label.

### Initial Review is a flowchart, not a checklist

Screens can be *not applicable* (by size or technology) or *skipped* (routed
around by an earlier screen). Both are recorded with the citation that caused
them, like any other result.

| Screen | Question (tariff wording, shortened) | Kind | Decision rule as written | Sheet |
|---|---|---|---|---|
| **A** | PCC on a networked secondary system? | lookup | Yes = fail → Supplemental, *unless* spot network, inverter-based, and aggregate ≤ min(5% of spot network max load, 50 kW) | 140–141 |
| **B** | Certified equipment used? | lookup | Certified per §L or has interim approval. Fail continues to C | 141 |
| **C** | Starting voltage drop within limits? | computed | **N/A unless the generator starts by motoring** (not inverters). Drop < 2.5% primary / 5% secondary | 142 |
| **D** | Transformer or secondary conductor rating exceeded? | **utility practice** | Aggregate gross ratings vs rating "modified per established Distribution Provider practice" | 143 |
| **E** | Single-phase generator causes unacceptable imbalance? | **utility practice** | Single-phase on 240 V center tap; "unacceptable" is not quantified | 143–144 |
| **F** | Short circuit current contribution ratio ≤ 0.1? | computed | Sum of ratios on the circuit ≤ 0.1. **N/A if gross rating ≤ 30 kVA** | 144 |
| **F1** | Per-unit short circuit contribution acceptable? | computed | pu ≤ 1.2, **or** nameplate × pu < Protection ICA × 1.2 | 145 |
| **G** | Short circuit interrupting capability exceeded? | computed | Aggregate must not push any device beyond 87.5% of interrupting capability. **N/A ≤ 30 kVA** | 145–146 |
| **H** | Line configuration compatible? | lookup + computed | Table G-1. 3-phase 4-wire, "all others": aggregate ≤ 10% of line-section peak load. **N/A ≤ 30 kVA** | 146–147 |
| **I** | Power exported across the PCC? | routing | Export (Options 5, 6, 9–11) → J. Non-export needs Options 1–4, 7 or 8 → **skip J–M, Initial Review complete**. Option 3: ≤ 25% of service equipment amps, ≤ 50% of service transformer, certified non-islanding. Option 4: ≤ 50% of 12-month minimum host load | 147–150 |
| **J** | Gross rating ≤ 30 kVA? | computed | Yes → **skip K, L, M; Initial Review complete** | 151 |
| **K** | NEM-1 / NEM-2 / NBT-1 and nameplate ≤ 500 kW? | computed | Yes → skip L, go to M | 151 |
| **L** | Transmission dependency, stability, islanding, overvoltage? | lookup | Any known or posted condition → fail → Supplemental | 152 |
| **M** | Passes ICA? | computed | Aggregate gross nameplate ≤ 90% of the lowest ICA-SG 576 value **and** ≤ 90% of the lowest ICA-OF 576 value. **No ICA available:** aggregate < 15% of line-section peak load | 153–154 |

**What this means for the product:**

- **A typical residential rooftop system (≤ 30 kVA, exporting, inverter-based)
  actually runs A, B, D, E, I, J.** C, F, G and H don't apply; J routes around
  K, L and M. The ICA and line-section-peak arithmetic only matter for systems
  above 30 kVA, so the eval corpus must include small commercial systems
  (30 kVA–1 MW) or half the engine goes untested.
- **Screens D and E have no threshold in the tariff.** Their numbers come from
  a `utility_practice` configuration entry that carries its own source label
  (e.g. "synthetic, for demonstration"). If none is configured, the screen is
  `INCONCLUSIVE` with the blocker `utility`. The LLM never supplies the number.
- **Ambiguities in the text are recorded, not silently resolved:**
  - Screen M lists its two questions joined by "or" but decides on "yes to
    both". We implement the explicit decision rule ("both").
  - The "≤ 30 kVA does not apply" note sits under Screen F, ahead of F1. We
    apply F1 at every size and record the reading in the rulebook.

### Rulebook: every constant carries its source

`screens/rulebook.py` holds each threshold together with its section, sheet,
and a **verbatim quote**. A test loads the cited page text from the pinned PDF
and asserts that every quote appears on its sheet. A threshold whose quote
cannot be found fails the build.

### Result states

| State | Meaning | Required fields |
|---|---|---|
| `PASS` / `FAIL` | Decided | inputs · formula · computed · threshold · citation. A FAIL also needs a classification |
| `NOT_APPLICABLE` | Excluded by size or technology | citation of the exclusion note |
| `SKIPPED` | Routed around by an earlier screen | citation + which screen routed it |
| `INCONCLUSIVE` | Required input missing | `missing_inputs`, `reason`, and a **blocker**: `applicant` (becomes a deficiency item) or `utility` (circuit data or utility practice absent) |

FAIL classification follows §G.1: Screens B–H are `mitigable_in_initial_review`
(a quick review "may determine the requirements to address the failure",
Sheet 140). Screen A, L and M failures are `supplemental_required`.

### Materiality becomes partly computable

Reconciliation (stage 2) gets a deterministic first test: **re-run the screens
with each conflicting value.** If every screen outcome is the same, the
discrepancy cannot change the review (7.6 vs 7.68 kW on a residential system).
If an outcome flips, it is material by construction: 29.9 kW on the form vs
30.4 kVA from the inverter spec sheets flips Screen J, which reroutes K–M. The
LLM only judges discrepancies that no screen consumes (names, addresses, dates).

### Scope

- **In:** completeness (§E.5), Initial Review A–M, for inverter-based solar
  and/or storage, exporting (NEM-2 / NBT-1) or non-export Options 1–4, up to
  1 MW.
- **Computed as a helper, not a decision:** Screen N(i) (≤ 100% of lowest
  ICA-SG value) when ICA data exists.
- **Out:** Screens O and P (they need power-flow analysis and engineering
  judgment), Detailed Study (Q, R), Large Generation Profile (§Mm5), motoring
  generators, the §N non-export storage expedited process, and cost envelopes.

## 4. Stage 4 — the agent loop

A bounded tool-use loop written directly against the Claude API. No agent
framework — the control flow is the artifact.

### Tools

| Tool | Effect | Notes |
|---|---|---|
| `run_screens(facts, overrides?)` | read-only | The **only** way to obtain a screen number. `overrides` lets the agent explore mitigations ("cap export at 5 kW") without mutating the case. |
| `get_circuit_model(feeder_id)` | read-only | Line-section peak load, existing DER, transformer, fault duty. Flags every synthetic field. |
| `search_rules(query)` | read-only | Retrieval over the pinned Rule 21 text. Returns section + sheet. |
| `get_field_provenance(field)` | read-only | Returns every document that asserted a field, with page and quote. |
| `flag_deficiency(item)` | writes case state | Accumulates a deficiency item; does not send anything. |
| `propose_disposition(...)` | **terminal, gated** | Writes a `pending_review` draft and ends the loop. Cannot send. |

There is deliberately no tool that computes, no tool that emails, and no tool
that approves.

### Loop policy

- **Step budget** — hard cap on iterations; exhausting it is itself an
  outcome (`NEEDS_ENGINEER_DETERMINATION`, reason: budget exhausted), never a crash.
- **Cost ceiling** — per-case USD cap, checked before each model call.
- **Termination** — the loop ends on `propose_disposition`, budget, or ceiling.
  Nothing else ends it.
- **Full trace** — every prompt, tool call, tool result, token count and
  latency is persisted per case. A review is replayable and auditable months
  later, which is the actual requirement in a regulated setting.

---

## 5. Stage 5 — guardrails as code

Deterministic checks that run *after* the model, on its output. Prompting is
not a control.

1. **Number faithfulness.** Every numeric literal in the drafted letter is
   extracted and must match a value present in a recorded tool result. A number
   the model invented fails the case closed for human attention.
2. **Citation validity.** Every cited section must resolve to real ingested
   text at the cited page. Plausible-looking citations to sections that do not
   exist are caught here.
3. **Disposition veto.** `INITIAL_REVIEW_PASS` is reachable only if every
   screen is PASS, NOT_APPLICABLE or SKIPPED. Any applicant-blocked
   INCONCLUSIVE forces `DEFICIENCY_NOTICE`, and any FAIL forces at least
   `SUPPLEMENTAL_REVIEW_REQUIRED`. The code overrides the model's proposal and
   records that it did.
4. **Provenance completeness.** Every deficiency item must point at a screen
   result or a document page. Unsourced items are stripped and flagged.
5. **Authority.** There is no send path. The strongest thing the agent can do
   is write a draft that a human has not yet read.

Each guardrail firing is recorded on the case, so the eval can report how often
code had to overrule the model — a number worth being able to quote out loud.

---

## 6. Data grounding

Real where it exists, synthetic where it doesn't, labeled either way.

| Layer | Source | Status |
|---|---|---|
| Interconnection rules | PG&E Electric Rule 21, effective 2025-08-29, pinned by SHA-256 | **Real** |
| Circuit / feeder model | PG&E Integration Capacity Analysis (ICA) data: feeder and line-section IDs, ICA-SG / ICA-OF values, line-section load. Whether the full 576-value profiles and Protection ICA values are downloadable is **not yet verified**; check when ICA data is ingested | **Real** where published |
| Fields no utility publishes | Service transformer kVA, secondary conductor rating, device interrupting ratings, networked-secondary flag, Screen L area flags, Screen D/E utility practice | **Synthetic**, flagged at the field level and surfaced in the UI |
| Inverter specs | Real manufacturer datasheets + CEC-listed equipment attributes | **Real** |
| Application packets | Generated from real form layouts with deliberately injected defects | **Synthetic by necessity** — real packets contain customer PII and are not public. This is a feature: injected defects *are* the eval ground truth. |

Synthetic provenance is carried through to the screen result, so a screen that
depended on a synthesized transformer rating says so on its face.

---

## 7. The eval — what makes this an engineering artifact

A generated corpus of application packets, each with known ground truth:
which defects were injected, which screens must fail, which disposition is
correct.

**Defect families:** missing spec sheet · nameplate mismatch that changes no
screen outcome · nameplate mismatch that **crosses a threshold** (e.g. the
30 kVA line at Screen J) · inverter not on the certified list (Screen B) ·
oversized for service transformer (Screen D) · non-export option claimed but
its conditions not met (Screen I, Option 3) · NEM/NBT status inconsistent
across documents (Screen K) · exceeds ICA on its line section (Screen M) ·
one-line diagram contradicting the form · illegible scan.

**Size mix:** residential (≤ 30 kVA) *and* small commercial (30 kVA–1 MW).
Otherwise Screens F–H and K–M never execute.

**Metrics:**

- Defect detection precision / recall, per defect family
- Disposition accuracy — 3×3 confusion matrix against ground truth
- Citation validity rate
- Hallucinated-number rate (should be structurally zero; measured anyway)
- Guardrail intervention rate — how often code overruled the model
- Cost per application (USD), latency per application, tool calls per application
- **Determinism test** — the same packet run N times must produce byte-identical
  screen results, and a stable disposition. Screens are code; this must hold.

---

## 8. Data model (as built)

Core, domain-agnostic tables (`app/core/models.py`), with the invariants enforced by the database:

```
cases            id · domain · status · submitter · received_at
documents        id · case_id · kind · filename · sha256 · page_count · storage_uri
pages            document_id · page_no · text · has_text_layer
extracted_facts  field · value/unit (canonical) · value_as_written · unit_as_written · instance
                   · (document_id, page_no) → pages · quote (non-empty) · verification · extracted_by
discrepancies    field · observed[] · material · method (rule_outcome | llm) · rationale
rule_results     rule_set · rule_id · status (PASS|FAIL|INCONCLUSIVE|NOT_APPLICABLE|SKIPPED) · inputs · formula
                   · computed · threshold · citation[] · classification · blocker · routed_by
                   · missing_inputs · synthetic_inputs · overrides (agent what-ifs) · engine_version · input_hash
rule_chunks      ruleset · section · heading · sheet · text · tsvector (full-text search)
agent_runs       model · step_budget · steps_used · cost_ceiling_usd · cost_usd · terminated_by
agent_steps      run_id · n · role · tool · args · result · tokens · cost_usd · latency_ms
proposals        disposition · model_disposition (set when code overrode it) · letter_md · items[]
                   · guardrail_verdicts[] · status · reviewed_by · reviewed_at · review_note
eval_runs        mode (oracle|live) · status · config · metrics · packets[]
```

Interconnection tables (`app/domains/interconnection/models.py`): `interconnection_applications`
(1:1 with a case) and `circuit_models` (validated screen-engine attributes plus `synthetic_fields`).

The human gate lives in the schema: a trigger makes every proposal start as `pending_review`, requires a
named reviewer to leave it, forbids changing the letter under `approved` (that is `edited`), and freezes a
proposal once reviewed. There is no `sent` state.

## 9. Repo layout

The review engine is split from the domain so a second domain (expense
reimbursement) can reuse it later. `app/core` must never import `app/domains`
— asserted by a test.

```
PROJECT GREENLIGHT/
├── IDEA.md · ARCHITECTURE.md · docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py · config.py · db.py
│   │   ├── routers/                  health · (applications · review · evals …)
│   │   ├── core/                     ← DOMAIN-AGNOSTIC
│   │   │   ├── models.py             cases · documents · pages · facts · rule results
│   │   │   │                         · agent runs/steps · proposals (+ gate trigger)
│   │   │   ├── intake.py · extraction.py · reconcile.py
│   │   │   ├── agent/                loop · tools · policy
│   │   │   ├── guardrails.py · observability.py
│   │   │   └── evals/                metrics · runner
│   │   └── domains/
│   │       └── interconnection/
│   │           ├── models.py         circuit_models · interconnection_applications
│   │           ├── screens/          ← NO MODEL MAY BE IMPORTED HERE
│   │           ├── grid_data.py · rules_rag.py · letters.py
│   │           └── evals/            packet generator · defect injection · ground truth
│   ├── migrations/                   Alembic
│   └── tests/
└── frontend/
    └── app/  queue/ · review/[id]/ · trace/[id]/ · evals/
```

The review screen is the product. Every claim in the drafted letter sits
beside the screen result or document page it came from, one click from the
original scan. An engineer should be able to disagree with the agent in
seconds.

---

## 10. Build order

1. **Skeleton + data model** — FastAPI, Postgres/pgvector, docker-compose, migrations.
2. **Intake** — PDF → page-anchored text, hashing, storage.
3. **Screen engine + rulebook** — Rule 21 Initial Review as a flow, every threshold quote-verified against the pinned PDF, unit-tested to the digit, with the no-model import guard.
4. **Rules corpus ingest + retrieval** — Rule 21 chunked, embedded, sheet-cited.
5. **Extraction with enforced provenance.**
6. **Reconciliation** — deterministic diffing, LLM materiality judgment.
7. **Agent loop** — tools, budget, ceiling, full trace.
8. **Guardrails** — the four post-hoc checks and the veto.
9. **Packet generator + eval harness** — defect injection and ground truth.
10. **Frontend** — queue, review gate, trace replay, eval dashboard.
11. **Cost work** — measured routing, not assumed.

Order is deliberate: the deterministic layer is built and trusted *before*
anything probabilistic is allowed to depend on it.
