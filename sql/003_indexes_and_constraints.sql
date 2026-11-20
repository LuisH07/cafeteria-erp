-- =============================================================================
-- 003_indexes_and_constraints.sql
-- Índices de performance para operações transacionais e consultas BI (2ª VA)
-- =============================================================================

-- Auditoria
CREATE INDEX IF NOT EXISTS idx_audit_logs_criado_em ON audit_logs (criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_modulo ON audit_logs (modulo, criado_em DESC);

-- Cadastros e Ficha Técnica
CREATE INDEX IF NOT EXISTS idx_insumos_categoria ON insumos (categoria_id);
CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos (categoria_id);
CREATE INDEX IF NOT EXISTS idx_ficha_tecnica_produto ON ficha_tecnica_itens (produto_id) WHERE ativo = TRUE;
CREATE INDEX IF NOT EXISTS idx_ficha_tecnica_insumo ON ficha_tecnica_itens (insumo_id) WHERE ativo = TRUE;
CREATE INDEX IF NOT EXISTS idx_hist_preco_produto ON historico_precos_produtos (produto_id, criado_em DESC);

-- Compras
CREATE INDEX IF NOT EXISTS idx_compras_fornecedor ON compras (fornecedor_id);
CREATE INDEX IF NOT EXISTS idx_compras_status_data ON compras (status, data_pedido DESC);
CREATE INDEX IF NOT EXISTS idx_compra_itens_compra ON compra_itens (compra_id);
CREATE INDEX IF NOT EXISTS idx_compra_itens_insumo ON compra_itens (insumo_id);

-- Estoque
CREATE INDEX IF NOT EXISTS idx_mov_estoque_insumo_data ON movimentacoes_estoque (insumo_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_mov_estoque_tipo_data ON movimentacoes_estoque (tipo_movimentacao, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_mov_estoque_origem ON movimentacoes_estoque (origem_modulo, origem_id);

-- Vendas
CREATE INDEX IF NOT EXISTS idx_vendas_data_status ON vendas (data_venda DESC, status);
CREATE INDEX IF NOT EXISTS idx_vendas_cliente ON vendas (cliente_id);
CREATE INDEX IF NOT EXISTS idx_vendas_canal_pag ON vendas (canal_venda, forma_pagamento);
CREATE INDEX IF NOT EXISTS idx_venda_itens_venda ON venda_itens (venda_id);
CREATE INDEX IF NOT EXISTS idx_venda_itens_produto ON venda_itens (produto_id);

-- Operacional
CREATE INDEX IF NOT EXISTS idx_ordens_preparo_status ON ordens_preparo (status, criado_em ASC);
CREATE INDEX IF NOT EXISTS idx_ordens_preparo_barista ON ordens_preparo (barista_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_ordem_hist_ordem ON ordem_preparo_historico (ordem_preparo_id, criado_em ASC);
CREATE INDEX IF NOT EXISTS idx_perdas_insumo_data ON registros_perdas (insumo_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_perdas_motivo ON registros_perdas (motivo, criado_em DESC);

-- Financeiro
CREATE INDEX IF NOT EXISTS idx_titulos_tipo_status_venc ON titulos_financeiros (tipo, status, data_vencimento);
CREATE INDEX IF NOT EXISTS idx_titulos_competencia ON titulos_financeiros (data_competencia);
CREATE INDEX IF NOT EXISTS idx_titulos_origem ON titulos_financeiros (origem_modulo, origem_id);
CREATE INDEX IF NOT EXISTS idx_mov_fin_data ON movimentacoes_financeiras (data_movimentacao DESC);
CREATE INDEX IF NOT EXISTS idx_mov_fin_titulo ON movimentacoes_financeiras (titulo_id);
