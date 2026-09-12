"""Index the pinned Rule 21 text for search_rules.

    python -m scripts.fetch_rules && python -m scripts.ingest_rules
"""

from app.db import SessionLocal
from app.domains.interconnection.rules.ingest import ingest


def main() -> None:
    with SessionLocal() as session:
        count, source = ingest(session)
        session.commit()
    print(f"indexed {count} rule chunks from the {source}")


if __name__ == "__main__":
    main()
