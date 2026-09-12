"""Search and fetch pinned rule text. Results always carry section and sheet, so they can be cited."""

from dataclasses import dataclass

from sqlalchemy import Text, cast, delete, func, select
from sqlalchemy.orm import Session

from app.core.models import RuleChunk


@dataclass(frozen=True)
class RuleHit:
    ruleset: str
    section: str
    heading: str
    sheet: int
    snippet: str
    rank: float


def replace_chunks(session: Session, ruleset: str, chunks: list[dict[str, object]]) -> int:
    session.execute(delete(RuleChunk).where(RuleChunk.ruleset == ruleset))
    session.add_all(RuleChunk(ruleset=ruleset, **c) for c in chunks)
    session.flush()
    return len(chunks)


def search_rules(session: Session, ruleset: str, query: str, *, limit: int = 5) -> list[RuleHit]:
    """All-terms match first; if nothing matches every term, fall back to any-term ranking."""
    strict = func.websearch_to_tsquery("english", query)
    hits = _search(session, ruleset, strict, limit)
    if hits:
        return hits
    loose = func.to_tsquery("english", func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|"))
    return _search(session, ruleset, loose, limit)


def _search(session: Session, ruleset: str, tsquery, limit: int) -> list[RuleHit]:  # type: ignore[no-untyped-def]
    rank = func.ts_rank_cd(RuleChunk.search, tsquery)
    snippet = func.ts_headline("english", RuleChunk.text, tsquery,
                               "MaxWords=40, MinWords=15, StartSel=«, StopSel=», MaxFragments=2")
    rows = session.execute(
        select(RuleChunk.ruleset, RuleChunk.section, RuleChunk.heading, RuleChunk.sheet, snippet, rank)
        .where(RuleChunk.ruleset == ruleset, RuleChunk.search.op("@@")(tsquery))
        .order_by(rank.desc(), RuleChunk.ordinal)
        .limit(limit)
    ).all()
    return [RuleHit(r[0], r[1], r[2], r[3], " ".join(r[4].split()), float(r[5])) for r in rows]


def sheet_text(session: Session, ruleset: str, sheet: int) -> str | None:
    """All indexed text on one sheet, in document order; None if the sheet is not in the corpus."""
    parts = session.scalars(
        select(RuleChunk.text).where(RuleChunk.ruleset == ruleset, RuleChunk.sheet == sheet).order_by(RuleChunk.ordinal)
    ).all()
    return "\n".join(parts) if parts else None


def sections_on_sheet(session: Session, ruleset: str, sheet: int) -> set[str]:
    return set(session.scalars(
        select(RuleChunk.section).where(RuleChunk.ruleset == ruleset, RuleChunk.sheet == sheet)
    ).all())
