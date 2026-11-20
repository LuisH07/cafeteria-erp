"""Testes de Compras, Estoque (custo médio ponderado) e Financeiro (contas a pagar)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.auth.permissions import can_access_module, has_permission, require_permission
from src.db.queries import fetch_all, fetch_one
from src.services.compras_service import criar_compra, receber_compra
from src.services.estoque_service import registrar_ajuste_inventario
from src.services.exceptions import AuthorizationError, BusinessRuleError


def test_rbac_permissions_unit():
    """Teste unitário (sem BD) da matriz de permissões RBAC."""
    assert can_access_module("ADMIN", "usuarios_admin")
    assert can_access_module("GERENTE", "dashboard_bi")
    assert not can_access_module("BARISTA", "financeiro")
    assert has_permission("CAIXA", "vendas:create")
    assert not has_permission("CAIXA", "vendas:cancel")
    with pytest.raises(AuthorizationError):
        require_permission("BARISTA", "financeiro:write")


def test_receber_compra_atualiza_estoque_custo_medio_e_financeiro(clean_db):
    admin_id = clean_db["admin_id"]
    forn_id = clean_db["fornecedor_id"]
    cafe_id = clean_db["cafe_id"]

    # 1ª compra: 1000g a R$ 0.10/g
    c1 = criar_compra(
        fornecedor_id=forn_id,
        forma_pagamento="BOLETO",
        itens=[{"insumo_id": cafe_id, "quantidade": 1000, "custo_unitario": 0.10}],
        usuario_id=admin_id,
        receber_agora=False,
    )
    assert c1["status"] == "CONFIRMADA"

    rec1 = receber_compra(compra_id=int(c1["id"]), usuario_id=admin_id)
    assert rec1["status"] == "RECEBIDA"

    ins1 = fetch_one("SELECT estoque_atual, custo_medio_atual FROM insumos WHERE id = :id", {"id": cafe_id})
    assert Decimal(str(ins1["estoque_atual"])) == Decimal("1000.000")
    assert Decimal(str(ins1["custo_medio_atual"])) == Decimal("0.1000")

    # 2ª compra: 1000g a R$ 0.14/g -> custo médio ponderado deve virar R$ 0.12/g
    criar_compra(
        fornecedor_id=forn_id,
        forma_pagamento="BOLETO",
        itens=[{"insumo_id": cafe_id, "quantidade": 1000, "custo_unitario": 0.14}],
        usuario_id=admin_id,
        receber_agora=True,
    )
    ins2 = fetch_one("SELECT estoque_atual, custo_medio_atual FROM insumos WHERE id = :id", {"id": cafe_id})
    assert Decimal(str(ins2["estoque_atual"])) == Decimal("2000.000")
    assert Decimal(str(ins2["custo_medio_atual"])) == Decimal("0.1200")

    # Deve ter gerado 2 contas a pagar em titulos_financeiros
    titulos = fetch_all("SELECT * FROM titulos_financeiros WHERE origem_modulo = 'COMPRAS'")
    assert len(titulos) == 2
    assert all(t["tipo"] == "PAGAR" and t["status"] == "ABERTO" for t in titulos)

    # Receber compra já recebida deve falhar
    with pytest.raises(BusinessRuleError):
        receber_compra(compra_id=int(c1["id"]), usuario_id=admin_id)


def test_ajuste_inventario_registra_movimentacao_auditada(clean_db):
    admin_id = clean_db["admin_id"]
    cafe_id = clean_db["cafe_id"]

    criar_compra(
        fornecedor_id=clean_db["fornecedor_id"],
        forma_pagamento="PIX",
        itens=[{"insumo_id": cafe_id, "quantidade": 500, "custo_unitario": 0.10}],
        usuario_id=admin_id,
        receber_agora=True,
    )
    res = registrar_ajuste_inventario(
        insumo_id=cafe_id,
        novo_saldo_fisico=480,
        motivo="Contagem física semanal",
        usuario_id=admin_id,
    )
    assert res["tipo_movimentacao"] == "AJUSTE_SAIDA"
    assert Decimal(str(res["quantidade"])) == Decimal("20.000")
    assert Decimal(str(res["saldo_posterior"])) == Decimal("480.000")
