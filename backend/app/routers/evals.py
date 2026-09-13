import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.models import EvalRun
from app.deps import SessionDep
from app.domains.interconnection.evals.generator import FAMILIES

router = APIRouter(prefix="/evals", tags=["evals"])


@router.get("")
def list_runs(session: SessionDep) -> list[dict[str, Any]]:
    runs = session.scalars(select(EvalRun).order_by(EvalRun.started_at.desc()).limit(50)).all()
    return [{"id": str(r.id), "mode": r.mode, "status": r.status, "note": r.note, "started_at": r.started_at,
             "finished_at": r.finished_at, "packets": r.metrics.get("packets"),
             "disposition_accuracy": r.metrics.get("disposition_accuracy"), "detection": r.metrics.get("detection"),
             "cost_usd": r.metrics.get("cost_usd")} for r in runs]


@router.get("/families")
def families() -> list[dict[str, Any]]:
    return [{"name": f.name, "profile": f.profile, "expected": f.expected.value, "description": f.description,
             "detections": list(f.detections), "consequences": list(f.consequences)} for f in FAMILIES.values()]


@router.get("/{run_id}")
def get_run(run_id: uuid.UUID, session: SessionDep) -> dict[str, Any]:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "eval run not found")
    return {"id": str(run.id), "mode": run.mode, "status": run.status, "note": run.note, "config": run.config,
            "metrics": run.metrics, "packets": run.packets, "started_at": run.started_at, "finished_at": run.finished_at}
