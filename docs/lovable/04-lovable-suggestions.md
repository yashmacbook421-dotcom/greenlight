# Greenlight product recommendations

## Trust and review quality
- **[needs backend] Per-fact confidence and extraction method.** Show low-confidence OCR or interpretation first, without presenting one misleading case-wide confidence score.
- **[needs backend] Immutable audit history.** Preserve every generated draft, engineer edit, decision, prompt/model version, rule-engine version, and evidence hash.
- **[frontend only] Saved review views.** Let engineers save queue filters such as “my urgent deficiencies” once ownership data exists.
- **[frontend only] Side-by-side letter diff.** Use a true line/word diff once expected letter sizes and the preferred comparison policy are known.
- **[needs backend] Evidence integrity status.** Return document hash verification and source-page availability as explicit fields.

## Operational UX
- **[needs backend] Stream review events.** The current review request returns only when finished. Stage events would replace elapsed-time waiting with honest progress and allow recovery after refresh.
- **[needs backend] Deadline calculation and notifications.** Return tariff deadline, calendar basis, pauses, and escalation state; do not derive regulatory deadlines only in the browser.
- **[needs backend] Assignment, authentication, and roles.** Add engineer/team-lead/reviewer permissions and server-enforced case ownership before production use.
- **[needs backend] Idempotency keys for creation and review.** Prevent duplicate cases or expensive duplicate model runs after retries.
- **[frontend only] Bulk triage.** Once assignment and deadline fields exist, add selection and bulk reassignment—not bulk approval.

## Brief clarifications and simplifications
- The exact PDF page-text endpoint was not in the supplied endpoint list; this frontend assumes `GET /cases/{caseId}/documents/{documentId}/pages/{pageNo}` for accessible quote highlighting.
- “Needs my attention” requires user identity, assignment, and/or explicit attention reasons from the backend. The mock queue currently prioritizes guardrail failures without claiming ownership.
- Browser PDF viewers cannot be reliably searched or highlighted across origins. Greenlight uses the PDF at the requested page beside normalized extracted page text and the exact quote.
- The decision endpoint locks the proposal, but production should also enforce authorization, optimistic concurrency, and immutable audit events server-side.