# Documentação Analítica — 2ª VA (Dashboard BI — Cafeteria Grão do Agreste)

* **Disciplina:** Sistemas de Informação e Tecnologias — UFAPE (2026.2)
* **Professor:** Dr. Assuero Fonseca Ximenes
* **Aplicação Publicada:** [https://cafeteria-erp.streamlit.app/](https://cafeteria-erp.streamlit.app/)
* **Módulo Analítico:** `src/ui/pages/08_dashboard_bi.py` · `src/services/bi_service.py` · `sql/002_views_bi.sql`

---

## 1. Arquitetura Analítica e Integração Direta com o ERP

Em total conformidade com a seção 10.3.1 do `especificacao.md`, o Dashboard BI é um módulo integrado à navegação do ERP da 1ª VA e está conectado **diretamente ao banco PostgreSQL/Supabase**, utilizando **exclusivamente** os dados gerados pelas operações transacionais do sistema (nenhum arquivo externo ou dado simulado em memória).

### Fluxo Operação → View SQL → Indicador → Decisão
1. Cada operação registrada na 1ª VA (venda no PDV, recebimento de compra, transição na fila do barista, perda de insumo ou liquidação financeira) persiste imediatamente nas tabelas transacionais do PostgreSQL.
2. A camada analítica no banco (`sql/002_views_bi.sql`) consolida esses dados por meio de **6 views SQL especializadas**:
   * `vw_bi_vendas_diarias`
   * `vw_bi_produtos_desempenho`
   * `vw_bi_horarios_pico`
   * `vw_bi_estoque_saude`
   * `vw_bi_operacional_sla`
   * `vw_bi_financeiro_dre_fluxo`
3. O serviço `src/services/bi_service.py` consulta essas views com filtros dinâmicos (intervalo de datas, canais de venda e categorias de produto), calcula variações frente ao período anterior equivalente e alimenta as 4 abas do dashboard (`Desempenho Comercial`, `Suprimentos e Perdas`, `Operação e SLA` e `Resultado Financeiro`).
4. Qualquer nova transação executada no ERP reflete-se imediatamente nos gráficos e KPIs do dashboard.

---

## 2. Catálogo e Definição dos Indicadores (KPIs)

### 2.1 Indicadores Comerciais e Executivos

| KPI | Definição e Fórmula | Fonte SQL | O que Mede no Contexto da Cafeteria |
| :--- | :--- | :--- | :--- |
| **Receita Líquida** | $\sum \text{valor\_total}$ das vendas `CONCLUIDA` | `vw_bi_vendas_diarias` | Faturamento efetivo após descontos, com comparativo percentual frente ao período anterior. |
| **CMV Total** | $\sum \text{custo\_total\_cmv}$ (calculado pelos snapshots históricos) | `vw_bi_vendas_diarias` | Custo direto dos insumos consumidos pelas receitas vendidas no período. |
| **Margem Bruta (R\$ e %)** | $\text{Receita Líquida} - \text{CMV}$ e $\frac{\text{Margem Bruta}}{\text{Receita Líquida}} \times 100$ | `vw_bi_vendas_diarias` | Capacidade do cardápio de gerar contribuição antes de perdas e despesas fixas. |
| **Ticket Médio** | $\frac{\text{Receita Líquida}}{\text{Quantidade de Vendas}}$ | `vw_bi_vendas_diarias` | Gasto médio por pedido; sensível a vendas casadas (combos e acompanhamento de salgados/doces). |
| **Taxa de Cancelamento (%)** | $\frac{\text{Vendas Canceladas}}{\text{Total de Vendas}} \times 100$ | `vendas` | Falhas operacionais no atendimento, erros de caixa ou desistências por fila longa. |
| **Curva ABC (Pareto)** | Classificação dos produtos pelo % acumulado de receita (`A ≤ 80%`, `B ≤ 95%`, `C > 95%`) | `vw_bi_produtos_desempenho` | Identifica os itens vitais do cardápio que sustentam o faturamento e a margem. |
| **Mapa de Calor de Picos** | Matriz $\text{Dia da Semana} \times \text{Hora}$ de volume de pedidos | `vw_bi_horarios_pico` | Revela janelas de pico e ociosidade para escala de baristas e promoções direcionadas. |

### 2.2 Indicadores de Estoque, Compras e Perdas

| KPI | Definição e Fórmula | Fonte SQL | O que Mede no Contexto da Cafeteria |
| :--- | :--- | :--- | :--- |
| **Valor Imobilizado em Estoque** | $\sum (\text{estoque\_atual} \times \text{custo\_medio\_atual})$ | `vw_bi_estoque_saude` | Capital de giro parado em insumos; excesso aumenta risco de vencimento. |
| **Insumos em Nível Crítico** | Contagem de insumos ativos com $\text{estoque\_atual} \le \text{estoque\_minimo}$ | `vw_bi_estoque_saude` | Risco iminente de ruptura de cardápio (indisponibilidade de bebidas/itens). |
| **Dias de Cobertura Estimada** | $\frac{\text{estoque\_atual}}{\text{consumo\_30d} / 30}$ | `vw_bi_estoque_saude` | Quantos dias o saldo atual suporta o ritmo recente de vendas antes de zerar. |
| **Custo de Perdas por Motivo/Insumo** | $\sum \text{custo\_estimado}$ em `registros_perdas` | `registros_perdas` | Vazamento financeiro causado por vencimento, desperdício na regulagem ou quebra no preparo. |
| **Evolução do Custo Unitário** | Média de `compra_itens.custo_unitario` por data de recebimento | `compra_itens` + `compras` | Monitora inflação de fornecedores em insumos-chave (café especial, leite integral). |

### 2.3 Indicadores Operacionais (Barista / Produção)

| KPI | Definição e Fórmula | Fonte SQL | O que Mede no Contexto da Cafeteria |
| :--- | :--- | :--- | :--- |
| **Espera Média na Fila** | Média de `tempo_espera_fila_seg` (`iniciado_em - criado_em`) | `vw_bi_operacional_sla` | Gargalo entre o pagamento no caixa e o início efetivo do preparo pelo barista. |
| **Tempo Médio de Preparo Real vs. Meta** | Média de `tempo_preparo_real_seg` vs. `tempo_estimado_total_seg` | `vw_bi_operacional_sla` | Eficiência técnica do preparo frente ao padrão operacional definido na ficha técnica. |
| **Taxa de Cumprimento de SLA (%)** | $\frac{\text{Ordens com preparo\_real} \le \text{tempo\_estimado}}{\text{Total de Ordens Concluídas}} \times 100$ | `vw_bi_operacional_sla` | Qualidade do nível de serviço percebido pelo cliente, segmentável por hora e por barista. |

### 2.4 Indicadores Financeiros (DRE e Fluxo de Caixa)

| KPI | Definição e Fórmula | Fonte SQL | O que Mede no Contexto da Cafeteria |
| :--- | :--- | :--- | :--- |
| **Resultado Operacional Líquido (DRE)** | $\text{Receita} - \text{CMV} - \text{Perdas} - \text{Despesas Operacionais}$ | `vw_bi_financeiro_dre_fluxo` | Lucratividade econômica real do negócio por competência mensal. |
| **Fluxo de Caixa Líquido e Acumulado** | $\text{Entradas Efetivadas} - \text{Saídas Efetivadas}$ (e soma acumulada) | `vw_bi_financeiro_dre_fluxo` | Liquidez financeira real (regime de caixa) frente aos prazos de cartão/faturado e boletos. |
| **Aging de Títulos Abertos** | Soma de `titulos_financeiros` em aberto por faixa (vencidos, ≤7d, 8–30d, >30d) | `titulos_financeiros` | Visibilidade de compromissos imediatos, risco de juros por atraso e cobrança de recebíveis. |

---

## 3. Análise dos Resultados, Padrões e Problemas Identificados

A partir da consolidação do histórico operacional de 90 dias gerado pelo ERP na base PostgreSQL, os indicadores do Dashboard BI evidenciam cinco achados gerenciais centrais:

### 3.1 Concentração Comercial (Curva ABC) e Sazonalidade Semanal
* **Padrão observado:** os itens da **Classe A** (liderados por *Cappuccino Clássico*, *Combo Manhã*, *Iced Caramel Macchiato*, *Iced Latte Baunilha*, *Espresso Tradicional* e *Pão de Queijo*) concentram cerca de **75% a 80% da receita total**, enquanto a demanda apresenta picos pronunciados às **sextas-feiras e sábados** e retração significativa às **segundas-feiras**.
* **Interpretação:** a cafeteria possui forte dependência de poucos itens-âncora e sofre ociosidade estrutural no início da semana (segunda-feira) enquanto mantém custos fixos constantes (aluguel e folha).

### 3.2 Gargalo Operacional de SLA no Pico da Tarde (15h–17h)
* **Problema identificado:** o gráfico *Desempenho Operacional por Hora* e o *Mapa de Calor* mostram dois picos diários (08h–10h e 15h–17h). Contudo, no turno da tarde (**15h às 17h**), há aumento simultâneo do tempo de espera na fila e do tempo real de preparo acima da meta estimada, derrubando a taxa de SLA nessa faixa horária — impulsionado pelo maior mix de bebidas geladas e combos mais complexos.
* **Impacto:** eleva o risco de desistências/cancelamentos e deteriora a experiência de clientes de balcão e delivery justamente no segundo maior horário de faturamento.

### 3.3 Pressão Inflacionária em Insumos-Chave sobre a Margem Bruta
* **Tendência identificada:** o gráfico *Evolução do Custo Unitário de Compra* evidencia alta progressiva no custo de reposição do **Café Especial Arábica em Grão** (~+14% ao longo do trimestre) e do **Leite Integral Fresco** (~+9%). Como os preços de venda permaneceram constantes, o custo médio ponderado cresceu e pressionou a margem de produtos com maior proporção de leite/itens prontos (especialmente *Croissant*, *Combo Manhã* e *Latte Vegetal*).
* **Impacto:** erosão gradual da margem bruta percentual mês a mês caso não haja revisão de precificação ou renegociação com fornecedores.

### 3.4 Perdas Operacionais (Quebra no Preparo e Vencimento) e Cobertura de Estoque
* **Problema identificado:** a análise de `registros_perdas` aponta os motivos **`QUEBRA_PREPARO`** (incluindo cancelamentos pós-início de preparo) e **`VENCIMENTO`** (laticínios e itens de vitrine) como os principais ofensores financeiros, seguidos por **`DESPERDICIO_BARISTA`** na regulagem diária do moedor de café. Paralelamente, a view `vw_bi_estoque_saude` monitora em tempo real os **dias de cobertura estimada** e sinaliza insumos próximos ou abaixo do estoque mínimo.
* **Impacto:** vazamento direto na margem líquida (custo de perdas na DRE) e risco de ruptura de cardápio caso a reposição de itens perecíveis não acompanhe o giro semanal.

### 3.5 Descompasso Financeiro (Regime de Caixa vs. Competência) e Títulos Atrasados
* **Padrão observado:** vendas no **Cartão de Crédito** (recebimento D+30) e clientes **Corporativos Faturados** (D+15) geram receita imediata na DRE, mas entram no caixa posteriormente, enquanto compras de laticínios/padaria têm vencimento curto (7 a 10 dias). Além disso, o gráfico de *Aging* destaca títulos vencidos em aberto que exigem baixa/regularização imediata.

---

## 4. Recomendações Gerenciais Baseadas em Dados

| # | Problema / Evidência no BI | Recomendação Acionável | Impacto Esperado e KPI de Monitoramento |
| :-: | :--- | :--- | :--- |
| **1** | Queda de SLA entre **15h e 17h** com fila elevada | Redesenhar a escala de trabalho alocando **2 baristas simultâneos** na janela de 14h30 às 17h30 e adotar *pré-mise en place* (xaropes dosados e gelo abastecido) antes das 15h. | Elevar a **Taxa de SLA** no período da tarde para **≥ 90%** e reduzir a **Espera Média na Fila** em 35%. |
| **2** | Alta de custo de **Café Especial (+14%)** e **Leite (+9%)** comprimindo margens | Aplicar reajuste seletivo de **5% a 8%** nos itens Classe A de menor elasticidade ou criar combos que aumentem o ticket médio; negociar contrato trimestral de volume com a *Torrefação Serra do Agreste*. | Recuperar **+2,5 a +4,0 p.p. na Margem Bruta** sem reduzir o volume de vendas (acompanhar em *Desempenho Comercial*). |
| **3** | Perdas por **`QUEBRA_PREPARO`** e **`VENCIMENTO`** em perecíveis e vitrine | Padronizar conferência de pedidos antes do preparo (reduzindo erros de sabor/cancelamentos pós-preparo), reduzir o tamanho do lote de perecíveis aumentando a frequência de entrega (2× por semana), aplicar regra **PEPS/FEFO** e lançar *"Happy Hour Vitrine"* (20% off após 18h). | Reduzir o **Custo de Perdas** em **≥ 40%** nos próximos 30 dias (acompanhar na aba *Suprimentos e Perdas*). |
| **4** | Insumos em nível **`CRITICO`** na view `vw_bi_estoque_saude` | Adotar rotina diária de conferência do painel de alertas às 08h usando o indicador **Dias de Cobertura Estimada** (disparar pedido de compra sempre que cobertura ≤ 4 dias). | Zerar episódios de bloqueio de venda no PDV por falta de insumo. |
| **5** | Ociosidade às **segundas-feiras** (menor faturamento da semana) | Lançar campanha de fidelização *"Segunda do Espresso Duplo / Combo Coworking"* direcionada aos clientes `FIDELIDADE` e `CORPORATIVO` cadastrados no ERP. | Aumentar o volume de vendas das segundas-feiras em **+20%**, diluindo custos fixos mensais na DRE. |
| **6** | Títulos vencidos no **Aging** e descasamento de caixa | Incentivar pagamentos via **PIX** no balcão (liquidez D+0 e sem taxa de adquirente) e revisar semanalmente a aba *Aging* para liquidar contas a pagar até o vencimento, evitando juros e multas. | Reduzir títulos atrasados a **R\$ 0,00** e aumentar a folga do **Saldo Acumulado de Caixa**. |
