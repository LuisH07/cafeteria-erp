"""Serviço Financeiro: Contas a Pagar/Receber, Fluxo de Caixa e DRE Simplificada."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import BusinessRuleError, NotFoundError, ValidationError


def list_titulos_financeiros(
    *,
    tipo: str | None = None,
    situacao: str | None = None,
    origem_modulo: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lista títulos com cálculo dinâmico de atraso (sem depender de cron job)."""
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": int(limit)}
    if tipo and tipo != "Todos":
        clauses.append("tf.tipo = :tipo")
        params["tipo"] = tipo
    if origem_modulo and origem_modulo != "Todos":
        clauses.append("tf.origem_modulo = :origem")
        params["origem"] = origem_modulo

    if situacao and situacao != "Todos":
        if situacao == "ATRASADO":
            clauses.append("tf.status = 'ABERTO' AND tf.data_vencimento < CURRENT_DATE")
        elif situacao == "ABERTO":
            clauses.append("tf.status = 'ABERTO' AND tf.data_vencimento >= CURRENT_DATE")
        else:
            clauses.append("tf.status = :status")
            params["status"] = situacao

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT
            tf.id,
            tf.tipo,
            c.nome AS categoria_nome,
            tf.descricao,
            tf.origem_modulo,
            tf.origem_id,
            COALESCE(cl.nome, f.nome_fantasia, '-') AS contraparte,
            tf.valor_original,
            tf.valor_pago,
            tf.data_competencia,
            tf.data_vencimento,
            tf.data_liquidacao,
            tf.status,
            CASE
                WHEN tf.status = 'ABERTO' AND tf.data_vencimento < CURRENT_DATE THEN 'ATRASADO'
                ELSE tf.status
            END AS situacao,
            tf.forma_pagamento,
            u.nome AS usuario_nome
        FROM titulos_financeiros tf
        JOIN categorias c ON c.id = tf.categoria_id
        JOIN usuarios u ON u.id = tf.usuario_id
        LEFT JOIN clientes cl ON cl.id = tf.cliente_id
        LEFT JOIN fornecedores f ON f.id = tf.fornecedor_id
        {where}
        ORDER BY
            CASE
                WHEN tf.status = 'ABERTO' AND tf.data_vencimento < CURRENT_DATE THEN 1
                WHEN tf.status = 'ABERTO' THEN 2
                ELSE 3
            END,
            tf.data_vencimento ASC,
            tf.id DESC
        LIMIT :limit
        """,
        params,
    )


def criar_titulo_manual(
    *,
    tipo: str,
    categoria_id: int,
    descricao: str,
    valor_original: Decimal | float,
    data_competencia: date,
    data_vencimento: date,
    forma_pagamento: str,
    usuario_id: int,
    liquidar_agora: bool = False,
    fornecedor_id: int | None = None,
    cliente_id: int | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Lança despesa operacional (aluguel, energia, folha etc.) ou receita manual."""
    if tipo not in {"PAGAR", "RECEBER"}:
        raise ValidationError("Tipo de título deve ser 'PAGAR' ou 'RECEBER'.")
    if not descricao.strip():
        raise ValidationError("Descrição do lançamento financeiro é obrigatória.")
    valor = Decimal(str(valor_original)).quantize(Decimal("0.01"))
    if valor <= 0:
        raise ValidationError("Valor do lançamento deve ser maior que zero.")

    ts = occurred_at or datetime.now(timezone.utc)

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO titulos_financeiros (
                    tipo, categoria_id, descricao, origem_modulo, origem_id,
                    cliente_id, fornecedor_id, valor_original, valor_pago,
                    data_competencia, data_vencimento, data_liquidacao,
                    status, forma_pagamento, usuario_id, criado_em, atualizado_em
                )
                VALUES (
                    :tipo, :categoria_id, :descricao, 'MANUAL', NULL,
                    :cliente_id, :fornecedor_id, :valor, :valor_pago,
                    :data_comp, :data_venc, :data_liq,
                    :status, :forma, :uid, :ts, :ts
                )
                RETURNING id, tipo, descricao, valor_original, status, data_vencimento
                """
            ),
            {
                "tipo": tipo,
                "categoria_id": int(categoria_id),
                "descricao": descricao.strip(),
                "cliente_id": int(cliente_id) if cliente_id else None,
                "fornecedor_id": int(fornecedor_id) if fornecedor_id else None,
                "valor": valor,
                "valor_pago": valor if liquidar_agora else Decimal("0.00"),
                "data_comp": data_competencia,
                "data_venc": data_vencimento,
                "data_liq": ts if liquidar_agora else None,
                "status": "PAGO" if liquidar_agora else "ABERTO",
                "forma": forma_pagamento,
                "uid": int(usuario_id),
                "ts": ts,
            },
        ).mappings().first()
        titulo = dict(row)

        if liquidar_agora:
            tipo_fluxo = "ENTRADA" if tipo == "RECEBER" else "SAIDA"
            conn.execute(
                text(
                    """
                    INSERT INTO movimentacoes_financeiras (
                        titulo_id, tipo_fluxo, valor, forma_pagamento, data_movimentacao,
                        descricao, usuario_id, criado_em
                    )
                    VALUES (
                        :tid, :fluxo, :valor, :forma, :ts, :desc, :uid, :ts
                    )
                    """
                ),
                {
                    "tid": int(titulo["id"]),
                    "fluxo": tipo_fluxo,
                    "valor": valor,
                    "forma": forma_pagamento,
                    "ts": ts,
                    "desc": descricao.strip(),
                    "uid": int(usuario_id),
                },
            )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="FINANCEIRO",
            entidade="titulos_financeiros",
            entidade_id=int(titulo["id"]),
            acao="CRIAR_TITULO_MANUAL",
            detalhes={
                "tipo": tipo,
                "valor": str(valor),
                "liquidar_agora": liquidar_agora,
            },
            conn=conn,
        )
        return titulo


def liquidar_titulo(
    *,
    titulo_id: int,
    forma_pagamento: str,
    usuario_id: int,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Liquida título em aberto e grava movimentação imutável no razão de fluxo de caixa."""
    ts = occurred_at or datetime.now(timezone.utc)

    with get_transaction() as conn:
        titulo = fetch_one(
            "SELECT * FROM titulos_financeiros WHERE id = :id FOR UPDATE",
            {"id": int(titulo_id)},
            conn=conn,
        )
        if not titulo:
            raise NotFoundError("Título financeiro não encontrado.")
        if titulo["status"] != "ABERTO":
            raise BusinessRuleError(
                f"Apenas títulos em ABERTO podem ser liquidados (status atual: {titulo['status']})."
            )

        valor = Decimal(str(titulo["valor_original"])).quantize(Decimal("0.01"))
        tipo_fluxo = "ENTRADA" if titulo["tipo"] == "RECEBER" else "SAIDA"

        updated = conn.execute(
            text(
                """
                UPDATE titulos_financeiros
                SET valor_pago = :valor,
                    data_liquidacao = :ts,
                    status = 'PAGO',
                    forma_pagamento = :forma,
                    atualizado_em = :ts
                WHERE id = :id
                RETURNING id, tipo, descricao, valor_original, valor_pago, status, data_liquidacao
                """
            ),
            {"id": int(titulo_id), "valor": valor, "ts": ts, "forma": forma_pagamento},
        ).mappings().first()

        conn.execute(
            text(
                """
                INSERT INTO movimentacoes_financeiras (
                    titulo_id, tipo_fluxo, valor, forma_pagamento, data_movimentacao,
                    descricao, usuario_id, criado_em
                )
                VALUES (
                    :tid, :fluxo, :valor, :forma, :ts, :desc, :uid, :ts
                )
                """
            ),
            {
                "tid": int(titulo_id),
                "fluxo": tipo_fluxo,
                "valor": valor,
                "forma": forma_pagamento,
                "ts": ts,
                "desc": f"Liquidação — {titulo['descricao']}",
                "uid": int(usuario_id),
            },
        )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="FINANCEIRO",
            entidade="titulos_financeiros",
            entidade_id=int(titulo_id),
            acao="LIQUIDAR_TITULO",
            detalhes={"tipo_fluxo": tipo_fluxo, "valor": str(valor), "forma": forma_pagamento},
            conn=conn,
        )
        return dict(updated)


def cancelar_titulo_manual(*, titulo_id: int, usuario_id: int) -> dict[str, Any]:
    """Cancela título manual em aberto (títulos de vendas/compras devem ser estornados na origem)."""
    with get_transaction() as conn:
        titulo = fetch_one(
            "SELECT * FROM titulos_financeiros WHERE id = :id FOR UPDATE",
            {"id": int(titulo_id)},
            conn=conn,
        )
        if not titulo:
            raise NotFoundError("Título financeiro não encontrado.")
        if titulo["origem_modulo"] != "MANUAL":
            raise BusinessRuleError(
                "Títulos originados de Vendas ou Compras devem ser cancelados no módulo de origem."
            )
        if titulo["status"] != "ABERTO":
            raise BusinessRuleError("Apenas títulos em ABERTO podem ser cancelados.")

        row = conn.execute(
            text(
                """
                UPDATE titulos_financeiros
                SET status = 'CANCELADO', atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, descricao, status
                """
            ),
            {"id": int(titulo_id)},
        ).mappings().first()
        log_audit_event(
            usuario_id=usuario_id,
            modulo="FINANCEIRO",
            entidade="titulos_financeiros",
            entidade_id=int(titulo_id),
            acao="CANCELAR_TITULO_MANUAL",
            detalhes={"descricao": titulo["descricao"]},
            conn=conn,
        )
        return dict(row)


def list_movimentacoes_financeiras(limit: int = 200) -> list[dict[str, Any]]:
    """Extrato imutável de entradas e saídas efetivadas no caixa."""
    return fetch_all(
        """
        SELECT
            mf.id,
            mf.data_movimentacao,
            mf.tipo_fluxo,
            mf.valor,
            mf.forma_pagamento,
            mf.descricao,
            tf.origem_modulo,
            c.nome AS categoria_nome,
            u.nome AS usuario_nome
        FROM movimentacoes_financeiras mf
        JOIN titulos_financeiros tf ON tf.id = mf.titulo_id
        JOIN categorias c ON c.id = tf.categoria_id
        JOIN usuarios u ON u.id = mf.usuario_id
        ORDER BY mf.data_movimentacao DESC, mf.id DESC
        LIMIT :limit
        """,
        {"limit": int(limit)},
    )


def get_resumo_financeiro() -> dict[str, Any]:
    """Consolida saldo de caixa, contas a pagar/receber em aberto e atrasos."""
    caixa = fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN tipo_fluxo = 'ENTRADA' THEN valor ELSE 0 END), 0)::NUMERIC(14,2) AS total_entradas,
            COALESCE(SUM(CASE WHEN tipo_fluxo = 'SAIDA' THEN valor ELSE 0 END), 0)::NUMERIC(14,2) AS total_saidas
        FROM movimentacoes_financeiras
        """
    ) or {"total_entradas": Decimal("0"), "total_saidas": Decimal("0")}

    titulos = fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'RECEBER' AND status = 'ABERTO' THEN valor_original ELSE 0 END), 0)::NUMERIC(14,2) AS a_receber_aberto,
            COALESCE(SUM(CASE WHEN tipo = 'PAGAR' AND status = 'ABERTO' THEN valor_original ELSE 0 END), 0)::NUMERIC(14,2) AS a_pagar_aberto,
            COALESCE(SUM(CASE WHEN tipo = 'PAGAR' AND status = 'ABERTO' AND data_vencimento < CURRENT_DATE THEN valor_original ELSE 0 END), 0)::NUMERIC(14,2) AS a_pagar_atrasado,
            COALESCE(SUM(CASE WHEN tipo = 'RECEBER' AND status = 'ABERTO' AND data_vencimento < CURRENT_DATE THEN valor_original ELSE 0 END), 0)::NUMERIC(14,2) AS a_receber_atrasado
        FROM titulos_financeiros
        """
    ) or {}

    entradas = Decimal(str(caixa["total_entradas"]))
    saidas = Decimal(str(caixa["total_saidas"]))
    return {
        "total_entradas": float(entradas),
        "total_saidas": float(saidas),
        "saldo_caixa": float(entradas - saidas),
        "a_receber_aberto": float(titulos.get("a_receber_aberto", 0)),
        "a_pagar_aberto": float(titulos.get("a_pagar_aberto", 0)),
        "a_pagar_atrasado": float(titulos.get("a_pagar_atrasado", 0)),
        "a_receber_atrasado": float(titulos.get("a_receber_atrasado", 0)),
    }
