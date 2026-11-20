"""Popula o PostgreSQL/Supabase com 90 dias de operações realistas usando os serviços do ERP.

Uso:
    python scripts/seed_db.py          # Popula apenas se o banco estiver vazio (idempotente)
    python scripts/seed_db.py --reset  # Limpa todas as tabelas e recria a base do zero
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db.connection import get_transaction
from src.db.queries import execute_scalar, fetch_all, fetch_one
from src.services.cadastros_service import (
    create_categoria,
    create_cliente,
    create_fornecedor,
    create_insumo,
    create_produto,
    upsert_ficha_tecnica_item,
)
from src.services.compras_service import criar_compra
from src.services.exceptions import InsufficientStockError
from src.services.financeiro_service import criar_titulo_manual, liquidar_titulo
from src.services.operacional_service import avancar_ordem_preparo, registrar_perda
from src.services.vendas_service import cancelar_venda, registrar_venda

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _reset_database() -> None:
    """Limpa todas as tabelas transacionais e cadastrais (apenas com --reset explícito)."""
    with get_transaction() as conn:
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
    print("[RESET] Base limpa com sucesso.")


def _seed_usuarios() -> dict[str, int]:
    """Cria usuários iniciais da cafeteria (incluindo conta do professor como ADMIN)."""
    users_spec = [
        ("seed-admin-prof", "assuero.ximenes@ufape.edu.br", "Prof. Assuero Ximenes", "ADMIN"),
        ("seed-gerente-1", "gerencia@graodoagreste.com.br", "Camila Ferreira (Gerente)", "GERENTE"),
        ("seed-caixa-1", "caixa@graodoagreste.com.br", "Lucas Almeida (Caixa)", "CAIXA"),
        ("seed-barista-1", "barista1@graodoagreste.com.br", "Marina Costa (Barista)", "BARISTA"),
        ("seed-barista-2", "barista2@graodoagreste.com.br", "Rafael Souza (Barista)", "BARISTA"),
        ("seed-estoquista-1", "estoque@graodoagreste.com.br", "Beatriz Lima (Estoquista)", "ESTOQUISTA"),
    ]
    ids: dict[str, int] = {}
    with get_transaction() as conn:
        for sub, email, nome, perfil in users_spec:
            row = conn.execute(
                text(
                    """
                    INSERT INTO usuarios (google_sub, email, nome, perfil, ativo, ultimo_login_em)
                    VALUES (:sub, :email, :nome, :perfil, TRUE, NOW())
                    ON CONFLICT (email) DO UPDATE SET nome = EXCLUDED.nome
                    RETURNING id
                    """
                ),
                {"sub": sub, "email": email, "nome": nome, "perfil": perfil},
            ).scalar()
            ids[sub] = int(row)
    return ids


def _seed_cadastros(admin_id: int) -> dict[str, Any]:
    """Cria categorias, fornecedores, clientes, insumos, produtos e fichas técnicas."""
    # Categorias
    cat_specs = [
        # Produtos
        ("Cafés Quentes", "PRODUTO"),
        ("Cafés Gelados", "PRODUTO"),
        ("Salgados & Padaria", "PRODUTO"),
        ("Doces & Bolos", "PRODUTO"),
        ("Bebidas & Revenda", "PRODUTO"),
        ("Combos", "PRODUTO"),
        # Insumos
        ("Cafés & Grãos", "INSUMO"),
        ("Laticínios", "INSUMO"),
        ("Padaria & Confeitaria", "INSUMO"),
        ("Xaropes & Complementos", "INSUMO"),
        ("Embalagens", "INSUMO"),
        ("Bebidas Prontas", "INSUMO"),
        # Despesas
        ("Compra de Insumos", "DESPESA"),
        ("Aluguel e Condomínio", "DESPESA"),
        ("Energia e Água", "DESPESA"),
        ("Folha e Pró-labore", "DESPESA"),
        ("Internet e Sistemas", "DESPESA"),
        ("Manutenção de Equipamentos", "DESPESA"),
        # Receitas
        ("Vendas de Cardápio", "RECEITA"),
        ("Eventos e Coffee Break", "RECEITA"),
    ]
    cat_ids: dict[tuple[str, str], int] = {}
    for nome, tipo in cat_specs:
        rec = create_categoria(nome=nome, tipo=tipo, usuario_id=admin_id)
        cat_ids[(nome, tipo)] = int(rec["id"])

    # Fornecedores
    forn_specs = [
        ("Torrefação Serra do Agreste Ltda", "Torrefação Serra do Agreste", "12.345.678/0001-10", "(87) 99101-1001", "vendas@serradoagreste.com.br", 15),
        ("Laticínios Vale do Leite S/A", "Laticínios Vale do Leite", "23.456.789/0001-21", "(87) 99102-2002", "pedidos@valedoleite.com.br", 7),
        ("Padaria Artesanal Trigo Nobre Ltda", "Padaria Trigo Nobre", "34.567.890/0001-32", "(87) 99103-3003", "comercial@trigonobre.com.br", 10),
        ("Gourmet Sabores e Xaropes ME", "Gourmet Sabores", "45.678.901/0001-43", "(81) 99104-4004", "contato@gourmetsabores.com.br", 21),
        ("EcoPack Embalagens Sustentáveis Ltda", "EcoPack Embalagens", "56.789.012/0001-54", "(81) 99105-5005", "vendas@ecopack.com.br", 30),
        ("Distribuidora Bebidas do Agreste Ltda", "Bebidas do Agreste", "67.890.123/0001-65", "(87) 99106-6006", "pedidos@bebidasagreste.com.br", 14),
    ]
    forn_ids: dict[str, int] = {}
    for razao, fantasia, cnpj, tel, email, prazo in forn_specs:
        rec = create_fornecedor(
            razao_social=razao,
            nome_fantasia=fantasia,
            cnpj=cnpj,
            telefone=tel,
            email=email,
            prazo_pagamento_dias=prazo,
            usuario_id=admin_id,
        )
        forn_ids[fantasia] = int(rec["id"])

    # Clientes
    cli_specs = [
        ("Consumidor Balcão", "", "", "", "BALCAO"),
        ("Ana Beatriz Vasconcelos", "111.222.333-01", "(87) 99801-0001", "ana.vasc@email.com", "FIDELIDADE"),
        ("Carlos Eduardo Melo", "111.222.333-02", "(87) 99801-0002", "carlos.melo@email.com", "FIDELIDADE"),
        ("Fernanda Rocha", "111.222.333-03", "(87) 99801-0003", "fernanda.rocha@email.com", "FIDELIDADE"),
        ("Gabriel Henrique Silva", "111.222.333-04", "(87) 99801-0004", "gabriel.silva@email.com", "FIDELIDADE"),
        ("Juliana Medeiros", "111.222.333-05", "(87) 99801-0005", "juliana.med@email.com", "FIDELIDADE"),
        ("Pedro Augusto Tavares", "111.222.333-06", "(87) 99801-0006", "pedro.tavares@email.com", "FIDELIDADE"),
        ("Larissa Cavalcanti", "111.222.333-07", "(87) 99801-0007", "larissa.cav@email.com", "FIDELIDADE"),
        ("Thiago Barbosa", "111.222.333-08", "(87) 99801-0008", "thiago.barb@email.com", "FIDELIDADE"),
        ("Mariana Albuquerque", "111.222.333-09", "(87) 99801-0009", "mariana.alb@email.com", "FIDELIDADE"),
        ("Rodrigo Santana", "111.222.333-10", "(87) 99801-0010", "rodrigo.sant@email.com", "FIDELIDADE"),
        ("Patrícia Nogueira", "111.222.333-11", "(87) 99801-0011", "patricia.nog@email.com", "FIDELIDADE"),
        ("Danielly Oliveira", "111.222.333-12", "(87) 99801-0012", "danielly.oliv@email.com", "FIDELIDADE"),
        ("Agreste Tech Coworking Ltda", "78.901.234/0001-76", "(87) 3761-2000", "financeiro@agrestetech.com.br", "CORPORATIVO"),
        ("Clínica Integrada Garanhuns", "89.012.345/0001-87", "(87) 3761-3000", "adm@clinicagaranhuns.com.br", "CORPORATIVO"),
    ]
    cli_ids: list[dict[str, Any]] = []
    for nome, doc, tel, email, tipo in cli_specs:
        rec = create_cliente(
            nome=nome,
            cpf_cnpj=doc,
            telefone=tel,
            email=email,
            tipo_cliente=tipo,
            usuario_id=admin_id,
        )
        cli_ids.append(rec)

    # Insumos: (sku, nome, categoria, un, est_min, custo_base, localizacao, perecivel, fornecedor_padrao)
    insumo_specs = [
        ("INS-CAF-ESP", "Café Especial Arábica em Grão", "Cafés & Grãos", "g", 3000, Decimal("0.0950"), "Bar Principal", False, "Torrefação Serra do Agreste"),
        ("INS-CAF-FIL", "Café Gourmet Torra Média (Coado)", "Cafés & Grãos", "g", 1500, Decimal("0.0820"), "Bar Principal", False, "Torrefação Serra do Agreste"),
        ("INS-LEI-INT", "Leite Integral Fresco", "Laticínios", "ml", 12000, Decimal("0.0058"), "Geladeira Bar", True, "Laticínios Vale do Leite"),
        ("INS-LEI-VEG", "Leite Vegetal de Aveia", "Laticínios", "ml", 4000, Decimal("0.0165"), "Geladeira Bar", True, "Laticínios Vale do Leite"),
        ("INS-CHO-PO", "Chocolate Belga 50% em Pó", "Xaropes & Complementos", "g", 1000, Decimal("0.0680"), "Bar Principal", False, "Gourmet Sabores"),
        ("INS-XAR-BAU", "Xarope Artesanal de Baunilha", "Xaropes & Complementos", "ml", 1200, Decimal("0.0480"), "Bar Principal", False, "Gourmet Sabores"),
        ("INS-XAR-CAR", "Calda de Caramelo Salgado", "Xaropes & Complementos", "ml", 1000, Decimal("0.0440"), "Bar Principal", False, "Gourmet Sabores"),
        ("INS-ACU-DEM", "Açúcar Demerara / Sachê", "Xaropes & Complementos", "g", 1500, Decimal("0.0090"), "Estoque Central", False, "Gourmet Sabores"),
        ("INS-GEL-CUB", "Gelo Filtrado em Cubos", "Bebidas Prontas", "g", 3000, Decimal("0.0020"), "Freezer Bar", False, "Bebidas do Agreste"),
        ("INS-COP-250", "Copo Biodegradável 250ml c/ Tampa", "Embalagens", "un", 150, Decimal("0.4800"), "Estoque Central", False, "EcoPack Embalagens"),
        ("INS-COP-400", "Copo Cristal Gelado 400ml c/ Canudo", "Embalagens", "un", 120, Decimal("0.6500"), "Estoque Central", False, "EcoPack Embalagens"),
        ("INS-SAC-PAP", "Embalagem Kraft Salgado/Doce", "Embalagens", "un", 150, Decimal("0.3200"), "Estoque Central", False, "EcoPack Embalagens"),
        ("INS-PDQ-UN", "Pão de Queijo Mineiro Artesanal", "Padaria & Confeitaria", "un", 45, Decimal("1.9500"), "Freezer Cozinha", True, "Padaria Trigo Nobre"),
        ("INS-CRO-UN", "Croissant Francês de Manteiga", "Padaria & Confeitaria", "un", 25, Decimal("4.4000"), "Vitrine / Cozinha", True, "Padaria Trigo Nobre"),
        ("INS-BOL-CEN", "Fatia Bolo de Cenoura c/ Chocolate", "Padaria & Confeitaria", "un", 20, Decimal("3.8000"), "Vitrine Refrigerada", True, "Padaria Trigo Nobre"),
        ("INS-BRO-CHO", "Brownie Meio Amargo Artesanal", "Padaria & Confeitaria", "un", 20, Decimal("4.1000"), "Vitrine / Cozinha", True, "Padaria Trigo Nobre"),
        ("INS-AGU-500", "Água Mineral sem Gás 500ml", "Bebidas Prontas", "un", 40, Decimal("1.4500"), "Geladeira Revenda", False, "Bebidas do Agreste"),
        ("INS-AGU-GAS", "Água Mineral com Gás 500ml", "Bebidas Prontas", "un", 30, Decimal("1.7500"), "Geladeira Revenda", False, "Bebidas do Agreste"),
    ]
    insumos_map: dict[str, dict[str, Any]] = {}
    for sku, nome, cat_nome, un, est_min, custo_base, loc, perecivel, forn_nome in insumo_specs:
        rec = create_insumo(
            sku=sku,
            nome=nome,
            categoria_id=cat_ids[(cat_nome, "INSUMO")],
            unidade_medida=un,
            estoque_minimo=est_min,
            custo_medio_atual=custo_base,
            localizacao=loc,
            perecivel=perecivel,
            usuario_id=admin_id,
        )
        rec["custo_base"] = custo_base
        rec["fornecedor_id"] = forn_ids[forn_nome]
        insumos_map[sku] = rec

    # Produtos: (sku, nome, categoria, tipo, preco_venda, tempo_est_seg, peso_demanda, receita)
    prod_specs = [
        ("PRD-ESP-01", "Espresso Tradicional", "Cafés Quentes", "PREPARADO", Decimal("8.00"), 90, 18,
         [("INS-CAF-ESP", 18), ("INS-ACU-DEM", 5), ("INS-COP-250", 1)]),
        ("PRD-ESP-02", "Espresso Duplo", "Cafés Quentes", "PREPARADO", Decimal("11.50"), 110, 10,
         [("INS-CAF-ESP", 32), ("INS-ACU-DEM", 5), ("INS-COP-250", 1)]),
        ("PRD-CAP-01", "Cappuccino Clássico", "Cafés Quentes", "PREPARADO", Decimal("14.50"), 180, 22,
         [("INS-CAF-ESP", 18), ("INS-LEI-INT", 160), ("INS-CHO-PO", 12), ("INS-COP-250", 1)]),
        ("PRD-LAT-01", "Café Latte Cremoso", "Cafés Quentes", "PREPARADO", Decimal("13.50"), 160, 14,
         [("INS-CAF-ESP", 18), ("INS-LEI-INT", 190), ("INS-COP-250", 1)]),
        ("PRD-LAT-AVE", "Latte Vegetal de Aveia", "Cafés Quentes", "PREPARADO", Decimal("16.50"), 170, 9,
         [("INS-CAF-ESP", 18), ("INS-LEI-VEG", 200), ("INS-COP-250", 1)]),
        ("PRD-MOC-01", "Mocha Belga", "Cafés Quentes", "PREPARADO", Decimal("16.00"), 200, 11,
         [("INS-CAF-ESP", 18), ("INS-LEI-INT", 150), ("INS-CHO-PO", 22), ("INS-COP-250", 1)]),
        ("PRD-V60-01", "Coado Especial V60", "Cafés Quentes", "PREPARADO", Decimal("13.00"), 240, 8,
         [("INS-CAF-FIL", 20), ("INS-COP-250", 1)]),
        ("PRD-ICE-LAT", "Iced Latte Baunilha", "Cafés Gelados", "PREPARADO", Decimal("17.50"), 180, 14,
         [("INS-CAF-ESP", 20), ("INS-LEI-INT", 180), ("INS-XAR-BAU", 25), ("INS-GEL-CUB", 120), ("INS-COP-400", 1)]),
        ("PRD-ICE-CAR", "Iced Caramel Macchiato", "Cafés Gelados", "PREPARADO", Decimal("18.50"), 200, 12,
         [("INS-CAF-ESP", 20), ("INS-LEI-INT", 170), ("INS-XAR-CAR", 30), ("INS-GEL-CUB", 120), ("INS-COP-400", 1)]),
        ("PRD-PDQ-01", "Pão de Queijo Mineiro (un)", "Salgados & Padaria", "REVENDA", Decimal("7.50"), 90, 20,
         [("INS-PDQ-UN", 1), ("INS-SAC-PAP", 1)]),
        ("PRD-CRO-01", "Croissant Francês", "Salgados & Padaria", "REVENDA", Decimal("11.00"), 110, 13,
         [("INS-CRO-UN", 1), ("INS-SAC-PAP", 1)]),
        ("PRD-BOL-01", "Bolo de Cenoura c/ Chocolate", "Doces & Bolos", "REVENDA", Decimal("12.50"), 80, 11,
         [("INS-BOL-CEN", 1), ("INS-SAC-PAP", 1)]),
        ("PRD-BRO-01", "Brownie Meio Amargo", "Doces & Bolos", "REVENDA", Decimal("11.50"), 80, 9,
         [("INS-BRO-CHO", 1), ("INS-SAC-PAP", 1)]),
        ("PRD-AGU-01", "Água Mineral sem Gás 500ml", "Bebidas & Revenda", "REVENDA", Decimal("5.50"), 30, 8,
         [("INS-AGU-500", 1)]),
        ("PRD-AGU-02", "Água Mineral com Gás 500ml", "Bebidas & Revenda", "REVENDA", Decimal("6.50"), 30, 6,
         [("INS-AGU-GAS", 1)]),
        ("PRD-CMB-01", "Combo Manhã (Cappuccino + Croissant)", "Combos", "PREPARADO", Decimal("22.00"), 210, 12,
         [("INS-CAF-ESP", 18), ("INS-LEI-INT", 160), ("INS-CHO-PO", 12), ("INS-COP-250", 1), ("INS-CRO-UN", 1), ("INS-SAC-PAP", 1)]),
    ]
    produtos_list: list[dict[str, Any]] = []
    for sku, nome, cat_nome, tipo, preco, tempo_est, peso, receita in prod_specs:
        rec = create_produto(
            sku=sku,
            nome=nome,
            categoria_id=cat_ids[(cat_nome, "PRODUTO")],
            tipo_produto=tipo,
            preco_venda=preco,
            tempo_preparo_estimado_seg=tempo_est,
            usuario_id=admin_id,
        )
        for ins_sku, qtd in receita:
            upsert_ficha_tecnica_item(
                produto_id=int(rec["id"]),
                insumo_id=int(insumos_map[ins_sku]["id"]),
                quantidade=qtd,
                usuario_id=admin_id,
            )
        rec["peso"] = peso
        rec["tempo_est"] = tempo_est
        produtos_list.append(rec)

    return {
        "cat_ids": cat_ids,
        "forn_ids": forn_ids,
        "clientes": cli_ids,
        "insumos": insumos_map,
        "produtos": produtos_list,
    }


def _repor_estoque_fornecedor(
    *,
    insumos_para_comprar: list[tuple[dict[str, Any], Decimal, Decimal]],
    fornecedor_id: int,
    usuario_id: int,
    ts: datetime,
    forma_pagamento: str,
    obs: str,
) -> None:
    itens = []
    for ins, qtd, custo_unit in insumos_para_comprar:
        validade = (ts.date() + timedelta(days=12 if ins["perecivel"] else 180))
        itens.append(
            {
                "insumo_id": int(ins["id"]),
                "quantidade": qtd,
                "custo_unitario": custo_unit,
                "lote": f"LT-{ts.strftime('%y%m%d')}-{ins['sku'][-3:]}",
                "data_validade": validade,
            }
        )
    criar_compra(
        fornecedor_id=fornecedor_id,
        forma_pagamento=forma_pagamento,
        itens=itens,
        usuario_id=usuario_id,
        observacoes=obs,
        receber_agora=True,
        liquidar_se_avista=False,
        occurred_at=ts,
    )


def run_seed(reset: bool = False) -> None:
    if reset:
        _reset_database()

    existing_sales = execute_scalar("SELECT COUNT(*) FROM vendas") or 0
    if existing_sales > 0:
        print(
            f"[SKIP] O banco já possui {existing_sales} venda(s). "
            "Use `python scripts/seed_db.py --reset` para recriar os dados do zero."
        )
        return

    rng = random.Random(42)
    print("[1/5] Criando usuários operacionais...")
    user_ids = _seed_usuarios()
    admin_id = user_ids["seed-admin-prof"]
    gerente_id = user_ids["seed-gerente-1"]
    caixa_id = user_ids["seed-caixa-1"]
    barista1_id = user_ids["seed-barista-1"]
    barista2_id = user_ids["seed-barista-2"]
    estoquista_id = user_ids["seed-estoquista-1"]

    print("[2/5] Criando cadastros base e fichas técnicas...")
    cad = _seed_cadastros(admin_id)
    cat_ids = cad["cat_ids"]
    clientes = cad["clientes"]
    insumos_map = cad["insumos"]
    produtos = cad["produtos"]

    cliente_balcao = clientes[0]
    clientes_fidelidade = [c for c in clientes if c["tipo_cliente"] == "FIDELIDADE"]
    clientes_corp = [c for c in clientes if c["tipo_cliente"] == "CORPORATIVO"]

    today = datetime.now(TZ_SP).date()
    start_date = today - timedelta(days=89)

    # Mapeamento de quantidade padrão de reposição por SKU
    lote_reposicao = {
        "INS-CAF-ESP": Decimal("15000"),
        "INS-CAF-FIL": Decimal("5000"),
        "INS-LEI-INT": Decimal("45000"),
        "INS-LEI-VEG": Decimal("12000"),
        "INS-CHO-PO": Decimal("4000"),
        "INS-XAR-BAU": Decimal("4000"),
        "INS-XAR-CAR": Decimal("4000"),
        "INS-ACU-DEM": Decimal("5000"),
        "INS-GEL-CUB": Decimal("15000"),
        "INS-COP-250": Decimal("600"),
        "INS-COP-400": Decimal("400"),
        "INS-SAC-PAP": Decimal("600"),
        "INS-PDQ-UN": Decimal("180"),
        "INS-CRO-UN": Decimal("120"),
        "INS-BOL-CEN": Decimal("80"),
        "INS-BRO-CHO": Decimal("80"),
        "INS-AGU-500": Decimal("120"),
        "INS-AGU-GAS": Decimal("100"),
    }
    # Insumos que deixarão de ser repostos nos últimos 6 dias para demonstrar alertas críticos reais
    skus_criticos_finais = {"INS-LEI-VEG", "INS-XAR-BAU", "INS-CRO-UN"}

    print("[3/5] Registrando compras iniciais de abastecimento...")
    ts_inicio = datetime.combine(start_date, time(7, 30), tzinfo=TZ_SP)
    por_forn: dict[int, list[tuple[dict[str, Any], Decimal, Decimal]]] = {}
    for sku, ins in insumos_map.items():
        fid = int(ins["fornecedor_id"])
        por_forn.setdefault(fid, []).append((ins, lote_reposicao[sku], ins["custo_base"]))

    for fid, itens_f in por_forn.items():
        _repor_estoque_fornecedor(
            insumos_para_comprar=itens_f,
            fornecedor_id=fid,
            usuario_id=estoquista_id,
            ts=ts_inicio,
            forma_pagamento="BOLETO",
            obs="Estoque inicial — abertura do ciclo trimestral",
        )

    print("[4/5] Simulando 90 dias de operações integradas (Vendas, Preparo, Perdas, Compras e Financeiro)...")
    pesos_prod = [p["peso"] for p in produtos]
    horas_dist = [7, 8, 8, 9, 9, 9, 10, 10, 11, 12, 13, 14, 15, 15, 15, 16, 16, 16, 17, 17, 18, 19]
    canais_dist = ["BALCAO", "BALCAO", "BALCAO", "MESA", "MESA", "RETIRADA", "DELIVERY"]
    pag_dist = ["PIX", "PIX", "PIX", "DEBITO", "DEBITO", "CREDITO", "CREDITO", "DINHEIRO"]

    total_vendas_geradas = 0
    total_perdas_geradas = 0
    total_compras_geradas = len(por_forn)
    meses_despesa_lancados: set[tuple[int, int]] = set()
    ultimas_ordens_hoje: list[int] = []

    for day_offset in range(90):
        dia = start_date + timedelta(days=day_offset)
        progresso = day_offset / 89.0  # 0.0 -> 1.0 (inflação leve de café e leite)
        if day_offset % 15 == 0 or day_offset == 89:
            print(
                f"      → Progresso: dia {day_offset + 1}/90 ({dia.strftime('%d/%m/%Y')}) "
                f"— {total_vendas_geradas} vendas acumuladas...",
                flush=True,
            )

        # 1) Despesas fixas mensais (lançadas no dia 5 de cada mês ou primeiro dia do ciclo)
        ym = (dia.year, dia.month)
        if ym not in meses_despesa_lancados and (dia.day >= 5 or day_offset == 0):
            meses_despesa_lancados.add(ym)
            despesas_mes = [
                ("Aluguel e Condomínio", f"Aluguel Ponto Comercial — {dia.strftime('%m/%Y')}", Decimal("3200.00"), 10),
                ("Energia e Água", f"Conta Energia Elétrica — {dia.strftime('%m/%Y')}", Decimal(str(round(820 + rng.uniform(-45, 95), 2))), 15),
                ("Energia e Água", f"Conta Água e Saneamento — {dia.strftime('%m/%Y')}", Decimal(str(round(190 + rng.uniform(-15, 25), 2))), 18),
                ("Folha e Pró-labore", f"Folha Equipe Baristas/Caixa — {dia.strftime('%m/%Y')}", Decimal("5400.00"), 5),
                ("Internet e Sistemas", f"Internet Fibra e Cloud — {dia.strftime('%m/%Y')}", Decimal("240.00"), 12),
                ("Manutenção de Equipamentos", f"Manutenção Preventiva Máquina Espresso — {dia.strftime('%m/%Y')}", Decimal("350.00"), 22),
            ]
            for cat_nome, desc, val, dia_venc in despesas_mes:
                venc = date(dia.year, dia.month, min(dia_venc, 28))
                if venc < start_date:
                    venc = dia + timedelta(days=5)
                ja_pago = venc <= today - timedelta(days=2)
                criar_titulo_manual(
                    tipo="PAGAR",
                    categoria_id=cat_ids[(cat_nome, "DESPESA")],
                    descricao=desc,
                    valor_original=val,
                    data_competencia=dia,
                    data_vencimento=venc,
                    forma_pagamento="TRANSFERENCIA" if "Aluguel" in desc or "Folha" in desc else "BOLETO",
                    usuario_id=gerente_id,
                    liquidar_agora=ja_pago,
                    occurred_at=datetime.combine(venc if ja_pago else dia, time(10, 0), tzinfo=TZ_SP),
                )

        # 2) Reposição inteligente de insumos abaixo de 1.8x o mínimo
        saldos_atuais = fetch_all("SELECT id, sku, estoque_atual, estoque_minimo FROM insumos")
        repor_por_forn: dict[int, list[tuple[dict[str, Any], Decimal, Decimal]]] = {}
        for row in saldos_atuais:
            sku = row["sku"]
            if day_offset >= 83 and sku in skus_criticos_finais:
                continue
            est_atual = Decimal(str(row["estoque_atual"]))
            est_min = Decimal(str(row["estoque_minimo"]))
            if est_atual < (est_min * Decimal("1.8")):
                ins = insumos_map[sku]
                fator_preco = Decimal("1.0")
                if sku == "INS-CAF-ESP":
                    fator_preco = Decimal(str(round(1.0 + 0.14 * progresso, 4)))
                elif sku == "INS-LEI-INT":
                    fator_preco = Decimal(str(round(1.0 + 0.09 * progresso, 4)))
                else:
                    fator_preco = Decimal(str(round(1.0 + rng.uniform(-0.02, 0.03), 4)))
                custo_novo = (ins["custo_base"] * fator_preco).quantize(Decimal("0.0001"))
                fid = int(ins["fornecedor_id"])
                repor_por_forn.setdefault(fid, []).append((ins, lote_reposicao[sku], custo_novo))

        if repor_por_forn:
            ts_compra = datetime.combine(dia, time(7, 45), tzinfo=TZ_SP)
            for fid, itens_f in repor_por_forn.items():
                _repor_estoque_fornecedor(
                    insumos_para_comprar=itens_f,
                    fornecedor_id=fid,
                    usuario_id=estoquista_id,
                    ts=ts_compra,
                    forma_pagamento=rng.choice(["BOLETO", "PIX", "TRANSFERENCIA"]),
                    obs=f"Reposição programada — {dia.strftime('%d/%m/%Y')}",
                )
                total_compras_geradas += 1

        # 3) Vendas diárias com sazonalidade (sexta/sábado mais fortes, segunda mais fraca)
        dow = dia.weekday()  # 0=Seg .. 6=Dom
        fator_dia = {0: 0.72, 1: 0.90, 2: 0.95, 3: 1.05, 4: 1.32, 5: 1.45, 6: 0.85}[dow]
        qtd_vendas_dia = max(4, int(round(6.5 * fator_dia + rng.uniform(-1, 1.5))))
        if day_offset == 89:
            qtd_vendas_dia = max(6, qtd_vendas_dia)

        horarios_dia = sorted(
            [
                datetime.combine(
                    dia,
                    time(rng.choice(horas_dist), rng.randint(0, 59), rng.randint(0, 59)),
                    tzinfo=TZ_SP,
                )
                for _ in range(qtd_vendas_dia)
            ]
        )

        for idx_v, ts_venda in enumerate(horarios_dia):
            # Escolha de cliente e pagamento
            r_cli = rng.random()
            if r_cli < 0.06:
                cli = rng.choice(clientes_corp)
                canal = "DELIVERY"
                forma = "FATURADO"
                n_itens = rng.randint(3, 5)
            elif r_cli < 0.48:
                cli = rng.choice(clientes_fidelidade)
                canal = rng.choice(canais_dist)
                forma = rng.choice(pag_dist)
                n_itens = rng.choices([1, 2, 3], weights=[40, 42, 18])[0]
            else:
                cli = cliente_balcao
                canal = rng.choice(["BALCAO", "MESA", "RETIRADA"])
                forma = rng.choice(pag_dist)
                n_itens = rng.choices([1, 2, 3], weights=[52, 36, 12])[0]

            escolhidos = rng.choices(produtos, weights=pesos_prod, k=n_itens)
            itens_venda = [
                {"produto_id": int(p["id"]), "quantidade": rng.choices([1, 2], weights=[85, 15])[0]}
                for p in escolhidos
            ]
            desconto = Decimal("2.00") if (cli["tipo_cliente"] == "FIDELIDADE" and rng.random() < 0.22) else Decimal("0.00")

            try:
                venda = registrar_venda(
                    cliente_id=int(cli["id"]),
                    canal_venda=canal,
                    forma_pagamento=forma,
                    itens=itens_venda,
                    usuario_id=caixa_id,
                    desconto=desconto,
                    prioridade="ALTA" if canal == "DELIVERY" else "NORMAL",
                    occurred_at=ts_venda,
                )
            except InsufficientStockError:
                continue

            total_vendas_geradas += 1
            ordem_id = int(venda["ordem_preparo_id"])
            is_ultimos_hoje = day_offset == 89 and idx_v >= len(horarios_dia) - 3

            if is_ultimos_hoje:
                ultimas_ordens_hoje.append(ordem_id)
                continue

            # ~3% de cancelamentos auditados
            if rng.random() < 0.03:
                if rng.random() < 0.65:
                    cancelar_venda(
                        venda_id=int(venda["id"]),
                        motivo="Cliente desistiu antes do preparo",
                        usuario_id=gerente_id,
                        occurred_at=ts_venda + timedelta(seconds=55),
                    )
                else:
                    barista = rng.choice([barista1_id, barista2_id])
                    avancar_ordem_preparo(
                        ordem_id=ordem_id,
                        novo_status="EM_PREPARO",
                        usuario_id=barista,
                        occurred_at=ts_venda + timedelta(seconds=45),
                    )
                    cancelar_venda(
                        venda_id=int(venda["id"]),
                        motivo="Pedido cancelado durante preparo (erro de sabor)",
                        usuario_id=gerente_id,
                        occurred_at=ts_venda + timedelta(seconds=120),
                    )
                continue

            # Avança preparo completo com gargalo realista no pico da tarde (15h-17h)
            barista = barista1_id if rng.random() < 0.56 else barista2_id
            pico_tarde = ts_venda.hour in {15, 16, 17}
            pico_manha = ts_venda.hour in {8, 9}

            espera_fila = (
                rng.randint(95, 220)
                if pico_tarde
                else (rng.randint(55, 130) if pico_manha else rng.randint(20, 75))
            )
            tempo_prep = (
                rng.randint(170, 310)
                if pico_tarde
                else (rng.randint(105, 195) if barista == barista1_id else rng.randint(125, 235))
            )
            ts_ini = ts_venda + timedelta(seconds=espera_fila)
            ts_pronto = ts_ini + timedelta(seconds=tempo_prep)
            ts_entregue = ts_pronto + timedelta(seconds=rng.randint(20, 90))

            avancar_ordem_preparo(
                ordem_id=ordem_id,
                novo_status="EM_PREPARO",
                usuario_id=barista,
                occurred_at=ts_ini,
            )
            avancar_ordem_preparo(
                ordem_id=ordem_id,
                novo_status="PRONTO",
                usuario_id=barista,
                occurred_at=ts_pronto,
            )
            avancar_ordem_preparo(
                ordem_id=ordem_id,
                novo_status="ENTREGUE",
                usuario_id=caixa_id,
                occurred_at=ts_entregue,
            )

        # 4) Registros realistas de perdas (~3x por semana, focados em perecíveis e regulagem de moedor)
        if day_offset % 3 == 1:
            perdas_candidatas = [
                ("INS-LEI-INT", Decimal(str(rng.randint(400, 1200))), "VENCIMENTO", "Sobras de leite aberto fora da janela térmica"),
                ("INS-LEI-VEG", Decimal(str(rng.randint(200, 600))), "VENCIMENTO", "Validade pós-abertura atingida"),
                ("INS-CAF-ESP", Decimal(str(rng.randint(60, 140))), "DESPERDICIO_BARISTA", "Regulagem diária de moagem do espresso"),
                ("INS-BOL-CEN", Decimal(str(rng.randint(1, 2))), "VENCIMENTO", "Fatia não vendida ao fim do expediente"),
                ("INS-CRO-UN", Decimal("1"), "QUEBRA_PREPARO", "Croissant queimado no aquecimento"),
            ]
            sku_p, qtd_p, mot_p, obs_p = rng.choice(perdas_candidatas)
            try:
                registrar_perda(
                    insumo_id=int(insumos_map[sku_p]["id"]),
                    quantidade=qtd_p,
                    motivo=mot_p,
                    usuario_id=rng.choice([barista1_id, barista2_id, estoquista_id]),
                    observacoes=obs_p,
                    occurred_at=datetime.combine(dia, time(19, 30), tzinfo=TZ_SP),
                )
                total_perdas_geradas += 1
            except InsufficientStockError:
                pass

    # Deixa as 3 últimas ordens de hoje em estágios diferentes para demonstração imediata na fila do Barista
    if len(ultimas_ordens_hoje) >= 2:
        now_sp = datetime.now(TZ_SP)
        avancar_ordem_preparo(
            ordem_id=ultimas_ordens_hoje[0],
            novo_status="EM_PREPARO",
            usuario_id=barista1_id,
            occurred_at=now_sp - timedelta(minutes=3),
        )
        avancar_ordem_preparo(
            ordem_id=ultimas_ordens_hoje[0],
            novo_status="PRONTO",
            usuario_id=barista1_id,
            occurred_at=now_sp - timedelta(minutes=1),
        )
        avancar_ordem_preparo(
            ordem_id=ultimas_ordens_hoje[1],
            novo_status="EM_PREPARO",
            usuario_id=barista2_id,
            occurred_at=now_sp - timedelta(minutes=2),
        )
        # ultimas_ordens_hoje[2] permanece NA_FILA!

    print("[5/5] Liquidando títulos vencidos de compras e vendas a prazo...")
    titulos_abertos = fetch_all(
        """
        SELECT id, tipo, data_vencimento, forma_pagamento
        FROM titulos_financeiros
        WHERE status = 'ABERTO'
        ORDER BY data_vencimento ASC
        """
    )
    liquidados = 0
    for idx_t, t in enumerate(titulos_abertos):
        venc: date = t["data_vencimento"]
        # Mantém 2 títulos vencidos recentemente em aberto para evidenciar alertas de atraso
        if venc <= today - timedelta(days=3):
            if idx_t % 19 == 0 and venc >= today - timedelta(days=10):
                continue
            liquidar_titulo(
                titulo_id=int(t["id"]),
                forma_pagamento=t["forma_pagamento"] or "TRANSFERENCIA",
                usuario_id=gerente_id,
                occurred_at=datetime.combine(venc, time(14, 0), tzinfo=TZ_SP),
            )
            liquidados += 1

    # Checagem final de integridade
    criticos = fetch_one(
        "SELECT COUNT(*) AS qtd FROM insumos WHERE ativo = TRUE AND estoque_atual <= estoque_minimo"
    )
    print(
        "\n[SEED CONCLUÍDO COM SUCESSO]\n"
        f"  • Período simulado : {start_date.strftime('%d/%m/%Y')} a {today.strftime('%d/%m/%Y')} (90 dias)\n"
        f"  • Compras recebidas: {total_compras_geradas}\n"
        f"  • Vendas geradas   : {total_vendas_geradas}\n"
        f"  • Perdas operac.   : {total_perdas_geradas}\n"
        f"  • Títulos baixados : {liquidados}\n"
        f"  • Insumos críticos : {criticos['qtd'] if criticos else 0} (alertas prontos para demonstração)\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realista de 90 dias para o ERP da Cafeteria.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Limpa todas as tabelas antes de recriar os dados iniciais.",
    )
    args = parser.parse_args()
    run_seed(reset=args.reset)


if __name__ == "__main__":
    main()
