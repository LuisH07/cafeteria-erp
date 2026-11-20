"""Serviço de Compras integrado a Estoque (custo médio ponderado) e Financeiro (contas a pagar)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import BusinessRuleError, NotFoundError, ValidationError


def _get_or_create_categoria_compras(conn: Connection) -> int:
    row = fetch_one(
        """
        SELECT id FROM categorias
        WHERE tipo = 'DESPESA' AND LOWER(nome) LIKE 'compra%insumo%'
        ORDER BY id ASC
        LIMIT 1
        """,
        conn=conn,
    )
    if row:
        return int(row["id"])

    row = fetch_one(
        "SELECT id FROM categorias WHERE tipo = 'DESPESA' ORDER BY id ASC LIMIT 1",
        conn=conn,
    )
    if row:
        return int(row["id"])

    inserted = conn.execute(
        text(
            """
            INSERT INTO categorias (nome, tipo)
            VALUES ('Compra de Insumos', 'DESPESA')
            RETURNING id
            """
        )
    ).scalar()
    return int(inserted)


def list_compras(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": int(limit)}
    if status and status != "Todos":
        clauses.append("c.status = :status")
        params["status"] = status
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT
            c.id,
            c.numero_pedido,
            c.fornecedor_id,
            f.nome_fantasia AS fornecedor_nome,
            c.status,
            c.data_pedido,
            c.data_recebimento,
            c.valor_total,
            c.forma_pagamento,
            c.observacoes,
            u.nome AS usuario_nome,
            COUNT(ci.id)::INT AS qtd_itens
        FROM compras c
        JOIN fornecedores f ON f.id = c.fornecedor_id
        JOIN usuarios u ON u.id = c.usuario_id
        LEFT JOIN compra_itens ci ON ci.compra_id = c.id
        {where}
        GROUP BY c.id, f.nome_fantasia, u.nome
        ORDER BY c.data_pedido DESC, c.id DESC
        LIMIT :limit
        """,
        params,
    )


def get_compra_detalhes(compra_id: int) -> dict[str, Any]:
    compra = fetch_one(
        """
        SELECT
            c.*, f.nome_fantasia AS fornecedor_nome, f.cnpj AS fornecedor_cnpj,
            f.prazo_pagamento_dias, u.nome AS usuario_nome
        FROM compras c
        JOIN fornecedores f ON f.id = c.fornecedor_id
        JOIN usuarios u ON u.id = c.usuario_id
        WHERE c.id = :id
        """,
        {"id": int(compra_id)},
    )
    if not compra:
        raise NotFoundError("Pedido de compra não encontrado.")

    itens = fetch_all(
        """
        SELECT
            ci.id, ci.insumo_id, i.sku AS insumo_sku, i.nome AS insumo_nome,
            i.unidade_medida, ci.quantidade, ci.custo_unitario, ci.subtotal,
            ci.lote, ci.data_validade
        FROM compra_itens ci
        JOIN insumos i ON i.id = ci.insumo_id
        WHERE ci.compra_id = :compra_id
        ORDER BY ci.id ASC
        """,
        {"compra_id": int(compra_id)},
    )
    compra["itens"] = itens
    return compra


def criar_compra(
    *,
    fornecedor_id: int,
    forma_pagamento: str,
    itens: list[dict[str, Any]],
    usuario_id: int,
    observacoes: str = "",
    receber_agora: bool = False,
    liquidar_se_avista: bool = False,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Cria pedido de compra com itens e opcionalmente realiza o recebimento imediato."""
    if not itens:
        raise ValidationError("Adicione ao menos um insumo ao pedido de compra.")
    if forma_pagamento not in {"BOLETO", "PIX", "TRANSFERENCIA", "CARTAO_CORP", "DINHEIRO"}:
        raise ValidationError("Forma de pagamento inválida para compras.")

    ts = occurred_at or datetime.now(timezone.utc)
    numero_pedido = f"CMP-{ts.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    prepared_items: list[dict[str, Any]] = []
    valor_total = Decimal("0.00")
    for item in itens:
        qtd = Decimal(str(item["quantidade"])).quantize(Decimal("0.001"))
        custo_unit = Decimal(str(item["custo_unitario"])).quantize(Decimal("0.0001"))
        if qtd <= 0:
            raise ValidationError("Quantidade do item de compra deve ser maior que zero.")
        if custo_unit < 0:
            raise ValidationError("Custo unitário do item de compra não pode ser negativo.")
        subtotal = (qtd * custo_unit).quantize(Decimal("0.01"))
        valor_total += subtotal
        prepared_items.append(
            {
                "insumo_id": int(item["insumo_id"]),
                "quantidade": qtd,
                "custo_unitario": custo_unit,
                "subtotal": subtotal,
                "lote": (item.get("lote") or "").strip() or None,
                "data_validade": item.get("data_validade") or None,
            }
        )

    if valor_total <= 0:
        raise ValidationError("Valor total do pedido de compra deve ser maior que zero.")

    with get_transaction() as conn:
        fornecedor = fetch_one(
            "SELECT id, ativo FROM fornecedores WHERE id = :id",
            {"id": int(fornecedor_id)},
            conn=conn,
        )
        if not fornecedor or not fornecedor["ativo"]:
            raise BusinessRuleError("Fornecedor inválido ou inativo.")

        compra_row = conn.execute(
            text(
                """
                INSERT INTO compras (
                    numero_pedido, fornecedor_id, usuario_id, status, data_pedido,
                    valor_total, forma_pagamento, observacoes, criado_em, atualizado_em
                )
                VALUES (
                    :numero_pedido, :fornecedor_id, :usuario_id, 'CONFIRMADA', :ts,
                    :valor_total, :forma_pagamento, :observacoes, :ts, :ts
                )
                RETURNING id, numero_pedido, fornecedor_id, status, valor_total, data_pedido
                """
            ),
            {
                "numero_pedido": numero_pedido,
                "fornecedor_id": int(fornecedor_id),
                "usuario_id": int(usuario_id),
                "ts": ts,
                "valor_total": valor_total,
                "forma_pagamento": forma_pagamento,
                "observacoes": observacoes.strip() or None,
            },
        ).mappings().first()
        compra = dict(compra_row)

        for item in prepared_items:
            conn.execute(
                text(
                    """
                    INSERT INTO compra_itens (
                        compra_id, insumo_id, quantidade, custo_unitario, subtotal,
                        lote, data_validade, criado_em
                    )
                    VALUES (
                        :compra_id, :insumo_id, :quantidade, :custo_unitario, :subtotal,
                        :lote, :data_validade, :ts
                    )
                    """
                ),
                {
                    "compra_id": compra["id"],
                    "insumo_id": item["insumo_id"],
                    "quantidade": item["quantidade"],
                    "custo_unitario": item["custo_unitario"],
                    "subtotal": item["subtotal"],
                    "lote": item["lote"],
                    "data_validade": item["data_validade"],
                    "ts": ts,
                },
            )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="COMPRAS",
            entidade="compras",
            entidade_id=compra["id"],
            acao="CRIAR_PEDIDO",
            detalhes={"numero_pedido": numero_pedido, "valor_total": str(valor_total)},
            conn=conn,
        )

        if receber_agora:
            compra = _receber_compra_tx(
                conn=conn,
                compra_id=int(compra["id"]),
                usuario_id=usuario_id,
                liquidar_se_avista=liquidar_se_avista,
                occurred_at=ts,
            )
        return compra


def _receber_compra_tx(
    *,
    conn: Connection,
    compra_id: int,
    usuario_id: int,
    liquidar_se_avista: bool = False,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Lógica transacional ACID de recebimento: Estoque + Custo Médio Ponderado + Conta a Pagar."""
    ts = occurred_at or datetime.now(timezone.utc)

    compra = fetch_one(
        """
        SELECT c.*, f.nome_fantasia AS fornecedor_nome, f.prazo_pagamento_dias
        FROM compras c
        JOIN fornecedores f ON f.id = c.fornecedor_id
        WHERE c.id = :id
        FOR UPDATE OF c
        """,
        {"id": int(compra_id)},
        conn=conn,
    )
    if not compra:
        raise NotFoundError("Pedido de compra não encontrado.")
    if compra["status"] not in {"RASCUNHO", "CONFIRMADA"}:
        raise BusinessRuleError(
            f"Compra '{compra['numero_pedido']}' não pode ser recebida (status atual: {compra['status']})."
        )

    itens = fetch_all(
        """
        SELECT id, insumo_id, quantidade, custo_unitario, subtotal
        FROM compra_itens
        WHERE compra_id = :compra_id
        ORDER BY insumo_id ASC
        """,
        {"compra_id": int(compra_id)},
        conn=conn,
    )
    if not itens:
        raise BusinessRuleError("Pedido de compra não possui itens para recebimento.")

    # Lock pessimista ordenado por insumo_id para evitar deadlock
    insumo_ids = sorted({int(it["insumo_id"]) for it in itens})
    insumos_map: dict[int, dict[str, Any]] = {}
    for iid in insumo_ids:
        row = fetch_one(
            """
            SELECT id, estoque_atual, custo_medio_atual
            FROM insumos
            WHERE id = :id
            FOR UPDATE
            """,
            {"id": iid},
            conn=conn,
        )
        if not row:
            raise NotFoundError(f"Insumo ID {iid} não encontrado.")
        insumos_map[iid] = row

    # Atualiza estoque e custo médio ponderado de cada item
    for item in itens:
        iid = int(item["insumo_id"])
        insumo_state = insumos_map[iid]
        saldo_anterior = Decimal(str(insumo_state["estoque_atual"])).quantize(Decimal("0.001"))
        custo_anterior = Decimal(str(insumo_state["custo_medio_atual"])).quantize(Decimal("0.0001"))
        qtd_entrada = Decimal(str(item["quantidade"])).quantize(Decimal("0.001"))
        custo_entrada = Decimal(str(item["custo_unitario"])).quantize(Decimal("0.0001"))

        novo_saldo = (saldo_anterior + qtd_entrada).quantize(Decimal("0.001"))
        if novo_saldo > 0:
            novo_custo_medio = (
                ((saldo_anterior * custo_anterior) + (qtd_entrada * custo_entrada)) / novo_saldo
            ).quantize(Decimal("0.0001"))
        else:
            novo_custo_medio = custo_entrada

        insumo_state["estoque_atual"] = novo_saldo
        insumo_state["custo_medio_atual"] = novo_custo_medio

        conn.execute(
            text(
                """
                UPDATE insumos
                SET estoque_atual = :novo_saldo,
                    custo_medio_atual = :novo_custo_medio,
                    atualizado_em = :ts
                WHERE id = :id
                """
            ),
            {
                "id": iid,
                "novo_saldo": novo_saldo,
                "novo_custo_medio": novo_custo_medio,
                "ts": ts,
            },
        )

        conn.execute(
            text(
                """
                INSERT INTO movimentacoes_estoque (
                    insumo_id, tipo_movimentacao, quantidade, saldo_anterior, saldo_posterior,
                    custo_unitario_snapshot, origem_modulo, origem_id, motivo, usuario_id, criado_em
                )
                VALUES (
                    :insumo_id, 'ENTRADA_COMPRA', :quantidade, :saldo_anterior, :saldo_posterior,
                    :custo_unit, 'COMPRAS', :origem_id, :motivo, :usuario_id, :ts
                )
                """
            ),
            {
                "insumo_id": iid,
                "quantidade": qtd_entrada,
                "saldo_anterior": saldo_anterior,
                "saldo_posterior": novo_saldo,
                "custo_unit": custo_entrada,
                "origem_id": int(compra_id),
                "motivo": f"Recebimento compra {compra['numero_pedido']}",
                "usuario_id": int(usuario_id),
                "ts": ts,
            },
        )

    # Atualiza status da compra
    updated_compra = conn.execute(
        text(
            """
            UPDATE compras
            SET status = 'RECEBIDA',
                data_recebimento = :ts,
                atualizado_em = :ts
            WHERE id = :id
            RETURNING id, numero_pedido, fornecedor_id, status, valor_total, data_pedido, data_recebimento
            """
        ),
        {"id": int(compra_id), "ts": ts},
    ).mappings().first()

    # Gera Conta a Pagar no Financeiro
    categoria_despesa_id = _get_or_create_categoria_compras(conn)
    prazo_dias = int(compra.get("prazo_pagamento_dias") or 0)
    data_comp = ts.date()
    data_venc = data_comp + timedelta(days=prazo_dias)
    valor_total = Decimal(str(compra["valor_total"])).quantize(Decimal("0.01"))
    auto_pagar = bool(
        liquidar_se_avista
        and prazo_dias == 0
        and compra["forma_pagamento"] in {"PIX", "DINHEIRO"}
    )

    titulo_row = conn.execute(
        text(
            """
            INSERT INTO titulos_financeiros (
                tipo, categoria_id, descricao, origem_modulo, origem_id,
                fornecedor_id, valor_original, valor_pago, data_competencia, data_vencimento,
                data_liquidacao, status, forma_pagamento, usuario_id, criado_em, atualizado_em
            )
            VALUES (
                'PAGAR', :categoria_id, :descricao, 'COMPRAS', :origem_id,
                :fornecedor_id, :valor_original, :valor_pago, :data_comp, :data_venc,
                :data_liq, :status, :forma_pagamento, :usuario_id, :ts, :ts
            )
            RETURNING id
            """
        ),
        {
            "categoria_id": categoria_despesa_id,
            "descricao": f"Compra {compra['numero_pedido']} — {compra['fornecedor_nome']}",
            "origem_id": int(compra_id),
            "fornecedor_id": int(compra["fornecedor_id"]),
            "valor_original": valor_total,
            "valor_pago": valor_total if auto_pagar else Decimal("0.00"),
            "data_comp": data_comp,
            "data_venc": data_venc,
            "data_liq": ts if auto_pagar else None,
            "status": "PAGO" if auto_pagar else "ABERTO",
            "forma_pagamento": compra["forma_pagamento"],
            "usuario_id": int(usuario_id),
            "ts": ts,
        },
    ).mappings().first()

    if auto_pagar:
        conn.execute(
            text(
                """
                INSERT INTO movimentacoes_financeiras (
                    titulo_id, tipo_fluxo, valor, forma_pagamento, data_movimentacao,
                    descricao, usuario_id, criado_em
                )
                VALUES (
                    :titulo_id, 'SAIDA', :valor, :forma_pagamento, :ts,
                    :descricao, :usuario_id, :ts
                )
                """
            ),
            {
                "titulo_id": int(titulo_row["id"]),
                "valor": valor_total,
                "forma_pagamento": compra["forma_pagamento"],
                "ts": ts,
                "descricao": f"Pagamento à vista compra {compra['numero_pedido']}",
                "usuario_id": int(usuario_id),
            },
        )

    log_audit_event(
        usuario_id=usuario_id,
        modulo="COMPRAS",
        entidade="compras",
        entidade_id=int(compra_id),
        acao="RECEBER_COMPRA",
        detalhes={
            "numero_pedido": compra["numero_pedido"],
            "valor_total": str(valor_total),
            "titulo_pagar_id": int(titulo_row["id"]),
            "pago_no_ato": auto_pagar,
        },
        conn=conn,
    )
    return dict(updated_compra)


def receber_compra(
    *,
    compra_id: int,
    usuario_id: int,
    liquidar_se_avista: bool = False,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Recebe pedido de compra confirmado, gerando entrada no estoque e conta a pagar."""
    with get_transaction() as conn:
        return _receber_compra_tx(
            conn=conn,
            compra_id=compra_id,
            usuario_id=usuario_id,
            liquidar_se_avista=liquidar_se_avista,
            occurred_at=occurred_at,
        )


def cancelar_compra(*, compra_id: int, motivo: str, usuario_id: int) -> dict[str, Any]:
    """Cancela pedido de compra ainda não recebido (preservando registro histórico)."""
    if not motivo.strip():
        raise ValidationError("Informe o motivo do cancelamento da compra.")

    with get_transaction() as conn:
        compra = fetch_one(
            "SELECT id, numero_pedido, status FROM compras WHERE id = :id FOR UPDATE",
            {"id": int(compra_id)},
            conn=conn,
        )
        if not compra:
            raise NotFoundError("Pedido de compra não encontrado.")
        if compra["status"] not in {"RASCUNHO", "CONFIRMADA"}:
            raise BusinessRuleError(
                "Apenas compras em RASCUNHO ou CONFIRMADA podem ser canceladas."
            )

        row = conn.execute(
            text(
                """
                UPDATE compras
                SET status = 'CANCELADA',
                    observacoes = COALESCE(observacoes || ' | ', '') || 'Cancelado: ' || :motivo,
                    atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, numero_pedido, status
                """
            ),
            {"id": int(compra_id), "motivo": motivo.strip()},
        ).mappings().first()

        log_audit_event(
            usuario_id=usuario_id,
            modulo="COMPRAS",
            entidade="compras",
            entidade_id=int(compra_id),
            acao="CANCELAR_COMPRA",
            detalhes={"numero_pedido": compra["numero_pedido"], "motivo": motivo.strip()},
            conn=conn,
        )
        return dict(row)
