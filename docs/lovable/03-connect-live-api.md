# Connecting a Lovable frontend to the live Greenlight API (later)

Use this after building the UI with `01-build-prompt.md` and `02-sample-data.md`, when you want the Lovable
preview to talk to your running backend instead of mock data.

## Path A (recommended): Lovable builds the UI, connected to the existing Greenlight API

Copy everything inside the block below into Lovable. Replace `https://YOUR-GREENLIGHT-API` with the public URL
of the backend (see "Making the backend reachable" at the bottom).

```text
Build "Greenlight", a web app for utility interconnection engineers. It reviews rooftop-solar and battery
interconnection applications under California's PG&E Electric Rule 21. An AI agent drafts the review; code
checks the draft; a human engineer approves it. Nothing reaches the applicant without a named engineer's
approval.

IMPORTANT ARCHITECTURE
- Frontend only. Do NOT create a database, auth, edge functions, or any business logic.
- All data comes from an existing REST API. Base URL: https://YOUR-GREENLIGHT-API
  Read it from an environment variable VITE_API_URL with that value as default.
- Never compute screen results, dispositions or costs in the frontend; display what the API returns.
- No API keys in the frontend. The API holds all secrets.

DESIGN
- Calm, professional, data-dense tool for engineers (think Linear/Vercel dashboards). Light theme,
  slate greys, emerald accent. shadcn/ui components, Tailwind.
- Top nav: green dot + "Greenlight", links "Queue" and "Evals", right side small text
  "PG&E Electric Rule 21 · effective 2025-08-29".
- Status badges: PASS = emerald, FAIL = rose, INCONCLUSIVE = amber, NOT_APPLICABLE and SKIPPED = slate.
- Disposition badges: INITIAL_REVIEW_PASS "Initial Review pass" (emerald), DEFICIENCY_NOTICE "Deficiency notice"
  (amber), SUPPLEMENTAL_REVIEW_REQUIRED "Supplemental Review required" (rose),
  NEEDS_ENGINEER_DETERMINATION "Needs engineer determination" (indigo).
- Citation chip style: small monospace outlined pill "§G.1.j · Sheet 151".

PAGES

1) /queue — Review queue (default route; "/" redirects here)
- GET /cases → array of { case_id, status, submitter, received_at, applicant_name, site_address, documents,
  proposal: null | { id, disposition, status, guardrail_failures } }
- Header "Review queue" with "N applications · M awaiting an engineer".
- Checkbox "show eval-corpus cases" (default off): hide rows whose submitter starts with "[eval".
- Table columns: Applicant/site (name bold, address small), Submitted by, Received (local datetime), Docs,
  Draft disposition (badge + red "N guardrail flag(s)" if guardrail_failures > 0), Review (status badge:
  pending_review, approved, edited, rejected), and an action: "Open review →" link to /review/:case_id if a
  proposal exists, otherwise a "Run review" button.
- "Run review" → POST /cases/{case_id}/review?use_llm={bool}. It can take 1–2 minutes when use_llm=true;
  show a spinner on that row and disable other actions; refresh the list when done; show API errors.
- Toolbar card: a family dropdown filled from GET /evals/families → [{ name, profile, expected, description }]
  (show name with underscores as spaces; show the selected family's description and expected outcome below),
  checkbox "oracle facts" (default on), button "Add demo application" → POST /demo/packets with JSON
  { family, seed: random int 0–9999, oracle_facts } → { case_id, family, expected_disposition }; then refresh.
  Separate checkbox "use Claude when reviewing" (default off, tooltip "Uses Claude; costs money").

2) /review/:id — the review (the core screen: every claim beside its evidence)
- GET /cases/{id}/review → {
    case: { id, status, submitter, received_at },
    application: { utility, applicant_name, site_address, circuit_model_id } | null,
    documents: [{ id, kind, filename, page_count, sha256, pages: [{ page_no, has_text_layer, anchor }] }],
    facts: [{ id, field, value, unit, instance, value_as_written, unit_as_written, document_id, document_kind,
              page_no, quote, verification }],
    discrepancies: [{ field, observed: [{ value, sources: [{ fact_ids, derivation }], chosen }], material,
                      method, rationale }],
    screens: [ScreenRow], scenarios: [ScreenRow],
    proposal: null | { id, disposition, model_disposition, status, letter_md,
                       items: [{ description, basis_kind, basis_ref, rule_section, rule_sheet }],
                       guardrail_verdicts: [{ name, passed, detail, data }], agent_run_id, reviewed_by,
                       reviewed_at, review_note, created_at } }
  ScreenRow = { screen, status, reason, formula, computed, threshold, inputs (object), citations:
    [{ section, sheet, quote?, interpretation? }], classification, blocker, routed_by, missing_inputs[],
    synthetic_inputs[], overrides (object), input_hash, engine_version }
- Header: applicant name, "site · submitted by X · utility", disposition badge, review status badge, and
  "Agent trace →" link to /trace/:id if proposal.agent_run_id, else small text "template draft (no agent)".
- Two columns on desktop (stack on mobile).
- LEFT column:
  a) "Code checks on this draft": if model_disposition is set, a rose banner "The model proposed X; code raised
     it to Y." Then list guardrail_verdicts except name "summary_for_engineer": ✓ green or ✕ red, a label
     (disposition_veto → "Disposition floor", provenance_completeness → "Items backed by evidence",
     number_faithfulness → "Numbers traceable to evidence", citation_validity → "Citations resolve to Rule 21
     text", fail_closed → "Fail-closed hold"), and the detail text. Show the summary_for_engineer verdict's
     detail as "Drafter's summary".
  b) "Deficiency items (n)": each item's description, a green button "evidence: {basis_kind} {basis_ref} ↗"
     and a citation chip if rule_section/rule_sheet. Clicking the evidence button smooth-scrolls to and
     highlights (emerald ring) the matching evidence on the right: basis_kind "screen" → that screen row;
     "discrepancy" → that conflict; "fact" → that fact row; "missing_document" → that document section.
  c) "Draft letter": render letter_md as Markdown with GitHub tables, scrollable panel.
  d) "Engineer decision" (bold dark border): if proposal.status != "pending_review", show who decided, when,
     the note, and "Reviewed proposals are locked by the database." Otherwise inputs "Your name" (required) and
     "Note (optional)", buttons "Approve as drafted", "Edit letter…" (reveals a monospace textarea prefilled
     with letter_md and a "Save edited letter" button, enabled only if changed), and "Reject draft" (rose
     outline, right aligned). POST /proposals/{proposal.id}/decision with JSON
     { action: "approve" | "edit" | "reject", reviewer, note, letter_md (only for edit) }. Show API errors
     (409 means already decided). Reload the page data after success.
- RIGHT column:
  a) "Initial Review screens": one row per screen: screen id (mono), status badge, reason, and an amber
     "synthetic data" tag if synthetic_inputs is non-empty. Click to expand: formula (code), computed and
     threshold, inputs as "key=value · …", missing inputs with who must supply them (blocker), "routed by
     Screen X", citation chips (tooltip = quote), and any citation interpretation in italics.
  b) "Conflicts across documents" (if any): field (mono), "material" (rose) / "immaterial" (emerald) /
     "unjudged" (amber), "judged by Claude" if method = "llm" or "judged by re-running the screens" if
     method = "rule_outcome"; observed values as chips (the chosen one dark), rationale text.
  c) "What the documents say": per document a header "kind · N page(s)" (+ amber "scanned" if any page has no
     text layer) with an "open PDF ↗" link to {API}/cases/{id}/documents/{document_id}/file, then a compact
     table of that document's facts: field (mono), value + unit, the quote in quotation marks, and a "p.N" link
     to {API}/cases/{id}/documents/{document_id}/file#page=N; a ⚠ if verification = "image_unverified".
  d) "What-if scenarios the agent ran" (if scenarios non-empty): group by input_hash; show overrides.rationale,
     the other override key=value pairs, and each screen's status badge.

3) /trace/:id — agent trace replay
- GET /cases/{id}/trace → [{ id, model, step_budget, steps_used, cost_ceiling_usd, cost_usd, terminated_by,
  started_at, ended_at, steps: [{ n, role, tool, args, result, input_tokens, output_tokens, cost_usd,
  latency_ms }] }]
- For each run: stat row (Model, Ended by, Model calls "used / budget", Cost "$x.xxxx / $ceiling", Started).
- Steps timeline: "#n", pill "model" (indigo) or "tool · name" (emerald), tokens in/out, cost, latency.
  For role "assistant", result.content is a list of blocks: show type "text" as paragraphs, "tool_use" as
  "→ calls name", "thinking" as grey italic "(thinking)"; show result.stop_reason small. For role "tool",
  show args as formatted JSON and a "show result" toggle revealing result as dark JSON (label "show error
  result" in rose if result.is_error).
- Empty state: "No agent runs for this case (the draft came from the template)."

4) /evals — evaluation dashboard
- Intro: generated application packets with injected defects and known ground truth; "oracle" runs use exact
  facts and measure everything after extraction; "live" runs call Claude end to end.
- GET /evals → [{ id, mode, status, note, started_at, finished_at, packets, disposition_accuracy,
  detection: { precision, recall, true_positives, false_positives } | null,
  cost_usd: { total, per_application_mean, per_application_max } | null }]
- Runs table (note or short id + date + status, mode pill, packets, disposition accuracy %, detection P / R %,
  cost per app) with "details". Auto-select the newest completed run with packets.
- GET /evals/{id} → { id, mode, status, note, config, metrics, packets, started_at, finished_at }.
  metrics has: packets, errors, disposition_accuracy, confusion { expected: { proposed: count } },
  detection {…}, families { name: { packets, disposition_accuracy, detection_recall, spurious_signals,
  consequential_signals } }, guardrail_failure_rates { name: rate }, determinism_pass_rate,
  latency_s { mean, max }, and for live runs extraction { recall_mean, precision_mean, rejections },
  cost_usd {…}, llm_calls_mean, cost_share_by_stage { stage: share }.
- Metric tiles: Disposition accuracy, Detection precision, Detection recall, Deterministic screens, and for live
  runs Extraction recall/precision, Cost per application, plus Latency.
- 4×4 confusion matrix (rows expected, columns proposed; order Pass, Deficiency, Supplemental, Engineer):
  diagonal emerald, off-diagonal non-zero rose, zeros faint.
- "How often code had to flag or overrule the draft": guardrail_failure_rates as percentages.
- "By defect family" table and a "Packets" table (packet_id, expected, proposed with ✕ if wrong, failed
  guardrails, cost, latency, "review →" link to /review/{case_id}; amber row if wrong, rose if error).

GENERAL
- Percentages: 1 → "100%", otherwise one decimal. Money: 3–4 decimals. Dates in local time.
- Loading and error states on every page ("Could not reach the Greenlight API: …").
- A small typed API client module with the types above.
```

## Making the backend reachable (required for Path A)

Lovable runs in the cloud and cannot reach `localhost`. Options:

1. **Temporary tunnel, for trying it out:**
   ```bash
   brew install cloudflared
   cloudflared tunnel --url http://localhost:8010
   ```
   Use the printed `https://….trycloudflare.com` URL in the prompt. Then allow Lovable's preview origin in
   the backend's CORS setting and restart the backend:
   ```bash
   # docker-compose.yml → backend → GREENLIGHT_CORS_ORIGINS: http://localhost:3100,https://<your-lovable-preview-domain>
   docker compose up -d backend
   ```
   **Warning:** the API has no login. Anyone with the tunnel URL can run reviews that spend your Claude
   credits. Keep the tunnel open only while testing, and stop it (Ctrl+C) afterwards.

2. **Deploy the backend** (e.g. Fly.io, Render, Railway) with managed Postgres, before sharing it with anyone.
   Add authentication first.

## Path B: Lovable rebuilds everything on Lovable Cloud (not recommended)

If you still want Lovable to build the whole system, start with this and expect to verify its screen logic
yourself. Greenlight's Python engine has 234 tests that a rebuild would not have.

```text
Build "Greenlight" on Lovable Cloud: an interconnection-review tool for utility engineers under PG&E Electric
Rule 21. Use the same four pages and design as described below [paste the PAGES and DESIGN sections from
Path A], but implement the backend yourself:
- Tables: cases, documents (file in storage + sha256), pages (text per page), extracted_facts (field, value,
  unit, value_as_written, unit_as_written, document_id, page_no, quote — quote required), rule_results,
  discrepancies, agent_runs, agent_steps, proposals (status pending_review | approved | edited | rejected;
  a database trigger must make new proposals pending_review, require reviewed_by to leave that state, and
  forbid changes after review).
- Edge function "extract": send a PDF to Claude (model claude-opus-5) with structured JSON output of facts
  (field, value_as_written, unit_as_written, page, quote); reject any fact whose quote is not found on that
  page's text or whose number is not in its quote. Keep the Anthropic API key as a secret.
- Screens A–M implemented as pure TypeScript functions with no AI, each returning PASS / FAIL / INCONCLUSIVE /
  NOT_APPLICABLE / SKIPPED with formula, computed, threshold and citation (section + sheet). Key rules:
  J: gross rating ≤ 30 kVA skips K, L, M; F, G, H not applicable at ≤ 30 kVA; F: sum of short-circuit
  contribution ratios ≤ 0.1; F1: per-unit contribution ≤ 1.2; G: ≤ 87.5% of interrupting capability;
  H: 3-phase 4-wire "other" aggregate ≤ 10% of line-section peak load; K: NEM-1/NEM-2/NBT-1 ≤ 500 kW skips L;
  M: gross nameplate ≤ 90% of the lowest ICA-SG and ICA-OF values, or < 15% of line-section peak if no ICA.
  Missing inputs return INCONCLUSIVE naming the input — never guess.
- Edge function "review": a bounded Claude tool-use loop (max 12 calls, $1 cost ceiling) with tools
  run_screens, search_rules, get_field_provenance, flag_deficiency, propose_disposition. After it proposes,
  code checks that every number in the letter appears in the evidence, and raises the disposition to the
  code-computed floor if the model proposed something less severe.
```
