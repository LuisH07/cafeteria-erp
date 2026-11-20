"""Serviço de auditoria append-only para rastreabilidade completa das operações."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.db.connection import get_transaction
from src.db.queries import fetch_all


def log_audit_event(
    *,
    usuario_id: int | None,
    modulo: str,
    entidade: str,
    entidade_id: int | None,
    acao: str,
    detalhes: dict[str, Any] | None = None,
    conn: Connection | None = None,
) -> None:
    """Registra evento imutável em audit_logs (participando de transação ativa se fornecida)."""
    payload = json.dumps(detalhes or {}, default=str, ensure_ascii=False)
    stmt = text(
        """
        INSERT INTO audit_logs (usuario_id, modulo, entidade, entidade_id, acao, detalhes_json)
        VALUES (:usuario_id, :modulo, :entidade, :entidade_id, :acao, CAST(:detalhes_json AS JSONB))
        """
    )
    params = {
        "usuario_id": usuario_id,
        "modulo": modulo,
        "entidade": entidade,
        "entidade_id": entidade_id,
        "acao": acao,
        "detalhes_json": payload,
    }
    if conn is not None:
        conn.execute(stmt, params)
        return

    with get_transaction() as local_conn:
        local_conn.execute(stmt, params)


def list_recent_audit_logs(limit: int = 50, modulo: str | None = None) -> list[dict[str, Any]]:
    """Lista os eventos de auditoria mais recentes com identificação do usuário."""
    where = "WHERE a.modulo = :modulo" if modulo else ""
    sql = f"""
        SELECT
            a.id,
            a.criado_em,
            a.modulo,
            a.entidade,
            a.entidade_id,
            a.acao,
            a.detalhes_json,
            COALESCE(u.nome, 'Sistema') AS usuario_nome,
            COALESCE(u.email, '-') AS usuario_email
        FROM audit_logs a
        LEFT JOIN usuarios u ON u.id = a.usuario_id
        {where}
        ORDER BY a.criado_em DESC
        LIMIT :limit
    """
    params: dict[str, Any] = {"limit": limit}
    if modulo:
        params["modulo"] = modulo
    return fetch_all(sql, params)
