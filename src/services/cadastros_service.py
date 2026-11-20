"""Serviço de Cadastros Base e Ficha Técnica (Módulo Cadastros)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import BusinessRuleError, NotFoundError, ValidationError


# =============================================================================
# CATEGORIAS
# =============================================================================
def list_categorias(tipo: str | None = None, apenas_ativas: bool = False) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if tipo:
        clauses.append("tipo = :tipo")
        params["tipo"] = tipo
    if apenas_ativas:
        clauses.append("ativo = TRUE")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT id, nome, tipo, ativo, criado_em, atualizado_em
        FROM categorias
        {where}
        ORDER BY tipo ASC, nome ASC
        """,
        params,
    )


def create_categoria(*, nome: str, tipo: str, usuario_id: int) -> dict[str, Any]:
    nome_clean = nome.strip()
    if not nome_clean:
        raise ValidationError("Nome da categoria é obrigatório.")
    if tipo not in {"PRODUTO", "INSUMO", "DESPESA", "RECEITA"}:
        raise ValidationError("Tipo de categoria inválido.")

    with get_transaction() as conn:
        dup = fetch_one(
            "SELECT id FROM categorias WHERE LOWER(nome) = LOWER(:nome) AND tipo = :tipo",
            {"nome": nome_clean, "tipo": tipo},
            conn=conn,
        )
        if dup:
            raise BusinessRuleError(f"Categoria '{nome_clean}' ({tipo}) já cadastrada.")

        row = conn.execute(
            text(
                """
                INSERT INTO categorias (nome, tipo)
                VALUES (:nome, :tipo)
                RETURNING id, nome, tipo, ativo, criado_em, atualizado_em
                """
            ),
            {"nome": nome_clean, "tipo": tipo},
        ).mappings().first()
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="categorias",
            entidade_id=record["id"],
            acao="CRIAR",
            detalhes={"nome": nome_clean, "tipo": tipo},
            conn=conn,
        )
        return record


def update_categoria(*, categoria_id: int, nome: str, ativo: bool, usuario_id: int) -> dict[str, Any]:
    nome_clean = nome.strip()
    if not nome_clean:
        raise ValidationError("Nome da categoria é obrigatório.")

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                UPDATE categorias
                SET nome = :nome, ativo = :ativo, atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, nome, tipo, ativo, criado_em, atualizado_em
                """
            ),
            {"id": categoria_id, "nome": nome_clean, "ativo": ativo},
        ).mappings().first()
        if not row:
            raise NotFoundError("Categoria não encontrada.")
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="categorias",
            entidade_id=categoria_id,
            acao="ATUALIZAR",
            detalhes={"nome": nome_clean, "ativo": ativo},
            conn=conn,
        )
        return record


# =============================================================================
# FORNECEDORES
# =============================================================================
def list_fornecedores(apenas_ativos: bool = False) -> list[dict[str, Any]]:
    where = "WHERE ativo = TRUE" if apenas_ativos else ""
    return fetch_all(
        f"""
        SELECT id, razao_social, nome_fantasia, cnpj, telefone, email,
               prazo_pagamento_dias, ativo, criado_em, atualizado_em
        FROM fornecedores
        {where}
        ORDER BY ativo DESC, nome_fantasia ASC
        """
    )


def create_fornecedor(
    *,
    razao_social: str,
    nome_fantasia: str,
    cnpj: str,
    telefone: str = "",
    email: str = "",
    prazo_pagamento_dias: int = 0,
    usuario_id: int,
) -> dict[str, Any]:
    if not razao_social.strip() or not nome_fantasia.strip() or not cnpj.strip():
        raise ValidationError("Razão social, nome fantasia e CNPJ são obrigatórios.")
    if prazo_pagamento_dias < 0:
        raise ValidationError("Prazo de pagamento não pode ser negativo.")

    with get_transaction() as conn:
        dup = fetch_one(
            "SELECT id FROM fornecedores WHERE cnpj = :cnpj",
            {"cnpj": cnpj.strip()},
            conn=conn,
        )
        if dup:
            raise BusinessRuleError(f"Já existe fornecedor cadastrado com o CNPJ {cnpj.strip()}.")

        row = conn.execute(
            text(
                """
                INSERT INTO fornecedores (
                    razao_social, nome_fantasia, cnpj, telefone, email, prazo_pagamento_dias
                )
                VALUES (
                    :razao_social, :nome_fantasia, :cnpj, :telefone, :email, :prazo_pagamento_dias
                )
                RETURNING id, razao_social, nome_fantasia, cnpj, telefone, email,
                          prazo_pagamento_dias, ativo, criado_em, atualizado_em
                """
            ),
            {
                "razao_social": razao_social.strip(),
                "nome_fantasia": nome_fantasia.strip(),
                "cnpj": cnpj.strip(),
                "telefone": telefone.strip() or None,
                "email": email.strip() or None,
                "prazo_pagamento_dias": int(prazo_pagamento_dias),
            },
        ).mappings().first()
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="fornecedores",
            entidade_id=record["id"],
            acao="CRIAR",
            detalhes={"nome_fantasia": record["nome_fantasia"], "cnpj": record["cnpj"]},
            conn=conn,
        )
        return record


def update_fornecedor(
    *,
    fornecedor_id: int,
    razao_social: str,
    nome_fantasia: str,
    telefone: str = "",
    email: str = "",
    prazo_pagamento_dias: int = 0,
    ativo: bool = True,
    usuario_id: int,
) -> dict[str, Any]:
    if not razao_social.strip() or not nome_fantasia.strip():
        raise ValidationError("Razão social e nome fantasia são obrigatórios.")
    if prazo_pagamento_dias < 0:
        raise ValidationError("Prazo de pagamento não pode ser negativo.")

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                UPDATE fornecedores
                SET razao_social = :razao_social,
                    nome_fantasia = :nome_fantasia,
                    telefone = :telefone,
                    email = :email,
                    prazo_pagamento_dias = :prazo_pagamento_dias,
                    ativo = :ativo,
                    atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, razao_social, nome_fantasia, cnpj, telefone, email,
                          prazo_pagamento_dias, ativo, criado_em, atualizado_em
                """
            ),
            {
                "id": fornecedor_id,
                "razao_social": razao_social.strip(),
                "nome_fantasia": nome_fantasia.strip(),
                "telefone": telefone.strip() or None,
                "email": email.strip() or None,
                "prazo_pagamento_dias": int(prazo_pagamento_dias),
                "ativo": ativo,
            },
        ).mappings().first()
        if not row:
            raise NotFoundError("Fornecedor não encontrado.")
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="fornecedores",
            entidade_id=fornecedor_id,
            acao="ATUALIZAR",
            detalhes={"nome_fantasia": record["nome_fantasia"], "ativo": ativo},
            conn=conn,
        )
        return record


# =============================================================================
# CLIENTES
# =============================================================================
def list_clientes(apenas_ativos: bool = False) -> list[dict[str, Any]]:
    where = "WHERE ativo = TRUE" if apenas_ativos else ""
    return fetch_all(
        f"""
        SELECT id, nome, cpf_cnpj, telefone, email, tipo_cliente, ativo, criado_em, atualizado_em
        FROM clientes
        {where}
        ORDER BY ativo DESC, nome ASC
        """
    )


def create_cliente(
    *,
    nome: str,
    cpf_cnpj: str = "",
    telefone: str = "",
    email: str = "",
    tipo_cliente: str = "BALCAO",
    usuario_id: int,
) -> dict[str, Any]:
    if not nome.strip():
        raise ValidationError("Nome do cliente é obrigatório.")
    if tipo_cliente not in {"BALCAO", "FIDELIDADE", "CORPORATIVO"}:
        raise ValidationError("Tipo de cliente inválido.")

    doc = cpf_cnpj.strip() or None
    with get_transaction() as conn:
        if doc:
            dup = fetch_one(
                "SELECT id FROM clientes WHERE cpf_cnpj = :doc",
                {"doc": doc},
                conn=conn,
            )
            if dup:
                raise BusinessRuleError(f"Já existe cliente com CPF/CNPJ {doc}.")

        row = conn.execute(
            text(
                """
                INSERT INTO clientes (nome, cpf_cnpj, telefone, email, tipo_cliente)
                VALUES (:nome, :cpf_cnpj, :telefone, :email, :tipo_cliente)
                RETURNING id, nome, cpf_cnpj, telefone, email, tipo_cliente, ativo, criado_em, atualizado_em
                """
            ),
            {
                "nome": nome.strip(),
                "cpf_cnpj": doc,
                "telefone": telefone.strip() or None,
                "email": email.strip() or None,
                "tipo_cliente": tipo_cliente,
            },
        ).mappings().first()
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="clientes",
            entidade_id=record["id"],
            acao="CRIAR",
            detalhes={"nome": record["nome"], "tipo_cliente": tipo_cliente},
            conn=conn,
        )
        return record


def update_cliente(
    *,
    cliente_id: int,
    nome: str,
    telefone: str = "",
    email: str = "",
    tipo_cliente: str = "BALCAO",
    ativo: bool = True,
    usuario_id: int,
) -> dict[str, Any]:
    if not nome.strip():
        raise ValidationError("Nome do cliente é obrigatório.")
    if tipo_cliente not in {"BALCAO", "FIDELIDADE", "CORPORATIVO"}:
        raise ValidationError("Tipo de cliente inválido.")

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                UPDATE clientes
                SET nome = :nome,
                    telefone = :telefone,
                    email = :email,
                    tipo_cliente = :tipo_cliente,
                    ativo = :ativo,
                    atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, nome, cpf_cnpj, telefone, email, tipo_cliente, ativo, criado_em, atualizado_em
                """
            ),
            {
                "id": cliente_id,
                "nome": nome.strip(),
                "telefone": telefone.strip() or None,
                "email": email.strip() or None,
                "tipo_cliente": tipo_cliente,
                "ativo": ativo,
            },
        ).mappings().first()
        if not row:
            raise NotFoundError("Cliente não encontrado.")
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="clientes",
            entidade_id=cliente_id,
            acao="ATUALIZAR",
            detalhes={"nome": record["nome"], "ativo": ativo},
            conn=conn,
        )
        return record


# =============================================================================
# INSUMOS
# =============================================================================
def list_insumos(apenas_ativos: bool = False) -> list[dict[str, Any]]:
    where = "WHERE i.ativo = TRUE" if apenas_ativos else ""
    return fetch_all(
        f"""
        SELECT
            i.id, i.sku, i.nome, i.categoria_id, c.nome AS categoria_nome,
            i.unidade_medida, i.estoque_atual, i.estoque_minimo, i.custo_medio_atual,
            i.localizacao, i.perecivel, i.ativo, i.criado_em, i.atualizado_em
        FROM insumos i
        JOIN categorias c ON c.id = i.categoria_id
        {where}
        ORDER BY i.ativo DESC, i.nome ASC
        """
    )


def create_insumo(
    *,
    sku: str,
    nome: str,
    categoria_id: int,
    unidade_medida: str,
    estoque_minimo: Decimal | float = 0,
    custo_medio_atual: Decimal | float = 0,
    localizacao: str = "Estoque Central",
    perecivel: bool = False,
    usuario_id: int,
) -> dict[str, Any]:
    sku_clean = sku.strip().upper()
    if not sku_clean or not nome.strip():
        raise ValidationError("SKU e nome do insumo são obrigatórios.")
    if unidade_medida not in {"g", "ml", "un"}:
        raise ValidationError("Unidade de medida deve ser 'g', 'ml' ou 'un'.")
    if Decimal(str(estoque_minimo)) < 0 or Decimal(str(custo_medio_atual)) < 0:
        raise ValidationError("Estoque mínimo e custo médio não podem ser negativos.")

    with get_transaction() as conn:
        dup = fetch_one("SELECT id FROM insumos WHERE sku = :sku", {"sku": sku_clean}, conn=conn)
        if dup:
            raise BusinessRuleError(f"Já existe insumo cadastrado com SKU '{sku_clean}'.")

        row = conn.execute(
            text(
                """
                INSERT INTO insumos (
                    sku, nome, categoria_id, unidade_medida, estoque_atual,
                    estoque_minimo, custo_medio_atual, localizacao, perecivel
                )
                VALUES (
                    :sku, :nome, :categoria_id, :unidade_medida, 0,
                    :estoque_minimo, :custo_medio_atual, :localizacao, :perecivel
                )
                RETURNING id, sku, nome, categoria_id, unidade_medida, estoque_atual,
                          estoque_minimo, custo_medio_atual, localizacao, perecivel, ativo
                """
            ),
            {
                "sku": sku_clean,
                "nome": nome.strip(),
                "categoria_id": int(categoria_id),
                "unidade_medida": unidade_medida,
                "estoque_minimo": Decimal(str(estoque_minimo)),
                "custo_medio_atual": Decimal(str(custo_medio_atual)),
                "localizacao": localizacao.strip() or "Estoque Central",
                "perecivel": bool(perecivel),
            },
        ).mappings().first()
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="insumos",
            entidade_id=record["id"],
            acao="CRIAR",
            detalhes={"sku": sku_clean, "nome": record["nome"], "unidade": unidade_medida},
            conn=conn,
        )
        return record


def update_insumo(
    *,
    insumo_id: int,
    nome: str,
    categoria_id: int,
    estoque_minimo: Decimal | float,
    localizacao: str,
    perecivel: bool,
    ativo: bool,
    usuario_id: int,
) -> dict[str, Any]:
    if not nome.strip():
        raise ValidationError("Nome do insumo é obrigatório.")
    if Decimal(str(estoque_minimo)) < 0:
        raise ValidationError("Estoque mínimo não pode ser negativo.")

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                UPDATE insumos
                SET nome = :nome,
                    categoria_id = :categoria_id,
                    estoque_minimo = :estoque_minimo,
                    localizacao = :localizacao,
                    perecivel = :perecivel,
                    ativo = :ativo,
                    atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, sku, nome, categoria_id, unidade_medida, estoque_atual,
                          estoque_minimo, custo_medio_atual, localizacao, perecivel, ativo
                """
            ),
            {
                "id": insumo_id,
                "nome": nome.strip(),
                "categoria_id": int(categoria_id),
                "estoque_minimo": Decimal(str(estoque_minimo)),
                "localizacao": localizacao.strip() or "Estoque Central",
                "perecivel": bool(perecivel),
                "ativo": bool(ativo),
            },
        ).mappings().first()
        if not row:
            raise NotFoundError("Insumo não encontrado.")
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="insumos",
            entidade_id=insumo_id,
            acao="ATUALIZAR",
            detalhes={"nome": record["nome"], "ativo": ativo},
            conn=conn,
        )
        return record


# =============================================================================
# PRODUTOS E FICHA TÉCNICA
# =============================================================================
def list_produtos(apenas_ativos: bool = False) -> list[dict[str, Any]]:
    where = "WHERE p.ativo = TRUE" if apenas_ativos else ""
    return fetch_all(
        f"""
        SELECT
            p.id,
            p.sku,
            p.nome,
            p.categoria_id,
            c.nome AS categoria_nome,
            p.tipo_produto,
            p.preco_venda,
            p.tempo_preparo_estimado_seg,
            p.ativo,
            p.criado_em,
            p.atualizado_em,
            COALESCE(ft.qtd_insumos, 0)::INT AS qtd_insumos_ficha,
            COALESCE(ft.custo_ficha, 0)::NUMERIC(12,4) AS custo_cmv_estimado,
            CASE
                WHEN p.preco_venda > 0
                THEN ROUND(((p.preco_venda - COALESCE(ft.custo_ficha, 0)) / p.preco_venda * 100)::NUMERIC, 2)
                ELSE 0::NUMERIC(6,2)
            END AS margem_estimada_pct
        FROM produtos p
        JOIN categorias c ON c.id = p.categoria_id
        LEFT JOIN (
            SELECT
                fti.produto_id,
                COUNT(*) AS qtd_insumos,
                SUM(fti.quantidade * i.custo_medio_atual) AS custo_ficha
            FROM ficha_tecnica_itens fti
            JOIN insumos i ON i.id = fti.insumo_id
            WHERE fti.ativo = TRUE
            GROUP BY fti.produto_id
        ) ft ON ft.produto_id = p.id
        {where}
        ORDER BY p.ativo DESC, c.nome ASC, p.nome ASC
        """
    )


def create_produto(
    *,
    sku: str,
    nome: str,
    categoria_id: int,
    tipo_produto: str,
    preco_venda: Decimal | float,
    tempo_preparo_estimado_seg: int = 180,
    usuario_id: int,
) -> dict[str, Any]:
    sku_clean = sku.strip().upper()
    preco = Decimal(str(preco_venda)).quantize(Decimal("0.01"))
    if not sku_clean or not nome.strip():
        raise ValidationError("SKU e nome do produto são obrigatórios.")
    if tipo_produto not in {"PREPARADO", "REVENDA"}:
        raise ValidationError("Tipo do produto deve ser 'PREPARADO' ou 'REVENDA'.")
    if preco <= 0:
        raise ValidationError("Preço de venda deve ser maior que zero.")
    if tempo_preparo_estimado_seg < 0:
        raise ValidationError("Tempo estimado de preparo não pode ser negativo.")

    with get_transaction() as conn:
        dup = fetch_one("SELECT id FROM produtos WHERE sku = :sku", {"sku": sku_clean}, conn=conn)
        if dup:
            raise BusinessRuleError(f"Já existe produto cadastrado com SKU '{sku_clean}'.")

        row = conn.execute(
            text(
                """
                INSERT INTO produtos (
                    sku, nome, categoria_id, tipo_produto, preco_venda, tempo_preparo_estimado_seg
                )
                VALUES (
                    :sku, :nome, :categoria_id, :tipo_produto, :preco_venda, :tempo_preparo_estimado_seg
                )
                RETURNING id, sku, nome, categoria_id, tipo_produto, preco_venda,
                          tempo_preparo_estimado_seg, ativo
                """
            ),
            {
                "sku": sku_clean,
                "nome": nome.strip(),
                "categoria_id": int(categoria_id),
                "tipo_produto": tipo_produto,
                "preco_venda": preco,
                "tempo_preparo_estimado_seg": int(tempo_preparo_estimado_seg),
            },
        ).mappings().first()
        record = dict(row)

        conn.execute(
            text(
                """
                INSERT INTO historico_precos_produtos (produto_id, preco_anterior, preco_novo, alterado_por)
                VALUES (:produto_id, NULL, :preco_novo, :alterado_por)
                """
            ),
            {
                "produto_id": record["id"],
                "preco_novo": preco,
                "alterado_por": usuario_id,
            },
        )
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="produtos",
            entidade_id=record["id"],
            acao="CRIAR",
            detalhes={"sku": sku_clean, "nome": record["nome"], "preco_venda": str(preco)},
            conn=conn,
        )
        return record


def update_produto(
    *,
    produto_id: int,
    nome: str,
    categoria_id: int,
    tipo_produto: str,
    preco_venda: Decimal | float,
    tempo_preparo_estimado_seg: int,
    ativo: bool,
    usuario_id: int,
) -> dict[str, Any]:
    preco = Decimal(str(preco_venda)).quantize(Decimal("0.01"))
    if not nome.strip():
        raise ValidationError("Nome do produto é obrigatório.")
    if tipo_produto not in {"PREPARADO", "REVENDA"}:
        raise ValidationError("Tipo de produto inválido.")
    if preco <= 0:
        raise ValidationError("Preço de venda deve ser maior que zero.")
    if tempo_preparo_estimado_seg < 0:
        raise ValidationError("Tempo de preparo não pode ser negativo.")

    with get_transaction() as conn:
        current = fetch_one(
            "SELECT id, preco_venda FROM produtos WHERE id = :id FOR UPDATE",
            {"id": produto_id},
            conn=conn,
        )
        if not current:
            raise NotFoundError("Produto não encontrado.")

        old_price = Decimal(str(current["preco_venda"])).quantize(Decimal("0.01"))
        row = conn.execute(
            text(
                """
                UPDATE produtos
                SET nome = :nome,
                    categoria_id = :categoria_id,
                    tipo_produto = :tipo_produto,
                    preco_venda = :preco_venda,
                    tempo_preparo_estimado_seg = :tempo_preparo_estimado_seg,
                    ativo = :ativo,
                    atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, sku, nome, categoria_id, tipo_produto, preco_venda,
                          tempo_preparo_estimado_seg, ativo
                """
            ),
            {
                "id": produto_id,
                "nome": nome.strip(),
                "categoria_id": int(categoria_id),
                "tipo_produto": tipo_produto,
                "preco_venda": preco,
                "tempo_preparo_estimado_seg": int(tempo_preparo_estimado_seg),
                "ativo": bool(ativo),
            },
        ).mappings().first()
        record = dict(row)

        if old_price != preco:
            conn.execute(
                text(
                    """
                    INSERT INTO historico_precos_produtos (
                        produto_id, preco_anterior, preco_novo, alterado_por
                    )
                    VALUES (:produto_id, :preco_anterior, :preco_novo, :alterado_por)
                    """
                ),
                {
                    "produto_id": produto_id,
                    "preco_anterior": old_price,
                    "preco_novo": preco,
                    "alterado_por": usuario_id,
                },
            )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="produtos",
            entidade_id=produto_id,
            acao="ATUALIZAR",
            detalhes={
                "nome": record["nome"],
                "preco_anterior": str(old_price),
                "preco_novo": str(preco),
                "ativo": ativo,
            },
            conn=conn,
        )
        return record


def list_historico_precos(produto_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT h.id, h.preco_anterior, h.preco_novo, h.criado_em,
               COALESCE(u.nome, 'Sistema') AS alterado_por_nome
        FROM historico_precos_produtos h
        LEFT JOIN usuarios u ON u.id = h.alterado_por
        WHERE h.produto_id = :produto_id
        ORDER BY h.criado_em DESC
        """,
        {"produto_id": produto_id},
    )


def list_ficha_tecnica(produto_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT
            fti.id,
            fti.produto_id,
            fti.insumo_id,
            i.sku AS insumo_sku,
            i.nome AS insumo_nome,
            i.unidade_medida,
            fti.quantidade,
            i.custo_medio_atual,
            ROUND((fti.quantidade * i.custo_medio_atual)::NUMERIC, 4) AS custo_item
        FROM ficha_tecnica_itens fti
        JOIN insumos i ON i.id = fti.insumo_id
        WHERE fti.produto_id = :produto_id
          AND fti.ativo = TRUE
        ORDER BY i.nome ASC
        """,
        {"produto_id": produto_id},
    )


def upsert_ficha_tecnica_item(
    *,
    produto_id: int,
    insumo_id: int,
    quantidade: Decimal | float,
    usuario_id: int,
) -> dict[str, Any]:
    qtd = Decimal(str(quantidade))
    if qtd <= 0:
        raise ValidationError("A quantidade do insumo na ficha técnica deve ser maior que zero.")

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO ficha_tecnica_itens (produto_id, insumo_id, quantidade, ativo)
                VALUES (:produto_id, :insumo_id, :quantidade, TRUE)
                ON CONFLICT (produto_id, insumo_id)
                DO UPDATE SET quantidade = EXCLUDED.quantidade, ativo = TRUE, atualizado_em = NOW()
                RETURNING id, produto_id, insumo_id, quantidade, ativo
                """
            ),
            {
                "produto_id": int(produto_id),
                "insumo_id": int(insumo_id),
                "quantidade": qtd,
            },
        ).mappings().first()
        record = dict(row)
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="ficha_tecnica_itens",
            entidade_id=record["id"],
            acao="UPSERT",
            detalhes={
                "produto_id": produto_id,
                "insumo_id": insumo_id,
                "quantidade": str(qtd),
            },
            conn=conn,
        )
        return record


def remove_ficha_tecnica_item(*, item_id: int, usuario_id: int) -> None:
    """Inativa logicamente um insumo da ficha técnica (sem apagar histórico)."""
    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                UPDATE ficha_tecnica_itens
                SET ativo = FALSE, atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, produto_id, insumo_id
                """
            ),
            {"id": item_id},
        ).mappings().first()
        if not row:
            raise NotFoundError("Item de ficha técnica não encontrado.")
        log_audit_event(
            usuario_id=usuario_id,
            modulo="CADASTROS",
            entidade="ficha_tecnica_itens",
            entidade_id=item_id,
            acao="INATIVAR",
            detalhes={"produto_id": row["produto_id"], "insumo_id": row["insumo_id"]},
            conn=conn,
        )
