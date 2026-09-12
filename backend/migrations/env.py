from alembic import context
from sqlalchemy import create_engine, pool

import app.core.models  # noqa: F401  (register tables)
import app.domains.interconnection.models  # noqa: F401
from app.config import settings
from app.db import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # Tests pass an explicit URL; everything else uses settings.
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
