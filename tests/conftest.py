"""Fixtures de teste para validação unitária e de integração transacional PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event, text

from src.config.settings import _normalize_db_url
from src.db.connection import set_engine_override
from src.services.cadastros_service import (
    create_categoria,
    create_cliente,
    create_fornecedor,
    create_insumo,
    create_produto,
    upsert_ficha_tecnica_item,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
TEST_SCHEMA = "test_cafeteria_erp"


@pytest.fixture(scope="session")
def pg_engine():
    """Cria schema isolado no PostgreSQL quando TEST_DATABASE_URL está definido."""
    raw_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip("Defina TEST_DATABASE_URL para executar os testes de integração PostgreSQL.")

    db_url = _normalize_db_url(raw_url)
    base_engine = create_engine(db_url, future=True)

    with base_engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))

    # Engine configurado com search_path apontando para o schema isolado
    test_engine = create_engine(db_url, future=True)

    @event.listens_for(test_engine, "connect")
    def _set_search_path(dbapi_conn, _connection_record):
        with dbapi_conn.cursor() as cur:
            cur.execute(f"SET search_path TO {TEST_SCHEMA}")

    # Aplica DDL, índices e views no schema de teste
    raw_conn = test_engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.execute(f"SET search_path TO {TEST_SCHEMA}")
            for sql_name in ("001_schema.sql", "003_indexes_and_constraints.sql", "002_views_bi.sql"):
                cur.execute((ROOT_DIR / "sql" / sql_name).read_text(encoding="utf-8"))
        raw_conn.commit()
    finally:
        raw_conn.close()

    set_engine_override(test_engine)
    yield test_engine

    set_engine_override(None)
    test_engine.dispose()
    with base_engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
    base_engine.dispose()


@pytest.fixture()
def clean_db(pg_engine) -> dict[str, Any]:
    """Limpa tabelas antes de cada teste e semeia entidades cadastrais mínimas."""
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                """
                TRUNCATE TABLE
                    movimentacoes_financeiras,
                    titulos_financeiros,
                    registros_perdas,
                    ordem_preparo_historico,
                    ordens_preparo,
                    venda_itens,
                    vendas,
                    movimentacoes_estoque,
                    compra_itens,
                    compras,
                    historico_precos_produtos,
                    ficha_tecnica_itens,
                    produtos,
                    insumos,
                    clientes,
                    fornecedores,
                    categorias,
                    audit_logs,
                    usuarios
                RESTART IDENTITY CASCADE
                """
            )
        )
        admin_id = conn.execute(
            text(
                """
                INSERT INTO usuarios (google_sub, email, nome, perfil)
                VALUES ('sub-test-admin', 'assuero.ximenes@ufape.edu.br', 'Admin Teste', 'ADMIN')
                RETURNING id
                """
            )
        ).scalar()

    cat_ins = create_categoria(nome="Cafés", tipo="INSUMO", usuario_id=int(admin_id))
    cat_prod = create_categoria(nome="Bebidas Quentes", tipo="PRODUTO", usuario_id=int(admin_id))
    cat_desp = create_categoria(nome="Compra de Insumos", tipo="DESPESA", usuario_id=int(admin_id))
    cat_rec = create_categoria(nome="Vendas de Cardápio", tipo="RECEITA", usuario_id=int(admin_id))

    forn = create_fornecedor(
        razao_social="Torrefação Teste Ltda",
        nome_fantasia="Torrefação Teste",
        cnpj="11.111.111/0001-11",
        prazo_pagamento_dias=10,
        usuario_id=int(admin_id),
    )
    cli = create_cliente(nome="Consumidor Balcão", tipo_cliente="BALCAO", usuario_id=int(admin_id))

    cafe = create_insumo(
        sku="TST-CAF",
        nome="Café Grão Teste",
        categoria_id=int(cat_ins["id"]),
        unidade_medida="g",
        estoque_minimo=200,
        custo_medio_atual=0.10,
        usuario_id=int(admin_id),
    )
    leite = create_insumo(
        sku="TST-LEI",
        nome="Leite Integral Teste",
        categoria_id=int(cat_ins["id"]),
        unidade_medida="ml",
        estoque_minimo=1000,
        custo_medio_atual=0.006,
        perecivel=True,
        usuario_id=int(admin_id),
    )

    cappuccino = create_produto(
        sku="TST-CAP",
        nome="Cappuccino Teste",
        categoria_id=int(cat_prod["id"]),
        tipo_produto="PREPARADO",
        preco_venda=15.00,
        tempo_preparo_estimado_seg=180,
        usuario_id=int(admin_id),
    )
    upsert_ficha_tecnica_item(
        produto_id=int(cappuccino["id"]),
        insumo_id=int(cafe["id"]),
        quantidade=20,
        usuario_id=int(admin_id),
    )
    upsert_ficha_tecnica_item(
        produto_id=int(cappuccino["id"]),
        insumo_id=int(leite["id"]),
        quantidade=150,
        usuario_id=int(admin_id),
    )

    return {
        "admin_id": int(admin_id),
        "cat_desp_id": int(cat_desp["id"]),
        "cat_rec_id": int(cat_rec["id"]),
        "fornecedor_id": int(forn["id"]),
        "cliente_id": int(cli["id"]),
        "cafe_id": int(cafe["id"]),
        "leite_id": int(leite["id"]),
        "cappuccino_id": int(cappuccino["id"]),
    }
