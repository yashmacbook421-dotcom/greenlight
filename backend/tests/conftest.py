"""Integration tests run against a throwaway `greenlight_test` database on the compose Postgres."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DB = "greenlight_test"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    base_url = make_url(os.environ.get("GREENLIGHT_TEST_DATABASE_URL", settings.database_url))
    test_url = base_url.set(database=TEST_DB)

    admin = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", test_url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")

    eng = create_engine(test_url)
    yield eng
    eng.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Each test runs inside a transaction that is rolled back afterwards."""
    with engine.connect() as conn:
        trans = conn.begin()
        with Session(bind=conn, join_transaction_mode="create_savepoint") as s:
            yield s
        trans.rollback()
