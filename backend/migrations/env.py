from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlmodel import SQLModel


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.core.config import settings  # noqa: E402
from app.db import models  # noqa: E402, F401
from app.db.database import engine  # noqa: E402


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = SQLModel.metadata

MANAGED_TABLES = {
    "segmentation_queries",
}


def include_object(
    object_,
    name,
    type_,
    reflected,
    compare_to,
):
    """
    Prevent Alembic from modifying unrelated tables that might exist
    in the same PostgreSQL database, such as pgSTAC tables.
    """

    if type_ == "table":
        return name in MANAGED_TABLES

    table = getattr(object_, "table", None)

    if table is not None:
        return table.name in MANAGED_TABLES

    return True


def configure_context(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=False,
        include_object=include_object,
        version_table="geoai_alembic_version",
        **kwargs,
    )


def run_migrations_offline() -> None:
    configure_context(
        url=settings.database_url,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        configure_context(
            connection=connection,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()