"""Evaluate the review pipeline on a generated corpus.

    python -m scripts.run_eval --mode oracle --per-family 3
    python -m scripts.run_eval --mode live --per-family 1 --max-cost 5   # calls Claude; costs money
"""

import argparse
import json
from decimal import Decimal

from app.config import settings
from app.core.llm import default_client
from app.core.models import EvalRun
from app.core.storage import LocalStorage
from app.db import SessionLocal
from app.domains.interconnection.evals.generator import FAMILIES, corpus
from app.domains.interconnection.evals.runner import RunConfig, run_eval


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["oracle", "live"], default="oracle")
    ap.add_argument("--per-family", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--families", nargs="*", choices=sorted(FAMILIES))
    ap.add_argument("--max-cost", default="5.00", help="live mode: stop starting packets once this much USD is spent")
    ap.add_argument("--note")
    args = ap.parse_args()

    packets = corpus(args.per_family, seed=args.seed, families=args.families)
    client = default_client() if args.mode == "live" else None

    def progress(r: dict) -> None:
        if "error" in r:
            print(f"  ERROR  {r['packet_id']}: {r['error']}")
        else:
            mark = "ok " if r["correct"] else "BAD"
            print(f"  {mark} {r['packet_id']:32} expected {r['expected_disposition']:30} got {r['disposition']:30}"
                  f" spurious={len(r['spurious'])} cost=${r['cost_usd']} {r['latency_s']}s")

    print(f"{args.mode} eval: {len(packets)} packets")
    run_id = run_eval(SessionLocal, LocalStorage(settings.storage_dir), packets,
                      RunConfig(args.mode, Decimal(args.max_cost)), client, note=args.note, on_packet=progress)
    with SessionLocal() as s:
        run = s.get(EvalRun, run_id)
        print(f"\nrun {run_id} ({run.status})")
        print(json.dumps(run.metrics, indent=1))


if __name__ == "__main__":
    main()
