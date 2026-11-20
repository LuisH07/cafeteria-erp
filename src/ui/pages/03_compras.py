"""Página 03 — Módulo de Compras integrado a Estoque e Financeiro."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.services.cadastros_service import list_fornecedores, list_insumos
from src.services.compras_service import (
    cancelar_compra,
    criar_compra,
    get_compra_detalhes,
    list_compras,
    receber_compra,
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

user = ensure_page_access("compras")
can_write = user_can(user, "compras:write")

render_page_header(
    "🛒 Compras & Suprimentos",
    "Registro de aquisições de insumos com entrada automática no estoque, recálculo de custo médio e conta a pagar.",
)

if "compra_cart" not in st.session_state:
    st.session_state["compra_cart"] = []

tab_nova, tab_hist = st.tabs(["➕ Novo Pedido de Compra", "📄 Pedidos e Recebimentos"])

# -----------------------------------------------------------------------------
# ABA 1: NOVO PEDIDO DE COMPRA
# -----------------------------------------------------------------------------
with tab_nova:
    if not can_write:
        st.info("Seu perfil possui permissão apenas de visualização neste módulo.")
    else:
        fornecedores = list_fornecedores(apenas_ativos=True)
        insumos = list_insumos(apenas_ativos=True)

        if not fornecedores or not insumos:
            st.warning("Cadastre ao menos um fornecedor e um insumo ativos antes de registrar compras.")
        else:
            st.subheader("1. Adicionar Insumos ao Pedido")
            ins_map = {f"{i['sku']} — {i['nome']} (base: {i['unidade_medida']})": i for i in insumos}
            sel_ins = ins_map[st.selectbox("Selecione o Insumo", list(ins_map.keys()), key="cmp_ins_sel")]
            base_un = sel_ins["unidade_medida"]

            un_options = (
                ["g", "kg (converte ×1000)"]
                if base_un == "g"
                else (["ml", "L (converte ×1000)"] if base_un == "ml" else ["un"])
            )

            with st.form("form_add_item_compra"):
                c1, c2, c3 = st.columns(3)
                un_entrada = c1.selectbox("Unidade de Compra", un_options)
                fator = 1000.0 if ("kg" in un_entrada or "L (" in un_entrada) else 1.0
                qtd_in = c2.number_input("Quantidade", min_value=0.01, value=5.0 if fator == 1000 else 50.0, step=1.0)
                custo_sug = float(sel_ins["custo_medio_atual"]) * fator
                custo_in = c3.number_input(
                    f"Custo Unitário (R$ por {un_entrada.split()[0]})",
                    min_value=0.0001,
                    value=max(0.01, round(custo_sug, 4)),
                    step=0.50 if fator == 1000 else 0.01,
                    format="%.4f",
                )
                c4, c5 = st.columns(2)
                lote = c4.text_input("Lote (opcional)", placeholder="LT-2026-01")
                validade = c5.date_input(
                    "Data de Validade",
                    value=date.today() + timedelta(days=15 if sel_ins["perecivel"] else 180),
                )

                if st.form_submit_button("Adicionar Item ao Pedido"):
                    qtd_base = round(qtd_in * fator, 3)
                    custo_base = round(custo_in / fator, 4)
                    st.session_state["compra_cart"].append(
                        {
                            "insumo_id": int(sel_ins["id"]),
                            "insumo_nome": sel_ins["nome"],
                            "unidade_medida": base_un,
                            "quantidade": qtd_base,
                            "custo_unitario": custo_base,
                            "subtotal": round(qtd_base * custo_base, 2),
                            "lote": lote,
                            "data_validade": validade,
                        }
                    )
                    st.success(
                        f"Adicionado: {fmt_qty(qtd_base, base_un)} de {sel_ins['nome']} "
                        f"(R$ {custo_base:.4f}/{base_un})."
                    )
                    st.rerun()

            cart = st.session_state["compra_cart"]
            if cart:
                st.subheader("2. Itens no Pedido Atual")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Insumo": it["insumo_nome"],
                                "Quantidade (base)": fmt_qty(it["quantidade"], it["unidade_medida"]),
                                "Custo Unit. (base)": f"R$ {it['custo_unitario']:.4f}",
                                "Subtotal": fmt_brl(it["subtotal"]),
                                "Lote": it["lote"] or "-",
                                "Validade": it["data_validade"].strftime("%d/%m/%Y") if it["data_validade"] else "-",
                            }
                            for it in cart
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                total_pedido = sum(it["subtotal"] for it in cart)
                st.metric("Total do Pedido de Compra", fmt_brl(total_pedido))

                if st.button("🗑️ Limpar Itens do Pedido"):
                    st.session_state["compra_cart"] = []
                    st.rerun()

                st.subheader("3. Fechamento do Pedido")
                with st.form("form_finalizar_compra"):
                    f_map = {
                        f"{f['nome_fantasia']} (prazo {f['prazo_pagamento_dias']}d)": int(f["id"])
                        for f in fornecedores
                    }
                    c_f, c_p = st.columns(2)
                    forn_sel = c_f.selectbox("Fornecedor*", list(f_map.keys()))
                    forma = c_p.selectbox(
                        "Forma de Pagamento*",
                        ["BOLETO", "PIX", "TRANSFERENCIA", "CARTAO_CORP", "DINHEIRO"],
                    )
                    obs = st.text_input("Observações", placeholder="Ex.: NF 4521 — entrega matinal")
                    c_chk1, c_chk2 = st.columns(2)
                    receber_agora = c_chk1.checkbox("Já recebido (dar entrada no Estoque e Financeiro agora)", value=True)
                    liquidar_avista = c_chk2.checkbox("Liquidar no caixa se prazo = 0 e PIX/Dinheiro", value=False)

                    if st.form_submit_button("✅ Salvar Pedido de Compra", type="primary", use_container_width=True):
                        try:
                            compra = criar_compra(
                                fornecedor_id=f_map[forn_sel],
                                forma_pagamento=forma,
                                itens=cart,
                                usuario_id=int(user["id"]),
                                observacoes=obs,
                                receber_agora=receber_agora,
                                liquidar_se_avista=liquidar_avista,
                            )
                            st.session_state["compra_cart"] = []
                            st.success(
                                f"Pedido **{compra['numero_pedido']}** registrado com status **{compra['status']}** "
                                f"({fmt_brl(compra['valor_total'])})!"
                            )
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 2: PEDIDOS E RECEBIMENTOS
# -----------------------------------------------------------------------------
with tab_hist:
    status_filtro = st.selectbox("Filtrar por Status", ["Todos", "CONFIRMADA", "RECEBIDA", "CANCELADA"])
    compras = list_compras(status=status_filtro, limit=100)

    if compras:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": c["id"],
                        "Pedido": c["numero_pedido"],
                        "Fornecedor": c["fornecedor_nome"],
                        "Data Pedido": fmt_datetime(c["data_pedido"]),
                        "Recebimento": fmt_datetime(c["data_recebimento"]),
                        "Itens": c["qtd_itens"],
                        "Total": fmt_brl(c["valor_total"]),
                        "Pagamento": c["forma_pagamento"],
                        "Status": c["status"],
                    }
                    for c in compras
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        sel_map = {f"{c['numero_pedido']} — {c['fornecedor_nome']} ({c['status']})": int(c["id"]) for c in compras}
        sel_id = sel_map[st.selectbox("Inspecionar / Ações no Pedido", list(sel_map.keys()))]
        det = get_compra_detalhes(sel_id)

        st.markdown(
            f"**Pedido:** `{det['numero_pedido']}` | **Fornecedor:** {det['fornecedor_nome']} | "
            f"**Status:** `{det['status']}` | **Total:** {fmt_brl(det['valor_total'])}"
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "SKU": it["insumo_sku"],
                        "Insumo": it["insumo_nome"],
                        "Qtd.": fmt_qty(it["quantidade"], it["unidade_medida"]),
                        "Custo Unit.": f"R$ {float(it['custo_unitario']):.4f}",
                        "Subtotal": fmt_brl(it["subtotal"]),
                        "Lote": it["lote"] or "-",
                    }
                    for it in det["itens"]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        if can_write and det["status"] in {"RASCUNHO", "CONFIRMADA"}:
            c_rec, c_can = st.columns(2)
            with c_rec:
                if st.button("📥 Confirmar Recebimento (Estoque + Financeiro)", type="primary", use_container_width=True):
                    try:
                        receber_compra(compra_id=sel_id, usuario_id=int(user["id"]))
                        st.success("Compra recebida! Estoque atualizado e Conta a Pagar gerada.")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
            with c_can:
                with st.form("form_cancelar_compra"):
                    motivo_c = st.text_input("Motivo do cancelamento*")
                    if st.form_submit_button("❌ Cancelar Pedido", use_container_width=True):
                        try:
                            cancelar_compra(compra_id=sel_id, motivo=motivo_c, usuario_id=int(user["id"]))
                            st.warning("Pedido cancelado.")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))
    else:
        st.info("Nenhum pedido de compra encontrado para o filtro selecionado.")
