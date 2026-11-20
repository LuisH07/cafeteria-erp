-- =============================================================================
-- 002_views_bi.sql
-- Camada Analítica (Views SQL) para o Dashboard BI (2ª VA)
-- Todas as views consultam EXCLUSIVAMENTE os dados transacionais gerados pelo ERP.
-- =============================================================================

-- 1. Vendas Diárias (por canal e forma de pagamento)
CREATE OR REPLACE VIEW vw_bi_vendas_diarias AS
SELECT
    DATE(v.data_venda AT TIME ZONE 'America/Sao_Paulo') AS data_dia,
    TO_CHAR(v.data_venda AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes,
    v.canal_venda,
    v.forma_pagamento,
    COUNT(*)::INT AS qtd_vendas,
    COALESCE(SUM(v.subtotal), 0)::NUMERIC(14,2) AS receita_bruta,
    COALESCE(SUM(v.desconto), 0)::NUMERIC(14,2) AS total_descontos,
    COALESCE(SUM(v.valor_total), 0)::NUMERIC(14,2) AS receita_liquida,
    COALESCE(SUM(v.custo_total_cmv), 0)::NUMERIC(14,2) AS cmv_total,
    COALESCE(SUM(v.valor_total - v.custo_total_cmv), 0)::NUMERIC(14,2) AS margem_bruta,
    CASE
        WHEN COALESCE(SUM(v.valor_total), 0) > 0
        THEN ROUND(((SUM(v.valor_total - v.custo_total_cmv) / SUM(v.valor_total)) * 100)::NUMERIC, 2)
        ELSE 0::NUMERIC(6,2)
    END AS margem_bruta_pct,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(v.valor_total) / COUNT(*))::NUMERIC, 2)
        ELSE 0::NUMERIC(12,2)
    END AS ticket_medio
FROM vendas v
WHERE v.status = 'CONCLUIDA'
GROUP BY 1, 2, 3, 4;

-- 2. Desempenho de Produtos (base para Ranking, Margem e Curva ABC)
CREATE OR REPLACE VIEW vw_bi_produtos_desempenho AS
SELECT
    DATE(v.data_venda AT TIME ZONE 'America/Sao_Paulo') AS data_dia,
    p.id AS produto_id,
    p.sku,
    p.nome AS produto_nome,
    c.nome AS categoria_nome,
    p.tipo_produto,
    v.canal_venda,
    SUM(vi.quantidade)::INT AS quantidade_vendida,
    COALESCE(SUM(vi.subtotal), 0)::NUMERIC(14,2) AS receita_total,
    COALESCE(SUM(vi.custo_unitario_cmv_snapshot * vi.quantidade), 0)::NUMERIC(14,2) AS cmv_total,
    COALESCE(SUM(vi.subtotal - (vi.custo_unitario_cmv_snapshot * vi.quantidade)), 0)::NUMERIC(14,2) AS margem_contribuicao
FROM venda_itens vi
JOIN vendas v ON v.id = vi.venda_id
JOIN produtos p ON p.id = vi.produto_id
JOIN categorias c ON c.id = p.categoria_id
WHERE v.status = 'CONCLUIDA'
GROUP BY 1, 2, 3, 4, 5, 6, 7;

-- 3. Horários de Pico (Mapa de Calor Dia da Semana x Hora)
CREATE OR REPLACE VIEW vw_bi_horarios_pico AS
SELECT
    DATE(v.data_venda AT TIME ZONE 'America/Sao_Paulo') AS data_dia,
    EXTRACT(DOW FROM (v.data_venda AT TIME ZONE 'America/Sao_Paulo'))::INT AS dia_semana_num,
    CASE EXTRACT(DOW FROM (v.data_venda AT TIME ZONE 'America/Sao_Paulo'))::INT
        WHEN 0 THEN 'Domingo'
        WHEN 1 THEN 'Segunda'
        WHEN 2 THEN 'Terça'
        WHEN 3 THEN 'Quarta'
        WHEN 4 THEN 'Quinta'
        WHEN 5 THEN 'Sexta'
        WHEN 6 THEN 'Sábado'
    END AS dia_semana_nome,
    EXTRACT(HOUR FROM (v.data_venda AT TIME ZONE 'America/Sao_Paulo'))::INT AS hora,
    v.canal_venda,
    COUNT(*)::INT AS qtd_vendas,
    COALESCE(SUM(v.valor_total), 0)::NUMERIC(14,2) AS receita_liquida
FROM vendas v
WHERE v.status = 'CONCLUIDA'
GROUP BY 1, 2, 3, 4, 5;

-- 4. Saúde do Estoque, Giro e Perdas (últimos 30 dias)
CREATE OR REPLACE VIEW vw_bi_estoque_saude AS
WITH consumo AS (
    SELECT
        insumo_id,
        COALESCE(SUM(quantidade), 0)::NUMERIC(14,3) AS consumo_30d
    FROM movimentacoes_estoque
    WHERE tipo_movimentacao = 'SAIDA_VENDA'
      AND criado_em >= NOW() - INTERVAL '30 days'
    GROUP BY insumo_id
),
perdas AS (
    SELECT
        insumo_id,
        COALESCE(SUM(quantidade), 0)::NUMERIC(14,3) AS perdas_30d,
        COALESCE(SUM(custo_estimado), 0)::NUMERIC(14,2) AS custo_perdas_30d
    FROM registros_perdas
    WHERE criado_em >= NOW() - INTERVAL '30 days'
    GROUP BY insumo_id
)
SELECT
    i.id AS insumo_id,
    i.sku,
    i.nome AS insumo_nome,
    c.nome AS categoria_nome,
    i.unidade_medida,
    i.localizacao,
    i.perecivel,
    i.estoque_atual,
    i.estoque_minimo,
    i.custo_medio_atual,
    ROUND((i.estoque_atual * i.custo_medio_atual)::NUMERIC, 2) AS valor_imobilizado,
    CASE
        WHEN i.estoque_atual <= i.estoque_minimo THEN 'CRITICO'
        WHEN i.estoque_atual <= (i.estoque_minimo * 1.25) THEN 'ATENCAO'
        ELSE 'SAUDAVEL'
    END AS status_estoque,
    COALESCE(co.consumo_30d, 0)::NUMERIC(14,3) AS consumo_30d,
    COALESCE(pe.perdas_30d, 0)::NUMERIC(14,3) AS perdas_30d,
    COALESCE(pe.custo_perdas_30d, 0)::NUMERIC(14,2) AS custo_perdas_30d,
    CASE
        WHEN COALESCE(co.consumo_30d, 0) > 0
        THEN ROUND((i.estoque_atual / (co.consumo_30d / 30.0))::NUMERIC, 1)
        ELSE NULL
    END AS dias_cobertura_estimado
FROM insumos i
JOIN categorias c ON c.id = i.categoria_id
LEFT JOIN consumo co ON co.insumo_id = i.id
LEFT JOIN perdas pe ON pe.insumo_id = i.id
WHERE i.ativo = TRUE;

-- 5. Operacional e SLA do Barista
CREATE OR REPLACE VIEW vw_bi_operacional_sla AS
WITH tempo_estimado_venda AS (
    SELECT
        vi.venda_id,
        (
            GREATEST(MAX(p.tempo_preparo_estimado_seg), 60)
            + GREATEST(SUM(vi.quantidade) - 1, 0) * 45
        )::INT AS tempo_estimado_total_seg
    FROM venda_itens vi
    JOIN produtos p ON p.id = vi.produto_id
    GROUP BY vi.venda_id
)
SELECT
    op.id AS ordem_id,
    op.venda_id,
    v.numero_venda,
    DATE(op.criado_em AT TIME ZONE 'America/Sao_Paulo') AS data_dia,
    EXTRACT(HOUR FROM (op.criado_em AT TIME ZONE 'America/Sao_Paulo'))::INT AS hora,
    v.canal_venda,
    op.status,
    op.barista_id,
    COALESCE(u.nome, 'Não atribuído') AS barista_nome,
    op.tempo_espera_fila_seg,
    op.tempo_preparo_real_seg,
    COALESCE(tev.tempo_estimado_total_seg, 180) AS tempo_estimado_total_seg,
    CASE
        WHEN op.tempo_espera_fila_seg IS NOT NULL AND op.tempo_preparo_real_seg IS NOT NULL
        THEN (op.tempo_espera_fila_seg + op.tempo_preparo_real_seg)
        ELSE NULL
    END AS tempo_total_atendimento_seg,
    CASE
        WHEN op.tempo_preparo_real_seg IS NOT NULL
        THEN (op.tempo_preparo_real_seg <= COALESCE(tev.tempo_estimado_total_seg, 180))
        ELSE NULL
    END AS dentro_sla
FROM ordens_preparo op
JOIN vendas v ON v.id = op.venda_id
LEFT JOIN usuarios u ON u.id = op.barista_id
LEFT JOIN tempo_estimado_venda tev ON tev.venda_id = op.venda_id;

-- 6. DRE Gerencial e Fluxo de Caixa Mensal
CREATE OR REPLACE VIEW vw_bi_financeiro_dre_fluxo AS
WITH meses AS (
    SELECT DISTINCT TO_CHAR(data_venda AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes FROM vendas
    UNION
    SELECT DISTINCT TO_CHAR(criado_em AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes FROM registros_perdas
    UNION
    SELECT DISTINCT TO_CHAR(data_competencia, 'YYYY-MM') AS ano_mes FROM titulos_financeiros
    UNION
    SELECT DISTINCT TO_CHAR(data_movimentacao AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes FROM movimentacoes_financeiras
),
vendas_mes AS (
    SELECT
        TO_CHAR(data_venda AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes,
        COALESCE(SUM(valor_total), 0)::NUMERIC(14,2) AS receita_vendas,
        COALESCE(SUM(custo_total_cmv), 0)::NUMERIC(14,2) AS cmv_vendas
    FROM vendas
    WHERE status = 'CONCLUIDA'
    GROUP BY 1
),
perdas_mes AS (
    SELECT
        TO_CHAR(criado_em AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes,
        COALESCE(SUM(custo_estimado), 0)::NUMERIC(14,2) AS custo_perdas
    FROM registros_perdas
    GROUP BY 1
),
despesas_op_mes AS (
    SELECT
        TO_CHAR(data_competencia, 'YYYY-MM') AS ano_mes,
        COALESCE(SUM(valor_original), 0)::NUMERIC(14,2) AS despesas_operacionais
    FROM titulos_financeiros
    WHERE tipo = 'PAGAR'
      AND origem_modulo IN ('MANUAL', 'OPERACIONAL')
      AND status <> 'CANCELADO'
    GROUP BY 1
),
compras_mes AS (
    SELECT
        TO_CHAR(COALESCE(data_recebimento, data_pedido) AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes,
        COALESCE(SUM(valor_total), 0)::NUMERIC(14,2) AS compras_recebidas
    FROM compras
    WHERE status = 'RECEBIDA'
    GROUP BY 1
),
caixa_mes AS (
    SELECT
        TO_CHAR(data_movimentacao AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM') AS ano_mes,
        COALESCE(SUM(CASE WHEN tipo_fluxo = 'ENTRADA' THEN valor ELSE 0 END), 0)::NUMERIC(14,2) AS entradas_caixa,
        COALESCE(SUM(CASE WHEN tipo_fluxo = 'SAIDA' THEN valor ELSE 0 END), 0)::NUMERIC(14,2) AS saidas_caixa
    FROM movimentacoes_financeiras
    GROUP BY 1
)
SELECT
    m.ano_mes,
    COALESCE(v.receita_vendas, 0)::NUMERIC(14,2) AS receita_vendas,
    COALESCE(v.cmv_vendas, 0)::NUMERIC(14,2) AS cmv_vendas,
    COALESCE(p.custo_perdas, 0)::NUMERIC(14,2) AS custo_perdas,
    COALESCE(d.despesas_operacionais, 0)::NUMERIC(14,2) AS despesas_operacionais,
    COALESCE(c.compras_recebidas, 0)::NUMERIC(14,2) AS compras_recebidas,
    COALESCE(cx.entradas_caixa, 0)::NUMERIC(14,2) AS entradas_caixa,
    COALESCE(cx.saidas_caixa, 0)::NUMERIC(14,2) AS saidas_caixa,
    (COALESCE(cx.entradas_caixa, 0) - COALESCE(cx.saidas_caixa, 0))::NUMERIC(14,2) AS fluxo_caixa_liquido,
    (COALESCE(v.receita_vendas, 0) - COALESCE(v.cmv_vendas, 0))::NUMERIC(14,2) AS lucro_bruto,
    (
        COALESCE(v.receita_vendas, 0)
        - COALESCE(v.cmv_vendas, 0)
        - COALESCE(p.custo_perdas, 0)
        - COALESCE(d.despesas_operacionais, 0)
    )::NUMERIC(14,2) AS resultado_operacional_liquido
FROM meses m
LEFT JOIN vendas_mes v ON v.ano_mes = m.ano_mes
LEFT JOIN perdas_mes p ON p.ano_mes = m.ano_mes
LEFT JOIN despesas_op_mes d ON d.ano_mes = m.ano_mes
LEFT JOIN compras_mes c ON c.ano_mes = m.ano_mes
LEFT JOIN caixa_mes cx ON cx.ano_mes = m.ano_mes
ORDER BY m.ano_mes ASC;
