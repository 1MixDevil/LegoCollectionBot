-- Выполняется при первом старте Postgres (POSTGRES_DB=lego_db уже создан)
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS figure;

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA figure;

-- public не используется
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
