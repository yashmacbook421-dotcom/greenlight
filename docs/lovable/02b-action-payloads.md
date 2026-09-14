# Greenlight — sample payloads for the remaining endpoints (message 3)

Paste everything below this line into Lovable after `02-sample-data.md`.

---

Here are REAL request/response payloads for every endpoint not covered by the previous message (actions, uploads, search, and error cases), captured from the running API. Together with the previous message this covers every endpoint. Notes:
- Errors raised by the app return `{"detail": "message"}` (a string). Request-validation errors (FastAPI) return `{"detail": [ {type, loc, msg, input, ...} ]}` (an array). Handle both.
- IDs are UUID strings. Timestamps are ISO-8601 with timezone. Decimal numbers are strings; keep them as strings.
- Long letters are truncated where marked.

### Health check
`GET /health` → **200**
Response:
```json
{"status":"ok","db":"ok"}
```

### Create a demo application
`POST /demo/packets` → **201**
Request:
```json
{"family":"uncertified_inverter","seed":4242,"oracle_facts":true}
```
Response:
```json
{"case_id":"3c10b8e5-3af8-49d2-97d4-9c0acdbad7e6","family":"uncertified_inverter","expected_disposition":"SUPPLEMENTAL_REVIEW_REQUIRED","description":"Inverter model is not on the certified list","oracle_facts":true}
```

### Create a demo application — unknown family
`POST /demo/packets` → **422**
Request:
```json
{"family":"nope"}
```
Response:
```json
{"detail":"family must be one of ['applicant_conflict', 'clean_commercial', 'clean_residential', 'crosses_30_kva', 'ica_exceeded', 'illegible_scan', 'invalid_non_export_option', 'missing_fault_current', 'missing_spec_sheet', 'nameplate_rounding', 'quantity_conflict', 'transformer_overload', 'uncertified_inverter']"}
```

### Run a review (no Claude: template draft)
`POST /cases/{case_id}/review?use_llm=false` → **200**
Takes well under a second without Claude, 1–2 minutes with `use_llm=true`. With Claude, `llm_used` is true and `proposal.agent_run_id` is set. `use_llm` defaults to true; if the server has no Claude key it falls back to the template.
Response:
```json
{"llm_used":false,"disposition_floor":"SUPPLEMENTAL_REVIEW_REQUIRED","proposal":{"id":"cc93acfa-7618-4c1a-acaf-6eec2fd8d164","disposition":"SUPPLEMENTAL_REVIEW_REQUIRED","model_disposition":null,"status":"pending_review","letter_md":"# Rule 21 Initial Review — Supplemental Review Required\n\n> Drafted by template: no Claude API client configured.\n\nThe request did not pass Initial Review. Technical reason, data and analysis (Rule 21 §F.2.a (Sheet 83)):\n\n- Screen B: equipment is not certified. Basis: Rule 21 §G.1.b (Sheet 141); Rule 21 §G.1 (Sheet 140).\n…(letter continues)…","items":[],"guardrail_verdicts":[{"name":"disposition_veto","passed":true,"detail":"SUPPLEMENTAL_REVIEW_REQUIRED is at or above the floor SUPPLEMENTAL_REVIEW_REQUIRED","data":{}},{"name":"provenance_completeness","passed":true,"detail":"all 0 item(s) point at recorded evidence","data":{}},{"name":"number_faithfulness","passed":true,"detail":"every number in the letter appears in recorded evidence","data":{}},{"name":"citation_validity","passed":true,"detail":"3 citation(s) resolve to pinned rule text","data":{"cited":[{"section":"F.2.a","sheet":83},{"section":"G.1.b","sheet":141},{"section":"G.1","sheet":140}]}},{"name":"summary_for_engineer","passed":true,"detail":"no Claude API client configured","data":{}}],"agent_run_id":null,"reviewed_by":null,"reviewed_at":null,"review_note":null,"created_at":"2026-09-14T07:19:08.391740Z"}}
```

### Run a review — unknown case
`POST /cases/{case_id}/review` → **404**
Response:
```json
{"detail":"case not found"}
```

### Decision — anonymous (validation error shape)
`POST /proposals/{proposal_id}/decision` → **422**
FastAPI request-validation errors return `detail` as an ARRAY of objects (not a string). Handle both shapes.
Request:
```json
{"action":"approve","reviewer":""}
```
Response:
```json
{"detail":[{"type":"string_too_short","loc":["body","reviewer"],"msg":"String should have at least 1 character","input":"","ctx":{"min_length":1}}]}
```

### Decision — edit without a letter
`POST /proposals/{proposal_id}/decision` → **422**
Request:
```json
{"action":"edit","reviewer":"j.engineer"}
```
Response:
```json
{"detail":"edit requires the revised letter_md"}
```

### Decision — approve
`POST /proposals/{proposal_id}/decision` → **200**
Other actions: `"reject"` (same shape, status `rejected`), `"edit"` with `letter_md` set to the revised letter (status `edited`, response `letter_md` is the revised text). The case's status becomes `closed`.
Request:
```json
{"action":"approve","reviewer":"j.engineer","note":"Checked Screen B against the CEC list.","letter_md":null}
```
Response:
```json
{"id":"cc93acfa-7618-4c1a-acaf-6eec2fd8d164","disposition":"SUPPLEMENTAL_REVIEW_REQUIRED","model_disposition":null,"status":"approved","letter_md":"# Rule 21 Initial Review — Supplemental Review Required\n\n> Drafted by template: no Claude API client configured.\n\nThe request did not pass Initial Review. Technical reason, data and analysis (Rule 21 §F.2.a (Sheet 83)):\n\n- Screen B: equipment is not certified. Basis: Rule 21 §G.1.b (Sheet 141); Rule\n…(letter continues)…","items":[],"guardrail_verdicts":[{"data":{},"name":"disposition_veto","detail":"SUPPLEMENTAL_REVIEW_REQUIRED is at or above the floor SUPPLEMENTAL_REVIEW_REQUIRED","passed":true},{"data":{},"name":"provenance_completeness","detail":"all 0 item(s) point at recorded evidence","passed":true},{"data":{},"name":"number_faithfulness","detail":"every number in the letter appears in recorded evidence","passed":true},{"data":{"cited":[{"sheet":83,"section":"F.2.a"},{"sheet":141,"section":"G.1.b"},{"sheet":140,"section":"G.1"}]},"name":"citation_validity","detail":"3 citation(s) resolve to pinned rule text","passed":true},{"data":{},"name":"summary_for_engineer","detail":"no Claude API client configured","passed":true}],"agent_run_id":null,"reviewed_by":"j.engineer","reviewed_at":"2026-09-14T07:19:08.414036Z","review_note":"Checked Screen B against the CEC list.","created_at":"2026-09-14T07:19:08.391740Z"}
```

### Decision — already decided
`POST /proposals/{proposal_id}/decision` → **409**
Request:
```json
{"action":"reject","reviewer":"someone"}
```
Response:
```json
{"detail":"proposal was already approved"}
```

### Decision — unknown proposal
`POST /proposals/{proposal_id}/decision` → **404**
Response:
```json
{"detail":"proposal not found"}
```

### Create an application
`POST /interconnection/applications` → **201**
`utility` is required (1–64 chars); the other fields are optional.
Request:
```json
{"utility":"PGE","submitter":"Golden State Solar","applicant_name":"Priya Patel","site_address":"1450 Laurel Dr, Chico, CA"}
```
Response:
```json
{"case_id":"8d8a6fd0-542e-40eb-9354-56b623e4b22c","status":"received"}
```

### Create an application — missing utility
`POST /interconnection/applications` → **422**
Request:
```json
{}
```
Response:
```json
{"detail":[{"type":"missing","loc":["body","utility"],"msg":"Field required","input":{}}]}
```

### Upload a document
`POST /cases/{case_id}/documents` → **201**
`multipart/form-data` with fields `kind` (text) and `file` (PDF). 201 = stored. Documents are also listed by `GET /cases/{case_id}` (same document shape) and in the review bundle.
Response:
```json
{"id":"a7751b64-8bf7-4b2b-b03d-2a2eb3b166d5","kind":"application_form","filename":"application_form.pdf","sha256":"c697a2bdc5296d192f15ee18d7c9cb7b14195c8ae86532b5f7442cce826b97c1","page_count":2,"created_at":"2026-09-14T07:19:08.434803Z","pages":[{"page_no":1,"anchor":"c697a2bdc529#p1","has_text_layer":true,"char_count":232},{"page_no":2,"anchor":"c697a2bdc529#p2","has_text_layer":true,"char_count":274}]}
```

### Upload the same file again
`POST /cases/{case_id}/documents` → **200**
**200** (not 201) and the existing document's id: identical bytes are never stored twice.
Response:
```json
{"id":"a7751b64-8bf7-4b2b-b03d-2a2eb3b166d5","kind":"application_form","filename":"application_form.pdf","sha256":"c697a2bdc5296d192f15ee18d7c9cb7b14195c8ae86532b5f7442cce826b97c1","page_count":2,"created_at":"2026-09-14T07:19:08.434803Z","pages":[{"page_no":1,"anchor":"c697a2bdc529#p1","has_text_layer":true,"char_count":232},{"page_no":2,"anchor":"c697a2bdc529#p2","has_text_layer":true,"char_count":274}]}
```

### Upload — not a PDF
`POST /cases/{case_id}/documents` → **422**
Other 422 details: `"PDF could not be read: …"`, `"PDF is password-protected"`, `"PDF has 312 pages; the limit is 200"`. Over 25 MB returns **413** `{"detail":"file exceeds 26214400 bytes"}`.
Response:
```json
{"detail":"file is not a PDF"}
```

### Upload — invalid kind
`POST /cases/{case_id}/documents` → **422**
Response:
```json
{"detail":"kind must be one of ['application_form', 'battery_spec_sheet', 'customer_authorization', 'inverter_spec_sheet', 'one_line_diagram', 'other', 'site_plan']"}
```

### Case with its documents
`GET /cases/{case_id}` → **200**
Response:
```json
{"id":"8d8a6fd0-542e-40eb-9354-56b623e4b22c","domain":"interconnection","status":"received","submitter":"Golden State Solar","received_at":"2026-09-14T07:19:08.418842Z","documents":[{"id":"a7751b64-8bf7-4b2b-b03d-2a2eb3b166d5","kind":"application_form","filename":"application_form.pdf","sha256":"c697a2bdc5296d192f15ee18d7c9cb7b14195c8ae86532b5f7442cce826b97c1","page_count":2,"created_at":"2026-09-14T07:19:08.434803Z","pages":[{"page_no":1,"anchor":"c697a2bdc529#p1","has_text_layer":true,"char_count":232},{"page_no":2,"anchor":"c697a2bdc529#p2","has_text_layer":true,"char_count":274}]}]}
```

### Original PDF
`GET /cases/{case_id}/documents/{document_id}/file` → **200**, `Content-Type: application/pdf`, `Content-Disposition: inline; filename="application_form.pdf"`, body = the PDF bytes (1956 bytes). Append `#page=N` in a viewer to open a page. 404 `{"detail":"document not found"}` for a wrong id.

### One page's text
`GET /cases/{case_id}/documents/{document_id}/pages/{page_no}` → **200**
Response:
```json
{"document_id":"a7751b64-8bf7-4b2b-b03d-2a2eb3b166d5","page_no":1,"anchor":"c697a2bdc529#p1","has_text_layer":true,"text":"PG&E Rule 21 Interconnection Request - Generating Facility\nApplicant name: Hana Tanaka\nService address: 648 Sequoia Way, Santa Rosa, CA\nInstaller: Sierra Sun Installers\nTariff: Net Billing Tariff (NBT-1)\nExport to grid: Yes - export"}
```

### Extract facts from one document (calls Claude)
`POST /cases/{case_id}/documents/{document_id}/extract` → **200**. Not called while capturing (it spends money). Shape:
```json
{"document_id":"uuid","model":"claude-opus-5","cost_usd":"0.0231","accepted":[{"field":"inverter_rated_ac_power","value":"7.616","unit":"kW","instance":null,"page_no":1,"quote":"Rated AC output power: 7,616 W","verification":"text_match"}],"rejected":[{"field":"inverter_rated_ac_power","page":1,"quote":"Rated AC output power 7,600 W","value_as_written":"7,600","unit_as_written":"W","reason":"quote_not_on_page","detail":""}]}
```
`reason` is one of `unknown_field`, `unknown_page`, `empty_quote`, `quote_not_on_page`, `value_not_numeric`, `value_not_in_quote`, `unit_missing`, `unit_not_allowed`, `unit_not_in_quote`, `choice_not_allowed`. **503** `{"detail":"Claude API is not configured: …"}` without a key; **502** if Claude refuses or truncates. The review endpoint runs extraction automatically, so the UI rarely needs this.

### Search the tariff
`GET /rules/search?q=gross rating 30 kVA&limit=3` → **200**
`q` needs at least 2 characters; `limit` 1–20 (default 5). `snippet` marks matched words with « ». Returns `[]` if nothing matches.
Response:
```json
[{"ruleset":"pge_rule21_2025-08-29","section":"G.1.j","heading":"Screen J:  Is the Gross Rating of the Generating Facility 30 kVA or","sheet":151,"snippet":"Screen J: Is the «Gross» «Rating» of the Generating Facility «30» «kVA» or less? •If Yes (pass), skip Screens K, L and M; Initial Review is complete. •If No (fail), continue to Screen K. i Significance: The Generating Facility will","rank":0.4950242},{"ruleset":"pge_rule21_2025-08-29","section":"H.2.b.i","heading":"Generating Facilities (30 kVA or less)","sheet":173,"snippet":"Generating Facilities («30» «kVA» or less) Generating Facilities with a «Gross» «Rating» of «30» «kVA» or less shall be capable of operating within the voltage range normally experienced on Distribution Provider’s Distribution System from plus to minus","rank":0.30714285},{"ruleset":"pge_rule21_2025-08-29","section":"G.1.f","heading":"Screens F and F1:","sheet":144,"snippet":"Screen F1 pursuant to Section G.1. Note: This Screen does not apply to Generating Facilities with a «Gross» «Rating» of «30» «kVA» or less. When measured at primary side (high side) of the Dedicated Distribution Transformer serving a Generating Facility","rank":0.2}]
```

### Search the tariff — query too short
`GET /rules/search?q=a` → **422**
Response:
```json
{"detail":[{"type":"string_too_short","loc":["query","q"],"msg":"String should have at least 2 characters","input":"a","ctx":{"min_length":2}}]}
```

### Eval run — unknown id
`GET /evals/{run_id}` → **404**
Response:
```json
{"detail":"eval run not found"}
```
