"use client";

import {
  ArrowRight,
  Bot,
  Calculator,
  CheckCircle2,
  FilePen,
  FileSearch,
  RotateCcw,
  Send,
  UserCheck,
} from "lucide-react";

import { AppLink } from "@/components/app-link";

const journey = [
  {
    who: "you",
    icon: Send,
    title: "Submit the packet",
    text: "Enter the customer and site, then upload the application form, single-line diagram and inverter spec sheet.",
  },
  {
    who: "utility",
    icon: FileSearch,
    title: "Automatic first pass",
    text: "The documents are read, checked against each other, and run through the Rule 21 Initial Review screens.",
  },
  {
    who: "utility",
    icon: UserCheck,
    title: "An engineer decides",
    text: "A named interconnection engineer checks the draft against the evidence and approves, edits or rejects it.",
  },
  {
    who: "you",
    icon: CheckCircle2,
    title: "Get the decision",
    text: "The approved letter appears in your portal and a notice goes to your contact email.",
  },
  {
    who: "you",
    icon: RotateCcw,
    title: "Fix and resubmit",
    text: "If something is missing or inconsistent, upload the corrected document and resubmit. It goes back for review.",
  },
] as const;

const documents = [
  ["Interconnection application form", "Customer, site, tariff, export choice, system ratings and service panel."],
  ["Single-line diagram", "The electrical path from the PV array through the inverter and disconnect to the meter."],
  ["Inverter specification sheet", "The manufacturer's data: rated output, maximum current, fault current, certification."],
] as const;

const outcomes = [
  ["green", "Passed Initial Review", "Every applicable screen passed. The utility follows up on the next steps."],
  ["amber", "Action required", "A deficiency notice lists what is missing or contradictory. Correct it and resubmit."],
  ["red", "Supplemental Review", "A technical screen did not pass, so the system needs a closer engineering study."],
  ["blue", "Engineering review", "Utility-side data or judgment is needed before the review can finish."],
] as const;

export function HomePage() {
  return (
    <div className="home">
      <section className="home-hero">
        <div>
          <div className="eyebrow">PG&amp;E ELECTRIC RULE 21 · ROOFTOP SOLAR AND BATTERIES</div>
          <h1>Connect a solar system to the grid, and see every step of the review.</h1>
          <p>
            Installers submit the interconnection packet here. The utility reviews it against the tariff and sends
            the decision back to the same place, so nobody has to chase an email thread to find out where it stands.
          </p>
          <div className="home-actions">
            <AppLink to="/portal/new" className="site-cta large">
              Start an application <ArrowRight size={17} />
            </AppLink>
            <AppLink to="/portal" className="site-secondary large">
              Track my applications
            </AppLink>
          </div>
        </div>
        <aside className="home-card" aria-label="Example application status">
          <div className="home-card-head">
            <span>GL-4F2A91C0</span>
            <span className="badge badge-amber">Action required</span>
          </div>
          <strong>Maria Delgado</strong>
          <small>2147 Brookwood Avenue, Santa Rosa</small>
          <ol className="mini-steps">
            <li className="done">Submitted</li>
            <li className="done">Reviewed</li>
            <li className="current">Correct the inverter spec sheet</li>
            <li>Resubmit</li>
          </ol>
        </aside>
      </section>

      <section id="how-it-works" className="home-section">
        <div className="section-head">
          <div className="eyebrow">HOW IT WORKS</div>
          <h2>From packet to decision</h2>
          <p>
            <span className="lane-key you">You</span> do three things. <span className="lane-key utility">The utility</span>{" "}
            does the rest, and you can watch it happen.
          </p>
        </div>
        <ol className="journey">
          {journey.map(({ who, icon: Icon, title, text }, i) => (
            <li key={title} className={`journey-step ${who}`}>
              <span className="journey-who">{who === "you" ? "You" : "Utility"}</span>
              <span className="journey-icon">
                <Icon size={20} />
              </span>
              <span className="journey-no">{i + 1}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="home-section home-split">
        <div>
          <div className="eyebrow">BEFORE YOU START</div>
          <h2>What you&apos;ll need</h2>
          <p className="muted">Three PDFs are required. A site plan, battery spec sheet or customer authorization can be added too.</p>
          <ul className="need-list">
            {documents.map(([title, text]) => (
              <li key={title}>
                <FilePen size={18} />
                <div>
                  <strong>{title}</strong>
                  <span>{text}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="eyebrow">WHAT COMES BACK</div>
          <h2>The possible decisions</h2>
          <p className="muted">Each one is a notice the Rule 21 tariff requires the utility to send.</p>
          <ul className="outcome-list">
            {outcomes.map(([tone, title, text]) => (
              <li key={title}>
                <span className={`badge badge-${tone}`}>{title}</span>
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="home-section behind">
        <div className="section-head">
          <div className="eyebrow">BEHIND THE COUNTER</div>
          <h2>What happens after you press submit</h2>
          <p>Automation does the reading. It is never the one that decides.</p>
        </div>
        <div className="behind-grid">
          <article>
            <Bot size={22} />
            <h3>AI reads the documents</h3>
            <p>Every value it pulls out must quote the page it came from, or it is thrown away.</p>
          </article>
          <article>
            <Calculator size={22} />
            <h3>Code runs the screens</h3>
            <p>The Rule 21 thresholds are plain arithmetic, cited to the tariff sheet, with the same answer every time.</p>
          </article>
          <article>
            <UserCheck size={22} />
            <h3>An engineer signs off</h3>
            <p>No letter reaches your portal until a named engineer approves it. The database enforces that.</p>
          </article>
        </div>
        <div className="behind-links">
          <AppLink to="/about" className="button-link">
            How the review engine works <ArrowRight size={15} />
          </AppLink>
          <AppLink to="/queue" className="button-link">
            Open the engineer workspace <ArrowRight size={15} />
          </AppLink>
        </div>
      </section>
    </div>
  );
}
