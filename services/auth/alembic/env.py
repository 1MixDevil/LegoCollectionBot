from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool, text
from alembic import context

from app.models import associations, permissions_model, user_model  # noqa: F401
from app.core.db import Base

config = context.config


def get_database_url() -> str:
    """DATABASE_URL из docker-compose имеет приоритет над POSTGRES_*."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("POSTGRES_USER", "aml1")
    password = os.getenv("POSTGRES_PASSWORD", "aml1")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "lego_db")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


config.set_main_option("sqlalchemy.url", get_database_url())

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
SCHEMA = target_metadata.schema


def include_object(obj, name, type_, reflected, compare_to):
    schema = getattr(obj, "schema", None)
    return schema in (None, SCHEMA)


def run_migrations_offline():
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=SCHEMA,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def ensure_schemas(connection):
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS figure"))
    connection.commit()


def run_migrations_online():
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = get_database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as conn:
        ensure_schemas(conn)
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=SCHEMA,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
