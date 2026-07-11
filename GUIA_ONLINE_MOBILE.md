# Guia Online Mobile — Gestão de Compras

## Estratégia escolhida

Continuar com Streamlit e usar o sistema no iPhone via Safari, adicionando um atalho na Tela de Início.

## Por que este caminho

- Menos complexo do que app nativo iOS.
- Mantém a velocidade de desenvolvimento atual.
- Permite testar a câmera pelo navegador.
- Facilita ajustes rápidos nas regras de NFC-e, produtos e categorias.

## Próxima etapa após v0.4

Migrar o banco local SQLite para banco online persistente.

Opções recomendadas:

1. **Turso** — mais próximo do SQLite atual.
2. **Supabase** — mais robusto, mas muda mais a estrutura.

## Publicação sugerida

1. Subir projeto em um repositório GitHub.
2. Criar app no Streamlit Cloud.
3. Configurar Secrets com senha de acesso.
4. Testar pelo iPhone.
5. Criar atalho na Tela de Início.

## Pontos para validar online

- A câmera abre no Safari.
- A leitura do QR Code funciona bem.
- A consulta NFC-e funciona fora do PC.
- Os dados permanecem após reiniciar o app.

O último item depende da migração para banco online persistente.
