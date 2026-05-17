import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://aml1:aml1@db:5432/lego_db",
)
SERVICE_PORT = int(os.getenv("AUTHORIZATION_PORT", "8000"))
