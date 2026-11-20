"""Página 08 — Módulo Analítico / Dashboard BI (2ª VA) conectado diretamente ao PostgreSQL."""

from __future__ import annotations

from datetime import timedelta

import plotly.express as px
import streamlit as st

from src.services.bi_service import (
    get_aging_titulos,
    get_bi_filter_options,
    get_compras_por_fornecedor,
    get_curva_abc_produtos,
    get_dre_e_fluxo_mensal,
    get_evolucao_custo_insumos,
    get_horarios_pico,
    get_insights_automaticos,
    get_kpis_executivos,
    get_mix_canal_pagamento,
    get_operacional_sla,
    get_saude_estoque_e_perdas,
    get_vendas_temporais,
)
from src.ui.components.charts import (
    chart_curva_abc,
    chart_dre_waterfall,
    chart_fluxo_caixa_mensal,
    chart_heatmap_horarios,
    chart_mix_pie,
    chart_receita_cmv_temporal,
    chart_sla_por_hora,
)
from src.ui.components.layout import (
    ensure_page_access,
    fmt_brl,
    fmt_seconds,
    render_page_header,
)

user = ensure_page_access("dashboard_bi")

render_page_header(
    "Dashboard BI - Inteligência de Negócios",
    "Indicadores de vendas, estoque, operação do barista e resultado financeiro em tempo real.",
    icon_name="bar-chart-3",
)

opts = get_bi_filter_options()
min_date = opts["min_date"]
max_date = opts["max_date"]
default_start = max(min_date, max_date - timedelta(days=29))

# Filtros globais
with st.container(border=True):
    f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.6, 1.6])
    data_inicio = f1.date_input("Data Inicial", value=default_start, min_value=min_date, max_value=max_date)
    data_fim = f2.date_input("Data Final", value=max_date, min_value=min_date, max_value=max_date)
    canais_sel = f3.multiselect("Canais de Venda", opts["canais"], default=opts["canais"])
    cats_sel = f4.multiselect("Categorias de Produto (ABC)", opts["categorias"], default=opts["categorias"])

if data_inicio > data_fim:
    st.error("A Data Inicial deve ser anterior ou igual à Data Final.")
    st.stop()

canais_filter = canais_sel if canais_sel else None
cats_filter = cats_sel if cats_sel else None

# Insights Automáticos baseados nos dados reais
insights = get_insights_automaticos(
    data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter
)
if insights:
    with st.expander(":material/lightbulb: Diagnósticos e Alertas Automáticos do Período", expanded=True):
        for ins in insights:
            msg = f"**{ins['titulo']}:** {ins['descricao']}"
            if ins["nivel"] == "error":
                st.error(msg)
            elif ins["nivel"] == "warning":
                st.warning(msg)
            else:
                st.info(msg)

tab_exec, tab_est, tab_op, tab_fin = st.tabs(
    [
        ":material/trending_up: Desempenho Comercial",
        ":material/inventory_2: Suprimentos e Perdas",
        ":material/timer: Operação e SLA",
        ":material/account_balance_wallet: Resultado Financeiro",
    ]
)

# =============================================================================
# ABA 1: EXECUTIVO & COMERCIAL
# =============================================================================
with tab_exec:
    kpis = get_kpis_executivos(
        data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter
    )
    prev_ini, prev_fim = kpis["periodo_anterior"]
    st.caption(
        f"Comparativo de variação frente ao período anterior equivalente "
        f"({prev_ini.strftime('%d/%m/%Y')} a {prev_fim.strftime('%d/%m/%Y')})."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Receita Líquida",
        fmt_brl(kpis["receita_liquida"]),
        f"{kpis['delta_receita_pct']:+.1f}%" if kpis["delta_receita_pct"] is not None else None,
    )
    c2.metric(
        "Margem Bruta",
        f"{kpis['margem_bruta_pct']:.1f}%",
        f"{kpis['delta_margem_pp']:+.2f} p.p." if kpis["delta_margem_pp"] is not None else fmt_brl(kpis["margem_bruta"]),
    )
    c3.metric(
        "Ticket Médio",
        fmt_brl(kpis["ticket_medio"]),
        f"{kpis['delta_ticket_pct']:+.1f}%" if kpis["delta_ticket_pct"] is not None else None,
    )
    c4.metric(
        "Vendas Concluídas",
        f"{kpis['qtd_vendas']:,}".replace(",", "."),
        f"{kpis['delta_vendas_pct']:+.1f}%" if kpis["delta_vendas_pct"] is not None else None,
    )
    c5.metric(
        "Taxa de Cancelamento",
        f"{kpis['taxa_cancelamento_pct']:.1f}%",
        f"{kpis['canceladas']} cancelada(s)",
        delta_color="inverse" if kpis["taxa_cancelamento_pct"] > 5 else "normal",
    )

    df_temp = get_vendas_temporais(data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter)
    if not df_temp.empty:
        st.plotly_chart(chart_receita_cmv_temporal(df_temp), use_container_width=True)
    else:
        st.info("Sem vendas concluídas no período filtrado.")

    mix = get_mix_canal_pagamento(data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter)
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        if not mix["por_canal"].empty:
            st.plotly_chart(
                chart_mix_pie(mix["por_canal"], "canal_venda", "receita_liquida", "Receita por Canal de Venda"),
                use_container_width=True,
            )
    with col_m2:
        if not mix["por_pagamento"].empty:
            st.plotly_chart(
                chart_mix_pie(
                    mix["por_pagamento"], "forma_pagamento", "receita_liquida", "Receita por Forma de Pagamento"
                ),
                use_container_width=True,
            )

    df_abc = get_curva_abc_produtos(
        data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter, categorias=cats_filter
    )
    if not df_abc.empty:
        st.plotly_chart(chart_curva_abc(df_abc), use_container_width=True)
        with st.expander(":material/table_chart: Tabela Detalhada - Desempenho e Margem por Produto"):
            st.dataframe(
                df_abc[
                    [
                        "classe_abc",
                        "sku",
                        "produto_nome",
                        "categoria_nome",
                        "quantidade_vendida",
                        "receita_total",
                        "cmv_total",
                        "margem_contribuicao",
                        "margem_pct",
                        "participacao_pct",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    df_heat = get_horarios_pico(data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter)
    if not df_heat.empty:
        st.plotly_chart(chart_heatmap_horarios(df_heat), use_container_width=True)

# =============================================================================
# ABA 2: ESTOQUE, COMPRAS & PERDAS
# =============================================================================
with tab_est:
    est_data = get_saude_estoque_e_perdas(data_inicio=data_inicio, data_fim=data_fim)
    df_est = est_data["estoque"]
    df_perdas_mot = est_data["perdas_por_motivo"]
    df_perdas_ins = est_data["perdas_por_insumo"]

    val_imob = float(df_est["valor_imobilizado"].sum()) if not df_est.empty else 0.0
    n_crit = int((df_est["status_estoque"] == "CRITICO").sum()) if not df_est.empty else 0
    custo_perdas_p = float(df_perdas_mot["custo_total"].sum()) if not df_perdas_mot.empty else 0.0

    df_forn = get_compras_por_fornecedor(data_inicio=data_inicio, data_fim=data_fim)
    total_compras_p = float(df_forn["valor_total"].sum()) if not df_forn.empty else 0.0

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Valor Imobilizado em Estoque", fmt_brl(val_imob))
    e2.metric("Insumos Críticos", n_crit, delta_color="inverse" if n_crit else "normal")
    e3.metric("Compras Recebidas no Período", fmt_brl(total_compras_p))
    e4.metric("Custo de Perdas no Período", fmt_brl(custo_perdas_p), delta_color="inverse")

    c_p1, c_p2 = st.columns(2)
    with c_p1:
        if not df_perdas_mot.empty:
            fig_pm = px.bar(
                df_perdas_mot,
                x="motivo",
                y="custo_total",
                text_auto=".2f",
                title="Custo de Perdas por Motivo (R$)",
                color_discrete_sequence=["#7A2E20"],
            )
            st.plotly_chart(fig_pm, use_container_width=True)
        else:
            st.info("Sem perdas registradas no período.")
    with c_p2:
        if not df_forn.empty:
            fig_fn = px.bar(
                df_forn,
                x="valor_total",
                y="fornecedor_nome",
                orientation="h",
                text_auto=".2f",
                title="Volume de Compras por Fornecedor (R$)",
                color_discrete_sequence=["#6F4E37"],
            )
            fig_fn.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_fn, use_container_width=True)
        else:
            st.info("Sem compras recebidas no período.")

    df_custo = get_evolucao_custo_insumos(data_inicio=data_inicio, data_fim=data_fim)
    if not df_custo.empty:
        top_insumos = df_custo["insumo_nome"].value_counts().head(6).index.tolist()
        ins_sel_chart = st.multiselect(
            "Insumos para acompanhar evolução de custo unitário",
            sorted(df_custo["insumo_nome"].unique().tolist()),
            default=top_insumos[:3],
        )
        if ins_sel_chart:
            df_c_filt = df_custo[df_custo["insumo_nome"].isin(ins_sel_chart)]
            fig_custo = px.line(
                df_c_filt,
                x="data_compra",
                y="custo_unitario_medio",
                color="insumo_nome",
                markers=True,
                title="Evolução do Custo Unitário de Compra por Insumo (R$ por unidade)",
                color_discrete_sequence=["#3E2419", "#8B5A2B", "#C68B59", "#6F4E37", "#A67B5B", "#7A2E20"],
            )
            st.plotly_chart(fig_custo, use_container_width=True)

    if not df_est.empty:
        st.subheader("Saúde de Estoque, Cobertura (dias) e Perdas (30d)")
        st.dataframe(
            df_est[
                [
                    "status_estoque",
                    "sku",
                    "insumo_nome",
                    "estoque_atual",
                    "estoque_minimo",
                    "unidade_medida",
                    "dias_cobertura_estimado",
                    "valor_imobilizado",
                    "custo_perdas_30d",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    if not df_perdas_ins.empty:
        with st.expander("Ranking de Insumos com Maior Custo de Perda no Período"):
            st.dataframe(df_perdas_ins, use_container_width=True, hide_index=True)

# =============================================================================
# ABA 3: OPERACIONAL & SLA (BARISTA)
# =============================================================================
with tab_op:
    sla_data = get_operacional_sla(
        data_inicio=data_inicio, data_fim=data_fim, canais=canais_filter
    )
    res_sla = sla_data["resumo"]

    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Ordens Concluídas", res_sla["total_ordens"])
    o2.metric("Espera Média na Fila", fmt_seconds(res_sla["tempo_fila_medio_seg"]))
    o3.metric(
        "Preparo Real Médio",
        fmt_seconds(res_sla["tempo_preparo_medio_seg"]),
        f"Meta: {fmt_seconds(res_sla['tempo_estimado_medio_seg'])}",
    )
    o4.metric("Taxa de Cumprimento SLA", f"{res_sla['taxa_sla_pct']:.1f}%")

    if not sla_data["por_hora"].empty:
        st.plotly_chart(chart_sla_por_hora(sla_data["por_hora"]), use_container_width=True)
    else:
        st.info("Sem ordens de preparo finalizadas no período selecionado.")

    if not sla_data["por_barista"].empty:
        st.subheader("Produtividade e SLA por Barista")
        st.dataframe(sla_data["por_barista"], use_container_width=True, hide_index=True)

# =============================================================================
# ABA 4: FINANCEIRO, DRE & FLUXO DE CAIXA
# =============================================================================
with tab_fin:
    df_dre = get_dre_e_fluxo_mensal()
    if not df_dre.empty:
        tot_rec = float(df_dre["receita_vendas"].sum())
        tot_cmv = float(df_dre["cmv_vendas"].sum())
        tot_perdas = float(df_dre["custo_perdas"].sum())
        tot_desp = float(df_dre["despesas_operacionais"].sum())
        res_liq = tot_rec - tot_cmv - tot_perdas - tot_desp
        margem_liq_pct = (res_liq / tot_rec * 100) if tot_rec > 0 else 0.0

        fn1, fn2, fn3, fn4 = st.columns(4)
        fn1.metric("Receita Acumulada (DRE)", fmt_brl(tot_rec))
        fn2.metric("Despesas Operacionais", fmt_brl(tot_desp))
        fn3.metric("Resultado Líquido", fmt_brl(res_liq), f"Margem líq.: {margem_liq_pct:.1f}%")
        fn4.metric("Saldo Final em Caixa", fmt_brl(float(df_dre["saldo_caixa_acumulado"].iloc[-1])))

        col_w, col_fx = st.columns(2)
        with col_w:
            st.plotly_chart(
                chart_dre_waterfall(tot_rec, tot_cmv, tot_perdas, tot_desp),
                use_container_width=True,
            )
        with col_fx:
            st.plotly_chart(chart_fluxo_caixa_mensal(df_dre), use_container_width=True)

    df_aging = get_aging_titulos()
    st.subheader("Aging de Contas a Pagar e a Receber (Títulos em Aberto)")
    if not df_aging.empty:
        fig_ag = px.bar(
            df_aging,
            x="faixa_vencimento",
            y="valor_total",
            color="tipo",
            barmode="group",
            text_auto=".2f",
            title="Distribuição de Títulos Abertos por Faixa de Vencimento (R$)",
            color_discrete_map={"PAGAR": "#7A2E20", "RECEBER": "#6F4E37"},
        )
        st.plotly_chart(fig_ag, use_container_width=True)
        st.dataframe(df_aging, use_container_width=True, hide_index=True)
    else:
        st.success("Nenhum título financeiro em aberto.")
