"""Gerenciamento de conexão e transações ACID com PostgreSQL (Supabase)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import sys
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from src.config.settings import load_settings

_ENGINE_OVERRIDE: Engine | None = None
_CLI_ENGINE: Engine | None = None


def set_engine_override(engine: Engine | None) -> None:
    """Permite injetar um Engine customizado em testes automatizados."""
    global _ENGINE_OVERRIDE
    _ENGINE_OVERRIDE = engine


def _build_engine(database_url: str) -> Engine:
    """Cria Engine SQLAlchemy com pool enxuto compatível com Supabase Transaction/Session Pooler."""
    connect_args: dict[str, Any] = {}
    if "+psycopg" in database_url:
        # Evita DuplicatePreparedStatement no Supavisor/PgBouncer em modo transaction pooler
        connect_args["prepare_threshold"] = None

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=3,
        pool_recycle=300,
        connect_args=connect_args,
        future=True,
    )


def _is_running_in_streamlit() -> bool:
    """Detecta se estamos dentro do servidor Streamlit sem emitir warnings em scripts CLI."""
    if "streamlit" not in sys.modules:
        return False
    try:
        from streamlit.runtime import exists

        return bool(exists())
    except Exception:
        return False


def _get_cached_streamlit_engine(database_url: str) -> Engine:
    """Singleton de Engine em cache quando rodando dentro do Streamlit."""
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _cached(url: str) -> Engine:
        return _build_engine(url)

    return _cached(database_url)


def get_engine() -> Engine:
    """Retorna o Engine ativo (override de teste, cache Streamlit ou singleton CLI)."""
    global _CLI_ENGINE

    if _ENGINE_OVERRIDE is not None:
        return _ENGINE_OVERRIDE

    settings = load_settings()
    if not settings.is_database_configured:
        raise RuntimeError(
            "Banco de dados não configurado. Defina [database].url em .streamlit/secrets.toml "
            "ou a variável de ambiente DATABASE_URL."
        )

    if _is_running_in_streamlit():
        return _get_cached_streamlit_engine(settings.database_url)

    if _CLI_ENGINE is None:
        _CLI_ENGINE = _build_engine(settings.database_url)
    return _CLI_ENGINE


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Abre uma conexão de leitura com fechamento garantido."""
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


@contextmanager
def get_transaction() -> Iterator[Connection]:
    """Abre uma transação ACID (commit automático ao sair ou rollback em erro)."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def check_database_health() -> dict[str, Any]:
    """Verifica conectividade com o PostgreSQL/Supabase e retorna metadados básicos."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                text("SELECT version() AS version, current_database() AS database, NOW() AS server_time")
            ).mappings().first()
            return {
                "ok": True,
                "version": row["version"] if row else "",
                "database": row["database"] if row else "",
                "server_time": row["server_time"] if row else None,
            }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }
