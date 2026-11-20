<p align="center">
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" width="85" alt="Python Logo" />
  &nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/streamlit/streamlit-original.svg" width="85" alt="Streamlit Logo" />
  &nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/postgresql/postgresql-original.svg" width="85" alt="PostgreSQL Logo" />
  &nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/supabase/supabase-original.svg" width="85" alt="Supabase Logo" />
  &nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/google/google-original.svg" width="85" alt="Google OAuth Logo" />
  &nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/pandas/pandas-original.svg" width="85" alt="Pandas Logo" />
</p>

<h1 align="center">Cafeteria Grão do Agreste — ERP &amp; BI</h1>

<p align="center">
  Sistema Integrado de Gestão (ERP) e Inteligência de Negócios (Dashboard BI) para cafeteria artesanal — UFAPE
</p>

<p align="center">
  <a href="https://cafeteria-erp.streamlit.app/" target="_blank"><img src="https://img.shields.io/badge/App%20Online-cafeteria--erp.streamlit.app-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" /></a>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/Streamlit-1.42+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/PostgreSQL-15+-336791?style=for-the-badge&logo=postgresql&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/Supabase-Hosted%20DB-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/Google-OAuth%202.0%20OIDC-4285F4?style=for-the-badge&logo=google&logoColor=white" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/SQLAlchemy-2.x%20ACID-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white" />
  <img src="https://img.shields.io/badge/Plotly%20%26%20Pandas-Dashboard%20BI-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" />
  <img src="https://img.shields.io/badge/Pytest-Testes%20de%20Integra%C3%A7%C3%A3o-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/Git-Conventional%20Commits-F05032?style=for-the-badge&logo=git&logoColor=white" />
</p>

---

## Descrição

O **Cafeteria Grão do Agreste — ERP & BI** é um sistema web desenvolvido no âmbito da disciplina **Sistemas de Informação e Tecnologias** do **Bacharelado em Ciência da Computação** da **UFAPE (Universidade Federal do Agreste de Pernambuco)**, período **2026.2**, sob orientação do **Prof. Dr. Assuero Fonseca Ximenes**.

A plataforma simula, em escala aplicada, a relação **Operações → Dados → Decisão** no contexto real de uma cafeteria artesanal, integrando a camada operacional transacional (**1ª VA — ERP**) com a camada analítica gerencial (**2ª VA — Dashboard BI**) sobre um único banco de dados relacional PostgreSQL hospedado no Supabase.

Com o sistema, é possível gerenciar cadastros e **fichas técnicas (receitas)**, registrar compras com recálculo automático de custo médio ponderado, operar o PDV com baixa atômica de insumos e emissão de comprovante, controlar a fila de preparo dos baristas (SLA) e perdas de perecíveis, consolidar contas a pagar/receber, fluxo de caixa e DRE, além de acompanhar indicadores estratégicos em tempo real no Dashboard BI.

### Módulos do sistema

| Avaliação | Módulo | Descrição |
|-----------|--------|-----------|
| **1ª VA (ERP)** | **Visão Geral** | Resumo diário de vendas, fila aberta do barista, insumos críticos, contas vencendo e gestão de usuários/auditoria |
| **1ª VA (ERP)** | **Catálogo e Cadastros** | CRUD com exclusão lógica de Categorias, Fornecedores, Clientes, Insumos, Produtos do Cardápio, Receitas e histórico de preços |
| **1ª VA (ERP)** | **Compras** | Pedidos com conversão `kg/L → g/ml`, recebimento integrado a estoque, custo médio ponderado e geração de conta a pagar |
| **1ª VA (ERP)** | **Estoque** | Posição em tempo real, alertas de estoque mínimo, ajustes de inventário auditados e razão imutável de movimentações |
| **1ª VA (ERP)** | **Vendas** | Frente de caixa com pré-checagem de insumos, baixa atômica pela ficha técnica, CMV histórico, comprovante `.txt` e estorno seguro |
| **1ª VA (ERP)** | **Operação do Barista** | Fila Kanban (`NA_FILA → EM_PREPARO → PRONTO → ENTREGUE`) com medição de SLA e registro de perdas |
| **1ª VA (ERP)** | **Financeiro** | Contas a pagar e a receber, despesas operacionais, liquidações no caixa, extrato de fluxo de caixa e DRE mensal |
| **2ª VA (BI)** | **Dashboard BI** | Módulo analítico conectado exclusivamente às 6 views SQL do PostgreSQL (Desempenho Comercial, Suprimentos e Perdas, Operação e SLA, Resultado Financeiro) |

### Perfis de acesso (RBAC)

| Perfil | Descrição |
|--------|-----------|
| **ADMIN** | Acesso completo a todos os módulos, gestão de perfis de usuários e visualização da trilha de auditoria (`audit_logs`) |
| **GERENTE** | Gestão integral de cadastros, compras, estoque, vendas (incluindo cancelamentos), operacional, financeiro e Dashboard BI |
| **CAIXA** | Operação do PDV/vendas, consulta de cadastros e acompanhamento da fila de entrega |
| **BARISTA** | Execução da fila de preparo (SLA), consulta de estoque e registro de perdas operacionais |
| **ESTOQUISTA** | Gestão de cadastros de insumos/fornecedores, recebimento de compras, ajustes de inventário e registro de perdas |

---

## Tecnologias Utilizadas

### Aplicação e Interface

* Python 3.11+
* Streamlit 1.42+ (`st.navigation` multipage + OIDC nativo `st.login`)
* Plotly (gráficos interativos de séries temporais, Curva ABC, heatmap, SLA e DRE waterfall)
* Pandas
* Pydantic 2.x

### Banco de Dados e Persistência

* PostgreSQL 15+
* Supabase (hospedagem PostgreSQL + Transaction/Session Pooler IPv4)
* SQLAlchemy 2.x (controle explícito de transações ACID com `SELECT ... FOR UPDATE`)
* `psycopg[binary]` (psycopg3)
* Scripts SQL versionados (19 tabelas, índices e 6 views analíticas `vw_bi_*`)

### Autenticação, Qualidade e Práticas

* Google OAuth 2.0 / OpenID Connect (`Authlib`, `httpx` e `itsdangerous`)
* Ícones vetoriais Lucide (`assets/icons/`) e Google Material Symbols
* Pytest (testes unitários e de integração transacional em schema isolado)
* Git & GitHub
* Conventional Commits
* GitFlow (`main` e `develop`)
* Streamlit Community Cloud

---

## Documentação Técnica e Analítica

| Documento | Conteúdo |
|-----------|----------|
| [`docs/DOCUMENTACAO_1VA.md`](docs/DOCUMENTACAO_1VA.md) | Documentação técnica oficial da 1ª VA (escopo, módulos, arquitetura, integrações e regras de negócio) |
| [`docs/DOCUMENTACAO_2VA.md`](docs/DOCUMENTACAO_2VA.md) | Documentação analítica oficial da 2ª VA (catálogo de KPIs, diagnóstico de padrões e recomendações) |
| [`docs/MER.md`](docs/MER.md) | Diagrama Entidade-Relacionamento (MER), dicionário das 19 tabelas e especificação das 6 views BI |
| [`docs/GUIA_DEPLOY_SUPABASE_GOOGLE.md`](docs/GUIA_DEPLOY_SUPABASE_GOOGLE.md) | Passo a passo completo para Supabase, Google Cloud Console OAuth e Streamlit Community Cloud |

---

## Instalação e Execução

### Pré-requisitos

* Python 3.11+ (ou `uv`)
* Git
* Projeto PostgreSQL ativo no **Supabase**
* Credenciais OAuth 2.0 configuradas no **Google Cloud Console**

Verifique:

```bash
python3 --version
git --version
```

---

## Configuração de secrets e variáveis de ambiente

As credenciais e configurações sensíveis ficam em **`.streamlit/secrets.toml`** (lido automaticamente tanto pelo app Streamlit quanto pelos scripts CLI `init_db.py` e `seed_db.py`, com fallback opcional para a variável de ambiente `DATABASE_URL`). No diretório `.streamlit/` existe o modelo [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) sem valores reais. Crie seu arquivo local:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Gere uma chave segura para o cookie de sessão OIDC:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Edite `.streamlit/secrets.toml` com suas credenciais. O arquivo é ignorado pelo Git (`.gitignore`) e **nunca** deve ser versionado.

> **Atenção à senha do Supabase na URI:** caso sua senha contenha símbolos especiais (`@`, `%`, `^`, `!`, `#`, `/`, `?`), faça o *percent-encoding* deles na URL (ex.: `@` → `%40`, `%` → `%25`, `^` → `%5E`, `!` → `%21`), ou utilize uma senha apenas alfanumérica.

### Chaves disponíveis

| Chave / Variável | Descrição | Usada por |
|---|---|---|
| `[database].url` / `DATABASE_URL` | URI do Supabase Shared/Transaction Pooler IPv4 (`postgresql+psycopg://...?sslmode=require`) | `src/db`, `scripts/` e `app.py` |
| `[auth].redirect_uri` | URI de retorno OAuth (`http://localhost:8501/oauth2callback` ou produção) | Streamlit OIDC |
| `[auth].cookie_secret` | Segredo aleatório forte para assinatura do cookie de autenticação | Streamlit OIDC |
| `[auth.google].client_id` / `client_secret` | Credenciais do aplicativo Web no Google Cloud Console | `st.login("google")` |
| `[auth.google].server_metadata_url` | Endpoint OIDC do Google (`accounts.google.com/.well-known/openid-configuration`) | `st.login("google")` |
| `[auth_policy].admin_emails` | Contas promovidas automaticamente para `ADMIN` (inclui `assuero.ximenes@ufape.edu.br`) | `src/auth/google_auth.py` |
| `[auth_policy].allowed_domains` | Lista opcional de domínios permitidos (vazio = valida apenas pré-cadastro interno pelo `ADMIN`) | `src/auth/google_auth.py` |

> **Política interna de acesso:** o sistema não cria contas automaticamente para desconhecidos. Apenas funcionários previamente cadastrados pelo `ADMIN` (em *Visão Geral → Administração → Usuários e Perfis*) ou e-mails em `admin_emails` conseguem acessar. Certifique-se também de cadastrar `assuero.ximenes@ufape.edu.br` e seu e-mail em **Google Auth Platform → Público-alvo → Usuários de teste** (ou publicar o app em produção) no Google Cloud Console.

---

## Ambiente de Desenvolvimento

### Instalando dependências

Na raiz do projeto (recomendado com `uv` e Python 3.12, ou `python3 -m venv` + `pip`):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Inicializando o banco e populando o histórico (90 dias)

Com `.streamlit/secrets.toml` configurado (com `[database].url` apontando para o Supabase), os scripts leem a URL automaticamente — não é obrigatório exportar `DATABASE_URL`:

```bash
# Aplica schema (19 tabelas), índices e 6 views analíticas (idempotente)
python scripts/init_db.py

# Gera 90 dias de operações realistas usando os próprios serviços do ERP (idempotente)
python scripts/seed_db.py
```

> Para zerar e recriar toda a base de demonstração do zero, utilize `python scripts/seed_db.py --reset`. Como os dados ficam persistidos no Supabase, o seed precisa ser executado apenas uma vez.

### Subindo a aplicação localmente

```bash
streamlit run app.py
```

### URLs locais

Aplicação Web (ERP + Dashboard BI):
```
http://localhost:8501
```

Callback OAuth Google (local):
```
http://localhost:8501/oauth2callback
```

---

## Testes

A suíte automatizada em `tests/` combina **testes unitários** (RBAC, formatadores e comprovante, sem infraestrutura externa) e **testes de integração transacional** no PostgreSQL executados em um schema isolado (`test_cafeteria_erp`) que é criado e removido automaticamente sem tocar nos dados reais do schema `public`.

> Ao executar testes de integração contra o Supabase, utilize a URI do **Session pooler** (porta `5432`, IPv4) em `TEST_DATABASE_URL` para preservar `SET search_path` durante toda a sessão de testes.

```bash
# Testes unitários (sem banco)
pytest

# Todos os testes (unitários + integração ACID no PostgreSQL)
TEST_DATABASE_URL="postgresql+psycopg://postgres.SEU_PROJECT_REF:SUA_SENHA@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require" pytest -v

# Apenas integração de vendas, ficha técnica, estoque, financeiro e estorno
TEST_DATABASE_URL="$TEST_DATABASE_URL" pytest tests/test_vendas_integracao.py -v

# Apenas coerência matemática entre transações da 1ª VA e KPIs da 2ª VA
TEST_DATABASE_URL="$TEST_DATABASE_URL" pytest tests/test_bi_kpis.py -v
```

---

## Deploy (Streamlit Community Cloud + Supabase)

* **Aplicação publicada (Produção):** [https://cafeteria-erp.streamlit.app/](https://cafeteria-erp.streamlit.app/)
* **Callback OAuth (Produção):** `https://cafeteria-erp.streamlit.app/oauth2callback`

A publicação oficial segue o fluxo integrado entre **GitHub**, **Supabase** e **Streamlit Community Cloud** (detalhado em [`docs/GUIA_DEPLOY_SUPABASE_GOOGLE.md`](docs/GUIA_DEPLOY_SUPABASE_GOOGLE.md)):

| Branch | Papel no fluxo |
|---|---|
| `develop` | Integração contínua das funcionalidades do ERP (1ª VA) e do Dashboard BI (2ª VA) |
| `main` | Versão estável publicada automaticamente em [cafeteria-erp.streamlit.app](https://cafeteria-erp.streamlit.app/) |

### Checklist de publicação

1. Conectar o repositório GitHub em [share.streamlit.io](https://share.streamlit.io/) apontando para a branch **`main`** e arquivo principal **`app.py`**.
2. Configurar **App Settings → Secrets** com o conteúdo de `.streamlit/secrets.toml`, ajustando `[auth].redirect_uri` para:
   ```toml
   redirect_uri = "https://cafeteria-erp.streamlit.app/oauth2callback"
   ```
3. Confirmar que `https://cafeteria-erp.streamlit.app/oauth2callback` está cadastrada em **Authorized redirect URIs** no Google Cloud Console.
4. Garantir que o projeto no Supabase está ativo (Free Tier entra em pausa após 7 dias sem atividade) e que os scripts `init_db.py` e `seed_db.py` foram executados.

---

## Guia de Contribuição

O repositório adota práticas padronizadas de versionamento e organização para acompanhar a evolução incremental das entregas da 1ª VA e 2ª VA.

### Fluxo de versionamento

* Desenvolvimento concentrado na branch `develop` e branches dedicadas por funcionalidade (`feat/...`, `fix/...`, `docs/...`)
* Promoção para `main` mediante revisão e validação dos testes e do fluxo ponta-a-ponta
* Separação estrita entre camadas: nenhuma consulta SQL direta em `src/ui/` e nenhuma dependência de widgets Streamlit em `src/services/`

### Padrão de commit

```
tipo(escopo): descrição curta
```

Exemplos:

```
feat(vendas): adicionar baixa atômica de ficha técnica e estorno condicional

- Implementado lock pessimista (FOR UPDATE) nos insumos da receita
- Adicionada geração automática de ordem de preparo e título financeiro
- Criados testes de integração para estoque insuficiente e cancelamento pós-preparo
```

```
feat(bi): implementar views analíticas SQL e dashboard gerencial da 2ª VA

- Criadas 6 views vw_bi_* conectadas diretamente às tabelas do ERP
- Adicionadas abas Executivo/ABC, Estoque/Perdas, Operacional/SLA e Financeiro/DRE
```
