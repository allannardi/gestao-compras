# Guia de publicação — Gestão de Compras no Streamlit Cloud

Versão: **v0.4.1**

Este guia prepara o projeto para rodar online e ser usado no iPhone como um web app com atalho na tela inicial.

## 1. Preparar a pasta local

Diretório recomendado:

```text
C:\Users\USUARIO\Documents\4. Python\3_Gestao_Compras
```

Substitua os arquivos do projeto pela versão v0.4.1.

Não envie para o GitHub:

- `venv/`
- `.streamlit/secrets.toml`
- `database/*.db`
- `uploads/`

O arquivo `.gitignore` já está configurado para evitar isso.

## 2. Criar repositório no GitHub

No GitHub, crie um repositório chamado, por exemplo:

```text
gestao-compras
```

Depois, no terminal dentro da pasta do projeto:

```bash
git init
git add .
git commit -m "Gestao de Compras v0.4.1"
git branch -M main
git remote add origin URL_DO_SEU_REPOSITORIO
git push -u origin main
```

## 3. Publicar no Streamlit Cloud

No Streamlit Cloud:

1. Clique em **New app**.
2. Escolha o repositório `gestao-compras`.
3. Branch: `main`.
4. Main file path: `app.py`.
5. Deploy.

## 4. Configurar senha simples

No Streamlit Cloud, vá em **Settings → Secrets** e coloque:

```toml
[app]
password = "sua-senha-aqui"
```

Depois salve e reinicie o app.

## 5. Usar no iPhone como app

Depois que o link online abrir no Safari:

1. Toque em **Compartilhar**.
2. Toque em **Adicionar à Tela de Início**.
3. Nome: **Gestão de Compras**.
4. Abra pelo ícone criado.

## 6. Observação importante sobre dados

Esta versão ainda usa SQLite local. Em ambiente online gratuito, arquivos locais podem ser reiniciados ou perdidos em atualizações/redeploys.

Use esta etapa para validar o acesso mobile online. A próxima etapa recomendada é migrar o banco para **Turso**, mantendo a lógica parecida com SQLite, mas com persistência online.

## Banco persistente com Turso

A partir da v0.4.3, o app pode usar Turso online. No Streamlit Cloud, configure os Secrets:

```toml
app_password = "sua-senha"

[turso]
database_url = "libsql://SEU-BANCO-SUA-ORG.turso.io"
auth_token = "SEU_TOKEN"
```

Depois reinicie o app. A sidebar deve mostrar `Banco: Turso online`.
