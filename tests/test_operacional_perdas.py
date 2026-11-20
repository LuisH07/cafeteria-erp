"""Testes do módulo Operacional: fila do barista (SLA) e registro de perdas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.db.queries import fetch_all, fetch_one
from src.services.compras_service import criar_compra
from src.services.exceptions import BusinessRuleError
from src.services.operacional_service import avancar_ordem_preparo, registrar_perda
from src.services.vendas_service import registrar_venda


def test_transicoes_ordem_preparo_e_calculo_sla(clean_db):
    admin_id = clean_db["admin_id"]
    criar_compra(
        fornecedor_id=clean_db["fornecedor_id"],
        forma_pagamento="PIX",
        itens=[
            {"insumo_id": clean_db["cafe_id"], "quantidade": 500, "custo_unitario": 0.10},
            {"insumo_id": clean_db["leite_id"], "quantidade": 1000, "custo_unitario": 0.006},
        ],
        usuario_id=admin_id,
        receber_agora=True,
    )

    t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
    venda = registrar_venda(
        cliente_id=clean_db["cliente_id"],
        canal_venda="BALCAO",
        forma_pagamento="DEBITO",
        itens=[{"produto_id": clean_db["cappuccino_id"], "quantidade": 1}],
        usuario_id=admin_id,
        occurred_at=t0,
    )
    oid = int(venda["ordem_preparo_id"])

    # Transição inválida direta NA_FILA -> ENTREGUE deve ser bloqueada
    with pytest.raises(BusinessRuleError):
        avancar_ordem_preparo(ordem_id=oid, novo_status="ENTREGUE", usuario_id=admin_id)

    r1 = avancar_ordem_preparo(
        ordem_id=oid, novo_status="EM_PREPARO", usuario_id=admin_id, occurred_at=t0 + timedelta(seconds=60)
    )
    assert r1["tempo_espera_fila_seg"] == 60

    r2 = avancar_ordem_preparo(
        ordem_id=oid, novo_status="PRONTO", usuario_id=admin_id, occurred_at=t0 + timedelta(seconds=210)
    )
    assert r2["tempo_preparo_real_seg"] == 150

    r3 = avancar_ordem_preparo(
        ordem_id=oid, novo_status="ENTREGUE", usuario_id=admin_id, occurred_at=t0 + timedelta(seconds=240)
    )
    assert r3["status"] == "ENTREGUE"

    hist = fetch_all(
        "SELECT status_novo FROM ordem_preparo_historico WHERE ordem_preparo_id = :oid ORDER BY id ASC",
        {"oid": oid},
    )
    assert [h["status_novo"] for h in hist] == ["NA_FILA", "EM_PREPARO", "PRONTO", "ENTREGUE"]


def test_registro_perda_baixa_estoque_e_calcula_custo(clean_db):
    admin_id = clean_db["admin_id"]
    leite_id = clean_db["leite_id"]

    criar_compra(
        fornecedor_id=clean_db["fornecedor_id"],
        forma_pagamento="BOLETO",
        itens=[{"insumo_id": leite_id, "quantidade": 2000, "custo_unitario": 0.01}],
        usuario_id=admin_id,
        receber_agora=True,
    )

    perda = registrar_perda(
        insumo_id=leite_id,
        quantidade=500,
        motivo="VENCIMENTO",
        usuario_id=admin_id,
        observacoes="Embalagem vencida",
    )
    assert Decimal(str(perda["custo_estimado"])) == Decimal("5.00")

    saldo = fetch_one("SELECT estoque_atual FROM insumos WHERE id = :id", {"id": leite_id})
    assert Decimal(str(saldo["estoque_atual"])) == Decimal("1500.000")
