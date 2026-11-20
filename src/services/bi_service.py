"""Serviço Analítico (Camada BI — 2ª VA) conectado diretamente ao PostgreSQL."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from src.db.queries import fetch_all, fetch_df, fetch_one


def get_bi_filter_options() -> dict[str, Any]:
    """Carrega limites de datas, canais e categorias reais presentes no banco."""
    bounds = fetch_one(
        """
        SELECT
            MIN(DATE(data_venda AT TIME ZONE 'America/Sao_Paulo')) AS min_date,
            MAX(DATE(data_venda AT TIME ZONE 'America/Sao_Paulo')) AS max_date
        FROM vendas
        WHERE status = 'CONCLUIDA'
        """
    )
    today = date.today()
    min_date = bounds["min_date"] if bounds and bounds["min_date"] else today - timedelta(days=90)
    max_date = bounds["max_date"] if bounds and bounds["max_date"] else today

    canais = [
        r["canal_venda"]
        for r in fetch_all("SELECT DISTINCT canal_venda FROM vendas ORDER BY canal_venda ASC")
    ] or ["BALCAO", "MESA", "RETIRADA", "DELIVERY"]

    categorias = [
        r["nome"]
        for r in fetch_all(
            "SELECT DISTINCT nome FROM categorias WHERE tipo = 'PRODUTO' AND ativo = TRUE ORDER BY nome ASC"
        )
    ]
    return {
        "min_date": min_date,
        "max_date": max_date,
        "canais": canais,
        "categorias": categorias,
    }


def _build_canal_filter(canais: list[str] | None, alias: str = "") -> tuple[str, dict[str, Any]]:
    prefix = f"{alias}." if alias else ""
    if not canais:
        return "", {}
    placeholders = ", ".join(f":canal_{idx}" for idx in range(len(canais)))
    params = {f"canal_{idx}": val for idx, val in enumerate(canais)}
    return f" AND {prefix}canal_venda IN ({placeholders})", params


def _build_categoria_filter(
    categorias: list[str] | None, col: str = "categoria_nome"
) -> tuple[str, dict[str, Any]]:
    if not categorias:
        return "", {}
    placeholders = ", ".join(f":cat_{idx}" for idx in range(len(categorias)))
    params = {f"cat_{idx}": val for idx, val in enumerate(categorias)}
    return f" AND {col} IN ({placeholders})", params


def get_kpis_executivos(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
) -> dict[str, Any]:
    """Calcula KPIs comerciais/financeiros do período e variação frente ao período anterior."""
    delta_days = max(1, (data_fim - data_inicio).days + 1)
    prev_fim = data_inicio - timedelta(days=1)
    prev_inicio = prev_fim - timedelta(days=delta_days - 1)

    canal_sql, canal_params = _build_canal_filter(canais)

    def _query_window(d_ini: date, d_fim: date) -> dict[str, float]:
        row = fetch_one(
            f"""
            SELECT
                COALESCE(SUM(qtd_vendas), 0)::INT AS qtd_vendas,
                COALESCE(SUM(receita_bruta), 0)::NUMERIC(14,2) AS receita_bruta,
                COALESCE(SUM(total_descontos), 0)::NUMERIC(14,2) AS total_descontos,
                COALESCE(SUM(receita_liquida), 0)::NUMERIC(14,2) AS receita_liquida,
                COALESCE(SUM(cmv_total), 0)::NUMERIC(14,2) AS cmv_total,
                COALESCE(SUM(margem_bruta), 0)::NUMERIC(14,2) AS margem_bruta
            FROM vw_bi_vendas_diarias
            WHERE data_dia BETWEEN :d_ini AND :d_fim
            {canal_sql}
            """,
            {"d_ini": d_ini, "d_fim": d_fim, **canal_params},
        ) or {}
        qtd = int(row.get("qtd_vendas") or 0)
        receita = float(row.get("receita_liquida") or 0)
        cmv = float(row.get("cmv_total") or 0)
        margem = float(row.get("margem_bruta") or 0)
        ticket = round(receita / qtd, 2) if qtd > 0 else 0.0
        margem_pct = round((margem / receita) * 100.0, 2) if receita > 0 else 0.0
        return {
            "qtd_vendas": qtd,
            "receita_bruta": float(row.get("receita_bruta") or 0),
            "total_descontos": float(row.get("total_descontos") or 0),
            "receita_liquida": receita,
            "cmv_total": cmv,
            "margem_bruta": margem,
            "margem_bruta_pct": margem_pct,
            "ticket_medio": ticket,
        }

    atual = _query_window(data_inicio, data_fim)
    anterior = _query_window(prev_inicio, prev_fim)

    # Taxa de cancelamento no período
    canc_row = fetch_one(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE status = 'CANCELADA')::INT AS canceladas,
            COUNT(*)::INT AS total
        FROM vendas
        WHERE DATE(data_venda AT TIME ZONE 'America/Sao_Paulo') BETWEEN :d_ini AND :d_fim
        {canal_sql}
        """,
        {"d_ini": data_inicio, "d_fim": data_fim, **canal_params},
    ) or {"canceladas": 0, "total": 0}
    total_pedidos = int(canc_row["total"] or 0)
    canceladas = int(canc_row["canceladas"] or 0)
    taxa_cancelamento = round((canceladas / total_pedidos) * 100.0, 2) if total_pedidos > 0 else 0.0

    # Custo de perdas no período
    perdas_row = fetch_one(
        """
        SELECT COALESCE(SUM(custo_estimado), 0)::NUMERIC(14,2) AS custo_perdas
        FROM registros_perdas
        WHERE DATE(criado_em AT TIME ZONE 'America/Sao_Paulo') BETWEEN :d_ini AND :d_fim
        """,
        {"d_ini": data_inicio, "d_fim": data_fim},
    ) or {"custo_perdas": 0}

    def _pct_delta(cur: float, prev: float) -> float | None:
        if prev == 0:
            return None
        return round(((cur - prev) / abs(prev)) * 100.0, 1)

    return {
        **atual,
        "canceladas": canceladas,
        "taxa_cancelamento_pct": taxa_cancelamento,
        "custo_perdas": float(perdas_row["custo_perdas"] or 0),
        "delta_receita_pct": _pct_delta(atual["receita_liquida"], anterior["receita_liquida"]),
        "delta_vendas_pct": _pct_delta(atual["qtd_vendas"], anterior["qtd_vendas"]),
        "delta_ticket_pct": _pct_delta(atual["ticket_medio"], anterior["ticket_medio"]),
        "delta_margem_pp": round(atual["margem_bruta_pct"] - anterior["margem_bruta_pct"], 2)
        if anterior["qtd_vendas"] > 0
        else None,
        "periodo_anterior": (prev_inicio, prev_fim),
    }


def get_vendas_temporais(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
) -> pd.DataFrame:
    canal_sql, canal_params = _build_canal_filter(canais)
    df = fetch_df(
        f"""
        SELECT
            data_dia,
            SUM(qtd_vendas)::INT AS qtd_vendas,
            SUM(receita_liquida)::NUMERIC(14,2) AS receita_liquida,
            SUM(cmv_total)::NUMERIC(14,2) AS cmv_total,
            SUM(margem_bruta)::NUMERIC(14,2) AS margem_bruta
        FROM vw_bi_vendas_diarias
        WHERE data_dia BETWEEN :d_ini AND :d_fim
        {canal_sql}
        GROUP BY data_dia
        ORDER BY data_dia ASC
        """,
        {"d_ini": data_inicio, "d_fim": data_fim, **canal_params},
    )
    if not df.empty:
        for col in ("receita_liquida", "cmv_total", "margem_bruta"):
            df[col] = df[col].astype(float)
    return df


def get_mix_canal_pagamento(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    canal_sql, canal_params = _build_canal_filter(canais)
    params = {"d_ini": data_inicio, "d_fim": data_fim, **canal_params}

    df_canal = fetch_df(
        f"""
        SELECT
            canal_venda,
            SUM(qtd_vendas)::INT AS qtd_vendas,
            SUM(receita_liquida)::NUMERIC(14,2) AS receita_liquida,
            ROUND((SUM(receita_liquida) / NULLIF(SUM(qtd_vendas), 0))::NUMERIC, 2) AS ticket_medio
        FROM vw_bi_vendas_diarias
        WHERE data_dia BETWEEN :d_ini AND :d_fim
        {canal_sql}
        GROUP BY canal_venda
        ORDER BY receita_liquida DESC
        """,
        params,
    )
    df_pag = fetch_df(
        f"""
        SELECT
            forma_pagamento,
            SUM(qtd_vendas)::INT AS qtd_vendas,
            SUM(receita_liquida)::NUMERIC(14,2) AS receita_liquida
        FROM vw_bi_vendas_diarias
        WHERE data_dia BETWEEN :d_ini AND :d_fim
        {canal_sql}
        GROUP BY forma_pagamento
        ORDER BY receita_liquida DESC
        """,
        params,
    )
    for df in (df_canal, df_pag):
        if not df.empty:
            for col in ("receita_liquida", "ticket_medio"):
                if col in df.columns:
                    df[col] = df[col].astype(float)
    return {"por_canal": df_canal, "por_pagamento": df_pag}


def get_curva_abc_produtos(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
    categorias: list[str] | None = None,
) -> pd.DataFrame:
    canal_sql, canal_params = _build_canal_filter(canais)
    cat_sql, cat_params = _build_categoria_filter(categorias)

    df = fetch_df(
        f"""
        SELECT
            produto_id,
            sku,
            produto_nome,
            categoria_nome,
            tipo_produto,
            SUM(quantidade_vendida)::INT AS quantidade_vendida,
            SUM(receita_total)::NUMERIC(14,2) AS receita_total,
            SUM(cmv_total)::NUMERIC(14,2) AS cmv_total,
            SUM(margem_contribuicao)::NUMERIC(14,2) AS margem_contribuicao
        FROM vw_bi_produtos_desempenho
        WHERE data_dia BETWEEN :d_ini AND :d_fim
        {canal_sql}
        {cat_sql}
        GROUP BY produto_id, sku, produto_nome, categoria_nome, tipo_produto
        ORDER BY receita_total DESC
        """,
        {"d_ini": data_inicio, "d_fim": data_fim, **canal_params, **cat_params},
    )
    if df.empty:
        return df

    for col in ("receita_total", "cmv_total", "margem_contribuicao"):
        df[col] = df[col].astype(float)

    total_rec = df["receita_total"].sum()
    df["margem_pct"] = (
        (df["margem_contribuicao"] / df["receita_total"].replace(0, pd.NA)) * 100
    ).fillna(0).round(2)
    df["participacao_pct"] = ((df["receita_total"] / total_rec) * 100).round(2) if total_rec > 0 else 0.0
    df["acumulado_pct"] = df["participacao_pct"].cumsum().round(2)

    def _classe(acum: float) -> str:
        if acum <= 80.0:
            return "A"
        if acum <= 95.0:
            return "B"
        return "C"

    df["classe_abc"] = df["acumulado_pct"].apply(_classe)
    return df


def get_horarios_pico(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
) -> pd.DataFrame:
    canal_sql, canal_params = _build_canal_filter(canais)
    df = fetch_df(
        f"""
        SELECT
            dia_semana_num,
            dia_semana_nome,
            hora,
            SUM(qtd_vendas)::INT AS qtd_vendas,
            SUM(receita_liquida)::NUMERIC(14,2) AS receita_liquida
        FROM vw_bi_horarios_pico
        WHERE data_dia BETWEEN :d_ini AND :d_fim
        {canal_sql}
        GROUP BY dia_semana_num, dia_semana_nome, hora
        ORDER BY dia_semana_num ASC, hora ASC
        """,
        {"d_ini": data_inicio, "d_fim": data_fim, **canal_params},
    )
    if not df.empty:
        df["receita_liquida"] = df["receita_liquida"].astype(float)
    return df


def get_saude_estoque_e_perdas(
    *,
    data_inicio: date,
    data_fim: date,
) -> dict[str, Any]:
    df_estoque = fetch_df("SELECT * FROM vw_bi_estoque_saude ORDER BY valor_imobilizado DESC")
    if not df_estoque.empty:
        for col in (
            "estoque_atual",
            "estoque_minimo",
            "custo_medio_atual",
            "valor_imobilizado",
            "consumo_30d",
            "perdas_30d",
            "custo_perdas_30d",
        ):
            df_estoque[col] = df_estoque[col].astype(float)

    df_perdas_motivo = fetch_df(
        """
        SELECT
            motivo,
            COUNT(*)::INT AS qtd_ocorrencias,
            COALESCE(SUM(custo_estimado), 0)::NUMERIC(14,2) AS custo_total
        FROM registros_perdas
        WHERE DATE(criado_em AT TIME ZONE 'America/Sao_Paulo') BETWEEN :d_ini AND :d_fim
        GROUP BY motivo
        ORDER BY custo_total DESC
        """,
        {"d_ini": data_inicio, "d_fim": data_fim},
    )
    if not df_perdas_motivo.empty:
        df_perdas_motivo["custo_total"] = df_perdas_motivo["custo_total"].astype(float)

    df_perdas_insumo = fetch_df(
        """
        SELECT
            i.nome AS insumo_nome,
            i.unidade_medida,
            COUNT(*)::INT AS qtd_ocorrencias,
            COALESCE(SUM(rp.quantidade), 0)::NUMERIC(14,3) AS quantidade_perdida,
            COALESCE(SUM(rp.custo_estimado), 0)::NUMERIC(14,2) AS custo_total
        FROM registros_perdas rp
        JOIN insumos i ON i.id = rp.insumo_id
        WHERE DATE(rp.criado_em AT TIME ZONE 'America/Sao_Paulo') BETWEEN :d_ini AND :d_fim
        GROUP BY i.nome, i.unidade_medida
        ORDER BY custo_total DESC
        LIMIT 10
        """,
        {"d_ini": data_inicio, "d_fim": data_fim},
    )
    if not df_perdas_insumo.empty:
        df_perdas_insumo["custo_total"] = df_perdas_insumo["custo_total"].astype(float)
        df_perdas_insumo["quantidade_perdida"] = df_perdas_insumo["quantidade_perdida"].astype(float)

    return {
        "estoque": df_estoque,
        "perdas_por_motivo": df_perdas_motivo,
        "perdas_por_insumo": df_perdas_insumo,
    }


def get_evolucao_custo_insumos(*, data_inicio: date, data_fim: date) -> pd.DataFrame:
    df = fetch_df(
        """
        SELECT
            DATE(c.data_recebimento AT TIME ZONE 'America/Sao_Paulo') AS data_compra,
            i.nome AS insumo_nome,
            i.unidade_medida,
            AVG(ci.custo_unitario)::NUMERIC(12,4) AS custo_unitario_medio
        FROM compra_itens ci
        JOIN compras c ON c.id = ci.compra_id
        JOIN insumos i ON i.id = ci.insumo_id
        WHERE c.status = 'RECEBIDA'
          AND DATE(c.data_recebimento AT TIME ZONE 'America/Sao_Paulo') BETWEEN :d_ini AND :d_fim
        GROUP BY 1, 2, 3
        ORDER BY 1 ASC, 2 ASC
        """,
        {"d_ini": data_inicio, "d_fim": data_fim},
    )
    if not df.empty:
        df["custo_unitario_medio"] = df["custo_unitario_medio"].astype(float)
    return df


def get_compras_por_fornecedor(*, data_inicio: date, data_fim: date) -> pd.DataFrame:
    df = fetch_df(
        """
        SELECT
            f.nome_fantasia AS fornecedor_nome,
            COUNT(c.id)::INT AS qtd_pedidos,
            COALESCE(SUM(c.valor_total), 0)::NUMERIC(14,2) AS valor_total
        FROM compras c
        JOIN fornecedores f ON f.id = c.fornecedor_id
        WHERE c.status = 'RECEBIDA'
          AND DATE(COALESCE(c.data_recebimento, c.data_pedido) AT TIME ZONE 'America/Sao_Paulo')
              BETWEEN :d_ini AND :d_fim
        GROUP BY f.nome_fantasia
        ORDER BY valor_total DESC
        """,
        {"d_ini": data_inicio, "d_fim": data_fim},
    )
    if not df.empty:
        df["valor_total"] = df["valor_total"].astype(float)
    return df


def get_operacional_sla(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
) -> dict[str, Any]:
    canal_sql, canal_params = _build_canal_filter(canais)
    params = {"d_ini": data_inicio, "d_fim": data_fim, **canal_params}

    df = fetch_df(
        f"""
        SELECT *
        FROM vw_bi_operacional_sla
        WHERE data_dia BETWEEN :d_ini AND :d_fim
          AND status IN ('PRONTO', 'ENTREGUE')
        {canal_sql}
        ORDER BY data_dia ASC, hora ASC
        """,
        params,
    )
    if df.empty:
        return {
            "resumo": {
                "total_ordens": 0,
                "tempo_fila_medio_seg": 0.0,
                "tempo_preparo_medio_seg": 0.0,
                "tempo_estimado_medio_seg": 0.0,
                "taxa_sla_pct": 0.0,
            },
            "por_barista": pd.DataFrame(),
            "por_hora": pd.DataFrame(),
        }

    total = len(df)
    fila_med = float(df["tempo_espera_fila_seg"].dropna().mean() or 0)
    prep_med = float(df["tempo_preparo_real_seg"].dropna().mean() or 0)
    est_med = float(df["tempo_estimado_total_seg"].dropna().mean() or 0)
    sla_valid = df["dentro_sla"].dropna()
    taxa_sla = float(sla_valid.mean() * 100.0) if len(sla_valid) > 0 else 0.0

    por_barista = (
        df.groupby("barista_nome", as_index=False)
        .agg(
            ordens_concluidas=("ordem_id", "count"),
            tempo_fila_medio_seg=("tempo_espera_fila_seg", "mean"),
            tempo_preparo_medio_seg=("tempo_preparo_real_seg", "mean"),
            taxa_sla_pct=("dentro_sla", lambda s: round(float(s.dropna().mean() * 100), 1) if len(s.dropna()) else 0.0),
        )
        .sort_values("ordens_concluidas", ascending=False)
    )
    por_barista["tempo_fila_medio_seg"] = por_barista["tempo_fila_medio_seg"].round(1)
    por_barista["tempo_preparo_medio_seg"] = por_barista["tempo_preparo_medio_seg"].round(1)

    por_hora = (
        df.groupby("hora", as_index=False)
        .agg(
            qtd_ordens=("ordem_id", "count"),
            tempo_fila_medio_seg=("tempo_espera_fila_seg", "mean"),
            tempo_preparo_medio_seg=("tempo_preparo_real_seg", "mean"),
            tempo_estimado_medio_seg=("tempo_estimado_total_seg", "mean"),
            taxa_sla_pct=("dentro_sla", lambda s: round(float(s.dropna().mean() * 100), 1) if len(s.dropna()) else 0.0),
        )
        .sort_values("hora", ascending=True)
    )
    for c in ("tempo_fila_medio_seg", "tempo_preparo_medio_seg", "tempo_estimado_medio_seg"):
        por_hora[c] = por_hora[c].round(1)

    return {
        "resumo": {
            "total_ordens": total,
            "tempo_fila_medio_seg": round(fila_med, 1),
            "tempo_preparo_medio_seg": round(prep_med, 1),
            "tempo_estimado_medio_seg": round(est_med, 1),
            "taxa_sla_pct": round(taxa_sla, 1),
        },
        "por_barista": por_barista,
        "por_hora": por_hora,
    }


def get_dre_e_fluxo_mensal() -> pd.DataFrame:
    df = fetch_df("SELECT * FROM vw_bi_financeiro_dre_fluxo ORDER BY ano_mes ASC")
    if df.empty:
        return df
    numeric_cols = [
        "receita_vendas",
        "cmv_vendas",
        "custo_perdas",
        "despesas_operacionais",
        "compras_recebidas",
        "entradas_caixa",
        "saidas_caixa",
        "fluxo_caixa_liquido",
        "lucro_bruto",
        "resultado_operacional_liquido",
    ]
    for col in numeric_cols:
        df[col] = df[col].astype(float)
    df["saldo_caixa_acumulado"] = df["fluxo_caixa_liquido"].cumsum().round(2)
    return df


def get_aging_titulos() -> pd.DataFrame:
    df = fetch_df(
        """
        SELECT
            tipo,
            CASE
                WHEN data_vencimento < CURRENT_DATE THEN '1. Vencido (Atrasado)'
                WHEN data_vencimento <= CURRENT_DATE + INTERVAL '7 days' THEN '2. Vence em até 7 dias'
                WHEN data_vencimento <= CURRENT_DATE + INTERVAL '30 days' THEN '3. Vence em 8 a 30 dias'
                ELSE '4. Acima de 30 dias'
            END AS faixa_vencimento,
            COUNT(*)::INT AS qtd_titulos,
            COALESCE(SUM(valor_original), 0)::NUMERIC(14,2) AS valor_total
        FROM titulos_financeiros
        WHERE status = 'ABERTO'
        GROUP BY 1, 2
        ORDER BY 1 ASC, 2 ASC
        """
    )
    if not df.empty:
        df["valor_total"] = df["valor_total"].astype(float)
    return df


def get_insights_automaticos(
    *,
    data_inicio: date,
    data_fim: date,
    canais: list[str] | None = None,
) -> list[dict[str, str]]:
    """Gera diagnósticos objetivos a partir dos dados reais do PostgreSQL."""
    insights: list[dict[str, str]] = []

    abc = get_curva_abc_produtos(data_inicio=data_inicio, data_fim=data_fim, canais=canais)
    if not abc.empty:
        classe_a = abc[abc["classe_abc"] == "A"]
        top_prod = abc.iloc[0]
        insights.append(
            {
                "nivel": "info",
                "titulo": "Concentração Comercial (Curva ABC)",
                "descricao": (
                    f"{len(classe_a)} de {len(abc)} produtos pertencem à Classe A e concentram "
                    f"{classe_a['participacao_pct'].sum():.1f}% da receita. "
                    f"Líder do período: {top_prod['produto_nome']} (R$ {top_prod['receita_total']:,.2f}, "
                    f"margem de {top_prod['margem_pct']:.1f}%)."
                ),
            }
        )
        baixa_margem = abc[abc["margem_pct"] < 50.0].sort_values("receita_total", ascending=False)
        if not baixa_margem.empty:
            p = baixa_margem.iloc[0]
            insights.append(
                {
                    "nivel": "warning",
                    "titulo": "Produto com Margem Pressionada",
                    "descricao": (
                        f"'{p['produto_nome']}' apresentou margem de contribuição de {p['margem_pct']:.1f}% "
                        f"(receita de R$ {p['receita_total']:,.2f}). Avalie revisão de preço ou renegociação de insumo."
                    ),
                }
            )

    est = get_saude_estoque_e_perdas(data_inicio=data_inicio, data_fim=data_fim)
    df_est = est["estoque"]
    if not df_est.empty:
        criticos = df_est[df_est["status_estoque"] == "CRITICO"]
        if not criticos.empty:
            nomes = ", ".join(criticos["insumo_nome"].head(4).tolist())
            insights.append(
                {
                    "nivel": "error",
                    "titulo": f"{len(criticos)} Insumo(s) Abaixo do Estoque Mínimo",
                    "descricao": (
                        f"Risco de ruptura imediata em: {nomes}. "
                        "Emita pedido de compra prioritário no módulo Compras."
                    ),
                }
            )
    df_perdas = est["perdas_por_motivo"]
    if not df_perdas.empty:
        top_motivo = df_perdas.iloc[0]
        total_perdas = df_perdas["custo_total"].sum()
        share = (top_motivo["custo_total"] / total_perdas * 100) if total_perdas > 0 else 0
        insights.append(
            {
                "nivel": "warning",
                "titulo": "Principal Ofensor de Perdas Operacionais",
                "descricao": (
                    f"O motivo '{top_motivo['motivo']}' responde por {share:.1f}% do custo de perdas "
                    f"(R$ {top_motivo['custo_total']:,.2f} de R$ {total_perdas:,.2f} no período)."
                ),
            }
        )

    sla = get_operacional_sla(data_inicio=data_inicio, data_fim=data_fim, canais=canais)
    por_hora = sla["por_hora"]
    if not por_hora.empty:
        pior_hora = por_hora.sort_values("taxa_sla_pct", ascending=True).iloc[0]
        insights.append(
            {
                "nivel": "warning" if pior_hora["taxa_sla_pct"] < 80 else "info",
                "titulo": "Gargalo de SLA por Faixa Horária",
                "descricao": (
                    f"A faixa das {int(pior_hora['hora']):02d}h teve a menor aderência ao SLA "
                    f"({pior_hora['taxa_sla_pct']:.1f}%, preparo médio de {pior_hora['tempo_preparo_medio_seg']:.0f}s "
                    f"em {int(pior_hora['qtd_ordens'])} pedidos). Recomenda-se reforço de barista nesse turno."
                ),
            }
        )

    return insights
