"""Load a generated packet as a real case, for demos and manual testing of the review UI."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import SessionDep, StorageDep
from app.domains.interconnection.evals.generator import FAMILIES, generate
from app.domains.interconnection.evals.runner import insert_oracle_facts, load_packet

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoPacket(BaseModel):
    family: str = "clean_residential"
    seed: Annotated[int, Field(ge=0)] = 0
    oracle_facts: bool = Field(False, description="Insert the generator's exact facts instead of running extraction "
                                                  "(lets the review run without Claude credentials)")


@router.post("/packets", status_code=status.HTTP_201_CREATED)
def create_demo_packet(body: DemoPacket, session: SessionDep, storage: StorageDep) -> dict[str, object]:
    if body.family not in FAMILIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"family must be one of {sorted(FAMILIES)}")
    packet = generate(body.family, body.seed)
    case, docs = load_packet(session, storage, packet, tag=f"demo-{uuid.uuid4().hex[:6]}")
    case.submitter = f"[demo] {packet.installer_name}"
    if body.oracle_facts:
        insert_oracle_facts(session, case, docs, packet)
    session.commit()
    return {"case_id": str(case.id), "family": packet.family.name, "expected_disposition": packet.family.expected.value,
            "description": packet.family.description, "oracle_facts": body.oracle_facts}
