"""Testes de integração de Vendas (PDV) com Estoque, Ficha Técnica, Operacional e Financeiro."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.db.queries import fetch_all, fetch_one
from src.services.compras_service import criar_compra
from src.services.exceptions import InsufficientStockError
from src.services.operacional_service import avancar_ordem_preparo
from src.services.vendas_service import cancelar_venda, registrar_venda


def test_venda_bloqueada_sem_estoque_suficiente(clean_db):
    with pytest.raises(InsufficientStockError) as exc_info:
        registrar_venda(
            cliente_id=clean_db["cliente_id"],
            canal_venda="BALCAO",
            forma_pagamento="PIX",
            itens=[{"produto_id": clean_db["cappuccino_id"], "quantidade": 1}],
            usuario_id=clean_db["admin_id"],
        )
    assert len(exc_info.value.missing_items) == 2
    # Garante atomicidade (zero registros parciais)
    assert len(fetch_all("SELECT id FROM vendas")) == 0
    assert len(fetch_all("SELECT id FROM ordens_preparo")) == 0
    assert len(fetch_all("SELECT id FROM titulos_financeiros")) == 0


def test_fluxo_venda_completo_e_estorno_antes_preparo(clean_db):
    admin_id = clean_db["admin_id"]
    cafe_id = clean_db["cafe_id"]
    leite_id = clean_db["leite_id"]

    # Abastece insumos via Compras
    criar_compra(
        fornecedor_id=clean_db["fornecedor_id"],
        forma_pagamento="BOLETO",
        itens=[
            {"insumo_id": cafe_id, "quantidade": 1000, "custo_unitario": 0.10},
            {"insumo_id": leite_id, "quantidade": 3000, "custo_unitario": 0.006},
        ],
        usuario_id=admin_id,
        receber_agora=True,
    )

    # Vende 2 cappuccinos (consome 40g café + 300ml leite; CMV = 2*(2.00+0.90) = 5.80)
    venda = registrar_venda(
        cliente_id=clean_db["cliente_id"],
        canal_venda="BALCAO",
        forma_pagamento="PIX",
        itens=[{"produto_id": clean_db["cappuccino_id"], "quantidade": 2}],
        usuario_id=admin_id,
    )
    assert Decimal(str(venda["valor_total"])) == Decimal("30.00")
    assert Decimal(str(venda["custo_total_cmv"])) == Decimal("5.80")

    cafe_saldo = fetch_one("SELECT estoque_atual FROM insumos WHERE id = :id", {"id": cafe_id})
    leite_saldo = fetch_one("SELECT estoque_atual FROM insumos WHERE id = :id", {"id": leite_id})
    assert Decimal(str(cafe_saldo["estoque_atual"])) == Decimal("960.000")
    assert Decimal(str(leite_saldo["estoque_atual"])) == Decimal("2700.000")

    # Ordem de preparo criada NA_FILA e entrada efetivada no caixa (PIX)
    ordem = fetch_one("SELECT status FROM ordens_preparo WHERE venda_id = :vid", {"vid": venda["id"]})
    assert ordem["status"] == "NA_FILA"
    movs_fin = fetch_all("SELECT tipo_fluxo, valor FROM movimentacoes_financeiras")
    assert len(movs_fin) == 1
    assert movs_fin[0]["tipo_fluxo"] == "ENTRADA"
    assert Decimal(str(movs_fin[0]["valor"])) == Decimal("30.00")

    # Cancelamento ainda NA_FILA deve estornar estoque e lançar saída de estorno no caixa
    canc = cancelar_venda(venda_id=int(venda["id"]), motivo="Desistência imediata", usuario_id=admin_id)
    assert canc["estoque_estornado"] is True

    cafe_pos = fetch_one("SELECT estoque_atual FROM insumos WHERE id = :id", {"id": cafe_id})
    assert Decimal(str(cafe_pos["estoque_atual"])) == Decimal("1000.000")

    movs_fin_pos = fetch_all("SELECT tipo_fluxo, valor FROM movimentacoes_financeiras ORDER BY id ASC")
    assert len(movs_fin_pos) == 2
    assert movs_fin_pos[1]["tipo_fluxo"] == "SAIDA"
    assert Decimal(str(movs_fin_pos[1]["valor"])) == Decimal("30.00")


def test_cancelamento_apos_inicio_preparo_registra_perda_sem_devolver_estoque(clean_db):
    admin_id = clean_db["admin_id"]
    criar_compra(
        fornecedor_id=clean_db["fornecedor_id"],
        forma_pagamento="BOLETO",
        itens=[
            {"insumo_id": clean_db["cafe_id"], "quantidade": 500, "custo_unitario": 0.10},
            {"insumo_id": clean_db["leite_id"], "quantidade": 1000, "custo_unitario": 0.006},
        ],
        usuario_id=admin_id,
        receber_agora=True,
    )
    venda = registrar_venda(
        cliente_id=clean_db["cliente_id"],
        canal_venda="MESA",
        forma_pagamento="CREDITO",
        itens=[{"produto_id": clean_db["cappuccino_id"], "quantidade": 1}],
        usuario_id=admin_id,
    )
    avancar_ordem_preparo(
        ordem_id=int(venda["ordem_preparo_id"]),
        novo_status="EM_PREPARO",
        usuario_id=admin_id,
    )

    canc = cancelar_venda(venda_id=int(venda["id"]), motivo="Cliente trocou pedido", usuario_id=admin_id)
    assert canc["estoque_estornado"] is False

    # Estoque não retorna (480g) e perdas são registradas
    cafe_pos = fetch_one("SELECT estoque_atual FROM insumos WHERE id = :id", {"id": clean_db["cafe_id"]})
    assert Decimal(str(cafe_pos["estoque_atual"])) == Decimal("480.000")
    perdas = fetch_all("SELECT * FROM registros_perdas")
    assert len(perdas) == 2
