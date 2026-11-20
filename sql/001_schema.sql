-- =============================================================================
-- 001_schema.sql
-- Modelagem Relacional Completa — ERP + BI Cafeteria Grão do Agreste
-- SGBD: PostgreSQL 15+ (Supabase)
-- Regras de integridade:
--   * Todas as entidades possuem timestamps TIMESTAMPTZ.
--   * Cadastros utilizam exclusão lógica (ativo = FALSE).
--   * Tabelas transacionais e de razão são imutáveis (append-only).
-- =============================================================================

-- 1. SEGURANÇA E AUDITORIA
CREATE TABLE IF NOT EXISTS usuarios (
    id BIGSERIAL PRIMARY KEY,
    google_sub TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    avatar_url TEXT,
    perfil TEXT NOT NULL DEFAULT 'GERENTE'
        CHECK (perfil IN ('ADMIN', 'GERENTE', 'CAIXA', 'BARISTA', 'ESTOQUISTA')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_login_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT REFERENCES usuarios(id),
    modulo TEXT NOT NULL,
    entidade TEXT NOT NULL,
    entidade_id BIGINT,
    acao TEXT NOT NULL,
    detalhes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. CADASTROS BASE E FICHA TÉCNICA
CREATE TABLE IF NOT EXISTS categorias (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('PRODUTO', 'INSUMO', 'DESPESA', 'RECEITA')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (nome, tipo)
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id BIGSERIAL PRIMARY KEY,
    razao_social TEXT NOT NULL,
    nome_fantasia TEXT NOT NULL,
    cnpj TEXT UNIQUE NOT NULL,
    telefone TEXT,
    email TEXT,
    prazo_pagamento_dias INT NOT NULL DEFAULT 0 CHECK (prazo_pagamento_dias >= 0),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clientes (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf_cnpj TEXT UNIQUE,
    telefone TEXT,
    email TEXT,
    tipo_cliente TEXT NOT NULL DEFAULT 'BALCAO'
        CHECK (tipo_cliente IN ('BALCAO', 'FIDELIDADE', 'CORPORATIVO')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS insumos (
    id BIGSERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    categoria_id BIGINT NOT NULL REFERENCES categorias(id),
    unidade_medida TEXT NOT NULL CHECK (unidade_medida IN ('g', 'ml', 'un')),
    estoque_atual NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (estoque_atual >= 0),
    estoque_minimo NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    custo_medio_atual NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (custo_medio_atual >= 0),
    localizacao TEXT NOT NULL DEFAULT 'Estoque Central',
    perecivel BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS produtos (
    id BIGSERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    categoria_id BIGINT NOT NULL REFERENCES categorias(id),
    tipo_produto TEXT NOT NULL CHECK (tipo_produto IN ('PREPARADO', 'REVENDA')),
    preco_venda NUMERIC(12,2) NOT NULL CHECK (preco_venda > 0),
    tempo_preparo_estimado_seg INT NOT NULL DEFAULT 180 CHECK (tempo_preparo_estimado_seg >= 0),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ficha_tecnica_itens (
    id BIGSERIAL PRIMARY KEY,
    produto_id BIGINT NOT NULL REFERENCES produtos(id),
    insumo_id BIGINT NOT NULL REFERENCES insumos(id),
    quantidade NUMERIC(14,3) NOT NULL CHECK (quantidade > 0),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (produto_id, insumo_id)
);

CREATE TABLE IF NOT EXISTS historico_precos_produtos (
    id BIGSERIAL PRIMARY KEY,
    produto_id BIGINT NOT NULL REFERENCES produtos(id),
    preco_anterior NUMERIC(12,2),
    preco_novo NUMERIC(12,2) NOT NULL CHECK (preco_novo > 0),
    alterado_por BIGINT REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. COMPRAS
CREATE TABLE IF NOT EXISTS compras (
    id BIGSERIAL PRIMARY KEY,
    numero_pedido TEXT UNIQUE NOT NULL,
    fornecedor_id BIGINT NOT NULL REFERENCES fornecedores(id),
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    status TEXT NOT NULL DEFAULT 'CONFIRMADA'
        CHECK (status IN ('RASCUNHO', 'CONFIRMADA', 'RECEBIDA', 'CANCELADA')),
    data_pedido TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_recebimento TIMESTAMPTZ,
    valor_total NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (valor_total >= 0),
    forma_pagamento TEXT NOT NULL DEFAULT 'BOLETO'
        CHECK (forma_pagamento IN ('BOLETO', 'PIX', 'TRANSFERENCIA', 'CARTAO_CORP', 'DINHEIRO')),
    observacoes TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS compra_itens (
    id BIGSERIAL PRIMARY KEY,
    compra_id BIGINT NOT NULL REFERENCES compras(id),
    insumo_id BIGINT NOT NULL REFERENCES insumos(id),
    quantidade NUMERIC(14,3) NOT NULL CHECK (quantidade > 0),
    custo_unitario NUMERIC(12,4) NOT NULL CHECK (custo_unitario >= 0),
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    lote TEXT,
    data_validade DATE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. ESTOQUE (RAZÃO IMUTÁVEL)
CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
    id BIGSERIAL PRIMARY KEY,
    insumo_id BIGINT NOT NULL REFERENCES insumos(id),
    tipo_movimentacao TEXT NOT NULL
        CHECK (tipo_movimentacao IN (
            'ENTRADA_COMPRA',
            'SAIDA_VENDA',
            'SAIDA_PERDA',
            'AJUSTE_ENTRADA',
            'AJUSTE_SAIDA',
            'ESTORNO_VENDA'
        )),
    quantidade NUMERIC(14,3) NOT NULL CHECK (quantidade > 0),
    saldo_anterior NUMERIC(14,3) NOT NULL CHECK (saldo_anterior >= 0),
    saldo_posterior NUMERIC(14,3) NOT NULL CHECK (saldo_posterior >= 0),
    custo_unitario_snapshot NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (custo_unitario_snapshot >= 0),
    origem_modulo TEXT NOT NULL CHECK (origem_modulo IN ('COMPRAS', 'VENDAS', 'OPERACIONAL', 'ESTOQUE')),
    origem_id BIGINT,
    motivo TEXT,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. VENDAS / PDV
CREATE TABLE IF NOT EXISTS vendas (
    id BIGSERIAL PRIMARY KEY,
    numero_venda TEXT UNIQUE NOT NULL,
    cliente_id BIGINT NOT NULL REFERENCES clientes(id),
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    canal_venda TEXT NOT NULL CHECK (canal_venda IN ('BALCAO', 'MESA', 'RETIRADA', 'DELIVERY')),
    forma_pagamento TEXT NOT NULL CHECK (forma_pagamento IN ('PIX', 'DEBITO', 'CREDITO', 'DINHEIRO', 'FATURADO')),
    status TEXT NOT NULL DEFAULT 'CONCLUIDA' CHECK (status IN ('CONCLUIDA', 'CANCELADA')),
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    desconto NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (desconto >= 0),
    valor_total NUMERIC(12,2) NOT NULL CHECK (valor_total >= 0),
    custo_total_cmv NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (custo_total_cmv >= 0),
    data_venda TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    motivo_cancelamento TEXT,
    cancelada_em TIMESTAMPTZ,
    cancelada_por BIGINT REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (desconto <= subtotal)
);

CREATE TABLE IF NOT EXISTS venda_itens (
    id BIGSERIAL PRIMARY KEY,
    venda_id BIGINT NOT NULL REFERENCES vendas(id),
    produto_id BIGINT NOT NULL REFERENCES produtos(id),
    quantidade INT NOT NULL CHECK (quantidade > 0),
    preco_unitario_snapshot NUMERIC(12,2) NOT NULL CHECK (preco_unitario_snapshot > 0),
    custo_unitario_cmv_snapshot NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (custo_unitario_cmv_snapshot >= 0),
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. OPERACIONAL (BARISTA / PREPARO E PERDAS)
CREATE TABLE IF NOT EXISTS ordens_preparo (
    id BIGSERIAL PRIMARY KEY,
    venda_id BIGINT UNIQUE NOT NULL REFERENCES vendas(id),
    status TEXT NOT NULL DEFAULT 'NA_FILA'
        CHECK (status IN ('NA_FILA', 'EM_PREPARO', 'PRONTO', 'ENTREGUE', 'CANCELADO')),
    barista_id BIGINT REFERENCES usuarios(id),
    prioridade TEXT NOT NULL DEFAULT 'NORMAL' CHECK (prioridade IN ('NORMAL', 'ALTA')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    iniciado_em TIMESTAMPTZ,
    finalizado_em TIMESTAMPTZ,
    entregue_em TIMESTAMPTZ,
    tempo_espera_fila_seg INT CHECK (tempo_espera_fila_seg >= 0),
    tempo_preparo_real_seg INT CHECK (tempo_preparo_real_seg >= 0),
    observacoes TEXT
);

CREATE TABLE IF NOT EXISTS ordem_preparo_historico (
    id BIGSERIAL PRIMARY KEY,
    ordem_preparo_id BIGINT NOT NULL REFERENCES ordens_preparo(id),
    status_anterior TEXT,
    status_novo TEXT NOT NULL,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registros_perdas (
    id BIGSERIAL PRIMARY KEY,
    insumo_id BIGINT NOT NULL REFERENCES insumos(id),
    quantidade NUMERIC(14,3) NOT NULL CHECK (quantidade > 0),
    motivo TEXT NOT NULL
        CHECK (motivo IN ('VENCIMENTO', 'QUEBRA_PREPARO', 'DESPERDICIO_BARISTA', 'CONTAMINACAO', 'OUTRO')),
    custo_estimado NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (custo_estimado >= 0),
    observacoes TEXT,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. FINANCEIRO
CREATE TABLE IF NOT EXISTS titulos_financeiros (
    id BIGSERIAL PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('RECEBER', 'PAGAR')),
    categoria_id BIGINT NOT NULL REFERENCES categorias(id),
    descricao TEXT NOT NULL,
    origem_modulo TEXT NOT NULL CHECK (origem_modulo IN ('VENDAS', 'COMPRAS', 'OPERACIONAL', 'MANUAL')),
    origem_id BIGINT,
    cliente_id BIGINT REFERENCES clientes(id),
    fornecedor_id BIGINT REFERENCES fornecedores(id),
    valor_original NUMERIC(12,2) NOT NULL CHECK (valor_original > 0),
    valor_pago NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (valor_pago >= 0),
    data_competencia DATE NOT NULL,
    data_vencimento DATE NOT NULL,
    data_liquidacao TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ABERTO' CHECK (status IN ('ABERTO', 'PAGO', 'CANCELADO')),
    forma_pagamento TEXT,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS movimentacoes_financeiras (
    id BIGSERIAL PRIMARY KEY,
    titulo_id BIGINT NOT NULL REFERENCES titulos_financeiros(id),
    tipo_fluxo TEXT NOT NULL CHECK (tipo_fluxo IN ('ENTRADA', 'SAIDA')),
    valor NUMERIC(12,2) NOT NULL CHECK (valor > 0),
    forma_pagamento TEXT NOT NULL,
    data_movimentacao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    descricao TEXT NOT NULL,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
