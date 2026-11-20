# Guia Prático — Supabase, Google OAuth e Deploy no Streamlit Community Cloud

Este guia descreve o passo a passo completo para provisionar o PostgreSQL no **Supabase**, configurar a **Autenticação Google (OIDC)** — incluindo acesso garantido do professor (`assuero.ximenes@ufape.edu.br`) — e executar o projeto localmente e no **Streamlit Community Cloud**.

---

## 1. Provisionar o Banco PostgreSQL no Supabase

1. Acesse [supabase.com](https://supabase.com) e crie um novo projeto (ex.: `cafeteria-erp`, região `South America (São Paulo)`), mantendo **Postgres (Default)** (não é necessário habilitar a *Data API*).
2. Anote a senha definida para o banco de dados (evite caracteres como `@`, `%`, `^`, `!`, `#`, `/`, `?`, ou faça o *percent-encoding* deles na URI).
3. No painel do projeto, clique em **Connect → Direct (Connection string)**:
   * Em **Method**, selecione **Transaction pooler** (Shared pooler, porta `6543`, host `*.pooler.supabase.com` — gratuito e compatível com IPv4 no Streamlit Community Cloud).
   * Em **Type**, mantenha **URI**.
   * Copie a URI e adapte o prefixo para `postgresql+psycopg://` mantendo `?sslmode=require`, por exemplo:
     ```text
     postgresql+psycopg://postgres.SEU_PROJECT_REF:SUA_SENHA@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require
     ```

> **Atenção (Free Tier do Supabase):** projetos gratuitos entram em pausa após 7 dias sem atividade. Antes das apresentações/correções da 1ª e 2ª VA, acesse o sistema ou o painel do Supabase para garantir que o banco esteja ativo.

---

## 2. Configurar a Autenticação Google (OAuth 2.0 / OIDC)

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/) e crie/selecione um projeto (ex.: `Cafeteria ERP UFAPE`).
2. Vá em **APIs & Services → OAuth consent screen**:
   * Escolha **External** (permite contas `@ufape.edu.br` e contas `@gmail.com`).
   * Preencha o nome do app (*Cafeteria Grão do Agreste — ERP & BI*), e-mail de suporte e contato do desenvolvedor.
   * Em **Scopes**, mantenha os escopos padrão `openid`, `email` e `profile`.
   * Em **Test users**, adicione obrigatoriamente:
     * `assuero.ximenes@ufape.edu.br` *(conta do professor avaliador)*
     * Seu próprio e-mail Google / institucional.
   * *(Opcional recomendado para produção)* Clique em **Publish App** para liberar login a qualquer conta Google sem limite de *Test Users*.
3. Vá em **APIs & Services → Credentials → + Create Credentials → OAuth client ID**:
   * **Application type:** `Web application`
   * **Authorized redirect URIs** (adicione exatamente ambas):
     * Ambiente local: `http://localhost:8501/oauth2callback`
     * Produção (Streamlit Cloud): `https://SEU-APP.streamlit.app/oauth2callback`
4. Copie o **Client ID** e o **Client Secret** gerados.

---

## 3. Configurar Credenciais Locais (`.streamlit/secrets.toml`)

1. Copie o arquivo de modelo:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
2. Gere uma chave segura para `cookie_secret`:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. Preencha `.streamlit/secrets.toml` com a URL do Supabase, `cookie_secret`, `client_id`, `client_secret` e os e-mails em `[auth_policy].admin_emails` (já inclui `assuero.ximenes@ufape.edu.br`).
4. **Verificação de segurança:** `.streamlit/secrets.toml` já está listado no `.gitignore` — nunca faça commit desse arquivo.

---

## 4. Instalar Dependências, Inicializar o Banco e Popular o Seed (90 dias)

```bash
# 1. Criar e ativar ambiente virtual Python 3.12 (ou python3 -m venv .venv)
uv venv --python 3.12 .venv
source .venv/bin/activate

# 2. Instalar dependências
uv pip install -r requirements.txt

# 3. Criar tabelas, índices e views analíticas no Supabase
# (lê automaticamente [database].url do .streamlit/secrets.toml; DATABASE_URL é opcional)
python scripts/init_db.py

# 4. Popular 90 dias de dados operacionais realistas (idempotente; executa apenas uma vez)
python scripts/seed_db.py
```

*Alternativa via Supabase SQL Editor:* caso prefira criar o schema manualmente pela interface web do Supabase, execute na ordem:
1. `sql/001_schema.sql`
2. `sql/003_indexes_and_constraints.sql`
3. `sql/002_views_bi.sql`
Em seguida execute `python scripts/seed_db.py` localmente apontando para o Supabase.

---

## 5. Executar a Aplicação Localmente

```bash
streamlit run app.py
```

Acesse `http://localhost:8501`, clique em **Entrar com Google** e autentique-se.

---

## 6. Executar Testes Automatizados (`pytest`)

```bash
# Testes unitários (sem necessidade de banco)
pytest

# Testes completos (unitários + integração ACID no PostgreSQL em schema isolado `test_cafeteria_erp`)
TEST_DATABASE_URL="$DATABASE_URL" pytest -v
```

---

## 7. Publicar no Streamlit Community Cloud

1. Faça push da branch desejada para o repositório GitHub.
2. Acesse [share.streamlit.io](https://share.streamlit.io/), clique em **Create app** e conecte seu repositório GitHub:
   * **Branch:** `main` (ou `develop`, conforme entrega)
   * **Main file path:** `app.py`
3. Antes ou logo após criar o app, abra **Settings → Secrets** e cole o conteúdo do seu `.streamlit/secrets.toml`, **atualizando apenas `redirect_uri`** para a URL real do deploy:
   ```toml
   [auth]
   redirect_uri = "https://SEU-APP.streamlit.app/oauth2callback"
   ```
4. Confirme que essa mesma URL `https://SEU-APP.streamlit.app/oauth2callback` está cadastrada em **Authorized redirect URIs** no Google Cloud Console.
5. Reinicie o app no Streamlit Cloud e teste o fluxo completo de login com Google + ERP + Dashboard BI.
