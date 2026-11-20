"""Serviço de Controle de Estoque, Inventário e Razão de Movimentações."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import BusinessRuleError, NotFoundError, ValidationError


def get_estoque_position(
    *,
    apenas_criticos: bool = False,
    localizacao: str | None = None,
) -> list[dict[str, Any]]:
    """Retorna posição atual de estoque com classificação de criticidade e valor imobilizado."""
    clauses = ["i.ativo = TRUE"]
    params: dict[str, Any] = {}
    if apenas_criticos:
        clauses.append("i.estoque_atual <= i.estoque_minimo")
    if localizacao and localizacao != "Todas":
        clauses.append("i.localizacao = :localizacao")
        params["localizacao"] = localizacao

    where = " AND ".join(clauses)
    return fetch_all(
        f"""
        SELECT
            i.id,
            i.sku,
            i.nome,
            c.nome AS categoria_nome,
            i.unidade_medida,
            i.localizacao,
            i.perecivel,
            i.estoque_atual,
            i.estoque_minimo,
            i.custo_medio_atual,
            ROUND((i.estoque_atual * i.custo_medio_atual)::NUMERIC, 2) AS valor_imobilizado,
            CASE
                WHEN i.estoque_atual <= i.estoque_minimo THEN 'CRITICO'
                WHEN i.estoque_atual <= (i.estoque_minimo * 1.25) THEN 'ATENCAO'
                ELSE 'SAUDAVEL'
            END AS status_estoque
        FROM insumos i
        JOIN categorias c ON c.id = i.categoria_id
        WHERE {where}
        ORDER BY
            CASE
                WHEN i.estoque_atual <= i.estoque_minimo THEN 1
                WHEN i.estoque_atual <= (i.estoque_minimo * 1.25) THEN 2
                ELSE 3
            END,
            i.nome ASC
        """,
        params,
    )


def list_localizacoes_estoque() -> list[str]:
    rows = fetch_all(
        "SELECT DISTINCT localizacao FROM insumos WHERE ativo = TRUE ORDER BY localizacao ASC"
    )
    return [str(r["localizacao"]) for r in rows]


def list_movimentacoes_estoque(
    *,
    insumo_id: int | None = None,
    tipo_movimentacao: str | None = None,
    origem_modulo: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Consulta o histórico imutável de movimentações de estoque."""
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": int(limit)}
    if insumo_id:
        clauses.append("m.insumo_id = :insumo_id")
        params["insumo_id"] = int(insumo_id)
    if tipo_movimentacao and tipo_movimentacao != "Todos":
        clauses.append("m.tipo_movimentacao = :tipo_movimentacao")
        params["tipo_movimentacao"] = tipo_movimentacao
    if origem_modulo and origem_modulo != "Todos":
        clauses.append("m.origem_modulo = :origem_modulo")
        params["origem_modulo"] = origem_modulo

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT
            m.id,
            m.criado_em,
            i.sku AS insumo_sku,
            i.nome AS insumo_nome,
            i.unidade_medida,
            m.tipo_movimentacao,
            m.quantidade,
            m.saldo_anterior,
            m.saldo_posterior,
            m.custo_unitario_snapshot,
            m.origem_modulo,
            m.origem_id,
            m.motivo,
            u.nome AS usuario_nome
        FROM movimentacoes_estoque m
        JOIN insumos i ON i.id = m.insumo_id
        JOIN usuarios u ON u.id = m.usuario_id
        {where}
        ORDER BY m.criado_em DESC, m.id DESC
        LIMIT :limit
        """,
        params,
    )


def registrar_ajuste_inventario(
    *,
    insumo_id: int,
    novo_saldo_fisico: Decimal | float,
    motivo: str,
    usuario_id: int,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Executa ajuste auditado de inventário (diferença entre contagem física e saldo sistêmico)."""
    saldo_fisico = Decimal(str(novo_saldo_fisico)).quantize(Decimal("0.001"))
    if saldo_fisico < 0:
        raise ValidationError("O saldo físico apurado não pode ser negativo.")
    if not motivo.strip():
        raise ValidationError("Informe o motivo/justificativa do ajuste de inventário.")

    ts = occurred_at or datetime.now(timezone.utc)

    with get_transaction() as conn:
        insumo = fetch_one(
            """
            SELECT id, sku, nome, estoque_atual, custo_medio_atual, ativo
            FROM insumos
            WHERE id = :id
            FOR UPDATE
            """,
            {"id": int(insumo_id)},
            conn=conn,
        )
        if not insumo:
            raise NotFoundError("Insumo não encontrado.")
        if not insumo["ativo"]:
            raise BusinessRuleError("Não é possível ajustar estoque de insumo inativo.")

        saldo_anterior = Decimal(str(insumo["estoque_atual"])).quantize(Decimal("0.001"))
        diferenca = saldo_fisico - saldo_anterior
        if diferenca == 0:
            raise BusinessRuleError("O saldo físico informado é igual ao saldo atual em estoque.")

        tipo_mov = "AJUSTE_ENTRADA" if diferenca > 0 else "AJUSTE_SAIDA"
        quantidade_abs = abs(diferenca)
        custo_unit = Decimal(str(insumo["custo_medio_atual"]))

        conn.execute(
            text(
                """
                UPDATE insumos
                SET estoque_atual = :novo_saldo, atualizado_em = :ts
                WHERE id = :id
                """
            ),
            {"id": int(insumo_id), "novo_saldo": saldo_fisico, "ts": ts},
        )

        mov = conn.execute(
            text(
                """
                INSERT INTO movimentacoes_estoque (
                    insumo_id, tipo_movimentacao, quantidade, saldo_anterior, saldo_posterior,
                    custo_unitario_snapshot, origem_modulo, origem_id, motivo, usuario_id, criado_em
                )
                VALUES (
                    :insumo_id, :tipo_mov, :quantidade, :saldo_anterior, :saldo_posterior,
                    :custo_unit, 'ESTOQUE', NULL, :motivo, :usuario_id, :ts
                )
                RETURNING id, tipo_movimentacao, quantidade, saldo_anterior, saldo_posterior, criado_em
                """
            ),
            {
                "insumo_id": int(insumo_id),
                "tipo_mov": tipo_mov,
                "quantidade": quantidade_abs,
                "saldo_anterior": saldo_anterior,
                "saldo_posterior": saldo_fisico,
                "custo_unit": custo_unit,
                "motivo": motivo.strip(),
                "usuario_id": int(usuario_id),
                "ts": ts,
            },
        ).mappings().first()
        record = dict(mov)

        log_audit_event(
            usuario_id=usuario_id,
            modulo="ESTOQUE",
            entidade="movimentacoes_estoque",
            entidade_id=record["id"],
            acao=tipo_mov,
            detalhes={
                "insumo_id": insumo_id,
                "saldo_anterior": str(saldo_anterior),
                "saldo_posterior": str(saldo_fisico),
                "motivo": motivo.strip(),
            },
            conn=conn,
        )
        return record
