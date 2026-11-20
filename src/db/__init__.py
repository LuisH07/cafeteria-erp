"""Camada de acesso ao banco de dados PostgreSQL/Supabase."""

from src.db.connection import (
    check_database_health,
    get_connection,
    get_engine,
    get_transaction,
    set_engine_override,
)
from src.db.queries import execute_scalar, fetch_all, fetch_df, fetch_one

__all__ = [
    "check_database_health",
    "execute_scalar",
    "fetch_all",
    "fetch_df",
    "fetch_one",
    "get_connection",
    "get_engine",
    "get_transaction",
    "set_engine_override",
]
