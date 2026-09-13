from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.models import EvalRun
from app.core.storage import LocalStorage
from app.domains.interconnection.evals.generator import FAMILIES, corpus, generate
from app.domains.interconnection.evals.runner import RunConfig, run_eval
from app.domains.interconnection.rules.ingest import ingest


def test_generation_is_deterministic_per_seed() -> None:
    a, b = generate("clean_commercial", 3), generate("clean_commercial", 3)
    assert [f.quote for f in a.facts] == [f.quote for f in b.facts]
    assert generate("clean_commercial", 4).applicant_name != a.applicant_name or \
        [f.quote for f in generate("clean_commercial", 4).facts] != [f.quote for f in a.facts]


def test_equipment_comes_from_the_certified_list_unless_the_defect_says_otherwise() -> None:
    from app.domains.interconnection.equipment.lookup import lookup
    assert lookup(next(f.value_as_written for f in generate("clean_residential", 1).facts if f.field == "inverter_model")).certified
    assert not lookup(next(f.value_as_written for f in generate("uncertified_inverter", 1).facts if f.field == "inverter_model")).listed


@pytest.fixture
def committed_sessions(engine: Engine) -> Iterator[sessionmaker[Session]]:
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as s:
        ingest(s, pdf_path=Path("/nonexistent"))
        s.commit()
    yield factory


def test_oracle_eval_meets_ground_truth_on_every_family(committed_sessions, tmp_path: Path) -> None:
    run_id = run_eval(committed_sessions, LocalStorage(tmp_path), corpus(1, seed=42), RunConfig("oracle"))
    with committed_sessions() as s:
        run = s.get(EvalRun, run_id)
        m = run.metrics
        bad = [(p["packet_id"], p.get("disposition"), p.get("spurious"), p.get("error")) for p in run.packets
               if "error" in p or not p["correct"] or p["spurious"]]
        assert bad == []
        assert m["packets"] == len(FAMILIES) and m["disposition_accuracy"] == 1.0
        assert m["detection"] == {"precision": 1.0, "recall": 1.0, "true_positives": 9, "false_positives": 0}
        assert m["determinism_pass_rate"] == 1.0
        assert all(v == 0.0 for v in m["guardrail_failure_rates"].values())


def test_live_mode_requires_a_client(committed_sessions, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_eval(committed_sessions, LocalStorage(tmp_path), corpus(1, families=["clean_residential"]), RunConfig("live"))
