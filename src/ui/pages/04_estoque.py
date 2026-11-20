"""Página 04 — Módulo de Estoque, Inventário e Extrato Imutável de Movimentações."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.services.cadastros_service import list_insumos
from src.services.estoque_service import (
    get_estoque_position,
    list_localizacoes_estoque,
    list_movimentacoes_estoque,
    registrar_ajuste_inventario,
)
from src.services.exceptions import DomainError
from src.ui.components.layout import (
    ensure_page_access,
    fmt_brl,
    fmt_datetime,
    fmt_qty,
    render_page_header,
    user_can,
)

user = ensure_page_access("estoque")
can_adjust = user_can(user, "estoque:adjust")

render_page_header(
    "Controle de Estoque",
    "Posição em tempo real de insumos, alertas de reposição, ajustes auditados e razão de movimentações.",
    icon_name="package",
)

pos_completa = get_estoque_position()
total_imobilizado = sum(float(i["valor_imobilizado"]) for i in pos_completa)
qtd_criticos = sum(1 for i in pos_completa if i["status_estoque"] == "CRITICO")
qtd_atencao = sum(1 for i in pos_completa if i["status_estoque"] == "ATENCAO")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Insumos Ativos", len(pos_completa))
m2.metric("Valor Imobilizado", fmt_brl(total_imobilizado))
m3.metric("Críticos (≤ Mínimo)", qtd_criticos, delta_color="inverse" if qtd_criticos else "normal")
m4.metric("Em Atenção", qtd_atencao)

tab_pos, tab_mov, tab_inv = st.tabs(
    [
        ":material/inventory_2: Posição Atual",
        ":material/history: Extrato de Movimentações",
        ":material/tune: Ajuste de Inventário",
    ]
)

with tab_pos:
    c1, c2 = st.columns(2)
    locs = ["Todas"] + list_localizacoes_estoque()
    loc_sel = c1.selectbox("Localização", locs)
    apenas_crit = c2.checkbox("Exibir apenas itens críticos (≤ mínimo)")
    pos = get_estoque_position(apenas_criticos=apenas_crit, localizacao=loc_sel)

    if pos:
        status_badge = {"CRITICO": "CRÍTICO", "ATENCAO": "ATENÇÃO", "SAUDAVEL": "SAUDÁVEL"}
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Status": status_badge.get(i["status_estoque"], i["status_estoque"]),
                        "SKU": i["sku"],
                        "Insumo": i["nome"],
                        "Categoria": i["categoria_nome"],
                        "Localização": i["localizacao"],
                        "Saldo Atual": fmt_qty(i["estoque_atual"], i["unidade_medida"]),
                        "Mínimo": fmt_qty(i["estoque_minimo"], i["unidade_medida"]),
                        "Custo Médio": f"R$ {float(i['custo_medio_atual']):.4f}",
                        "Valor em Estoque": fmt_brl(i["valor_imobilizado"]),
                    }
                    for i in pos
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum insumo encontrado para os filtros aplicados.")

with tab_mov:
    insumos = list_insumos(apenas_ativos=False)
    f1, f2, f3 = st.columns(3)
    ins_opts = {"Todos": None, **{f"{i['sku']} - {i['nome']}": int(i["id"]) for i in insumos}}
    ins_sel = f1.selectbox("Insumo", list(ins_opts.keys()))
    tipo_sel = f2.selectbox(
        "Tipo de Movimentação",
        [
            "Todos",
            "ENTRADA_COMPRA",
            "SAIDA_VENDA",
            "SAIDA_PERDA",
            "AJUSTE_ENTRADA",
            "AJUSTE_SAIDA",
            "ESTORNO_VENDA",
        ],
    )
    mod_sel = f3.selectbox("Módulo Origem", ["Todos", "COMPRAS", "VENDAS", "OPERACIONAL", "ESTOQUE"])

    movs = list_movimentacoes_estoque(
        insumo_id=ins_opts[ins_sel],
        tipo_movimentacao=tipo_sel,
        origem_modulo=mod_sel,
        limit=200,
    )
    if movs:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Data e Hora": fmt_datetime(m["criado_em"]),
                        "Insumo": m["insumo_nome"],
                        "Tipo": m["tipo_movimentacao"],
                        "Qtd.": fmt_qty(m["quantidade"], m["unidade_medida"]),
                        "Saldo Ant.": fmt_qty(m["saldo_anterior"], m["unidade_medida"]),
                        "Saldo Pós": fmt_qty(m["saldo_posterior"], m["unidade_medida"]),
                        "Origem": m["origem_modulo"],
                        "Motivo": m["motivo"] or "-",
                        "Usuário": m["usuario_nome"],
                    }
                    for m in movs
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma movimentação encontrada para os filtros selecionados.")

with tab_inv:
    if not can_adjust:
        st.info("Seu perfil não possui permissão para registrar ajustes de inventário.")
    else:
        st.caption(
            "Informe a contagem física apurada no inventário. O sistema calcula automaticamente "
            "a diferença e registra o ajuste de entrada ou saída no histórico."
        )
        ins_ativos = list_insumos(apenas_ativos=True)
        if ins_ativos:
            imap = {
                f"{i['sku']} - {i['nome']} (atual: {fmt_qty(i['estoque_atual'], i['unidade_medida'])})": i
                for i in ins_ativos
            }
            sel_i = imap[st.selectbox("Selecione o Insumo", list(imap.keys()), key="inv_sel_ins")]
            with st.form("form_ajuste_inv"):
                novo_saldo = st.number_input(
                    f"Saldo Físico Apurado ({sel_i['unidade_medida']})",
                    min_value=0.0,
                    value=float(sel_i["estoque_atual"]),
                    step=1.0,
                    format="%.3f",
                )
                motivo = st.text_input(
                    "Justificativa*",
                    placeholder="Ex.: Conferência física semanal do balcão",
                )
                if st.form_submit_button("Registrar Ajuste de Inventário", type="primary"):
                    try:
                        res = registrar_ajuste_inventario(
                            insumo_id=int(sel_i["id"]),
                            novo_saldo_fisico=novo_saldo,
                            motivo=motivo,
                            usuario_id=int(user["id"]),
                        )
                        st.success(
                            f"Ajuste de inventário registrado! "
                            f"Saldo atualizado de {res['saldo_anterior']} para {res['saldo_posterior']} {sel_i['unidade_medida']}."
                        )
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
