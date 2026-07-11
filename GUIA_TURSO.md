# Guia Turso — Gestão de Compras v0.4.4

Esta versão prepara o app para usar banco online Turso quando for publicado no Streamlit Cloud.

## 1. O que muda

Localmente, se você não configurar nada, o app continua usando:

```text
database/gestao_compras.db
```

Online, se você configurar as credenciais do Turso, o app passa a usar o banco remoto.

## 2. Criar banco Turso

No Turso, crie um banco para o projeto, por exemplo:

```text
gestao-compras
```

Depois obtenha:

```text
TURSO_DATABASE_URL
TURSO_AUTH_TOKEN
```

## 3. Configurar no Streamlit Cloud

No app publicado no Streamlit Cloud, acesse:

```text
Settings → Secrets
```

Cole algo neste formato:

```toml
app_password = "sua-senha-de-acesso"

[turso]
database_url = "libsql://SEU-BANCO-SUA-ORG.turso.io"
auth_token = "SEU_TOKEN"
```

Depois salve e reinicie o app.

## 4. Como saber se funcionou

Na sidebar do app deve aparecer:

```text
Banco: Turso online
```

Se aparecer:

```text
Banco: SQLite local
```

significa que as credenciais do Turso ainda não foram reconhecidas.

## 5. Primeiro acesso

Ao abrir com Turso pela primeira vez, o app cria automaticamente as tabelas principais e as categorias padrão.

## 6. Atenção

A versão v0.4.4 prepara o uso online persistente, mas o ideal é testar primeiro com banco vazio no Turso antes de migrar dados reais.
