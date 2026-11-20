"""Página 06 — Módulo Operacional (Fila de Preparo do Barista e Registro de Perdas)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.services.cadastros_service import list_insumos
from src.services.exceptions import DomainError
from src.services.operacional_service import (
    avancar_ordem_preparo,
    list_ordens_preparo,
    list_registros_perdas,
    registrar_perda,
)
from src.ui.components.layout import (
    ensure_page_access,
    fmt_brl,
    fmt_datetime,
    fmt_qty,
    fmt_seconds,
    render_page_header,
    user_can,
)

user = ensure_page_access("operacional")
can_prepare = user_can(user, "operacional:prepare")
can_loss = user_can(user, "operacional:loss")

render_page_header(
    "☕ Operacional — Fila do Barista & Controle de Perdas",
    "Execução da atividade principal da cafeteria com controle de SLA de preparo e rastreabilidade de desperdícios.",
)

tab_fila, tab_hist, tab_perdas = st.tabs(
    ["🔥 Fila Ativa (Barista)", "✅ Ordens Concluídas", "⚠️ Registro de Perdas / Descartes"]
)

# -----------------------------------------------------------------------------
# ABA 1: FILA ATIVA (KANBAN 3 COLUNAS)
# -----------------------------------------------------------------------------
with tab_fila:
    abertas = list_ordens_preparo(apenas_abertas=True, limit=100)
    na_fila = [o for o in abertas if o["status"] == "NA_FILA"]
    em_prep = [o for o in abertas if o["status"] == "EM_PREPARO"]
    prontos = [o for o in abertas if o["status"] == "PRONTO"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader(f"🟡 Na Fila ({len(na_fila)})")
        if not na_fila:
            st.caption("Nenhum pedido aguardando.")
        for o in na_fila:
            with st.container(border=True):
                prio = "🔥 ALTA" if o["prioridade"] == "ALTA" else "Normal"
                st.markdown(f"**{o['numero_venda']}** · `{o['canal_venda']}` · {prio}")
                st.write(f"**Cliente:** {o['cliente_nome']}")
                st.write(f"**Itens:** {o['itens_resumo']}")
                st.caption(
                    f"Recebido: {fmt_datetime(o['criado_em'])} | Meta: {fmt_seconds(o['tempo_estimado_seg'])}"
                )
                if o["observacoes"]:
                    st.caption(f"Obs.: {o['observacoes']}")
                if can_prepare:
                    if st.button("▶️ Iniciar Preparo", key=f"btn_ini_{o['id']}", type="primary", use_container_width=True):
                        try:
                            avancar_ordem_preparo(
                                ordem_id=int(o["id"]),
                                novo_status="EM_PREPARO",
                                usuario_id=int(user["id"]),
                            )
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

    with col2:
        st.subheader(f"🟠 Em Preparo ({len(em_prep)})")
        if not em_prep:
            st.caption("Nenhum pedido em preparo.")
        for o in em_prep:
            with st.container(border=True):
                st.markdown(f"**{o['numero_venda']}** · `{o['canal_venda']}`")
                st.write(f"**Barista:** {o['barista_nome']}")
                st.write(f"**Itens:** {o['itens_resumo']}")
                st.caption(
                    f"Iniciado: {fmt_datetime(o['iniciado_em'])} | Espera: {fmt_seconds(o['tempo_espera_fila_seg'])}"
                )
                if o["observacoes"]:
                    st.caption(f"Obs.: {o['observacoes']}")
                if can_prepare:
                    if st.button("✅ Marcar Pronto", key=f"btn_pronto_{o['id']}", type="primary", use_container_width=True):
                        try:
                            avancar_ordem_preparo(
                                ordem_id=int(o["id"]),
                                novo_status="PRONTO",
                                usuario_id=int(user["id"]),
                            )
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

    with col3:
        st.subheader(f"🟢 Prontos p/ Entrega ({len(prontos)})")
        if not prontos:
            st.caption("Nenhum pedido pronto aguardando retirada.")
        for o in prontos:
            with st.container(border=True):
                st.markdown(f"**{o['numero_venda']}** · `{o['canal_venda']}`")
                st.write(f"**Cliente:** {o['cliente_nome']}")
                st.write(f"**Itens:** {o['itens_resumo']}")
                st.caption(
                    f"Preparo real: {fmt_seconds(o['tempo_preparo_real_seg'])} "
                    f"(meta: {fmt_seconds(o['tempo_estimado_seg'])})"
                )
                if can_prepare:
                    if st.button("📦 Confirmar Entrega", key=f"btn_ent_{o['id']}", use_container_width=True):
                        try:
                            avancar_ordem_preparo(
                                ordem_id=int(o["id"]),
                                novo_status="ENTREGUE",
                                usuario_id=int(user["id"]),
                            )
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 2: HISTÓRICO DE ORDENS
# -----------------------------------------------------------------------------
with tab_hist:
    st_sel = st.selectbox("Filtrar Status", ["ENTREGUE", "CANCELADO", "Todos"])
    ordens_h = list_ordens_preparo(status=st_sel, limit=120)
    if ordens_h:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Venda": o["numero_venda"],
                        "Canal": o["canal_venda"],
                        "Barista": o["barista_nome"],
                        "Itens": o["itens_resumo"],
                        "Criado em": fmt_datetime(o["criado_em"]),
                        "Espera Fila": fmt_seconds(o["tempo_espera_fila_seg"]),
                        "Preparo Real": fmt_seconds(o["tempo_preparo_real_seg"]),
                        "Meta SLA": fmt_seconds(o["tempo_estimado_seg"]),
                        "Status": o["status"],
                    }
                    for o in ordens_h
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma ordem encontrada para o filtro selecionado.")

# -----------------------------------------------------------------------------
# ABA 3: REGISTRO DE PERDAS E DESCARTES
# -----------------------------------------------------------------------------
with tab_perdas:
    st.caption(
        "Cada perda registrada baixa automaticamente o saldo do insumo (`SAIDA_PERDA`) "
        "e contabiliza o custo estimado para a DRE e o Dashboard BI."
    )
    if can_loss:
        insumos = list_insumos(apenas_ativos=True)
        if insumos:
            imap = {
                f"{i['sku']} — {i['nome']} (saldo: {fmt_qty(i['estoque_atual'], i['unidade_medida'])})": i
                for i in insumos
            }
            sel_i = imap[st.selectbox("Insumo Perdido / Descartado", list(imap.keys()), key="perda_ins_sel")]
            with st.form("form_registrar_perda"):
                c1, c2 = st.columns(2)
                qtd = c1.number_input(
                    f"Quantidade ({sel_i['unidade_medida']})*",
                    min_value=0.001,
                    value=1.0 if sel_i["unidade_medida"] == "un" else 100.0,
                    step=1.0,
                    format="%.3f",
                )
                motivo = c2.selectbox(
                    "Motivo da Perda*",
                    ["VENCIMENTO", "QUEBRA_PREPARO", "DESPERDICIO_BARISTA", "CONTAMINACAO", "OUTRO"],
                )
                obs = st.text_input("Observações", placeholder="Ex.: Leite aberto fora da temperatura ideal")
                if st.form_submit_button("⚠️ Registrar Perda e Baixar Estoque", type="primary"):
                    try:
                        res = registrar_perda(
                            insumo_id=int(sel_i["id"]),
                            quantidade=qtd,
                            motivo=motivo,
                            usuario_id=int(user["id"]),
                            observacoes=obs,
                        )
                        st.success(
                            f"Perda registrada! Custo apurado: **{fmt_brl(res['custo_estimado'])}** "
                            "e estoque atualizado."
                        )
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))

    st.subheader("Histórico de Perdas Registradas")
    perdas = list_registros_perdas(limit=100)
    if perdas:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Data/Hora": fmt_datetime(p["criado_em"]),
                        "Insumo": p["insumo_nome"],
                        "Quantidade": fmt_qty(p["quantidade"], p["unidade_medida"]),
                        "Motivo": p["motivo"],
                        "Custo Estimado": fmt_brl(p["custo_estimado"]),
                        "Observações": p["observacoes"] or "-",
                        "Registrado por": p["usuario_nome"],
                    }
                    for p in perdas
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma perda operacional registrada.")
