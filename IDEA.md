# Project Greenlight — The Idea

**Tagline:** An agent that reviews DER interconnection applications end to end.

## The problem

Every time someone wants to install rooftop solar, a home battery, or a
small commercial generator, the local utility has to review and approve
the application before it can be legally connected to the grid. This is
called **DER interconnection review** (DER = Distributed Energy Resource).

The review isn't a formality. The utility has to check whether adding
that equipment to a specific point on a specific circuit is safe: will it
overload the local transformer, push voltage out of bounds, contribute
too much fault current, confuse a voltage regulator, or exceed how much
DER that line section can safely carry alongside everything already
connected to it.

Each application arrives as a packet of documents — an application form,
a one-line electrical diagram, inverter spec sheets, a site plan — filled
out by installers with wildly inconsistent formats and, often, small
inconsistencies between documents (the form says 7.6 kW, the spec sheet
says 7.68 kW). An engineer has to read all of it, run the technical
screens by hand, decide whether any failure is fixable with a design
change or requires escalation to a full study, and write back to the
applicant.

This is not a rare or niche complaint — interconnection backlogs are a
mainstream story right now, tied directly to solar, storage, and EV
adoption outpacing utility review capacity. Applications that should take
days are sitting in queues for months or years.

## Why this is a genuinely good fit for an AI agent

Not every part of this problem needs an LLM, and that distinction is the
whole design:

- **Extracting structured facts from messy, inconsistent PDFs** —
  document-shaped, ambiguous, LLM work.
- **Deciding whether a discrepancy between documents is material** (7.6 kW
  vs. 7.68 kW: probably rounding; a missing spec sheet entirely: not
  fine) — a judgment call, LLM work.
- **Deciding what to check next when the first pass is inconclusive, and
  drafting the human-facing letter or justification** — LLM work.
- **The actual technical screens** — aggregate loading vs. line capacity,
  transformer thermal limits, voltage rise, fault current contribution —
  are **arithmetic with a correct answer**. Handing that to a
  probabilistic model would be a mistake; it belongs in deterministic
  code that produces the same answer every time.
- **Whether a letter or approval actually goes out** — always a human
  call. The agent never has unilateral authority to take a consequential
  action.

That split — *LLM handles ambiguity, code handles arithmetic, a human
holds authority* — is the whole thesis of the project. It's also the
thing most portfolio "AI agent" projects get wrong: they either bury an
LLM inside work a for-loop should do, or they let a model take
consequential action with no deterministic check in between.

## Why it's a strong project to build (vs. the alternative we considered)

The original idea for this slot was an autonomous outage-response agent
(fault detection → restoration switching → crew dispatch). That concept
was rejected after review: real utilities already automate that path with
dedicated systems (FLISR for fault isolation/restoration, OR-Tools-style
solvers for crew dispatch) that are faster, deterministic, and already
trusted. An LLM competing with those systems on their own turf is a hard
argument to win in an interview.

Interconnection review has the opposite shape: the hard part genuinely is
unstructured, ambiguous, and judgment-heavy, and the parts that aren't
(the screens) are cleanly separable into their own deterministic layer.
That's what makes it defensible instead of decorative.

## Who uses it

Interconnection engineers and application-processing staff at a
distribution utility — the people currently doing this review by hand,
document by document.

## What "done" looks like, conceptually

An application comes in. The system reads it, runs the technical screens,
and — when the evidence is ambiguous or a document conflicts with
another — reasons through what that means. It proposes one of three
outcomes: fast-track approval, a deficiency letter explaining exactly
what needs fixing (with every claim traceable back to a specific page or
rule section), or escalation to a full engineering study. A human reviews
that proposal, with full visibility into every number and every citation
behind it, and decides whether to send it. Nothing goes to an applicant
without that sign-off.

The measure of success isn't "does it sound smart" — it's a real eval:
does it correctly detect injected defects, does it get the disposition
right against known ground truth, are its citations actually real, and
what does it cost per application. That's what turns this from a demo
into something closer to an actual engineering artifact.

## The one-sentence version, for talking to anyone

*"Solar interconnection applications, reviewed by an agent, approved by a
human."*
