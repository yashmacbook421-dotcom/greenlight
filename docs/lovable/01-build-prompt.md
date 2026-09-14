# Greenlight — Lovable build prompt (message 1 of 2)

Paste everything below this line into Lovable as your first message. Then paste `02-sample-data.md` as the second.

---

Build the frontend for **Greenlight**: a web app where AI drafts reviews of rooftop-solar interconnection applications and a human engineer approves them. I already have a working backend (Python/FastAPI, PostgreSQL, Claude). I want you to design a much better, genuinely user-friendly UI, built so that I can move the code into my existing Next.js app afterwards. Please read this whole brief before building.

## 1. The real-world problem

Before a home or business in California can switch on rooftop solar or a battery, the local utility (for us, PG&E) must review an **interconnection application**. The installer submits a packet of PDFs: an application form, a one-line electrical diagram, and inverter spec sheets. An interconnection engineer then:

1. reads every document and checks they agree (the form says 7.6 kW, the spec sheet says 7,616 W — fine; the form says 1 inverter, the diagram says 2 — not fine),
2. runs the technical safety "screens" in California's tariff, **Electric Rule 21**: can the local transformer carry it, will it disturb fault protection, is the inverter certified, is the line section already saturated with solar,
3. decides the outcome and writes a formal letter back.

The documents are messy and inconsistent, the rules are dense (a 290-page tariff), and the work is manual, one packet at a time. Solar and battery adoption is outpacing review capacity, so applications queue up. The tariff itself sets deadlines, for example 10 business days to tell an applicant their request is incomplete, and 15 business days for Initial Review results.

## 2. What Greenlight does, and the vision

Greenlight does the reading, checking and drafting, and hands the engineer a finished draft where **every claim sits next to the evidence behind it**. The engineer verifies instead of investigating from scratch, so the same team can clear far more of the queue.

The core idea, which the UI must make visible:

> **The AI handles ambiguity. Deterministic code handles arithmetic. A human holds authority.**

- **Claude (AI)** reads the PDFs, judges whether a conflict between documents matters, investigates, and drafts the letter.
- **Code** runs the Rule 21 screens (pure math, same answer every time, every threshold quoted from the real tariff), and checks the AI's work: every number in the letter must appear in the evidence, every citation must exist in the tariff, and the AI can never propose a more lenient outcome than the evidence allows.
- **A named engineer** approves, edits or rejects. Nothing is ever sent without them. The database enforces this.

The vision is **trustworthy automation for regulated work**: not "AI decides", but "AI does the tedious reading and drafting, code bounds what it's allowed to be wrong about, and humans stay in charge, faster". The same engine could later review other document-heavy, rule-based work (e.g. expense reimbursements), so keep the design domain-neutral where it's cheap to do so.

## 3. Who uses it

- **Interconnection engineer (primary):** works through a queue all day. Needs to verify a draft quickly, see exactly why each conclusion was reached, open the source PDF page, and approve or fix it with confidence.
- **Team lead:** watches the queue, deadlines and bottlenecks.
- **Technical reviewer / interviewer / stakeholder:** wants to understand how it works and whether it's accurate (eval results, agent trace, cost).

Assume users are domain experts but not AI experts. Explain AI-specific concepts in plain language; don't dumb down electrical ones, but offer short glossary tooltips (PCC, ICA, SCCR, kVA vs kW, NEM/NBT).

## 4. Key concepts (use these exact terms and values)

**Outcomes (dispositions)**, each tied to a notice the tariff requires:
- `INITIAL_REVIEW_PASS` "Initial Review pass": every applicable screen passed.
- `DEFICIENCY_NOTICE` "Deficiency notice": the application is incomplete or contradicts itself; the applicant must fix listed items.
- `SUPPLEMENTAL_REVIEW_REQUIRED` "Supplemental Review required": a technical screen failed.
- `NEEDS_ENGINEER_DETERMINATION` "Needs engineer determination": utility-side data or judgment is missing.

**Screens:** A, B, C, D, E, F, F1, G, H, I, J, K, L, M (always 14 results). Each has a status: `PASS`, `FAIL`, `INCONCLUSIVE` (an input is missing; says who must supply it: `applicant` or `utility`), `NOT_APPLICABLE` (excluded by size/technology), or `SKIPPED` (routed around by an earlier screen). Each carries a formula, computed value, threshold, inputs, and citations like "§G.1.j · Sheet 151".

**Draft statuses:** `pending_review`, `approved`, `edited`, `rejected`.

**Trust signals to make visually distinct everywhere:**
- *Verified by code*: screens, citation checks, number checks.
- *Judged by AI*: extraction, conflict materiality with `method: "llm"`, the drafted letter.
- *Synthetic data*: circuit/utility values that are demonstration data (`synthetic_inputs`).
- *Code overrode the AI*: `model_disposition` is set.

## 5. Screens to build

Use my existing data shapes exactly (sample data comes in my next message). Improve the design freely.

1. **How it works** (`/about`, linked in the nav): a clear, visual one-page explanation of the problem, the pipeline (Intake → Extraction → Reconciliation → Screens → Agent → Guardrails → Engineer), the "AI / code / human" split, and a small live summary of the latest eval. This is what I show people first.

2. **Queue** (`/queue`, the default): the engineer's worklist. Show applicant, site, submitter, received date, document count, draft outcome, guardrail flags, and review status. Add useful sorting and filtering (by outcome, by status, "needs my attention" first), search, and a clear primary action per row ("Run review" or "Open review"). Include "Add demo application" (pick a defect family, "oracle facts" toggle) and a "use Claude when reviewing" toggle with a clear cost note. A live review takes 1–2 minutes, so design a good waiting state (you can't get real progress events yet; see Suggestions). Hide cases whose submitter starts with `[eval` behind a toggle.

3. **Review** (`/review/:id`): **the most important screen.** Design it for fast, confident verification:
   - The draft outcome, and whether code overrode the AI, above the fold.
   - "Code checks on this draft" (guardrail verdicts), with plain-language labels.
   - Deficiency items, each linked to the exact evidence it rests on (clicking highlights and scrolls to it).
   - The draft letter (Markdown, with tables).
   - All 14 screens, scannable at a glance and expandable into formula / computed vs threshold / inputs / missing inputs / citations with the tariff quote.
   - Conflicts across documents: values, which one was used, material or not, and who judged it (code by re-running the screens, or Claude).
   - "What the documents say": every extracted fact with its verbatim quote and page, and a **built-in PDF viewer** that jumps to the page (URL pattern `{API}/cases/{caseId}/documents/{documentId}/file#page={n}`) and highlights the quote if possible.
   - What-if scenarios the agent ran.
   - The engineer decision panel: name (required), note, "Approve as drafted", "Edit letter" (show a diff against the draft before saving), "Reject". After a decision, show it as locked.
   - Keyboard shortcuts for power users (e.g. `j`/`k` to move between items, `?` for help), shown in a help overlay.

4. **Agent trace** (`/trace/:id`): a readable replay of what the AI did. Each model call and tool call in order, with tokens, cost, latency, and expandable inputs/results. Summary: model, calls used vs budget, cost vs ceiling, how it ended.

5. **Evals** (`/evals`): accuracy and cost. List runs (oracle vs live), then for the selected run: headline tiles, a 4×4 confusion matrix (expected vs proposed outcome), guardrail failure rates ("how often code had to flag or overrule the AI"), per-defect-family results, per-packet results linking to the review, and cost share by stage for live runs. Explain in one sentence what "oracle" and "live" mean.

6. **New application** (`/new`): a real upload flow for installers' packets, using endpoints that already exist:
   - `POST /interconnection/applications` JSON `{ utility, submitter, applicant_name, site_address }` → `{ case_id, status }`
   - `POST /cases/{case_id}/documents` multipart form fields `kind` and `file` (PDF, max 25 MB). `kind` is one of `application_form`, `one_line_diagram`, `site_plan`, `inverter_spec_sheet`, `battery_spec_sheet`, `customer_authorization`, `other`. Returns `{ id, kind, filename, sha256, page_count, created_at, pages: [{ page_no, anchor, has_text_layer, char_count }] }`; `200` means an identical file already existed, `422` means an unreadable or password-protected PDF (show the `detail` message).
   - Show which documents are required (application form, one-line diagram, inverter spec sheet) and which are still missing, then offer "Run review".

## 6. API endpoints (all JSON unless noted)

`GET /cases` · `POST /cases/{id}/review?use_llm=true|false` · `GET /cases/{id}/review` · `GET /cases/{id}/trace` · `POST /proposals/{id}/decision` with `{ action: "approve"|"edit"|"reject", reviewer, note, letter_md }` (409 if already decided) · `GET /cases/{id}/documents/{documentId}/file` (PDF) · `GET /evals` · `GET /evals/{id}` · `GET /evals/families` · `POST /demo/packets` with `{ family, seed, oracle_facts }` · `POST /interconnection/applications` · `POST /cases/{id}/documents` (multipart) · `GET /rules/search?q=` → `[{ ruleset, section, heading, sheet, snippet, rank }]` (use this for a "search the tariff" box on the review page).

Errors come back as `{ "detail": "message" }`.

## 7. User-friendliness requirements

- Plain-language labels first, technical detail on demand (progressive disclosure).
- Every page has loading, empty and error states. Errors say what happened and what to do.
- Never rely on color alone: pair colors with icons/text. WCAG AA contrast, visible focus, full keyboard navigation.
- Responsive: excellent on a laptop, usable on a tablet.
- Calm, professional, data-dense but not cluttered (think Linear or Vercel dashboards). Light theme by default, with a dark theme.
- Numbers exactly as the API returns them (never recompute or reformat decimals that are evidence). Money to 3–4 decimals, dates in local time.

## 8. How to structure the code (important: I will port it into Next.js)

My production app is **Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS v4**. Build in Lovable's standard React + TypeScript + Tailwind + shadcn/ui stack, but follow these rules so the code moves over cleanly:

- **No Lovable Cloud, Supabase, auth, or database.** Frontend only.
- `src/lib/types.ts`: TypeScript types matching the sample data exactly.
- `src/lib/api.ts`: one typed function per endpoint (`listCases`, `getReview`, `runReview`, `getTrace`, `decide`, `listEvals`, `getEval`, `listFamilies`, `createDemoPacket`, `createApplication`, `uploadDocument`, `searchRules`), with base URL from `VITE_API_URL` (default `http://localhost:8010`) and a `USE_MOCKS` switch that returns the sample data from `src/mocks/`. Mocks must behave realistically (latency, a decision locks the draft, errors for bad input).
- `src/components/`: presentational components only. They get data and callbacks via props, **never fetch data, and never import the router**.
- `src/pages/`: thin route containers that call `api.ts` and pass props down.
- One `AppLink` component wraps navigation (so I can swap the router's link for `next/link`), and one `useAppNavigate` hook for programmatic navigation.
- Styling with Tailwind utility classes and CSS variables only (no CSS-in-JS). Keep extra dependencies minimal and justified (shadcn/ui, lucide-react, react-markdown + remark-gfm, a PDF viewer library if needed, a diff library if needed).
- Add `EXPORT.md` at the root: the file map, every dependency with its purpose, the CSS variables/theme tokens, and anything specific to Vite or react-router that I must change for Next.js.

## 9. What I want from you besides the UI

Please create `SUGGESTIONS.md` with your honest recommendations, each tagged **[frontend only]** or **[needs backend]**:

1. UX improvements beyond this brief that would make engineers faster or more confident.
2. Features that would make the product more trustworthy or explainable (e.g. how to present AI confidence, audit history).
3. Anything in this brief you think is a mistake or could be simpler.
4. Backend or model changes that would enable better UX. For example: streaming review progress (the review currently returns only when finished), per-fact confidence, a notification when a tariff deadline approaches, authentication and roles, an audit log of decisions.

Also tell me in your first reply which parts of the brief you're unsure about, so I can clarify before you go too far.

Start with the design system and the Review screen, since it is the heart of the product; then Queue, How it works, Trace, Evals, and New application.
