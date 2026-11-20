"""Serviço Operacional: Fila de Preparo do Barista (SLA) e Registro de Perdas."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import (
    BusinessRuleError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "NA_FILA": {"EM_PREPARO"},
    "EM_PREPARO": {"PRONTO"},
    "PRONTO": {"ENTREGUE"},
}


def list_ordens_preparo(
    *,
    status: str | None = None,
    apenas_abertas: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Lista ordens de preparo com resumo dos produtos da venda e tempo estimado."""
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": int(limit)}
    if apenas_abertas:
        clauses.append("op.status IN ('NA_FILA', 'EM_PREPARO', 'PRONTO')")
    elif status and status != "Todos":
        clauses.append("op.status = :status")
        params["status"] = status

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT
            op.id,
            op.venda_id,
            v.numero_venda,
            c.nome AS cliente_nome,
            v.canal_venda,
            op.status,
            op.prioridade,
            op.barista_id,
            COALESCE(b.nome, 'Aguardando Barista') AS barista_nome,
            op.criado_em,
            op.iniciado_em,
            op.finalizado_em,
            op.entregue_em,
            op.tempo_espera_fila_seg,
            op.tempo_preparo_real_seg,
            op.observacoes,
            STRING_AGG(vi.quantidade || 'x ' || p.nome, ', ' ORDER BY p.nome) AS itens_resumo,
            (
                GREATEST(MAX(p.tempo_preparo_estimado_seg), 60)
                + GREATEST(SUM(vi.quantidade) - 1, 0) * 45
            )::INT AS tempo_estimado_seg
        FROM ordens_preparo op
        JOIN vendas v ON v.id = op.venda_id
        JOIN clientes c ON c.id = v.cliente_id
        JOIN venda_itens vi ON vi.venda_id = v.id
        JOIN produtos p ON p.id = vi.produto_id
        LEFT JOIN usuarios b ON b.id = op.barista_id
        {where}
        GROUP BY op.id, v.numero_venda, c.nome, v.canal_venda, b.nome
        ORDER BY
            CASE op.prioridade WHEN 'ALTA' THEN 1 ELSE 2 END,
            CASE op.status
                WHEN 'EM_PREPARO' THEN 1
                WHEN 'NA_FILA' THEN 2
                WHEN 'PRONTO' THEN 3
                ELSE 4
            END,
            op.criado_em ASC
        LIMIT :limit
        """,
        params,
    )


def avancar_ordem_preparo(
    *,
    ordem_id: int,
    novo_status: str,
    usuario_id: int,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Avança status de preparo, calcula tempos reais de fila/preparo e grava histórico."""
    ts = occurred_at or datetime.now(timezone.utc)

    with get_transaction() as conn:
        ordem = fetch_one(
            "SELECT * FROM ordens_preparo WHERE id = :id FOR UPDATE",
            {"id": int(ordem_id)},
            conn=conn,
        )
        if not ordem:
            raise NotFoundError("Ordem de preparo não encontrada.")

        status_atual = str(ordem["status"])
        permitidos = VALID_TRANSITIONS.get(status_atual, set())
        if novo_status not in permitidos:
            raise BusinessRuleError(
                f"Transição inválida: '{status_atual}' → '{novo_status}'."
            )

        criado_em: datetime = ordem["criado_em"]
        iniciado_em: datetime | None = ordem["iniciado_em"]
        finalizado_em: datetime | None = ordem["finalizado_em"]
        entregue_em: datetime | None = ordem["entregue_em"]
        tempo_fila = ordem["tempo_espera_fila_seg"]
        tempo_preparo = ordem["tempo_preparo_real_seg"]
        barista_id = ordem["barista_id"]

        if novo_status == "EM_PREPARO":
            iniciado_em = ts
            barista_id = int(usuario_id)
            tempo_fila = max(0, int((ts - criado_em).total_seconds()))
        elif novo_status == "PRONTO":
            finalizado_em = ts
            base_inicio = iniciado_em or criado_em
            tempo_preparo = max(1, int((ts - base_inicio).total_seconds()))
            if barista_id is None:
                barista_id = int(usuario_id)
        elif novo_status == "ENTREGUE":
            entregue_em = ts

        updated = conn.execute(
            text(
                """
                UPDATE ordens_preparo
                SET status = :novo_status,
                    barista_id = :barista_id,
                    iniciado_em = :iniciado_em,
                    finalizado_em = :finalizado_em,
                    entregue_em = :entregue_em,
                    tempo_espera_fila_seg = :tempo_fila,
                    tempo_preparo_real_seg = :tempo_preparo
                WHERE id = :id
                RETURNING id, venda_id, status, barista_id,
                          tempo_espera_fila_seg, tempo_preparo_real_seg,
                          iniciado_em, finalizado_em, entregue_em
                """
            ),
            {
                "id": int(ordem_id),
                "novo_status": novo_status,
                "barista_id": barista_id,
                "iniciado_em": iniciado_em,
                "finalizado_em": finalizado_em,
                "entregue_em": entregue_em,
                "tempo_fila": tempo_fila,
                "tempo_preparo": tempo_preparo,
            },
        ).mappings().first()

        conn.execute(
            text(
                """
                INSERT INTO ordem_preparo_historico (
                    ordem_preparo_id, status_anterior, status_novo, usuario_id, criado_em
                )
                VALUES (:oid, :ant, :novo, :uid, :ts)
                """
            ),
            {
                "oid": int(ordem_id),
                "ant": status_atual,
                "novo": novo_status,
                "uid": int(usuario_id),
                "ts": ts,
            },
        )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="OPERACIONAL",
            entidade="ordens_preparo",
            entidade_id=int(ordem_id),
            acao=f"TRANSICAO_{novo_status}",
            detalhes={
                "status_anterior": status_atual,
                "status_novo": novo_status,
                "tempo_espera_fila_seg": tempo_fila,
                "tempo_preparo_real_seg": tempo_preparo,
            },
            conn=conn,
        )
        return dict(updated)


def registrar_perda(
    *,
    insumo_id: int,
    quantidade: Decimal | float,
    motivo: str,
    usuario_id: int,
    observacoes: str = "",
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Registra perda/descarte de insumo, baixa estoque automaticamente e apura custo."""
    qtd = Decimal(str(quantidade)).quantize(Decimal("0.001"))
    if qtd <= 0:
        raise ValidationError("A quantidade perdida deve ser maior que zero.")
    if motivo not in {"VENCIMENTO", "QUEBRA_PREPARO", "DESPERDICIO_BARISTA", "CONTAMINACAO", "OUTRO"}:
        raise ValidationError("Motivo de perda inválido.")

    ts = occurred_at or datetime.now(timezone.utc)

    with get_transaction() as conn:
        insumo = fetch_one(
            """
            SELECT id, sku, nome, unidade_medida, estoque_atual, custo_medio_atual, ativo
            FROM insumos
            WHERE id = :id
            FOR UPDATE
            """,
            {"id": int(insumo_id)},
            conn=conn,
        )
        if not insumo or not insumo["ativo"]:
            raise NotFoundError("Insumo não encontrado ou inativo.")

        saldo_ant = Decimal(str(insumo["estoque_atual"])).quantize(Decimal("0.001"))
        if saldo_ant < qtd:
            raise InsufficientStockError(
                f"Saldo insuficiente de '{insumo['nome']}' para registrar perda "
                f"(disponível: {saldo_ant} {insumo['unidade_medida']})."
            )

        saldo_pos = (saldo_ant - qtd).quantize(Decimal("0.001"))
        custo_unit = Decimal(str(insumo["custo_medio_atual"])).quantize(Decimal("0.0001"))
        custo_est = (qtd * custo_unit).quantize(Decimal("0.01"))

        perda_row = conn.execute(
            text(
                """
                INSERT INTO registros_perdas (
                    insumo_id, quantidade, motivo, custo_estimado, observacoes, usuario_id, criado_em
                )
                VALUES (
                    :insumo_id, :quantidade, :motivo, :custo_estimado, :observacoes, :usuario_id, :ts
                )
                RETURNING id, insumo_id, quantidade, motivo, custo_estimado, criado_em
                """
            ),
            {
                "insumo_id": int(insumo_id),
                "quantidade": qtd,
                "motivo": motivo,
                "custo_estimado": custo_est,
                "observacoes": observacoes.strip() or None,
                "usuario_id": int(usuario_id),
                "ts": ts,
            },
        ).mappings().first()
        perda = dict(perda_row)

        conn.execute(
            text("UPDATE insumos SET estoque_atual = :pos, atualizado_em = :ts WHERE id = :id"),
            {"id": int(insumo_id), "pos": saldo_pos, "ts": ts},
        )
        conn.execute(
            text(
                """
                INSERT INTO movimentacoes_estoque (
                    insumo_id, tipo_movimentacao, quantidade, saldo_anterior, saldo_posterior,
                    custo_unitario_snapshot, origem_modulo, origem_id, motivo, usuario_id, criado_em
                )
                VALUES (
                    :iid, 'SAIDA_PERDA', :qtd, :ant, :pos,
                    :custo_unit, 'OPERACIONAL', :pid, :motivo_txt, :uid, :ts
                )
                """
            ),
            {
                "iid": int(insumo_id),
                "qtd": qtd,
                "ant": saldo_ant,
                "pos": saldo_pos,
                "custo_unit": custo_unit,
                "pid": int(perda["id"]),
                "motivo_txt": f"Perda operacional ({motivo}): {observacoes.strip() or '-'}",
                "uid": int(usuario_id),
                "ts": ts,
            },
        )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="OPERACIONAL",
            entidade="registros_perdas",
            entidade_id=int(perda["id"]),
            acao="REGISTRAR_PERDA",
            detalhes={
                "insumo_id": insumo_id,
                "quantidade": str(qtd),
                "motivo": motivo,
                "custo_estimado": str(custo_est),
            },
            conn=conn,
        )
        return perda


def list_registros_perdas(limit: int = 100) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT
            rp.id,
            rp.criado_em,
            i.sku AS insumo_sku,
            i.nome AS insumo_nome,
            i.unidade_medida,
            rp.quantidade,
            rp.motivo,
            rp.custo_estimado,
            rp.observacoes,
            u.nome AS usuario_nome
        FROM registros_perdas rp
        JOIN insumos i ON i.id = rp.insumo_id
        JOIN usuarios u ON u.id = rp.usuario_id
        ORDER BY rp.criado_em DESC, rp.id DESC
        LIMIT :limit
        """,
        {"limit": int(limit)},
    )
