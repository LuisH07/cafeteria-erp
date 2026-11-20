"""Testes de coerência matemática entre transações da 1ª VA e KPIs do Dashboard BI (2ª VA)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.services.bi_service import (
    get_curva_abc_produtos,
    get_dre_e_fluxo_mensal,
    get_kpis_executivos,
    get_operacional_sla,
)
from src.services.compras_service import criar_compra
from src.services.financeiro_service import criar_titulo_manual
from src.services.operacional_service import avancar_ordem_preparo, registrar_perda
from src.services.vendas_service import registrar_venda
from src.ui.components.layout import fmt_brl, fmt_qty, fmt_seconds
from src.ui.components.receipt import build_receipt_text


def test_formatadores_e_comprovante_unit():
    """Teste unitário (sem BD) dos formatadores brasileiros e geração de comprovante."""
    assert fmt_brl(1234.5) == "R$ 1.234,50"
    assert fmt_brl(-50) == "-R$ 50,00"
    assert fmt_qty(1500, "g") == "1.500 g"
    assert fmt_seconds(185) == "3m 05s"

    txt = build_receipt_text(
        {
            "id": 1,
            "numero_venda": "VND-TEST-01",
            "data_venda": datetime(2026, 11, 19, 14, 30, tzinfo=timezone.utc),
            "cliente_nome": "Consumidor Balcão",
            "canal_venda": "BALCAO",
            "forma_pagamento": "PIX",
            "operador_nome": "Caixa",
            "status": "CONCLUIDA",
            "status_preparo": "NA_FILA",
            "subtotal": 15.0,
            "desconto": 0.0,
            "valor_total": 15.0,
            "itens": [
                {
                    "quantidade": 1,
                    "produto_nome": "Cappuccino",
                    "preco_unitario_snapshot": 15.0,
                    "subtotal": 15.0,
                }
            ],
        }
    )
    assert "VND-TEST-01" in txt
    assert "Cappuccino" in txt
    assert "R$ 15,00" in txt


def test_kpis_bi_refletem_exatamente_operacoes_erp(clean_db):
    admin_id = clean_db["admin_id"]
    criar_compra(
        fornecedor_id=clean_db["fornecedor_id"],
        forma_pagamento="BOLETO",
        itens=[
            {"insumo_id": clean_db["cafe_id"], "quantidade": 1000, "custo_unitario": 0.10},
            {"insumo_id": clean_db["leite_id"], "quantidade": 3000, "custo_unitario": 0.01},
        ],
        usuario_id=admin_id,
        receber_agora=True,
    )

    t0 = datetime.now(timezone.utc) - timedelta(minutes=5)
    v = registrar_venda(
        cliente_id=clean_db["cliente_id"],
        canal_venda="BALCAO",
        forma_pagamento="PIX",
        itens=[{"produto_id": clean_db["cappuccino_id"], "quantidade": 2}],
        usuario_id=admin_id,
        occurred_at=t0,
    )
    avancar_ordem_preparo(
        ordem_id=int(v["ordem_preparo_id"]),
        novo_status="EM_PREPARO",
        usuario_id=admin_id,
        occurred_at=t0 + timedelta(seconds=30),
    )
    avancar_ordem_preparo(
        ordem_id=int(v["ordem_preparo_id"]),
        novo_status="PRONTO",
        usuario_id=admin_id,
        occurred_at=t0 + timedelta(seconds=150),
    )
    registrar_perda(
        insumo_id=clean_db["leite_id"],
        quantidade=100,
        motivo="VENCIMENTO",
        usuario_id=admin_id,
    )
    criar_titulo_manual(
        tipo="PAGAR",
        categoria_id=clean_db["cat_desp_id"],
        descricao="Internet Fibra",
        valor_original=10.00,
        data_competencia=date.today(),
        data_vencimento=date.today(),
        forma_pagamento="PIX",
        usuario_id=admin_id,
        liquidar_agora=True,
    )

    hoje = date.today()
    kpis = get_kpis_executivos(data_inicio=hoje - timedelta(days=1), data_fim=hoje + timedelta(days=1))
    assert kpis["qtd_vendas"] == 1
    assert kpis["receita_liquida"] == 30.0
    # 2 cappuccinos: 2*(20*0.10 + 150*0.01) = 2*(2.0 + 1.5) = 7.0
    assert kpis["cmv_total"] == 7.0
    assert kpis["margem_bruta"] == 23.0

    abc = get_curva_abc_produtos(data_inicio=hoje - timedelta(days=1), data_fim=hoje + timedelta(days=1))
    assert len(abc) == 1
    assert abc.iloc[0]["classe_abc"] == "A"

    sla = get_operacional_sla(data_inicio=hoje - timedelta(days=1), data_fim=hoje + timedelta(days=1))
    assert sla["resumo"]["total_ordens"] == 1
    assert sla["resumo"]["taxa_sla_pct"] == 100.0

    dre = get_dre_e_fluxo_mensal()
    assert not dre.empty
    # Resultado líquido = 30 (receita) - 7 (CMV) - 1 (perda 100ml*0.01) - 10 (despesa) = 12
    assert float(dre["resultado_operacional_liquido"].sum()) == 12.0
