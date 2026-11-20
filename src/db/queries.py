"""Helpers reutilizáveis para consultas parametrizadas no PostgreSQL."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.db.connection import get_connection


def fetch_all(
    sql: str,
    params: dict[str, Any] | None = None,
    conn: Connection | None = None,
) -> list[dict[str, Any]]:
    """Executa SELECT parametrizado e retorna lista de dicionários."""
    stmt = text(sql)
    bind = params or {}
    if conn is not None:
        return [dict(row) for row in conn.execute(stmt, bind).mappings().all()]
    with get_connection() as local_conn:
        return [dict(row) for row in local_conn.execute(stmt, bind).mappings().all()]


def fetch_one(
    sql: str,
    params: dict[str, Any] | None = None,
    conn: Connection | None = None,
) -> dict[str, Any] | None:
    """Executa SELECT parametrizado e retorna um único dicionário ou None."""
    stmt = text(sql)
    bind = params or {}
    if conn is not None:
        row = conn.execute(stmt, bind).mappings().first()
        return dict(row) if row is not None else None
    with get_connection() as local_conn:
        row = local_conn.execute(stmt, bind).mappings().first()
        return dict(row) if row is not None else None


def execute_scalar(
    sql: str,
    params: dict[str, Any] | None = None,
    conn: Connection | None = None,
) -> Any:
    """Executa query retornando valor escalar."""
    stmt = text(sql)
    bind = params or {}
    if conn is not None:
        return conn.execute(stmt, bind).scalar()
    with get_connection() as local_conn:
        return local_conn.execute(stmt, bind).scalar()


def fetch_df(
    sql: str,
    params: dict[str, Any] | None = None,
    conn: Connection | None = None,
) -> pd.DataFrame:
    """Executa SELECT parametrizado e retorna pandas.DataFrame."""
    rows = fetch_all(sql, params=params, conn=conn)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
