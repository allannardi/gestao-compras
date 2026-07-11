# Passo a passo rápido — Gestão de Compras no iPhone

Objetivo: usar o Gestão de Compras como web app no iPhone, abrindo pelo Safari e adicionando atalho na tela inicial.

## 1. Manter o Turso ativo

No computador, confirme que o app mostra na sidebar:

```text
Banco: Turso online
```

Isso significa que o banco online já está configurado.

## 2. Conferir o arquivo de secrets local

O arquivo local deve ficar em:

```text
.streamlit/secrets.toml
```

Formato esperado:

```toml
[turso]
database_url = "libsql://SEU-BANCO.turso.io"
auth_token = "SEU_TOKEN_DO_TURSO"
```

Nunca envie esse arquivo para o GitHub. O `.gitignore` já está preparado para bloquear esse arquivo.

## 3. Subir para GitHub

Na pasta do projeto:

```bash
git init
git add .
git commit -m "Gestao de Compras v0.4.9 online mobile"
git branch -M main
git remote add origin URL_DO_REPOSITORIO
git push -u origin main
```

Antes do `git push`, confira se `.streamlit/secrets.toml` não entrou no commit:

```bash
git status
```

## 4. Criar app no Streamlit Cloud

Crie o app apontando para:

```text
app.py
```

Use o repositório do GitHub.

## 5. Configurar Secrets no Streamlit Cloud

No painel do app, adicione os secrets:

```toml
[turso]
database_url = "libsql://SEU-BANCO.turso.io"
auth_token = "SEU_TOKEN_DO_TURSO"
```

Depois salve e reinicie o app.

## 6. Testar no iPhone

Abra o link HTTPS do Streamlit Cloud no Safari.

Depois:

```text
Compartilhar → Adicionar à Tela de Início → Gestão de Compras
```

Pronto. O ícone ficará na tela inicial do iPhone.

## 7. Primeiro teste no celular

1. Abra o atalho.
2. Entre em Adicionar Compra.
3. Toque em Ler QR-CODE da NF.
4. Permita acesso à câmera.
5. Leia uma NFC-e.
6. Confirme a compra.
7. Confira em Compras.
