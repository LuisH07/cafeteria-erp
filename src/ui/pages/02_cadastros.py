"""Página 02 — Módulo de Cadastros Base e Ficha Técnica (Receitas)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.services.cadastros_service import (
    create_categoria,
    create_cliente,
    create_fornecedor,
    create_insumo,
    create_produto,
    list_categorias,
    list_clientes,
    list_ficha_tecnica,
    list_fornecedores,
    list_historico_precos,
    list_insumos,
    list_produtos,
    remove_ficha_tecnica_item,
    update_categoria,
    update_cliente,
    update_fornecedor,
    update_insumo,
    update_produto,
    upsert_ficha_tecnica_item,
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

user = ensure_page_access("cadastros")
can_write = user_can(user, "cadastros:write")

render_page_header(
    "Catálogo e Cadastros",
    "Gestão de produtos do cardápio, receitas, insumos, fornecedores e clientes da cafeteria.",
    icon_name="clipboard-list",
)

tabs = st.tabs(
    [
        ":material/local_cafe: Produtos (Cardápio)",
        ":material/science: Ficha Técnica (Receitas)",
        ":material/inventory_2: Insumos",
        ":material/local_shipping: Fornecedores",
        ":material/group: Clientes",
        ":material/sell: Categorias",
    ]
)

# -----------------------------------------------------------------------------
# ABA 1: PRODUTOS
# -----------------------------------------------------------------------------
with tabs[0]:
    produtos = list_produtos(apenas_ativos=False)
    cats_prod = list_categorias(tipo="PRODUTO", apenas_ativas=True)

    if produtos:
        df_p = pd.DataFrame(
            [
                {
                    "ID": p["id"],
                    "SKU": p["sku"],
                    "Produto": p["nome"],
                    "Categoria": p["categoria_nome"],
                    "Tipo": p["tipo_produto"],
                    "Preço Venda": fmt_brl(p["preco_venda"]),
                    "CMV Est.": fmt_brl(p["custo_cmv_estimado"]),
                    "Margem Est.": f"{float(p['margem_estimada_pct']):.1f}%",
                    "Insumos Ficha": p["qtd_insumos_ficha"],
                    "Preparo (s)": p["tempo_preparo_estimado_seg"],
                    "Ativo": "Ativo" if p["ativo"] else "Inativo",
                }
                for p in produtos
            ]
        )
        st.dataframe(df_p, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado.")

    if can_write:
        col_new, col_edit = st.columns(2)
        with col_new:
            with st.form("form_novo_produto"):
                st.subheader("Novo Produto do Cardápio")
                sku = st.text_input("SKU*", placeholder="PRD-CAP-02")
                nome = st.text_input("Nome do Produto*", placeholder="Cappuccino Canela")
                cat_map = {c["nome"]: int(c["id"]) for c in cats_prod}
                cat_sel = st.selectbox("Categoria*", list(cat_map.keys())) if cat_map else None
                tipo = st.selectbox("Tipo", ["PREPARADO", "REVENDA"])
                preco = st.number_input("Preço de Venda (R$)*", min_value=0.50, value=14.00, step=0.50)
                tempo = st.number_input("Tempo Estimado de Preparo (segundos)", min_value=0, value=180, step=10)
                if st.form_submit_button("Cadastrar Produto", type="primary"):
                    if not cat_sel:
                        st.error("Cadastre ao menos uma categoria do tipo PRODUTO.")
                    else:
                        try:
                            create_produto(
                                sku=sku,
                                nome=nome,
                                categoria_id=cat_map[cat_sel],
                                tipo_produto=tipo,
                                preco_venda=preco,
                                tempo_preparo_estimado_seg=int(tempo),
                                usuario_id=int(user["id"]),
                            )
                            st.success("Produto cadastrado! Configure sua Ficha Técnica na aba ao lado.")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

        with col_edit:
            if produtos and cats_prod:
                st.subheader("Editar Produto")
                prod_map = {f"{p['sku']} - {p['nome']}": p for p in produtos}
                sel_p = prod_map[st.selectbox("Selecione o Produto", list(prod_map.keys()), key="sel_edit_prod")]
                cat_map = {c["nome"]: int(c["id"]) for c in cats_prod}
                cat_names = list(cat_map.keys())
                cat_idx = cat_names.index(sel_p["categoria_nome"]) if sel_p["categoria_nome"] in cat_names else 0

                with st.form("form_edit_produto"):
                    e_nome = st.text_input("Nome", value=sel_p["nome"])
                    e_cat = st.selectbox("Categoria", cat_names, index=cat_idx)
                    e_tipo = st.selectbox(
                        "Tipo", ["PREPARADO", "REVENDA"], index=0 if sel_p["tipo_produto"] == "PREPARADO" else 1
                    )
                    e_preco = st.number_input(
                        "Preço de Venda (R$)", min_value=0.50, value=float(sel_p["preco_venda"]), step=0.50
                    )
                    e_tempo = st.number_input(
                        "Tempo Preparo (seg)", min_value=0, value=int(sel_p["tempo_preparo_estimado_seg"]), step=10
                    )
                    e_ativo = st.checkbox("Produto Ativo", value=bool(sel_p["ativo"]))
                    if st.form_submit_button("Salvar Alterações"):
                        try:
                            update_produto(
                                produto_id=int(sel_p["id"]),
                                nome=e_nome,
                                categoria_id=cat_map[e_cat],
                                tipo_produto=e_tipo,
                                preco_venda=e_preco,
                                tempo_preparo_estimado_seg=int(e_tempo),
                                ativo=e_ativo,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Produto atualizado (alterações de preço ficam registradas no histórico).")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

                with st.expander(":material/trending_up: Histórico de Preços deste Produto"):
                    hist = list_historico_precos(int(sel_p["id"]))
                    if hist:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Data": fmt_datetime(h["criado_em"]),
                                        "Preço Anterior": fmt_brl(h["preco_anterior"]) if h["preco_anterior"] else "-",
                                        "Preço Novo": fmt_brl(h["preco_novo"]),
                                        "Alterado por": h["alterado_por_nome"],
                                    }
                                    for h in hist
                                ]
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

# -----------------------------------------------------------------------------
# ABA 2: FICHA TÉCNICA (RECEITAS)
# -----------------------------------------------------------------------------
with tabs[1]:
    st.caption(
        "A Ficha Técnica vincula cada produto do cardápio aos insumos consumidos no preparo ou revenda, "
        "garantindo baixa automática de estoque e cálculo exato do CMV em cada venda."
    )
    produtos_ativos = list_produtos(apenas_ativos=True)
    insumos_ativos = list_insumos(apenas_ativos=True)

    if produtos_ativos:
        p_map = {f"{p['sku']} - {p['nome']} ({fmt_brl(p['preco_venda'])})": p for p in produtos_ativos}
        p_sel = p_map[st.selectbox("Selecione o Produto", list(p_map.keys()), key="sel_prod_ficha")]
        ficha = list_ficha_tecnica(int(p_sel["id"]))

        custo_total_ficha = sum(float(f["custo_item"]) for f in ficha)
        preco_p = float(p_sel["preco_venda"])
        margem_pct = ((preco_p - custo_total_ficha) / preco_p * 100) if preco_p > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Preço de Venda", fmt_brl(preco_p))
        m2.metric("CMV da Receita", fmt_brl(custo_total_ficha))
        m3.metric("Margem Bruta Unitária", f"{margem_pct:.1f}%", fmt_brl(preco_p - custo_total_ficha))

        if ficha:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "SKU Insumo": f["insumo_sku"],
                            "Insumo": f["insumo_nome"],
                            "Qtd. por Unidade": fmt_qty(f["quantidade"], f["unidade_medida"]),
                            "Custo Unit. Insumo": f"R$ {float(f['custo_medio_atual']):.4f}",
                            "Custo na Receita": fmt_brl(f["custo_item"]),
                        }
                        for f in ficha
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("Este produto ainda não possui insumos na Ficha Técnica (não poderá ser vendido no PDV).")

        if can_write and insumos_ativos:
            c_add, c_rem = st.columns(2)
            with c_add:
                with st.form("form_add_ficha"):
                    st.markdown("**Configurar Insumo na Receita**")
                    ins_map = {f"{i['sku']} - {i['nome']} ({i['unidade_medida']})": i for i in insumos_ativos}
                    ins_sel = ins_map[st.selectbox("Insumo", list(ins_map.keys()))]
                    qtd = st.number_input(
                        f"Quantidade consumida ({ins_sel['unidade_medida']})",
                        min_value=0.001,
                        value=18.0 if ins_sel["unidade_medida"] == "g" else (150.0 if ins_sel["unidade_medida"] == "ml" else 1.0),
                        step=1.0,
                        format="%.3f",
                    )
                    if st.form_submit_button("Salvar Item na Ficha Técnica", type="primary"):
                        try:
                            upsert_ficha_tecnica_item(
                                produto_id=int(p_sel["id"]),
                                insumo_id=int(ins_sel["id"]),
                                quantidade=qtd,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Item salvo na ficha técnica!")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

            with c_rem:
                if ficha:
                    with st.form("form_rem_ficha"):
                        st.markdown("**Remover Insumo da Receita**")
                        f_map = {f"{f['insumo_nome']} ({f['quantidade']} {f['unidade_medida']})": int(f["id"]) for f in ficha}
                        rem_sel = st.selectbox("Item a remover", list(f_map.keys()))
                        if st.form_submit_button("Remover Item"):
                            try:
                                remove_ficha_tecnica_item(item_id=f_map[rem_sel], usuario_id=int(user["id"]))
                                st.success("Item removido da ficha técnica.")
                                st.rerun()
                            except DomainError as exc:
                                st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 3: INSUMOS
# -----------------------------------------------------------------------------
with tabs[2]:
    insumos = list_insumos(apenas_ativos=False)
    cats_ins = list_categorias(tipo="INSUMO", apenas_ativas=True)
    if insumos:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "SKU": i["sku"],
                        "Insumo": i["nome"],
                        "Categoria": i["categoria_nome"],
                        "Un.": i["unidade_medida"],
                        "Saldo Atual": fmt_qty(i["estoque_atual"], i["unidade_medida"]),
                        "Mínimo": fmt_qty(i["estoque_minimo"], i["unidade_medida"]),
                        "Custo Médio": f"R$ {float(i['custo_medio_atual']):.4f}",
                        "Localização": i["localizacao"],
                        "Perecível": "Sim" if i["perecivel"] else "Não",
                        "Ativo": "Ativo" if i["ativo"] else "Inativo",
                    }
                    for i in insumos
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if can_write:
        c_n, c_e = st.columns(2)
        with c_n:
            with st.form("form_novo_insumo"):
                st.subheader("Novo Insumo")
                sku = st.text_input("SKU*", placeholder="INS-CAN-PO")
                nome = st.text_input("Nome do Insumo*", placeholder="Canela em Pó")
                cat_map = {c["nome"]: int(c["id"]) for c in cats_ins}
                cat_sel = st.selectbox("Categoria*", list(cat_map.keys())) if cat_map else None
                un = st.selectbox("Unidade Base*", ["g", "ml", "un"])
                minimo = st.number_input("Estoque Mínimo", min_value=0.0, value=500.0, step=10.0)
                custo = st.number_input("Custo Médio Inicial (R$ por unidade)", min_value=0.0, value=0.05, step=0.005, format="%.4f")
                loc = st.text_input("Localização Física", value="Estoque Central")
                perec = st.checkbox("Item Perecível")
                if st.form_submit_button("Cadastrar Insumo", type="primary"):
                    if not cat_sel:
                        st.error("Cadastre ao menos uma categoria do tipo INSUMO.")
                    else:
                        try:
                            create_insumo(
                                sku=sku,
                                nome=nome,
                                categoria_id=cat_map[cat_sel],
                                unidade_medida=un,
                                estoque_minimo=minimo,
                                custo_medio_atual=custo,
                                localizacao=loc,
                                perecivel=perec,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Insumo cadastrado! Dê entrada no saldo pelo módulo Compras.")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

        with c_e:
            if insumos and cats_ins:
                st.subheader("Editar Insumo")
                imap = {f"{i['sku']} - {i['nome']}": i for i in insumos}
                sel_i = imap[st.selectbox("Selecione o Insumo", list(imap.keys()), key="sel_edit_ins")]
                cat_map = {c["nome"]: int(c["id"]) for c in cats_ins}
                cat_names = list(cat_map.keys())
                cat_idx = cat_names.index(sel_i["categoria_nome"]) if sel_i["categoria_nome"] in cat_names else 0
                with st.form("form_edit_insumo"):
                    e_nome = st.text_input("Nome", value=sel_i["nome"])
                    e_cat = st.selectbox("Categoria", cat_names, index=cat_idx)
                    e_min = st.number_input("Estoque Mínimo", min_value=0.0, value=float(sel_i["estoque_minimo"]))
                    e_loc = st.text_input("Localização", value=sel_i["localizacao"])
                    e_per = st.checkbox("Perecível", value=bool(sel_i["perecivel"]))
                    e_atv = st.checkbox("Ativo", value=bool(sel_i["ativo"]))
                    if st.form_submit_button("Salvar Insumo"):
                        try:
                            update_insumo(
                                insumo_id=int(sel_i["id"]),
                                nome=e_nome,
                                categoria_id=cat_map[e_cat],
                                estoque_minimo=e_min,
                                localizacao=e_loc,
                                perecivel=e_per,
                                ativo=e_atv,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Insumo atualizado com sucesso.")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 4: FORNECEDORES
# -----------------------------------------------------------------------------
with tabs[3]:
    fornecedores = list_fornecedores(apenas_ativos=False)
    if fornecedores:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Nome Fantasia": f["nome_fantasia"],
                        "Razão Social": f["razao_social"],
                        "CNPJ": f["cnpj"],
                        "Telefone": f["telefone"] or "-",
                        "E-mail": f["email"] or "-",
                        "Prazo (dias)": f["prazo_pagamento_dias"],
                        "Ativo": "Ativo" if f["ativo"] else "Inativo",
                    }
                    for f in fornecedores
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    if can_write:
        c_n, c_e = st.columns(2)
        with c_n:
            with st.form("form_novo_forn"):
                st.subheader("Novo Fornecedor")
                razao = st.text_input("Razão Social*")
                fantasia = st.text_input("Nome Fantasia*")
                cnpj = st.text_input("CNPJ*", placeholder="00.000.000/0001-00")
                tel = st.text_input("Telefone")
                email = st.text_input("E-mail")
                prazo = st.number_input("Prazo de Pagamento (dias)", min_value=0, value=15, step=1)
                if st.form_submit_button("Cadastrar Fornecedor", type="primary"):
                    try:
                        create_fornecedor(
                            razao_social=razao,
                            nome_fantasia=fantasia,
                            cnpj=cnpj,
                            telefone=tel,
                            email=email,
                            prazo_pagamento_dias=int(prazo),
                            usuario_id=int(user["id"]),
                        )
                        st.success("Fornecedor cadastrado!")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
        with c_e:
            if fornecedores:
                st.subheader("Editar Fornecedor")
                fmap = {f"{f['nome_fantasia']} ({f['cnpj']})": f for f in fornecedores}
                sel_f = fmap[st.selectbox("Selecione o Fornecedor", list(fmap.keys()), key="sel_edit_forn")]
                with st.form("form_edit_forn"):
                    e_razao = st.text_input("Razão Social", value=sel_f["razao_social"])
                    e_fant = st.text_input("Nome Fantasia", value=sel_f["nome_fantasia"])
                    e_tel = st.text_input("Telefone", value=sel_f["telefone"] or "")
                    e_email = st.text_input("E-mail", value=sel_f["email"] or "")
                    e_prazo = st.number_input("Prazo (dias)", min_value=0, value=int(sel_f["prazo_pagamento_dias"]))
                    e_atv = st.checkbox("Ativo", value=bool(sel_f["ativo"]))
                    if st.form_submit_button("Salvar Fornecedor"):
                        try:
                            update_fornecedor(
                                fornecedor_id=int(sel_f["id"]),
                                razao_social=e_razao,
                                nome_fantasia=e_fant,
                                telefone=e_tel,
                                email=e_email,
                                prazo_pagamento_dias=int(e_prazo),
                                ativo=e_atv,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Fornecedor atualizado!")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 5: CLIENTES
# -----------------------------------------------------------------------------
with tabs[4]:
    clientes = list_clientes(apenas_ativos=False)
    if clientes:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Nome": c["nome"],
                        "Documento": c["cpf_cnpj"] or "-",
                        "Tipo": c["tipo_cliente"],
                        "Telefone": c["telefone"] or "-",
                        "E-mail": c["email"] or "-",
                        "Ativo": "Ativo" if c["ativo"] else "Inativo",
                    }
                    for c in clientes
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    if can_write:
        c_n, c_e = st.columns(2)
        with c_n:
            with st.form("form_novo_cli"):
                st.subheader("Novo Cliente")
                nome = st.text_input("Nome ou Razão Social*")
                doc = st.text_input("CPF ou CNPJ (opcional)")
                tipo = st.selectbox("Tipo de Cliente", ["FIDELIDADE", "BALCAO", "CORPORATIVO"])
                tel = st.text_input("Telefone")
                email = st.text_input("E-mail")
                if st.form_submit_button("Cadastrar Cliente", type="primary"):
                    try:
                        create_cliente(
                            nome=nome,
                            cpf_cnpj=doc,
                            telefone=tel,
                            email=email,
                            tipo_cliente=tipo,
                            usuario_id=int(user["id"]),
                        )
                        st.success("Cliente cadastrado!")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
        with c_e:
            if clientes:
                st.subheader("Editar Cliente")
                cmap = {f"{c['nome']} ({c['tipo_cliente']})": c for c in clientes}
                sel_c = cmap[st.selectbox("Selecione o Cliente", list(cmap.keys()), key="sel_edit_cli")]
                tipos_c = ["BALCAO", "FIDELIDADE", "CORPORATIVO"]
                with st.form("form_edit_cli"):
                    e_nome = st.text_input("Nome", value=sel_c["nome"])
                    e_tipo = st.selectbox("Tipo", tipos_c, index=tipos_c.index(sel_c["tipo_cliente"]))
                    e_tel = st.text_input("Telefone", value=sel_c["telefone"] or "")
                    e_email = st.text_input("E-mail", value=sel_c["email"] or "")
                    e_atv = st.checkbox("Ativo", value=bool(sel_c["ativo"]))
                    if st.form_submit_button("Salvar Cliente"):
                        try:
                            update_cliente(
                                cliente_id=int(sel_c["id"]),
                                nome=e_nome,
                                telefone=e_tel,
                                email=e_email,
                                tipo_cliente=e_tipo,
                                ativo=e_atv,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Cliente atualizado!")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 6: CATEGORIAS
# -----------------------------------------------------------------------------
with tabs[5]:
    categorias = list_categorias(apenas_ativas=False)
    if categorias:
        st.dataframe(
            pd.DataFrame(
                [
                    {"ID": c["id"], "Nome": c["nome"], "Tipo": c["tipo"], "Status": "Ativa" if c["ativo"] else "Inativa"}
                    for c in categorias
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    if can_write:
        c_n, c_e = st.columns(2)
        with c_n:
            with st.form("form_nova_cat"):
                st.subheader("Nova Categoria")
                nome = st.text_input("Nome*")
                tipo = st.selectbox("Tipo*", ["PRODUTO", "INSUMO", "DESPESA", "RECEITA"])
                if st.form_submit_button("Cadastrar Categoria", type="primary"):
                    try:
                        create_categoria(nome=nome, tipo=tipo, usuario_id=int(user["id"]))
                        st.success("Categoria cadastrada!")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))
        with c_e:
            if categorias:
                st.subheader("Editar Categoria")
                cat_map = {f"[{c['tipo']}] {c['nome']}": c for c in categorias}
                sel_cat = cat_map[st.selectbox("Selecione a Categoria", list(cat_map.keys()), key="sel_edit_cat")]
                with st.form("form_edit_cat"):
                    e_nome = st.text_input("Nome", value=sel_cat["nome"])
                    e_atv = st.checkbox("Ativa", value=bool(sel_cat["ativo"]))
                    if st.form_submit_button("Salvar Categoria"):
                        try:
                            update_categoria(
                                categoria_id=int(sel_cat["id"]),
                                nome=e_nome,
                                ativo=e_atv,
                                usuario_id=int(user["id"]),
                            )
                            st.success("Categoria atualizada!")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))
