"""Serviço de Vendas / PDV integrado a Ficha Técnica, Estoque, Operacional e Financeiro."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import (
    BusinessRuleError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)


def _get_or_create_categoria_vendas(conn: Connection) -> int:
    row = fetch_one(
        """
        SELECT id FROM categorias
        WHERE tipo = 'RECEITA' AND LOWER(nome) LIKE '%venda%'
        ORDER BY id ASC
        LIMIT 1
        """,
        conn=conn,
    )
    if row:
        return int(row["id"])

    row = fetch_one(
        "SELECT id FROM categorias WHERE tipo = 'RECEITA' ORDER BY id ASC LIMIT 1",
        conn=conn,
    )
    if row:
        return int(row["id"])

    inserted = conn.execute(
        text(
            """
            INSERT INTO categorias (nome, tipo)
            VALUES ('Vendas de Cardápio', 'RECEITA')
            RETURNING id
            """
        )
    ).scalar()
    return int(inserted)


def verificar_disponibilidade_carrinho(itens: list[dict[str, Any]]) -> dict[str, Any]:
    """Verifica previamente se há saldo de insumos suficiente para todos os produtos do carrinho."""
    if not itens:
        return {"disponivel": False, "faltantes": [], "sem_ficha": []}

    consumo_por_insumo: dict[int, Decimal] = defaultdict(lambda: Decimal("0.000"))
    sem_ficha: list[str] = []

    for item in itens:
        pid = int(item["produto_id"])
        qtd = int(item["quantidade"])
        if qtd <= 0:
            continue
        produto = fetch_one("SELECT id, nome FROM produtos WHERE id = :id", {"id": pid})
        if not produto:
            continue
        ficha = fetch_all(
            """
            SELECT insumo_id, quantidade
            FROM ficha_tecnica_itens
            WHERE produto_id = :pid AND ativo = TRUE
            """,
            {"pid": pid},
        )
        if not ficha:
            sem_ficha.append(produto["nome"])
            continue
        for f in ficha:
            consumo_por_insumo[int(f["insumo_id"])] += Decimal(str(f["quantidade"])) * qtd

    faltantes: list[dict[str, Any]] = []
    for iid, necessario in consumo_por_insumo.items():
        insumo = fetch_one(
            "SELECT id, sku, nome, unidade_medida, estoque_atual FROM insumos WHERE id = :id",
            {"id": iid},
        )
        if not insumo:
            continue
        atual = Decimal(str(insumo["estoque_atual"]))
        if atual < necessario:
            faltantes.append(
                {
                    "insumo_id": iid,
                    "sku": insumo["sku"],
                    "nome": insumo["nome"],
                    "unidade_medida": insumo["unidade_medida"],
                    "necessario": float(necessario),
                    "disponivel": float(atual),
                    "faltando": float((necessario - atual).quantize(Decimal("0.001"))),
                }
            )

    return {
        "disponivel": (len(faltantes) == 0 and len(sem_ficha) == 0),
        "faltantes": faltantes,
        "sem_ficha": sem_ficha,
    }


def registrar_venda(
    *,
    cliente_id: int,
    canal_venda: str,
    forma_pagamento: str,
    itens: list[dict[str, Any]],
    usuario_id: int,
    desconto: Decimal | float = 0,
    observacoes_preparo: str = "",
    prioridade: str = "NORMAL",
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """
    Executa venda completa em transação ACID única:
      1) Valida produtos e fichas técnicas;
      2) Trava insumos (FOR UPDATE ordenado por ID) e impede estoque negativo;
      3) Calcula CMV histórico a partir do custo médio vigente;
      4) Persiste venda + itens com snapshots imutáveis;
      5) Baixa insumos em movimentacoes_estoque (SAIDA_VENDA);
      6) Gera ordem de preparo (NA_FILA) + histórico no Operacional;
      7) Gera Conta a Receber (e liquida no caixa se pagamento imediato);
      8) Registra evento em audit_logs.
    """
    if not itens:
        raise ValidationError("Adicione ao menos um produto ao pedido.")
    if canal_venda not in {"BALCAO", "MESA", "RETIRADA", "DELIVERY"}:
        raise ValidationError("Canal de venda inválido.")
    if forma_pagamento not in {"PIX", "DEBITO", "CREDITO", "DINHEIRO", "FATURADO"}:
        raise ValidationError("Forma de pagamento inválida.")
    if prioridade not in {"NORMAL", "ALTA"}:
        raise ValidationError("Prioridade de preparo inválida.")

    desconto_dec = Decimal(str(desconto)).quantize(Decimal("0.01"))
    if desconto_dec < 0:
        raise ValidationError("Desconto não pode ser negativo.")

    # Agrega itens repetidos do mesmo produto
    agrupado: dict[int, int] = defaultdict(int)
    for item in itens:
        pid = int(item["produto_id"])
        qtd = int(item["quantidade"])
        if qtd <= 0:
            raise ValidationError("Quantidade do produto deve ser maior que zero.")
        agrupado[pid] += qtd

    ts = occurred_at or datetime.now(timezone.utc)
    numero_venda = f"VND-{ts.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    with get_transaction() as conn:
        cliente = fetch_one(
            "SELECT id, nome, ativo FROM clientes WHERE id = :id",
            {"id": int(cliente_id)},
            conn=conn,
        )
        if not cliente or not cliente["ativo"]:
            raise BusinessRuleError("Cliente inválido ou inativo.")

        produtos_info: dict[int, dict[str, Any]] = {}
        fichas_por_produto: dict[int, list[dict[str, Any]]] = {}
        consumo_total_insumos: dict[int, Decimal] = defaultdict(lambda: Decimal("0.000"))

        for pid, qtd in agrupado.items():
            prod = fetch_one(
                """
                SELECT id, sku, nome, preco_venda, tipo_produto, ativo
                FROM produtos
                WHERE id = :id
                """,
                {"id": pid},
                conn=conn,
            )
            if not prod or not prod["ativo"]:
                raise BusinessRuleError(f"Produto ID {pid} não encontrado ou inativo.")
            produtos_info[pid] = prod

            ficha = fetch_all(
                """
                SELECT insumo_id, quantidade
                FROM ficha_tecnica_itens
                WHERE produto_id = :pid AND ativo = TRUE
                ORDER BY insumo_id ASC
                """,
                {"pid": pid},
                conn=conn,
            )
            if not ficha:
                raise BusinessRuleError(
                    f"Produto '{prod['nome']}' não possui Ficha Técnica cadastrada. "
                    "Cadastre os insumos da receita antes de vender."
                )
            fichas_por_produto[pid] = ficha
            for f in ficha:
                consumo_total_insumos[int(f["insumo_id"])] += (
                    Decimal(str(f["quantidade"])) * qtd
                ).quantize(Decimal("0.001"))

        # Lock pessimista ordenado por insumo_id para garantir atomicidade sem deadlock
        insumos_locked: dict[int, dict[str, Any]] = {}
        faltantes: list[dict[str, Any]] = []
        for iid in sorted(consumo_total_insumos.keys()):
            ins = fetch_one(
                """
                SELECT id, sku, nome, unidade_medida, estoque_atual, custo_medio_atual, ativo
                FROM insumos
                WHERE id = :id
                FOR UPDATE
                """,
                {"id": iid},
                conn=conn,
            )
            if not ins or not ins["ativo"]:
                raise BusinessRuleError(f"Insumo ID {iid} da ficha técnica está inativo.")
            insumos_locked[iid] = ins

            atual = Decimal(str(ins["estoque_atual"])).quantize(Decimal("0.001"))
            necessario = consumo_total_insumos[iid]
            if atual < necessario:
                faltantes.append(
                    {
                        "insumo_id": iid,
                        "sku": ins["sku"],
                        "nome": ins["nome"],
                        "unidade_medida": ins["unidade_medida"],
                        "necessario": float(necessario),
                        "disponivel": float(atual),
                    }
                )

        if faltantes:
            nomes = ", ".join(
                f"{f['nome']} (precisa {f['necessario']} {f['unidade_medida']}, tem {f['disponivel']})"
                for f in faltantes
            )
            raise InsufficientStockError(
                f"Estoque insuficiente para concluir a venda: {nomes}.",
                missing_items=faltantes,
            )

        # Calcula totais, CMV unitário e CMV total
        subtotal_venda = Decimal("0.00")
        cmv_total_venda = Decimal("0.00")
        itens_para_inserir: list[dict[str, Any]] = []

        for pid, qtd in agrupado.items():
            prod = produtos_info[pid]
            preco_unit = Decimal(str(prod["preco_venda"])).quantize(Decimal("0.01"))
            custo_unit_cmv = Decimal("0.0000")
            for f in fichas_por_produto[pid]:
                ins = insumos_locked[int(f["insumo_id"])]
                custo_unit_cmv += Decimal(str(f["quantidade"])) * Decimal(
                    str(ins["custo_medio_atual"])
                )
            custo_unit_cmv = custo_unit_cmv.quantize(Decimal("0.0001"))
            subtotal_item = (preco_unit * qtd).quantize(Decimal("0.01"))
            subtotal_venda += subtotal_item
            cmv_total_venda += (custo_unit_cmv * qtd).quantize(Decimal("0.01"))

            itens_para_inserir.append(
                {
                    "produto_id": pid,
                    "quantidade": qtd,
                    "preco_unitario_snapshot": preco_unit,
                    "custo_unitario_cmv_snapshot": custo_unit_cmv,
                    "subtotal": subtotal_item,
                }
            )

        if desconto_dec > subtotal_venda:
            raise ValidationError("O desconto não pode ser maior que o subtotal da venda.")

        valor_total = (subtotal_venda - desconto_dec).quantize(Decimal("0.01"))
        if valor_total <= 0:
            raise ValidationError("O valor total líquido da venda deve ser maior que zero.")

        # 1. Insere venda
        venda_row = conn.execute(
            text(
                """
                INSERT INTO vendas (
                    numero_venda, cliente_id, usuario_id, canal_venda, forma_pagamento,
                    status, subtotal, desconto, valor_total, custo_total_cmv,
                    data_venda, criado_em, atualizado_em
                )
                VALUES (
                    :numero_venda, :cliente_id, :usuario_id, :canal_venda, :forma_pagamento,
                    'CONCLUIDA', :subtotal, :desconto, :valor_total, :custo_total_cmv,
                    :ts, :ts, :ts
                )
                RETURNING id, numero_venda, cliente_id, canal_venda, forma_pagamento,
                          status, subtotal, desconto, valor_total, custo_total_cmv, data_venda
                """
            ),
            {
                "numero_venda": numero_venda,
                "cliente_id": int(cliente_id),
                "usuario_id": int(usuario_id),
                "canal_venda": canal_venda,
                "forma_pagamento": forma_pagamento,
                "subtotal": subtotal_venda,
                "desconto": desconto_dec,
                "valor_total": valor_total,
                "custo_total_cmv": cmv_total_venda,
                "ts": ts,
            },
        ).mappings().first()
        venda = dict(venda_row)
        venda_id = int(venda["id"])

        # 2. Insere itens da venda
        for it in itens_para_inserir:
            conn.execute(
                text(
                    """
                    INSERT INTO venda_itens (
                        venda_id, produto_id, quantidade, preco_unitario_snapshot,
                        custo_unitario_cmv_snapshot, subtotal, criado_em
                    )
                    VALUES (
                        :venda_id, :produto_id, :quantidade, :preco_unit,
                        :custo_unit, :subtotal, :ts
                    )
                    """
                ),
                {
                    "venda_id": venda_id,
                    "produto_id": it["produto_id"],
                    "quantidade": it["quantidade"],
                    "preco_unit": it["preco_unitario_snapshot"],
                    "custo_unit": it["custo_unitario_cmv_snapshot"],
                    "subtotal": it["subtotal"],
                    "ts": ts,
                },
            )

        # 3. Baixa insumos no estoque (append-only)
        for iid in sorted(consumo_total_insumos.keys()):
            ins = insumos_locked[iid]
            qtd_saida = consumo_total_insumos[iid]
            saldo_ant = Decimal(str(ins["estoque_atual"])).quantize(Decimal("0.001"))
            saldo_pos = (saldo_ant - qtd_saida).quantize(Decimal("0.001"))
            custo_snap = Decimal(str(ins["custo_medio_atual"])).quantize(Decimal("0.0001"))

            conn.execute(
                text(
                    """
                    UPDATE insumos
                    SET estoque_atual = :saldo_pos, atualizado_em = :ts
                    WHERE id = :id
                    """
                ),
                {"id": iid, "saldo_pos": saldo_pos, "ts": ts},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO movimentacoes_estoque (
                        insumo_id, tipo_movimentacao, quantidade, saldo_anterior, saldo_posterior,
                        custo_unitario_snapshot, origem_modulo, origem_id, motivo, usuario_id, criado_em
                    )
                    VALUES (
                        :insumo_id, 'SAIDA_VENDA', :quantidade, :saldo_ant, :saldo_pos,
                        :custo_snap, 'VENDAS', :origem_id, :motivo, :usuario_id, :ts
                    )
                    """
                ),
                {
                    "insumo_id": iid,
                    "quantidade": qtd_saida,
                    "saldo_ant": saldo_ant,
                    "saldo_pos": saldo_pos,
                    "custo_snap": custo_snap,
                    "origem_id": venda_id,
                    "motivo": f"Baixa automática ficha técnica — {numero_venda}",
                    "usuario_id": int(usuario_id),
                    "ts": ts,
                },
            )

        # 4. Cria Ordem de Preparo no Operacional (Barista) + histórico inicial
        ordem_row = conn.execute(
            text(
                """
                INSERT INTO ordens_preparo (
                    venda_id, status, prioridade, criado_em, observacoes
                )
                VALUES (
                    :venda_id, 'NA_FILA', :prioridade, :ts, :obs
                )
                RETURNING id
                """
            ),
            {
                "venda_id": venda_id,
                "prioridade": prioridade,
                "ts": ts,
                "obs": observacoes_preparo.strip() or None,
            },
        ).mappings().first()
        ordem_id = int(ordem_row["id"])

        conn.execute(
            text(
                """
                INSERT INTO ordem_preparo_historico (
                    ordem_preparo_id, status_anterior, status_novo, usuario_id, criado_em
                )
                VALUES (:ordem_id, NULL, 'NA_FILA', :usuario_id, :ts)
                """
            ),
            {"ordem_id": ordem_id, "usuario_id": int(usuario_id), "ts": ts},
        )

        # 5. Integração Financeira: Conta a Receber + Fluxo de Caixa (se à vista)
        categoria_receita_id = _get_or_create_categoria_vendas(conn)
        pagamento_imediato = forma_pagamento in {"PIX", "DEBITO", "DINHEIRO"}
        prazo_recebimento = 0 if pagamento_imediato else (30 if forma_pagamento == "CREDITO" else 15)
        data_comp = ts.date()
        data_venc = data_comp + timedelta(days=prazo_recebimento)

        titulo_row = conn.execute(
            text(
                """
                INSERT INTO titulos_financeiros (
                    tipo, categoria_id, descricao, origem_modulo, origem_id,
                    cliente_id, valor_original, valor_pago, data_competencia, data_vencimento,
                    data_liquidacao, status, forma_pagamento, usuario_id, criado_em, atualizado_em
                )
                VALUES (
                    'RECEBER', :categoria_id, :descricao, 'VENDAS', :origem_id,
                    :cliente_id, :valor_total, :valor_pago, :data_comp, :data_venc,
                    :data_liq, :status, :forma_pagamento, :usuario_id, :ts, :ts
                )
                RETURNING id
                """
            ),
            {
                "categoria_id": categoria_receita_id,
                "descricao": f"Venda {numero_venda} — {cliente['nome']} ({canal_venda})",
                "origem_id": venda_id,
                "cliente_id": int(cliente_id),
                "valor_total": valor_total,
                "valor_pago": valor_total if pagamento_imediato else Decimal("0.00"),
                "data_comp": data_comp,
                "data_venc": data_venc,
                "data_liq": ts if pagamento_imediato else None,
                "status": "PAGO" if pagamento_imediato else "ABERTO",
                "forma_pagamento": forma_pagamento,
                "usuario_id": int(usuario_id),
                "ts": ts,
            },
        ).mappings().first()
        titulo_id = int(titulo_row["id"])

        if pagamento_imediato:
            conn.execute(
                text(
                    """
                    INSERT INTO movimentacoes_financeiras (
                        titulo_id, tipo_fluxo, valor, forma_pagamento, data_movimentacao,
                        descricao, usuario_id, criado_em
                    )
                    VALUES (
                        :titulo_id, 'ENTRADA', :valor, :forma_pagamento, :ts,
                        :descricao, :usuario_id, :ts
                    )
                    """
                ),
                {
                    "titulo_id": titulo_id,
                    "valor": valor_total,
                    "forma_pagamento": forma_pagamento,
                    "ts": ts,
                    "descricao": f"Recebimento venda {numero_venda} ({forma_pagamento})",
                    "usuario_id": int(usuario_id),
                },
            )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="VENDAS",
            entidade="vendas",
            entidade_id=venda_id,
            acao="REGISTRAR_VENDA",
            detalhes={
                "numero_venda": numero_venda,
                "valor_total": str(valor_total),
                "cmv_total": str(cmv_total_venda),
                "ordem_preparo_id": ordem_id,
                "titulo_financeiro_id": titulo_id,
            },
            conn=conn,
        )

        venda["ordem_preparo_id"] = ordem_id
        venda["titulo_financeiro_id"] = titulo_id
        return venda


def cancelar_venda(
    *,
    venda_id: int,
    motivo: str,
    usuario_id: int,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """
    Cancela venda sem apagar registros históricos:
      - Se ordem de preparo ainda estava NA_FILA: devolve insumos ao estoque (ESTORNO_VENDA).
      - Se ordem já estava EM_PREPARO/PRONTO/ENTREGUE: registra custo como perda operacional
        (sem retornar insumo já preparado ao estoque).
      - Cancela título financeiro e, se já havia entrado no caixa, lança SAIDA de estorno.
    """
    if not motivo.strip():
        raise ValidationError("Informe o motivo do cancelamento da venda.")

    ts = occurred_at or datetime.now(timezone.utc)

    with get_transaction() as conn:
        venda = fetch_one(
            "SELECT * FROM vendas WHERE id = :id FOR UPDATE",
            {"id": int(venda_id)},
            conn=conn,
        )
        if not venda:
            raise NotFoundError("Venda não encontrada.")
        if venda["status"] == "CANCELADA":
            raise BusinessRuleError("Esta venda já foi cancelada anteriormente.")

        ordem = fetch_one(
            "SELECT * FROM ordens_preparo WHERE venda_id = :vid FOR UPDATE",
            {"vid": int(venda_id)},
            conn=conn,
        )
        ordem_status_ant = ordem["status"] if ordem else "NA_FILA"

        # 1. Marca venda como cancelada
        conn.execute(
            text(
                """
                UPDATE vendas
                SET status = 'CANCELADA',
                    motivo_cancelamento = :motivo,
                    cancelada_em = :ts,
                    cancelada_por = :uid,
                    atualizado_em = :ts
                WHERE id = :id
                """
            ),
            {"id": int(venda_id), "motivo": motivo.strip(), "ts": ts, "uid": int(usuario_id)},
        )

        # 2. Cancela ordem de preparo
        if ordem and ordem["status"] != "CANCELADO":
            conn.execute(
                text(
                    """
                    UPDATE ordens_preparo
                    SET status = 'CANCELADO'
                    WHERE id = :oid
                    """
                ),
                {"oid": int(ordem["id"])},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO ordem_preparo_historico (
                        ordem_preparo_id, status_anterior, status_novo, usuario_id, criado_em
                    )
                    VALUES (:oid, :ant, 'CANCELADO', :uid, :ts)
                    """
                ),
                {
                    "oid": int(ordem["id"]),
                    "ant": ordem_status_ant,
                    "uid": int(usuario_id),
                    "ts": ts,
                },
            )

        # 3. Estoque / Perda conforme estágio do preparo
        saidas_venda = fetch_all(
            """
            SELECT insumo_id, quantidade, custo_unitario_snapshot
            FROM movimentacoes_estoque
            WHERE origem_modulo = 'VENDAS'
              AND origem_id = :vid
              AND tipo_movimentacao = 'SAIDA_VENDA'
            ORDER BY insumo_id ASC
            """,
            {"vid": int(venda_id)},
            conn=conn,
        )

        estoque_estornado = False
        if ordem_status_ant == "NA_FILA":
            estoque_estornado = True
            for s in saidas_venda:
                iid = int(s["insumo_id"])
                qtd = Decimal(str(s["quantidade"])).quantize(Decimal("0.001"))
                custo_snap = Decimal(str(s["custo_unitario_snapshot"])).quantize(Decimal("0.0001"))
                ins = fetch_one(
                    "SELECT estoque_atual FROM insumos WHERE id = :id FOR UPDATE",
                    {"id": iid},
                    conn=conn,
                )
                saldo_ant = Decimal(str(ins["estoque_atual"])).quantize(Decimal("0.001"))
                saldo_pos = (saldo_ant + qtd).quantize(Decimal("0.001"))

                conn.execute(
                    text("UPDATE insumos SET estoque_atual = :pos, atualizado_em = :ts WHERE id = :id"),
                    {"id": iid, "pos": saldo_pos, "ts": ts},
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO movimentacoes_estoque (
                            insumo_id, tipo_movimentacao, quantidade, saldo_anterior, saldo_posterior,
                            custo_unitario_snapshot, origem_modulo, origem_id, motivo, usuario_id, criado_em
                        )
                        VALUES (
                            :iid, 'ESTORNO_VENDA', :qtd, :ant, :pos,
                            :custo, 'VENDAS', :vid, :motivo, :uid, :ts
                        )
                        """
                    ),
                    {
                        "iid": iid,
                        "qtd": qtd,
                        "ant": saldo_ant,
                        "pos": saldo_pos,
                        "custo": custo_snap,
                        "vid": int(venda_id),
                        "motivo": f"Estorno por cancelamento antes do preparo — {venda['numero_venda']}",
                        "uid": int(usuario_id),
                        "ts": ts,
                    },
                )
        else:
            # Pedido já preparado/em preparo: registra perda sem alterar saldo novamente (já saiu na venda)
            for s in saidas_venda:
                qtd = Decimal(str(s["quantidade"])).quantize(Decimal("0.001"))
                custo_est = (qtd * Decimal(str(s["custo_unitario_snapshot"]))).quantize(
                    Decimal("0.01")
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO registros_perdas (
                            insumo_id, quantidade, motivo, custo_estimado, observacoes, usuario_id, criado_em
                        )
                        VALUES (
                            :iid, :qtd, 'QUEBRA_PREPARO', :custo, :obs, :uid, :ts
                        )
                        """
                    ),
                    {
                        "iid": int(s["insumo_id"]),
                        "qtd": qtd,
                        "custo": custo_est,
                        "obs": f"Cancelamento pós-preparo da venda {venda['numero_venda']}: {motivo.strip()}",
                        "uid": int(usuario_id),
                        "ts": ts,
                    },
                )

        # 4. Estorno financeiro
        titulo = fetch_one(
            """
            SELECT * FROM titulos_financeiros
            WHERE origem_modulo = 'VENDAS' AND origem_id = :vid
            FOR UPDATE
            """,
            {"vid": int(venda_id)},
            conn=conn,
        )
        if titulo and titulo["status"] != "CANCELADO":
            estava_pago = titulo["status"] == "PAGO" and Decimal(str(titulo["valor_pago"])) > 0
            conn.execute(
                text(
                    """
                    UPDATE titulos_financeiros
                    SET status = 'CANCELADO', atualizado_em = :ts
                    WHERE id = :tid
                    """
                ),
                {"tid": int(titulo["id"]), "ts": ts},
            )
            if estava_pago:
                conn.execute(
                    text(
                        """
                        INSERT INTO movimentacoes_financeiras (
                            titulo_id, tipo_fluxo, valor, forma_pagamento, data_movimentacao,
                            descricao, usuario_id, criado_em
                        )
                        VALUES (
                            :tid, 'SAIDA', :valor, :forma, :ts, :desc, :uid, :ts
                        )
                        """
                    ),
                    {
                        "tid": int(titulo["id"]),
                        "valor": Decimal(str(titulo["valor_pago"])),
                        "forma": titulo["forma_pagamento"] or venda["forma_pagamento"],
                        "ts": ts,
                        "desc": f"Estorno financeiro cancelamento venda {venda['numero_venda']}",
                        "uid": int(usuario_id),
                    },
                )

        log_audit_event(
            usuario_id=usuario_id,
            modulo="VENDAS",
            entidade="vendas",
            entidade_id=int(venda_id),
            acao="CANCELAR_VENDA",
            detalhes={
                "numero_venda": venda["numero_venda"],
                "motivo": motivo.strip(),
                "estoque_estornado": estoque_estornado,
                "status_ordem_anterior": ordem_status_ant,
            },
            conn=conn,
        )
        return {
            "venda_id": int(venda_id),
            "numero_venda": venda["numero_venda"],
            "status": "CANCELADA",
            "estoque_estornado": estoque_estornado,
        }


def list_vendas(
    *,
    status: str | None = None,
    canal_venda: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": int(limit)}
    if status and status != "Todos":
        clauses.append("v.status = :status")
        params["status"] = status
    if canal_venda and canal_venda != "Todos":
        clauses.append("v.canal_venda = :canal")
        params["canal"] = canal_venda
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    return fetch_all(
        f"""
        SELECT
            v.id,
            v.numero_venda,
            v.data_venda,
            c.nome AS cliente_nome,
            v.canal_venda,
            v.forma_pagamento,
            v.status,
            v.subtotal,
            v.desconto,
            v.valor_total,
            v.custo_total_cmv,
            (v.valor_total - v.custo_total_cmv)::NUMERIC(12,2) AS margem_bruta,
            COALESCE(op.status, '-') AS status_preparo,
            u.nome AS operador_nome
        FROM vendas v
        JOIN clientes c ON c.id = v.cliente_id
        JOIN usuarios u ON u.id = v.usuario_id
        LEFT JOIN ordens_preparo op ON op.venda_id = v.id
        {where}
        ORDER BY v.data_venda DESC, v.id DESC
        LIMIT :limit
        """,
        params,
    )


def get_venda_detalhes(venda_id: int) -> dict[str, Any]:
    venda = fetch_one(
        """
        SELECT
            v.*,
            c.nome AS cliente_nome,
            c.cpf_cnpj AS cliente_cpf_cnpj,
            c.tipo_cliente,
            u.nome AS operador_nome,
            op.id AS ordem_preparo_id,
            op.status AS status_preparo,
            tf.id AS titulo_financeiro_id,
            tf.status AS status_financeiro
        FROM vendas v
        JOIN clientes c ON c.id = v.cliente_id
        JOIN usuarios u ON u.id = v.usuario_id
        LEFT JOIN ordens_preparo op ON op.venda_id = v.id
        LEFT JOIN titulos_financeiros tf
               ON tf.origem_modulo = 'VENDAS' AND tf.origem_id = v.id
        WHERE v.id = :id
        """,
        {"id": int(venda_id)},
    )
    if not venda:
        raise NotFoundError("Venda não encontrada.")

    itens = fetch_all(
        """
        SELECT
            vi.id, vi.produto_id, p.sku AS produto_sku, p.nome AS produto_nome,
            vi.quantidade, vi.preco_unitario_snapshot, vi.custo_unitario_cmv_snapshot, vi.subtotal
        FROM venda_itens vi
        JOIN produtos p ON p.id = vi.produto_id
        WHERE vi.venda_id = :vid
        ORDER BY vi.id ASC
        """,
        {"vid": int(venda_id)},
    )
    venda["itens"] = itens
    return venda
