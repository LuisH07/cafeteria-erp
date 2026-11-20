"""Página 07 — Módulo Financeiro (Contas a Pagar/Receber, Fluxo de Caixa e DRE)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.services.bi_service import get_dre_e_fluxo_mensal
from src.services.cadastros_service import list_categorias, list_fornecedores
from src.services.exceptions import DomainError
from src.services.financeiro_service import (
    cancelar_titulo_manual,
    criar_titulo_manual,
    get_resumo_financeiro,
    liquidar_titulo,
    list_movimentacoes_financeiras,
    list_titulos_financeiros,
)
from src.ui.components.layout import (
    ensure_page_access,
    fmt_brl,
    fmt_date,
    fmt_datetime,
    render_page_header,
    user_can,
)

user = ensure_page_access("financeiro")
can_write = user_can(user, "financeiro:write")

render_page_header(
    "Gestão Financeira",
    "Consolidação monetária automática das vendas, compras e despesas operacionais da cafeteria.",
    icon_name="wallet",
)

resumo = get_resumo_financeiro()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Saldo Atual em Caixa", fmt_brl(resumo["saldo_caixa"]))
m2.metric("A Receber (Aberto)", fmt_brl(resumo["a_receber_aberto"]))
m3.metric("A Pagar (Aberto)", fmt_brl(resumo["a_pagar_aberto"]))
m4.metric(
    "A Pagar Atrasado",
    fmt_brl(resumo["a_pagar_atrasado"]),
    delta_color="inverse" if resumo["a_pagar_atrasado"] > 0 else "normal",
)

tab_tit, tab_novo, tab_caixa, tab_dre = st.tabs(
    [
        ":material/receipt_long: Contas a Pagar e Receber",
        ":material/add_circle: Novo Lançamento",
        ":material/payments: Fluxo de Caixa (Extrato)",
        ":material/bar_chart: DRE Mensal Consolidada",
    ]
)

# -----------------------------------------------------------------------------
# ABA 1: CONTAS A PAGAR E RECEBER
# -----------------------------------------------------------------------------
with tab_tit:
    f1, f2, f3 = st.columns(3)
    tipo_f = f1.selectbox("Tipo", ["Todos", "PAGAR", "RECEBER"])
    sit_f = f2.selectbox("Situação", ["Todos", "ATRASADO", "ABERTO", "PAGO", "CANCELADO"])
    orig_f = f3.selectbox("Origem", ["Todos", "VENDAS", "COMPRAS", "MANUAL", "OPERACIONAL"])

    titulos = list_titulos_financeiros(
        tipo=tipo_f, situacao=sit_f, origem_modulo=orig_f, limit=200
    )
    if titulos:
        badge_map = {
            "ATRASADO": "ATRASADO",
            "ABERTO": "ABERTO",
            "PAGO": "PAGO",
            "CANCELADO": "CANCELADO",
        }
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": t["id"],
                        "Tipo": t["tipo"],
                        "Situação": badge_map.get(t["situacao"], t["situacao"]),
                        "Origem": t["origem_modulo"],
                        "Categoria": t["categoria_nome"],
                        "Descrição": t["descricao"],
                        "Contraparte": t["contraparte"],
                        "Vencimento": fmt_date(t["data_vencimento"]),
                        "Valor": fmt_brl(t["valor_original"]),
                        "Liquidação": fmt_datetime(t["data_liquidacao"]),
                    }
                    for t in titulos
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        abertos = [t for t in titulos if t["status"] == "ABERTO"]
        if can_write and abertos:
            st.divider()
            st.subheader("Liquidar Título em Aberto")
            t_map = {
                f"#{t['id']} [{t['tipo']}] {t['descricao']} - {fmt_brl(t['valor_original'])} (venc. {fmt_date(t['data_vencimento'])})": t
                for t in abertos
            }
            sel_t = t_map[st.selectbox("Selecione o Título", list(t_map.keys()))]
            c_liq, c_can = st.columns([2, 1])
            with c_liq:
                with st.form("form_liquidar_titulo"):
                    forma_liq = st.selectbox(
                        "Meio de Liquidação",
                        ["PIX", "TRANSFERENCIA", "BOLETO", "DEBITO", "CREDITO", "DINHEIRO"],
                    )
                    if st.form_submit_button("Confirmar Liquidação no Caixa", icon=":material/check_circle:", type="primary", use_container_width=True):
                        try:
                            liquidar_titulo(
                                titulo_id=int(sel_t["id"]),
                                forma_pagamento=forma_liq,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Título liquidado e registrado no Fluxo de Caixa!")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))
            with c_can:
                if sel_t["origem_modulo"] == "MANUAL":
                    st.write("")
                    st.write("")
                    if st.button("Cancelar Título Manual", icon=":material/cancel:", use_container_width=True):
                        try:
                            cancelar_titulo_manual(titulo_id=int(sel_t["id"]), usuario_id=int(user["id"]))
                            st.warning("Título manual cancelado.")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))
    else:
        st.info("Nenhum título encontrado para os filtros aplicados.")

# -----------------------------------------------------------------------------
# ABA 2: LANÇAMENTO MANUAL (DESPESAS FIXAS / RECEITAS EXTRAS)
# -----------------------------------------------------------------------------
with tab_novo:
    if not can_write:
        st.info("Seu perfil possui permissão apenas de visualização neste módulo.")
    else:
        tipo_novo = st.radio("Natureza do Lançamento", ["PAGAR", "RECEBER"], horizontal=True)
        cats = list_categorias(
            tipo="DESPESA" if tipo_novo == "PAGAR" else "RECEITA",
            apenas_ativas=True,
        )
        forns = list_fornecedores(apenas_ativos=True)

        with st.form("form_lancamento_manual"):
            cat_map = {c["nome"]: int(c["id"]) for c in cats}
            c1, c2 = st.columns(2)
            cat_sel = c1.selectbox("Categoria*", list(cat_map.keys())) if cat_map else None
            valor = c2.number_input("Valor (R$)*", min_value=0.01, value=250.00, step=10.00)
            desc = st.text_input("Descrição*", placeholder="Ex.: Conta de Energia Elétrica - Nov/2026")
            c3, c4, c5 = st.columns(3)
            dt_comp = c3.date_input("Data Competência", value=date.today())
            dt_venc = c4.date_input("Data Vencimento", value=date.today() + timedelta(days=5))
            forma = c5.selectbox(
                "Forma de Pagamento",
                ["BOLETO", "PIX", "TRANSFERENCIA", "CARTAO_CORP", "DINHEIRO"],
            )
            forn_opts = {"Nenhum": None, **{f["nome_fantasia"]: int(f["id"]) for f in forns}}
            forn_sel = st.selectbox("Fornecedor (opcional)", list(forn_opts.keys())) if tipo_novo == "PAGAR" else "Nenhum"
            liquidar_agora = st.checkbox("Já liquidado (lançar imediatamente no Fluxo de Caixa)")

            if st.form_submit_button("Salvar Lançamento Financeiro", type="primary"):
                if not cat_sel:
                    st.error("Cadastre ao menos uma categoria financeira correspondente.")
                else:
                    try:
                        criar_titulo_manual(
                            tipo=tipo_novo,
                            categoria_id=cat_map[cat_sel],
                            descricao=desc,
                            valor_original=valor,
                            data_competencia=dt_comp,
                            data_vencimento=dt_venc,
                            forma_pagamento=forma,
                            usuario_id=int(user["id"]),
                            liquidar_agora=liquidar_agora,
                            fornecedor_id=forn_opts.get(forn_sel),
                        )
                        st.success("Lançamento financeiro registrado com sucesso!")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 3: FLUXO DE CAIXA (EXTRATO IMUTÁVEL)
# -----------------------------------------------------------------------------
with tab_caixa:
    movs = list_movimentacoes_financeiras(limit=250)
    if movs:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Data e Hora": fmt_datetime(m["data_movimentacao"]),
                        "Fluxo": "ENTRADA" if m["tipo_fluxo"] == "ENTRADA" else "SAÍDA",
                        "Valor": fmt_brl(m["valor"]),
                        "Forma": m["forma_pagamento"],
                        "Origem": m["origem_modulo"],
                        "Categoria": m["categoria_nome"],
                        "Descrição": m["descricao"],
                        "Usuário": m["usuario_nome"],
                    }
                    for m in movs
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma movimentação efetivada no caixa ainda.")

# -----------------------------------------------------------------------------
# ABA 4: DRE MENSAL CONSOLIDADA
# -----------------------------------------------------------------------------
with tab_dre:
    df_dre = get_dre_e_fluxo_mensal()
    if not df_dre.empty:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Mês": r["ano_mes"],
                        "Receita Vendas": fmt_brl(r["receita_vendas"]),
                        "(-) CMV": fmt_brl(r["cmv_vendas"]),
                        "Lucro Bruto": fmt_brl(r["lucro_bruto"]),
                        "(-) Perdas": fmt_brl(r["custo_perdas"]),
                        "(-) Despesas Op.": fmt_brl(r["despesas_operacionais"]),
                        "Resultado Líquido": fmt_brl(r["resultado_operacional_liquido"]),
                        "Fluxo Caixa Mês": fmt_brl(r["fluxo_caixa_liquido"]),
                        "Saldo Acumulado": fmt_brl(r["saldo_caixa_acumulado"]),
                    }
                    for _, r in df_dre.iterrows()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sem dados financeiros consolidados até o momento.")
