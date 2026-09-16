# Greenlight

**Solar interconnection applications, reviewed by an agent, approved by a human.**

When someone installs rooftop solar or a battery in California, the utility must review the application
before the system can connect to the grid. An engineer reads a packet of inconsistent PDFs, runs the tariff's
technical screens by hand, and writes back to the installer. That review work is a bottleneck behind
interconnection backlogs.

Greenlight does the review and hands the engineer a finished draft: a disposition, a letter, and every claim
next to the evidence it rests on. Nothing reaches the applicant until a named engineer approves it.

> **The LLM handles ambiguity. Deterministic code handles arithmetic. A human holds authority.**

The claim isn't that an agent can review an application. It's that you can **bound what the agent is allowed
to be wrong about**. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## What happens to an application

| Stage | What | Who |
|---|---|---|
| Intake | PDFs → fingerprinted, page-indexed text; scanned pages flagged | code |
| Extraction | Facts with value/unit **as written**, page and verbatim quote. A fact whose quote isn't on its page, or whose number or unit isn't in its quote, is rejected | Claude proposes, code admits |
| Reconciliation | Totals derived in code; conflicting values judged by **re-running the screens with each value**; name/model conflicts judged by Claude | code, then Claude |
| Screens | PG&E Electric Rule 21 Initial Review, Screens A–M, as the tariff's flowchart; every threshold quote-verified against the pinned tariff | pure code |
| Agent | Investigates with tools (what-if screens, rule search, provenance), flags deficiencies, drafts the letter. Step budget, cost ceiling, full trace | Claude, bounded |
| Guardrails | Numbers must appear in evidence; citations must resolve to real tariff text; disposition can't fall below the code-computed floor; items need evidence | code |
| Human gate | Approve / edit / reject by a named reviewer, enforced by a database trigger | engineer |

Dispositions correspond to notices Rule 21 itself requires: `DEFICIENCY_NOTICE` (§E.5.b.i),
`INITIAL_REVIEW_PASS` (§F.1.b), `SUPPLEMENTAL_REVIEW_REQUIRED` (§F.2.a), and `NEEDS_ENGINEER_DETERMINATION`.

## Two sides

- **Applicant portal** (`/`, `/portal`): an installer starts an application, uploads the packet, and submits.
  Submission starts the review automatically. The installer sees a status and, once a named engineer approves it,
  the decision letter. After a deficiency notice they replace documents and resubmit; the replaced versions stay
  on record but their facts no longer count. Drafts, guardrail verdicts and the agent trace never reach this side.
  Releasing a decision also records a notice to the applicant's contact email, shown on both sides. It is only
  delivered when SMTP is configured (see `.env.example`); otherwise it stays `queued`, which is what a demo shows.
- **Engineer workspace** (`/queue`, `/review/:id`): portal submissions arrive already drafted, with resubmissions
  marked. Approving or editing a draft releases its letter to the portal; rejecting keeps it internal.

## Run it

**Docker (everything):**

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -e 'backend[dev]'
(cd backend && .venv/bin/python -m scripts.fetch_rules)   # optional: pinned 290-page tariff PDF (hash-verified)
export ANTHROPIC_API_KEY=...                              # optional: without it, no extraction; template drafts
docker compose up -d --build
```

- Applicant site: http://localhost:3100 (start an application → upload → submit). A sample packet with a real
  SolarEdge spec sheet is in `samples/sample-packet-delgado/`.
- Engineer workspace: http://localhost:3100/queue (open review → approve, and the letter appears in the portal)
- API: http://localhost:8010/docs

The frontend image builds with webpack, because Turbopack exceeds the ~2 GB memory of a default Docker Desktop
VM. Expect a slow first build.

**Local development:**

```bash
docker compose up -d db
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m scripts.ingest_rules
.venv/bin/uvicorn app.main:app --port 8010 --reload
cd ../frontend && npm install && npm run dev -- --port 3100
```

Host ports are 8010 (API), 3100 (UI) and 5433 (Postgres) to avoid the usual 8000/3000/5432 clashes.

**Tests:** `cd backend && .venv/bin/pytest` (245 tests; uses a throwaway database on the compose Postgres).

## Evals

```bash
cd backend
.venv/bin/python -m scripts.run_eval --mode oracle --per-family 3             # no model calls
.venv/bin/python -m scripts.run_eval --mode live --per-family 1 --max-cost 5  # calls Claude; costs money
```

The generator builds application packets across **13 defect families** (clean residential and commercial,
rounding mismatches, quantity conflicts, a rating that crosses the 30 kVA Screen J line, missing spec sheet,
uncertified inverter, transformer overload, invalid non-export option, applicant conflict, missing fault
current, ICA exceeded, scanned form). Equipment comes from real rows of the CEC inverter list. Each family
states its expected disposition and required detections independently of the engine.

**Results so far:**

| Run | Packets | Disposition accuracy | Detection P / R | Cost / application |
|---|---|---|---|---|
| Oracle (fresh seeds) | 39 | 100% | 100% / 100% | $0 |
| Live, claude-opus-5 | 1 | 100% | 100% / 100% | $0.26 (99 s, 8 calls; agent ≈ 74%) |

Read these honestly:
- **Oracle** shows the deterministic pipeline implements its specification consistently. The generator's
  ground truth and the pipeline were written by the same author, so it is not evidence of real-world accuracy.
- **One live packet is a smoke test, not a benchmark.** It did surface three real issues, since fixed: a
  guardrail too strict about rounding, a gap in the generator's labels, and a missing-credentials fallback that
  never engaged. A full live run across all families is the next measurement.

## Where the data comes from

| Data | Source | Status |
|---|---|---|
| Rules | PG&E Electric Rule 21, Advice 7692-E, effective 2025-08-29, pinned by SHA-256 | real |
| Certified inverters (Screen B) | CEC Grid Support Inverter Lists snapshot, data as of 2026-09-11 (3,280 rows); used as a **proxy** for Rule 21 §L | real |
| Circuit data | Generated per packet; every field listed as synthetic and flagged on screen results | synthetic |
| Screens D/E thresholds | The tariff defers to "Distribution Provider practice", which isn't published; labelled demonstration values, switchable off | synthetic |
| Application packets | Generated (real packets contain PII) | synthetic |

## Known limits

- Supplemental Review screens O and P (power flow, engineering judgment) and Detailed Study are out of scope.
  Screen C for motoring generators and export Options 5, 6, 8–11 return INCONCLUSIVE to an engineer.
- Real PG&E ICA values (including the 576-hour profiles Screen M uses) are not ingested; circuits are synthetic.
- Rules search is Postgres full-text search, not embeddings. It's deterministic and cites section and sheet,
  but is weaker on paraphrased queries.
- No authentication: reviewer identity is typed, not verified, and the portal's installer sign-in is a remembered
  company name. Anyone who knows an application's link can open it.
