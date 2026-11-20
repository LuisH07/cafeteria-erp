"""Componentes de visualização analítica (Plotly) para o Dashboard BI (2ª VA)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PALETTE_PRIMARY = "#4A2C1D"
PALETTE_SECONDARY = "#C18553"
PALETTE_ACCENT = "#8B5A2B"
PALETTE_DANGER = "#7A2E20"
PALETTE_DARK = "#2B1810"
PALETTE_SOFT = "#D8C2AA"


def chart_receita_cmv_temporal(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["data_dia"],
            y=df["receita_liquida"],
            mode="lines+markers",
            name="Receita Líquida (R$)",
            line={"color": PALETTE_PRIMARY, "width": 3},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["data_dia"],
            y=df["margem_bruta"],
            mode="lines",
            name="Margem Bruta (R$)",
            line={"color": PALETTE_ACCENT, "width": 2, "dash": "solid"},
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["data_dia"],
            y=df["cmv_total"],
            name="CMV (R$)",
            marker_color="rgba(193, 124, 71, 0.35)",
        )
    )
    fig.update_layout(
        title="Evolução Diária: Receita Líquida, Margem Bruta e CMV",
        xaxis_title="Data",
        yaxis_title="Valor (R$)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"t": 60, "b": 40, "l": 40, "r": 20},
    )
    return fig


def chart_curva_abc(df: pd.DataFrame) -> go.Figure:
    top_df = df.head(15)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = [
        PALETTE_PRIMARY if c == "A" else (PALETTE_SECONDARY if c == "B" else "#B8A99A")
        for c in top_df["classe_abc"]
    ]
    fig.add_trace(
        go.Bar(
            x=top_df["produto_nome"],
            y=top_df["receita_total"],
            name="Receita (R$)",
            marker_color=colors,
            text=top_df["classe_abc"],
            textposition="outside",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=top_df["produto_nome"],
            y=top_df["acumulado_pct"],
            name="% Acumulado (Pareto)",
            mode="lines+markers",
            line={"color": PALETTE_DANGER, "width": 2.5},
        ),
        secondary_y=True,
    )
    fig.add_hline(y=80, line_dash="dot", line_color=PALETTE_DANGER, secondary_y=True)
    fig.update_layout(
        title="Curva ABC de Produtos (Receita e % Acumulado)",
        xaxis_tickangle=-30,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"t": 60, "b": 90, "l": 40, "r": 40},
    )
    fig.update_yaxes(title_text="Receita (R$)", secondary_y=False)
    fig.update_yaxes(title_text="% Acumulado", range=[0, 108], secondary_y=True)
    return fig


def chart_heatmap_horarios(df: pd.DataFrame) -> go.Figure:
    ordem_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    pivot = (
        df.pivot_table(
            index="dia_semana_nome",
            columns="hora",
            values="qtd_vendas",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex([d for d in ordem_dias if d in df["dia_semana_nome"].unique()])
    )
    fig = px.imshow(
        pivot,
        labels={"x": "Hora do Dia", "y": "Dia da Semana", "color": "Qtd. Vendas"},
        color_continuous_scale="YlOrBr",
        text_auto=True,
        aspect="auto",
        title="Mapa de Calor - Horários de Pico (Quantidade de Vendas)",
    )
    fig.update_layout(margin={"t": 55, "b": 40, "l": 40, "r": 20})
    return fig


def chart_mix_pie(df: pd.DataFrame, names_col: str, values_col: str, title: str) -> go.Figure:
    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        hole=0.45,
        title=title,
        color_discrete_sequence=["#6F4E37", "#A47148", "#C17C47", "#D9AE7E", "#4A3222"],
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin={"t": 55, "b": 20, "l": 20, "r": 20})
    return fig


def chart_sla_por_hora(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=df["hora"].astype(str) + "h",
            y=df["tempo_preparo_medio_seg"],
            name="Preparo Real Médio (s)",
            marker_color=PALETTE_SECONDARY,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["hora"].astype(str) + "h",
            y=df["tempo_estimado_medio_seg"],
            name="Meta Estimada (s)",
            mode="lines+markers",
            line={"color": PALETTE_DARK, "dash": "dash"},
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["hora"].astype(str) + "h",
            y=df["taxa_sla_pct"],
            name="Taxa SLA (%)",
            mode="lines+markers",
            line={"color": PALETTE_ACCENT, "width": 2.5},
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title="Desempenho Operacional por Hora: Tempo Real vs. Meta e SLA (%)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"t": 60, "b": 40, "l": 40, "r": 40},
    )
    fig.update_yaxes(title_text="Segundos", secondary_y=False)
    fig.update_yaxes(title_text="SLA (%)", range=[0, 108], secondary_y=True)
    return fig


def chart_dre_waterfall(receita: float, cmv: float, perdas: float, despesas: float) -> go.Figure:
    lucro_liq = receita - cmv - perdas - despesas
    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "total"],
            x=[
                "Receita Vendas",
                "(-) CMV Insumos",
                "(-) Perdas Operac.",
                "(-) Despesas Operacionais",
                "Resultado Líquido",
            ],
            y=[receita, -cmv, -perdas, -despesas, lucro_liq],
            text=[
                f"R$ {receita:,.2f}",
                f"-R$ {cmv:,.2f}",
                f"-R$ {perdas:,.2f}",
                f"-R$ {despesas:,.2f}",
                f"R$ {lucro_liq:,.2f}",
            ],
            textposition="outside",
            increasing={"marker": {"color": PALETTE_ACCENT}},
            decreasing={"marker": {"color": PALETTE_DANGER}},
            totals={"marker": {"color": PALETTE_PRIMARY}},
        )
    )
    fig.update_layout(
        title="DRE Gerencial Consolidada (Composição do Resultado)",
        yaxis_title="Valor (R$)",
        margin={"t": 55, "b": 40, "l": 40, "r": 20},
    )
    return fig


def chart_fluxo_caixa_mensal(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=df["ano_mes"],
            y=df["entradas_caixa"],
            name="Entradas de Caixa (R$)",
            marker_color=PALETTE_ACCENT,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=df["ano_mes"],
            y=df["saidas_caixa"],
            name="Saídas de Caixa (R$)",
            marker_color=PALETTE_DANGER,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["ano_mes"],
            y=df["saldo_caixa_acumulado"],
            name="Saldo Acumulado (R$)",
            mode="lines+markers",
            line={"color": PALETTE_PRIMARY, "width": 3},
        ),
        secondary_y=True,
    )
    fig.update_layout(
        barmode="group",
        title="Fluxo de Caixa Mensal (Entradas × Saídas × Saldo Acumulado)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"t": 60, "b": 40, "l": 40, "r": 40},
    )
    fig.update_yaxes(title_text="Entradas e Saídas (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Saldo Acumulado (R$)", secondary_y=True)
    return fig
