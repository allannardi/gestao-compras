# Gestão de Compras v0.5.7

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

Esta v0.5.7 está preparada para uso online com Turso. Localmente, se o Turso estiver configurado no secrets.toml, o app também usa Turso.
Para uso online permanente, o próximo passo recomendado é migrar o banco para **Turso**.


## v0.5.7 — Preparação Turso

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


## v0.5.7 — Caminho rápido para usar no iPhone

Esta versão mantém a estratégia de Streamlit online + atalho na tela inicial do iPhone.

Use Turso online configurado em `.streamlit/secrets.toml` localmente e depois repita os mesmos secrets no Streamlit Cloud.

Próximo fluxo recomendado:

1. Testar localmente com `Banco: Turso online`.
2. Subir o projeto para GitHub, sem enviar `.streamlit/secrets.toml`.
3. Criar o app no Streamlit Cloud.
4. Informar os secrets do Turso no painel do Streamlit Cloud.
5. Abrir o link HTTPS no Safari do iPhone.
6. Adicionar à Tela de Início.


## v0.5.7 — Correção Streamlit Cloud

Ajuste de deploy: removida a porta fixa `8502` do `.streamlit/config.toml` para o Streamlit Cloud subir na porta padrão `8501`. O inicializador local continua usando a porta `8502` pelo arquivo `start_gestao_compras.bat`.


## v0.5.7

Correções:
- Compatibilidade melhor com Turso/libSQL ao acessar linhas do banco.
- Evita compra parcial quando ocorre erro ao registrar itens da NFC-e.
- Adiciona `app_database_mode = "sqlite"` para validações locais rápidas e `app_database_mode = "turso"` para uso online.

Modo local leve no PC:
```toml
app_database_mode = "sqlite"
```

Modo online/celular/Streamlit Cloud:
```toml
app_database_mode = "turso"
```


## v0.5.7 - Layout mobile

- Tela Compras em cards para celular.
- Conferência da NFC-e em cards.
- Itens dentro do detalhe da compra em cards.
- Visual mobile-first para evitar tabelas quebradas no iPhone.


## v0.5.7

- Adicionado ícone próprio do Gestão de Compras para navegador/atalho no iPhone.
- Ícone sugerido: carrinho de compras branco com recibo em fundo azul.
- Após publicar, remova o atalho antigo do iPhone e adicione novamente pela tela de compartilhamento do Safari.


## v0.5.7

Ajuste de dependências para Streamlit Cloud: removidos pins rígidos de versões para evitar build lento do pandas em Python novo no ambiente online.


## v0.5.7
- Corrige detalhes da compra no mobile/online com carregamento leve.
- Inclui página Manutenção para limpar compras de teste ou zerar banco.
- Mantém ícones novos em assets.


## v0.5.7

- Ajuste de manutenção segura no Turso/Streamlit Cloud.
- Limpar compras de teste agora remove também vínculos de mapeamento, mantendo produtos, supermercados e categorias.
- As exclusões são feitas em conexões curtas para evitar instabilidade no mobile/online.
- Ícones novos mantidos em `assets/app_icon.png` e `assets/favicon.png`.


## v0.5.7

- Troca o acesso Turso para HTTP puro via `requests`, removendo dependência nativa `libsql` para evitar Segmentation fault no Streamlit Cloud.


## v0.5.12

- Corrige erro ao confirmar compra quando a unidade do produto (ex.: lt, kg, pc) era interpretada como categoria_id no Turso.
- Mantém ajustes de estabilidade online da v0.5.10.


## v0.5.12

- Consolida itens idênticos na mesma compra antes da conferência e do registro.
- Critério: mesma descrição, mesma unidade e mesmo valor unitário.
- Soma quantidade, valor total e desconto, exibindo apenas uma linha por item idêntico.
