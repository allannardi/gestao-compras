# Gestão de Compras v0.4.6

Checkpoint preparado para **GitHub + Streamlit Cloud + uso mobile via iPhone**.

## Status

Base validada até a v0.3.12, com preparação online iniciada na v0.4 e agora organizada para publicação em repositório.

## Principais recursos

- Adicionar Compra por QR Code da NFC-e.
- Upload de imagem do QR Code.
- Tirar foto da NF como fallback.
- Consulta da NFC-e e prévia para conferência.
- Registro inteligente da compra.
- Produtos, mercados e categorias automáticos/editáveis.
- Histórico de preços.
- Dashboard.
- Exportação Excel mantida.
- Login simples opcional para uso online.
- CSS com ajustes iniciais para celular.
- `.gitignore` preparado para GitHub.
- `runtime.txt` com Python 3.11.
- `GUIA_DEPLOY_STREAMLIT_CLOUD.md` incluído.

## Rodar localmente

```bash
cd "C:\Users\USUARIO\Documents\4. Python\3_Gestao_Compras"
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py --server.port 8502 --server.address 0.0.0.0
```

## Login simples

Por padrão, localmente o app abre sem senha.

Para ativar senha local, crie `.streamlit/secrets.toml` com:

```toml
[app]
password = "sua-senha"
```

No Streamlit Cloud, configure este segredo em **Settings → Secrets**.

## Publicação online

Siga o arquivo:

```text
GUIA_DEPLOY_STREAMLIT_CLOUD.md
```

## Uso no iPhone como atalho

Depois que o app estiver online com HTTPS:

1. Abra o link no Safari.
2. Toque no botão Compartilhar.
3. Escolha **Adicionar à Tela de Início**.
4. Nomeie como **Gestão de Compras**.
5. Abra pelo ícone criado.

## Observação sobre banco de dados

Esta v0.4.6 está preparada para uso online com Turso. Localmente, se o Turso estiver configurado no secrets.toml, o app também usa Turso.
Para uso online permanente, o próximo passo recomendado é migrar o banco para **Turso**.


## v0.4.6 — Preparação Turso

Esta versão adiciona suporte opcional ao banco online Turso.

- Sem credenciais: usa SQLite local normalmente.
- Com `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN`: usa Turso online.
- A sidebar mostra o modo atual do banco.
- Incluído o guia `GUIA_TURSO.md`.
- Incluídos scripts em `scripts/` para testar conexão e migrar dados locais.

Para o Streamlit Cloud, configure os Secrets assim:

```toml
app_password = "sua-senha"

[turso]
database_url = "libsql://SEU-BANCO-SUA-ORG.turso.io"
auth_token = "SEU_TOKEN"
```


## v0.4.6 — Caminho rápido para usar no iPhone

Esta versão mantém a estratégia de Streamlit online + atalho na tela inicial do iPhone.

Use Turso online configurado em `.streamlit/secrets.toml` localmente e depois repita os mesmos secrets no Streamlit Cloud.

Próximo fluxo recomendado:

1. Testar localmente com `Banco: Turso online`.
2. Subir o projeto para GitHub, sem enviar `.streamlit/secrets.toml`.
3. Criar o app no Streamlit Cloud.
4. Informar os secrets do Turso no painel do Streamlit Cloud.
5. Abrir o link HTTPS no Safari do iPhone.
6. Adicionar à Tela de Início.
