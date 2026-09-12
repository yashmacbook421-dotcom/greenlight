from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.rules_search import search_rules
from app.deps import SessionDep
from app.domains.interconnection.screens.rulebook import RULESET

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/search")
def search(q: Annotated[str, Query(min_length=2)], session: SessionDep,
           limit: Annotated[int, Query(ge=1, le=20)] = 5) -> list[dict[str, object]]:
    return [asdict(h) for h in search_rules(session, RULESET, q, limit=limit)]
