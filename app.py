from datetime import date, datetime
from io import BytesIO
import hmac
import os

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

try:
    from database.db import init_db, get_db_label
except ImportError:
    from database.db import init_db
    def get_db_label():
        return 'SQLite local'
from services import data as db
from services.utils import brl, pct, mes_atual
from services.captura import detectar_qrcode_em_imagem, extrair_chave_nfce, salvar_imagem_nf
from services.nfce import consultar_nfce_por_qrcode

st.set_page_config(
    page_title="Gestão de Compras",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    init_db()
except Exception as exc:
    st.set_page_config(page_title="Gestão de Compras", page_icon="🛒", layout="wide")
    st.error("Erro ao inicializar o banco de dados.")
    st.exception(exc)
    st.stop()

with open("assets/style.css", "r", encoding="utf-8") as f:
    st.markdown(f.read(), unsafe_allow_html=True)



def get_app_password():
    """Retorna senha simples configurada em variável de ambiente ou secrets.toml.

    Local: opcional. Online: configurar APP_PASSWORD ou [app].password.
    """
    env_pwd = os.environ.get("APP_PASSWORD") or os.environ.get("GESTAO_COMPRAS_PASSWORD")
    if env_pwd:
        return env_pwd
    try:
        if "app_password" in st.secrets:
            return str(st.secrets["app_password"])
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
        if "app" in st.secrets and "password" in st.secrets["app"]:
            return str(st.secrets["app"]["password"])
    except Exception:
        return None
    return None


def require_login():
    """Login simples para uso online.

    Se nenhuma senha estiver configurada, o app abre direto para manter o uso local simples.
    """
    senha_app = get_app_password()
    if not senha_app:
        return
    if st.session_state.get("authenticated"):
        return

    st.markdown('<div class="main-title">🛒 Gestão de Compras</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Acesso protegido para uso online.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        senha_digitada = st.text_input("Senha de acesso", type="password")
        entrar = st.button("Entrar", type="primary", use_container_width=True)
        if entrar:
            if hmac.compare_digest(str(senha_digitada), str(senha_app)):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()


require_login()


def rerun():
    st.rerun()


def options_from_df(df, label_col="nome", id_col="id", placeholder="Selecione"):
    opts = {placeholder: None}
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            opts[f"{row[label_col]} (ID {row[id_col]})"] = int(row[id_col])
    return opts


def header():
    st.markdown('<div class="main-title">🛒 Gestão de Compras</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Controle de compras de supermercado, histórico de preços e inflação pessoal da família.</div>', unsafe_allow_html=True)


def sidebar():
    st.sidebar.markdown("## Gestão de Compras")
    st.sidebar.caption("v0.5 • Layout mobile")
    pages = [
        "Adicionar Compra",
        "Dashboard",
        "Compras",
        "Produtos",
        "Mercados",
        "Categorias",
        "Histórico de Preços",
        "Exportar Excel",
    ]
    if "page" not in st.session_state:
        st.session_state.page = "Adicionar Compra"
    for i, p in enumerate(pages):
        label = "Adicionar Compra" if p == "Adicionar Compra" else p
        btn_type = "primary" if p == "Adicionar Compra" else "secondary"
        if st.sidebar.button(label, use_container_width=True, key=f"nav_{i}_{p}", type=btn_type):
            st.session_state.page = p
    st.sidebar.divider()
    st.sidebar.caption(f"Banco: {get_db_label()}")
    st.sidebar.caption("Uso recomendado: abrir online pelo Safari e adicionar à Tela de Início.")
    if get_app_password():
        if st.sidebar.button("Sair", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

def kpi_grid(items):
    """Renderiza os KPIs de forma compatível com diferentes versões do Streamlit."""
    if not items:
        return

    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        with col:
            card_html = f"""
<div class="kpi-card">
    <div class="kpi-label">{label}</div>
    <div class="kpi-value">{value}</div>
    <div class="kpi-help">{help_text}</div>
</div>
"""
            st.markdown(card_html, unsafe_allow_html=True)


def _prepare_plotly_currency(fig, y_title="Valor total (R$)"):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=35, b=10),
        font=dict(family="Inter", color="#0F172A"),
    )
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.2f", gridcolor="#E2E8F0", title_text=y_title)
    fig.update_xaxes(gridcolor="#F1F5F9")
    return fig


def qtd_br(valor):
    try:
        v = float(valor or 0)
    except Exception:
        return "0"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v))}"
    texto = f"{v:.3f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")




def _safe_html(value):
    import html
    return html.escape(str(value if value is not None else ""))



def render_tabela_conferencia_nf(itens):
    """Renderiza os itens da prévia NFC-e em cards mobile-first."""
    if not itens:
        return
    total = 0.0
    st.markdown('<div class="mobile-list-title">Itens encontrados na NF</div>', unsafe_allow_html=True)
    for idx, item in enumerate(itens, start=1):
        desc = _safe_html(item.get("descricao_original") or "-")
        unidade = _safe_html(item.get("unidade") or "-")
        qtd = qtd_br(item.get("quantidade") or 0)
        valor_unitario = brl(float(item.get("valor_unitario") or 0))
        valor_total_float = float(item.get("valor_total") or 0)
        valor_total = brl(valor_total_float)
        total += valor_total_float
        st.markdown(f"""
<div class="mobile-item-card nf-preview-card">
  <div class="mobile-card-topline">
    <div class="mobile-card-index">#{idx}</div>
    <div class="mobile-card-title">{desc}</div>
  </div>
  <div class="mobile-card-grid">
    <div><span>QTD</span><strong>{qtd}</strong></div>
    <div><span>Un.</span><strong>{unidade}</strong></div>
    <div><span>Unitário</span><strong>{valor_unitario}</strong></div>
    <div><span>Total</span><strong class="money-strong">{valor_total}</strong></div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.markdown(f"<div class='mobile-total-strip'>Soma dos itens lidos: <strong>{brl(total)}</strong></div>", unsafe_allow_html=True)


def render_itens_compra_modal(itens):
    """Renderiza os itens do modal de detalhes da compra em cards mobile-first."""
    if itens is None or itens.empty:
        return
    df = itens.copy()
    st.markdown('<div class="mobile-list-title">Itens desta compra</div>', unsafe_allow_html=True)
    for idx, row in df.iterrows():
        produto = _safe_html(row.get("produto") or row.get("descricao_original") or "-")
        desc = _safe_html(row.get("descricao_original") or "-")
        qtd = qtd_br(row.get("quantidade") or 0)
        unidade = _safe_html(row.get("unidade") or "-")
        valor_unitario = brl(float(row.get("valor_unitario") or 0))
        valor_total = brl(float(row.get("valor_total") or 0))
        categoria = _safe_html(row.get("categoria") or "Sem categoria")
        st.markdown(f"""
<div class="mobile-item-card purchase-item-card">
  <div class="mobile-card-title">{produto}</div>
  <div class="mobile-card-subtitle">{desc}</div>
  <div class="mobile-card-grid">
    <div><span>QTD</span><strong>{qtd}</strong></div>
    <div><span>Un.</span><strong>{unidade}</strong></div>
    <div><span>Unitário</span><strong>{valor_unitario}</strong></div>
    <div><span>Total</span><strong class="money-strong">{valor_total}</strong></div>
  </div>
  <div class="mobile-card-footer">Categoria: <strong>{categoria}</strong></div>
</div>
""", unsafe_allow_html=True)

def render_top_produtos_dashboard(top):
    widths = [2.8, 0.85, 0.85, 1.25, 0.85, 1.25]
    header_cols = st.columns(widths)
    labels = ["Produto", "QTD", "Unidade", "Valor Unitário", "Compras", "Valor Total"]
    for idx, (col, label) in enumerate(zip(header_cols, labels)):
        align = "left" if idx == 0 else "center"
        col.markdown(f"<div class='table-header table-{align}'>{label}</div>", unsafe_allow_html=True)
    for _, row in top.iterrows():
        cols = st.columns(widths)
        cols[0].markdown(f"<div class='table-cell'>{row['produto']}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div class='table-cell table-center'>{qtd_br(row['quantidade'])}</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div class='table-cell table-center'>{row['unidade'] or '-'}</div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div class='table-cell table-center'>{brl(float(row['valor_unitario'] or 0))}</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div class='table-cell table-center'>{int(row['compras'] or 0)}</div>", unsafe_allow_html=True)
        cols[5].markdown(f"<div class='table-cell table-center table-strong'>{brl(float(row['valor_total'] or 0))}</div>", unsafe_allow_html=True)


def page_dashboard():
    header()
    compras, itens = db.dashboard_data()

    if compras.empty:
        kpi_grid([
            ("Gasto do mês", brl(0), "Sem compras registradas"),
            ("Compras", "0", "Cadastre a primeira compra"),
            ("Ticket médio", brl(0), "Média por compra"),
            ("Itens", "0", "Itens registrados"),
        ])
        st.info("Comece usando **Adicionar Compra** para ler uma NFC-e e montar o histórico automaticamente.")
        return

    compras["data_compra"] = pd.to_datetime(compras["data_compra"])
    compras["mes"] = compras["data_compra"].dt.strftime("%Y-%m")
    mes = st.selectbox("Mês de análise", sorted(compras["mes"].unique(), reverse=True), index=0)
    compras_mes = compras[compras["mes"] == mes]
    itens_mes = itens.copy()
    if not itens_mes.empty:
        itens_mes["data_compra"] = pd.to_datetime(itens_mes["data_compra"])
        itens_mes["mes"] = itens_mes["data_compra"].dt.strftime("%Y-%m")
        itens_mes = itens_mes[itens_mes["mes"] == mes]

    gasto_mes = compras_mes["valor_total"].sum()
    qtd_compras = len(compras_mes)
    ticket = gasto_mes / qtd_compras if qtd_compras else 0
    qtd_itens = int(itens_mes.shape[0]) if not itens_mes.empty else 0

    kpi_grid([
        ("Gasto do mês", brl(gasto_mes), f"Referência: {mes}"),
        ("Compras", str(qtd_compras), "Compras registradas"),
        ("Ticket médio", brl(ticket), "Valor médio por compra"),
        ("Itens", str(qtd_itens), "Linhas de itens registradas"),
    ])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-title">Gastos por categoria</div>', unsafe_allow_html=True)
        if not itens_mes.empty and "categoria" in itens_mes:
            cat = itens_mes.groupby("categoria", dropna=False)["valor_total"].sum().reset_index().sort_values("valor_total", ascending=False)
            cat["categoria"] = cat["categoria"].fillna("Sem categoria")
            cat["valor_formatado"] = cat["valor_total"].apply(brl)
            fig = px.bar(cat, x="categoria", y="valor_total", text="valor_formatado")
            fig.update_traces(
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Valor: <b>R$ %{y:,.2f}</b><extra></extra>",
            )
            fig.update_layout(height=360, xaxis_title=None, showlegend=False)
            _prepare_plotly_currency(fig)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.caption("Ainda não há itens para gerar este gráfico.")

    with col2:
        st.markdown('<div class="section-title">Gastos por supermercado</div>', unsafe_allow_html=True)
        merc = compras_mes.groupby("mercado", dropna=False)["valor_total"].sum().reset_index().sort_values("valor_total", ascending=False)
        merc["mercado"] = merc["mercado"].fillna("Sem supermercado")
        merc["valor_formatado"] = merc["valor_total"].apply(brl)
        fig = px.pie(
            merc,
            names="mercado",
            values="valor_total",
            hole=0.58,
            custom_data=["valor_formatado"],
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>Valor: <b>%{customdata[0]}</b><br>Participação: %{percent}<extra></extra>",
        )
        fig.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=35, b=10),
            legend_title_text="",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#0F172A"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="section-title">Evolução mensal</div>', unsafe_allow_html=True)
    mensal = compras.groupby("mes")["valor_total"].sum().reset_index()
    mensal["valor_formatado"] = mensal["valor_total"].apply(brl)
    fig = px.line(mensal, x="mes", y="valor_total", markers=True)
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=9),
        customdata=mensal[["valor_formatado"]].to_numpy(),
        hovertemplate="<b>%{x}</b><br>Total: <b>%{customdata[0]}</b><extra></extra>",
    )
    fig.update_layout(height=340, xaxis_title="Mês", showlegend=False)
    _prepare_plotly_currency(fig)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="section-title">Top produtos do mês</div>', unsafe_allow_html=True)
    if not itens_mes.empty:
        base = itens_mes.copy()
        base["produto"] = base["produto"].fillna(base["descricao_original"]).fillna("Produto não padronizado")
        top = base.groupby(["produto", "unidade"], dropna=False).agg(
            valor_total=("valor_total", "sum"),
            quantidade=("quantidade", "sum"),
            compras=("compra_id", "nunique"),
        ).reset_index().sort_values("valor_total", ascending=False).head(10)
        top["valor_unitario"] = top.apply(lambda r: (float(r["valor_total"] or 0) / float(r["quantidade"] or 0)) if float(r["quantidade"] or 0) else 0, axis=1)
        render_top_produtos_dashboard(top)
    else:
        st.caption("Sem itens neste mês.")



def html_leitor_qr_ao_vivo():
    """Leitor QR Code no navegador usando a câmera do celular.

    Usa biblioteca JS via CDN para melhorar a leitura em tempo real. Ao ler,
    joga o conteúdo para a URL como parâmetro qr_text, e o Streamlit mostra
    a criação da compra pendente.
    """
    components.html(
        """
<div id="reader" style="width:100%; max-width:480px; margin:0 auto;"></div>
<div id="qr-result" style="margin-top:12px; padding:10px; border-radius:8px; background:#f1f5f9; font-family:Arial; font-size:14px; display:none;"></div>
<script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
<script>
function showResult(text) {
  const box = document.getElementById('qr-result');
  box.style.display = 'block';
  box.innerText = 'QR Code lido. Abrindo no app...';
  try {
    const url = new URL(window.parent.location.href);
    url.searchParams.set('qr_text', text);
    window.parent.location.href = url.toString();
  } catch (e) {
    box.innerText = text;
  }
}
function startScanner() {
  if (typeof Html5Qrcode === 'undefined') {
    document.getElementById('qr-result').style.display = 'block';
    document.getElementById('qr-result').innerText = 'Não foi possível carregar o leitor ao vivo. Use a aba de foto/upload ou cole a chave manualmente.';
    return;
  }
  const html5QrCode = new Html5Qrcode("reader");
  const config = { fps: 10, qrbox: { width: 260, height: 260 }, aspectRatio: 1.0 };
  html5QrCode.start(
    { facingMode: "environment" },
    config,
    (decodedText, decodedResult) => {
      html5QrCode.stop().then(() => showResult(decodedText)).catch(() => showResult(decodedText));
    },
    (errorMessage) => {}
  ).catch((err) => {
    document.getElementById('qr-result').style.display = 'block';
    document.getElementById('qr-result').innerText = 'Não consegui abrir a câmera neste navegador. Tente pelo celular ou use upload/foto.';
  });
}
startScanner();
</script>
        """,
        height=560,
    )


def _date_from_iso_safe(value):
    if not value:
        return date.today()
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return date.today()


def render_compra_registrada(compra_id):
    resumo = db.resumo_compra(compra_id)
    compra = resumo.get("compra")
    itens = resumo.get("itens")
    if not compra:
        st.warning("Não encontrei esta compra registrada.")
        return

    st.success(f"Compra registrada com sucesso. ID {compra_id}.")
    kpi_grid([
        ("Mercado", compra.get("mercado") or "Sem mercado", "Mercado vinculado automaticamente"),
        ("Valor da nota", brl(float(compra.get("valor_total") or 0)), "Valor a pagar da NFC-e"),
        ("Itens", str(resumo.get("qtd_itens") or 0), "Itens gravados na compra"),
        ("Pagamento", compra.get("forma_pagamento") or "Não informado", brl(float(compra.get("valor_pago") or 0))),
    ])

    diferenca = float(resumo.get("diferenca") or 0)
    if abs(diferenca) <= 0.05:
        st.caption(f"Conferência: soma dos itens {brl(resumo.get('total_itens') or 0)} x valor da nota {brl(float(compra.get('valor_total') or 0))}.")
    else:
        st.warning(f"Atenção: soma dos itens {brl(resumo.get('total_itens') or 0)} x valor da nota {brl(float(compra.get('valor_total') or 0))}. Diferença: {brl(diferenca)}.")

    with st.expander("Ver itens registrados", expanded=True):
        if itens is not None and not itens.empty:
            st.dataframe(
                itens[["descricao_original", "produto", "quantidade", "unidade", "valor_unitario", "valor_total", "categoria"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Compra criada sem itens. Complete os dados depois pela revisão da compra.")

    c1, c2 = st.columns(2)
    if c1.button("Adicionar outra compra", use_container_width=True):
        st.session_state.page = "Adicionar Compra"
        st.session_state.pop("compra_registrada_id", None)
        rerun()
    if c2.button("Ver lista de compras", use_container_width=True):
        st.session_state.pop("compra_registrada_id", None)
        st.session_state.page = "Compras"
        rerun()



def preparar_preview_nfce(qr_texto, key_prefix, obs_extra=""):
    """Mostra a prévia da NFC-e e registra a compra com um único OK."""
    chave = extrair_chave_nfce(qr_texto)
    with st.spinner("Buscando dados da NFC-e e montando prévia..."):
        dados = consultar_nfce_por_qrcode(qr_texto)

    if dados.get("ok"):
        st.success(dados.get("mensagem") or "Dados encontrados automaticamente.")
    else:
        st.warning(dados.get("mensagem") or "Não consegui completar a leitura automática. Você ainda pode registrar a compra pendente.")

    if chave:
        st.write(f"**Chave NFC-e:** `{chave}`")
        existente = db.get_compra_por_chave(chave)
        if existente:
            st.warning(f"Esta NFC-e já está registrada no sistema como compra ID {int(existente['id'])}. Para evitar duplicidade, a confirmação foi bloqueada.")
            if st.button("Abrir compra já registrada", use_container_width=True, key=f"{key_prefix}_abrir_existente"):
                st.session_state.compra_registrada_id = int(existente["id"])
                st.session_state.page = "Compras"
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                rerun()
            return

    st.markdown('<div class="section-title">Prévia para conferência</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    mercado_nome = c1.text_input("Mercado", value=dados.get("mercado_nome") or "", key=f"{key_prefix}_mercado")
    cnpj = c2.text_input("CNPJ", value=dados.get("cnpj") or "", key=f"{key_prefix}_cnpj")

    c3, c4 = st.columns(2)
    data_compra = c3.date_input("Data da compra", value=_date_from_iso_safe(dados.get("data_compra")), key=f"{key_prefix}_data")
    valor_default = float(dados.get("valor_total") or 0)
    valor_total = c4.number_input("Valor total / valor a pagar", min_value=0.0, value=valor_default, step=1.0, format="%.2f", key=f"{key_prefix}_valor")

    c5, c6 = st.columns(2)
    forma_pagamento = c5.text_input("Forma de pagamento", value=dados.get("forma_pagamento") or "", key=f"{key_prefix}_forma_pagamento")
    valor_pago_default = float(dados.get("valor_pago") or valor_default or 0)
    valor_pago = c6.number_input("Valor pago", min_value=0.0, value=valor_pago_default, step=1.0, format="%.2f", key=f"{key_prefix}_valor_pago")

    itens = dados.get("itens") or []
    if itens:
        st.caption(f"Itens encontrados automaticamente: {len(itens)}. Confira rapidamente antes de registrar.")
        itens_confirmados = []
        for item in itens:
            itens_confirmados.append({
                "descricao_original": item.get("descricao_original") or "",
                "quantidade": float(item.get("quantidade") or 1),
                "unidade": item.get("unidade") or "un",
                "valor_unitario": float(item.get("valor_unitario") or 0),
                "valor_total": float(item.get("valor_total") or 0),
                "desconto": float(item.get("desconto") or 0),
            })
        render_tabela_conferencia_nf(itens_confirmados)
    else:
        st.info("Nenhum item foi extraído automaticamente. Ao confirmar, será criada uma compra pendente para você completar depois.")
        itens_confirmados = []

    with st.expander("Ver conteúdo bruto lido do QR Code"):
        st.text_area("Conteúdo do QR Code", value=qr_texto or "", height=90, key=f"{key_prefix}_raw")

    texto_botao = "✅ Confirmar e registrar esta compra" if itens_confirmados else "✅ Criar compra pendente para completar depois"
    if st.button(texto_botao, use_container_width=True, key=f"{key_prefix}_confirmar"):
        obs = "Criada a partir da leitura do QR Code NFC-e."
        if obs_extra:
            obs += f" {obs_extra}"
        if not dados.get("ok"):
            obs += f" Observação da leitura: {dados.get('mensagem','')}"
        compra_id = db.add_compra_com_itens_nfce(
            mercado_nome=mercado_nome,
            cnpj=cnpj,
            data_compra=str(data_compra),
            valor_total=float(valor_total or 0),
            chave_nfce=chave,
            url_qrcode=qr_texto or "",
            itens=itens_confirmados,
            observacoes=obs,
            forma_pagamento=forma_pagamento,
            valor_pago=float(valor_pago or 0),
        )
        st.session_state.compra_registrada_id = int(compra_id)
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.session_state.page = "Compras"
        rerun()


def page_capturar_nf():
    header()
    st.markdown('<div class="section-title">Adicionar Compra</div>', unsafe_allow_html=True)
    st.info(
        "Use o QR Code da NFC-e como fluxo principal. O sistema lê a nota, monta a prévia e deixa apenas a conferência antes de registrar."
    )

    st.markdown("#### Ler QR-CODE da NF")
    st.caption("Tire uma foto aproximada do QR Code impresso na nota fiscal.")
    if st.button("Ler QR-CODE da NF", use_container_width=True, key="btn_ler_qrcode_nf"):
        st.session_state.mostrar_camera_qr = True
        st.session_state.mostrar_camera_nf = False

    foto_qr = None
    if st.session_state.get("mostrar_camera_qr"):
        foto_qr = st.camera_input("Fotografar QR Code da NF", key="camera_qr_nf")
        if st.button("Fechar câmera do QR Code", use_container_width=True, key="btn_fechar_camera_qr"):
            st.session_state.mostrar_camera_qr = False
            rerun()

    st.markdown("#### Upload da NF")
    uploaded_qr = st.file_uploader("Enviar imagem do QR Code da NF", type=["png", "jpg", "jpeg", "webp"], key="upload_qr")

    img = foto_qr or uploaded_qr
    if img is not None:
        try:
            texto_qr = detectar_qrcode_em_imagem(img)
            caminho_img = salvar_imagem_nf(img, "qrcode_nfce")
            if texto_qr:
                st.success("QR Code lido com sucesso.")
                preparar_preview_nfce(texto_qr, "foto_qr", obs_extra=f"Imagem salva em: {caminho_img}.")
            else:
                st.error("Não consegui ler o QR Code nesta imagem.")
                st.markdown(
                    "Tente novamente aproximando mais e enquadrando somente o QR Code.  \n"
                    "Se ainda não funcionar, use o botão **Tirar foto da NF** para criar uma compra pendente e completar depois."
                )
        except Exception as e:
            st.error(f"Erro ao processar a imagem: {e}")

    st.markdown("#### Tirar foto da NF")
    st.caption("Use esta opção apenas quando a leitura do QR Code não funcionar. Ela cria uma compra pendente para completar depois.")
    if st.button("Tirar foto da NF", use_container_width=True, key="btn_tirar_foto_nf"):
        st.session_state.mostrar_camera_nf = True
        st.session_state.mostrar_camera_qr = False

    if st.session_state.get("mostrar_camera_nf"):
        foto_nf = st.camera_input("Fotografar nota fiscal completa", key="camera_nf")
        if st.button("Fechar câmera da NF", use_container_width=True, key="btn_fechar_camera_nf"):
            st.session_state.mostrar_camera_nf = False
            rerun()
        if foto_nf is not None:
            caminho = salvar_imagem_nf(foto_nf, "foto_nf")
            st.success(f"Foto salva em: {caminho}")
            c1, c2 = st.columns(2)
            data_compra = c1.date_input("Data da compra", value=date.today(), key="foto_data_compra")
            valor_total = c2.number_input("Valor total", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="foto_valor_total")
            if st.button("Criar compra pendente com esta foto", use_container_width=True):
                obs = f"Criada a partir de foto da nota. Imagem salva em: {caminho}. OCR será tratado em versão futura."
                compra_id = db.add_compra(None, str(data_compra), valor_total, "", "", "OCR", "Pendente", obs)
                st.success(f"Compra pendente criada. ID {compra_id}. Agora revise em Compras e adicione os itens.")
                st.session_state.page = "Compras"
                rerun()

def _render_form_categoria(categoria_id=None):
    cats = db.get_categorias(ativas=False)
    row = None
    if categoria_id:
        row_df = cats[cats["id"] == categoria_id]
        if row_df.empty:
            st.warning("Categoria não encontrada.")
            return
        row = row_df.iloc[0]

    with st.form(f"form_categoria_{categoria_id or 'nova'}"):
        nome = st.text_input("Nome da categoria", value=(row["nome"] if row is not None else ""))
        grupo = st.text_input("Grupo", value=((row["grupo"] or "Geral") if row is not None else "Geral"))
        ativo = True if row is None else bool(row["ativo"])
        if row is not None:
            ativo = st.checkbox("Categoria ativa", value=ativo)
        salvar = st.form_submit_button("Salvar categoria", use_container_width=True)
        if salvar:
            if not nome.strip():
                st.warning("Informe o nome da categoria.")
                return
            try:
                if row is None:
                    db.add_categoria(nome.strip(), grupo.strip() or "Geral")
                    st.session_state.pop("adicionar_categoria", None)
                    st.success("Categoria cadastrada.")
                else:
                    db.update_categoria(int(row["id"]), nome.strip(), grupo.strip() or "Geral", ativo)
                    st.session_state.pop("editar_categoria_id", None)
                    st.success("Categoria atualizada.")
                rerun()
            except Exception as e:
                st.error(f"Não foi possível salvar: {e}")


def _abrir_modal_categoria(categoria_id=None):
    titulo = "Nova Categoria" if categoria_id is None else "Editar Categoria"
    if hasattr(st, "dialog"):
        @st.dialog(titulo, width="large")
        def _dialog():
            _render_form_categoria(categoria_id)
            if st.button("Fechar", use_container_width=True, key=f"fechar_categoria_{categoria_id or 'nova'}"):
                st.session_state.pop("adicionar_categoria", None)
                st.session_state.pop("editar_categoria_id", None)
                rerun()
        _dialog()
    else:
        st.markdown(f'<div class="section-title">{titulo}</div>', unsafe_allow_html=True)
        _render_form_categoria(categoria_id)


def page_categorias():
    header()
    st.markdown('<div class="section-title">Categorias</div>', unsafe_allow_html=True)
    st.caption("Categorias usadas para organizar os produtos lidos nas notas fiscais.")

    cats = db.get_categorias(ativas=False)
    if cats.empty:
        st.info("Nenhuma categoria cadastrada.")
    else:
        header_cols = st.columns([0.55, 2.4, 1.4, 0.9, 0.8])
        labels = ["ID", "Categoria", "Grupo", "Status", "Editar"]
        for col, label in zip(header_cols, labels):
            col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)

        for _, row in cats.iterrows():
            categoria_id = int(row["id"])
            cols = st.columns([0.55, 2.4, 1.4, 0.9, 0.8])
            cols[0].markdown(f"<div class='table-cell'>{categoria_id}</div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div class='table-cell'>{row['nome'] or '-'}</div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div class='table-cell'>{row['grupo'] or '-'}</div>", unsafe_allow_html=True)
            status = "Ativa" if int(row.get("ativo", 1)) == 1 else "Inativa"
            cols[3].markdown(f"<div class='table-cell'>{status}</div>", unsafe_allow_html=True)
            if cols[4].button("Editar", key=f"editar_categoria_{categoria_id}", use_container_width=True):
                st.session_state.editar_categoria_id = categoria_id
                rerun()

    st.markdown("")
    if st.button("Adicionar categoria", use_container_width=True):
        st.session_state.adicionar_categoria = True
        rerun()

    if st.session_state.get("adicionar_categoria"):
        _abrir_modal_categoria(None)
    if st.session_state.get("editar_categoria_id"):
        _abrir_modal_categoria(int(st.session_state.editar_categoria_id))


def _render_form_mercado(mercado_id=None):
    mercados = db.get_mercados(ativos=False)
    row = None
    if mercado_id:
        row_df = mercados[mercados["id"] == mercado_id]
        if row_df.empty:
            st.warning("Supermercado não encontrado.")
            return
        row = row_df.iloc[0]

    with st.form(f"form_mercado_{mercado_id or 'novo'}"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome do supermercado", value=(row["nome"] if row is not None else ""))
        cnpj = c2.text_input("CNPJ", value=((row["cnpj"] or "") if row is not None else ""))
        c3, c4, c5 = st.columns(3)
        cidade = c3.text_input("Cidade", value=((row["cidade"] or "") if row is not None else ""))
        bairro = c4.text_input("Bairro", value=((row["bairro"] or "") if row is not None else ""))
        uf = c5.text_input("UF", value=((row["uf"] or "") if row is not None else ""), max_chars=2)
        ativo = True if row is None else bool(row["ativo"])
        if row is not None:
            ativo = st.checkbox("Supermercado ativo", value=ativo)
        salvar = st.form_submit_button("Salvar supermercado", use_container_width=True)
        if salvar:
            if not nome.strip():
                st.warning("Informe o nome do supermercado.")
                return
            try:
                if row is None:
                    db.add_mercado(nome.strip(), cnpj.strip(), cidade.strip(), bairro.strip(), uf.strip().upper())
                    st.session_state.pop("adicionar_mercado", None)
                    st.success("Supermercado cadastrado.")
                else:
                    db.update_mercado(int(row["id"]), nome.strip(), cnpj.strip(), cidade.strip(), bairro.strip(), uf.strip().upper(), ativo)
                    st.session_state.pop("editar_mercado_id", None)
                    st.success("Supermercado atualizado.")
                rerun()
            except Exception as e:
                st.error(f"Não foi possível salvar: {e}")


def _abrir_modal_mercado(mercado_id=None):
    titulo = "Novo Supermercado" if mercado_id is None else "Editar Supermercado"
    if hasattr(st, "dialog"):
        @st.dialog(titulo, width="large")
        def _dialog():
            _render_form_mercado(mercado_id)
            if st.button("Fechar", use_container_width=True, key=f"fechar_mercado_{mercado_id or 'novo'}"):
                st.session_state.pop("adicionar_mercado", None)
                st.session_state.pop("editar_mercado_id", None)
                rerun()
        _dialog()
    else:
        st.markdown(f'<div class="section-title">{titulo}</div>', unsafe_allow_html=True)
        _render_form_mercado(mercado_id)


def page_mercados():
    header()
    st.markdown('<div class="section-title">Supermercados</div>', unsafe_allow_html=True)
    st.caption("Supermercados são criados automaticamente na leitura da NFC-e. Use esta tela para revisar ou corrigir dados.")

    mercados = db.get_mercados(ativos=False)
    if mercados.empty:
        st.info("Nenhum supermercado cadastrado ainda.")
    else:
        header_cols = st.columns([0.5, 2.2, 1.3, 1.2, 1.2, 0.6, 0.85, 0.8])
        labels = ["ID", "Supermercado", "CNPJ", "Cidade", "Bairro", "UF", "Status", "Editar"]
        for col, label in zip(header_cols, labels):
            col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)

        for _, row in mercados.iterrows():
            mercado_id = int(row["id"])
            cols = st.columns([0.5, 2.2, 1.3, 1.2, 1.2, 0.6, 0.85, 0.8])
            cols[0].markdown(f"<div class='table-cell'>{mercado_id}</div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div class='table-cell'>{row['nome'] or '-'}</div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div class='table-cell'>{row['cnpj'] or '-'}</div>", unsafe_allow_html=True)
            cols[3].markdown(f"<div class='table-cell'>{row['cidade'] or '-'}</div>", unsafe_allow_html=True)
            cols[4].markdown(f"<div class='table-cell'>{row['bairro'] or '-'}</div>", unsafe_allow_html=True)
            cols[5].markdown(f"<div class='table-cell'>{row['uf'] or '-'}</div>", unsafe_allow_html=True)
            status = "Ativo" if int(row.get("ativo", 1)) == 1 else "Inativo"
            cols[6].markdown(f"<div class='table-cell'>{status}</div>", unsafe_allow_html=True)
            if cols[7].button("Editar", key=f"editar_mercado_{mercado_id}", use_container_width=True):
                st.session_state.editar_mercado_id = mercado_id
                rerun()

    st.markdown("")
    if st.button("Adicionar supermercado", use_container_width=True):
        st.session_state.adicionar_mercado = True
        rerun()

    if st.session_state.get("adicionar_mercado"):
        _abrir_modal_mercado(None)
    if st.session_state.get("editar_mercado_id"):
        _abrir_modal_mercado(int(st.session_state.editar_mercado_id))


def _render_edit_produto_modal(produto_id):
    produtos = db.get_produtos(ativos=False)
    cats = db.get_categorias()
    cat_opts = options_from_df(cats, "nome", "id", "Sem categoria")
    row_df = produtos[produtos["id"] == produto_id]
    if row_df.empty:
        st.warning("Produto não encontrado.")
        return
    row = row_df.iloc[0]

    with st.form(f"edit_produto_modal_{produto_id}"):
        c1, c2 = st.columns([2, 1])
        nome_e = c1.text_input("Nome do produto", value=row["nome_padronizado"] or "")
        marca_e = c2.text_input("Marca", value=row["marca"] or "")
        c3, c4, c5 = st.columns(3)
        current_cat = None
        if pd.notna(row["categoria_id"]):
            for k, v in cat_opts.items():
                if v == int(row["categoria_id"]):
                    current_cat = k
        cat_keys = list(cat_opts.keys())
        cat_index = cat_keys.index(current_cat) if current_cat in cat_keys else 0
        cat_e = c3.selectbox("Categoria", cat_keys, index=cat_index)
        unidade_e = c4.text_input("Unidade padrão", value=row["unidade_padrao"] or "un")
        qtd_e = c5.number_input("Quantidade padrão", min_value=0.0, value=float(row["quantidade_padrao"] or 1), step=0.1)
        ativo_e = st.checkbox("Produto ativo", value=bool(row["ativo"]))

        salvar = st.form_submit_button("Salvar alterações", use_container_width=True)
        if salvar:
            if not nome_e.strip():
                st.warning("Informe o nome do produto.")
            else:
                db.update_produto(int(row["id"]), nome_e.strip(), marca_e.strip(), cat_opts[cat_e], unidade_e.strip() or "un", qtd_e, ativo_e)
                st.session_state.pop("editar_produto_id", None)
                st.success("Produto atualizado.")
                rerun()


def _abrir_modal_produto(produto_id):
    if hasattr(st, "dialog"):
        @st.dialog("Editar Produto", width="large")
        def _dialog():
            _render_edit_produto_modal(produto_id)
            if st.button("Fechar", use_container_width=True):
                st.session_state.pop("editar_produto_id", None)
                rerun()
        _dialog()
    else:
        st.markdown('<div class="section-title">Editar Produto</div>', unsafe_allow_html=True)
        _render_edit_produto_modal(produto_id)
        if st.button("Fechar edição", use_container_width=True):
            st.session_state.pop("editar_produto_id", None)
            rerun()


def page_produtos():
    header()
    st.markdown('<div class="section-title">Produtos</div>', unsafe_allow_html=True)
    st.info("Os produtos são criados automaticamente a partir das NFC-e lidas. O sistema agora tenta padronizar nome, identificar marca e sugerir categoria sozinho. Use esta tela apenas para revisar e corrigir quando necessário.")

    produtos = db.get_produtos(ativos=False)
    if not produtos.empty:
        total_produtos = len(produtos)
        sem_categoria = produtos[produtos["categoria"].fillna("").isin(["", "Outros"])]
        kpi_grid([
            ("Produtos", str(total_produtos), "Produtos cadastrados automaticamente"),
            ("Para revisar", str(len(sem_categoria)), "Sem categoria clara ou classificados como Outros"),
            ("Categorias", str(produtos["categoria"].fillna("Sem categoria").nunique()), "Categorias em uso"),
        ])
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("Reclassificar produtos", use_container_width=True):
                atualizados = db.recategorizar_produtos_sem_categoria()
                st.success(f"{atualizados} produto(s) reclassificado(s).")
                rerun()
        with c2:
            st.caption("Use este botão para reaplicar as regras automáticas em produtos antigos que ficaram como Outros ou sem categoria.")

    if produtos.empty:
        st.info("Nenhum produto cadastrado ainda. Use **Adicionar Compra** para ler uma NF e criar os produtos automaticamente.")
        return

    # Filtros rápidos para revisão.
    if "filtro_produtos" not in st.session_state:
        st.session_state.filtro_produtos = "Todos"

    f1, f2, f3 = st.columns([1, 1, 3])
    if f1.button("Todos", use_container_width=True, type="primary" if st.session_state.filtro_produtos == "Todos" else "secondary"):
        st.session_state.filtro_produtos = "Todos"
        rerun()
    if f2.button("Para revisar", use_container_width=True, type="primary" if st.session_state.filtro_produtos == "Para revisar" else "secondary"):
        st.session_state.filtro_produtos = "Para revisar"
        rerun()
    busca = f3.text_input("Buscar produto", placeholder="Digite parte do nome, marca ou categoria", label_visibility="collapsed")

    df = produtos.copy()
    if st.session_state.filtro_produtos == "Para revisar":
        df = df[df["categoria"].fillna("").isin(["", "Outros"])]

    if busca.strip():
        b = busca.strip().upper()
        mask = (
            df["nome_padronizado"].fillna("").str.upper().str.contains(b, regex=False) |
            df["marca"].fillna("").str.upper().str.contains(b, regex=False) |
            df["categoria"].fillna("").str.upper().str.contains(b, regex=False)
        )
        df = df[mask]

    if st.session_state.filtro_produtos == "Para revisar":
        st.caption(f"{len(df)} produto(s) para revisar. Corrija a categoria pelo botão Editar.")
    else:
        st.caption(f"{len(df)} produto(s) exibido(s).")

    header_cols = st.columns([0.55, 2.4, 1.1, 1.35, 0.9, 0.9, 0.8])
    labels = ["ID", "Produto", "Marca", "Categoria", "Unidade", "Status", "Editar"]
    for col, label in zip(header_cols, labels):
        col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)

    for _, row in df.iterrows():
        produto_id = int(row["id"])
        cols = st.columns([0.55, 2.4, 1.1, 1.35, 0.9, 0.9, 0.8])
        cols[0].markdown(f"<div class='table-cell'>{produto_id}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div class='table-cell'>{row['nome_padronizado'] or '-'}</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div class='table-cell'>{row['marca'] or '-'}</div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div class='table-cell'>{row['categoria'] or 'Sem categoria'}</div>", unsafe_allow_html=True)
        unidade = row['unidade_padrao'] or '-'
        qtd = float(row['quantidade_padrao'] or 0)
        unidade_txt = f"{qtd:g} {unidade}" if qtd and qtd != 1 else unidade
        cols[4].markdown(f"<div class='table-cell'>{unidade_txt}</div>", unsafe_allow_html=True)
        status = "Ativo" if int(row.get("ativo", 1)) == 1 else "Inativo"
        cols[5].markdown(f"<div class='table-cell'>{status}</div>", unsafe_allow_html=True)
        if cols[6].button("Editar", key=f"editar_produto_{produto_id}", use_container_width=True):
            st.session_state.editar_produto_id = produto_id
            rerun()

    if st.session_state.get("editar_produto_id"):
        _abrir_modal_produto(int(st.session_state.editar_produto_id))

def _format_date_br(value):
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value or "")


def _render_detalhes_compra(compra_id):
    resumo = db.resumo_compra(compra_id)
    compra = resumo.get("compra")
    itens = resumo.get("itens")
    if not compra:
        st.warning("Não encontrei esta compra.")
        return

    kpi_grid([
        ("Data", _format_date_br(compra.get("data_compra")), "Data da compra"),
        ("Valor total", brl(float(compra.get("valor_total") or 0)), "Valor final da NFC-e"),
        ("Itens", str(resumo.get("qtd_itens") or 0), "Itens registrados"),
        ("Pagamento", compra.get("forma_pagamento") or "Não informado", brl(float(compra.get("valor_pago") or 0))),
    ])

    c1, c2 = st.columns(2)
    c1.markdown(f"**Supermercado**  \n{compra.get('mercado') or 'Sem supermercado'}")
    c2.markdown(f"**CNPJ**  \n{compra.get('mercado_cnpj') or 'Não informado'}")

    c3, c4 = st.columns(2)
    c3.markdown(f"**Origem**  \n{compra.get('origem') or '-'}")
    c4.markdown(f"**Status da leitura**  \n{compra.get('status_leitura') or '-'}")

    if compra.get("chave_nfce"):
        st.markdown(f"**Chave NFC-e**  \n`{compra.get('chave_nfce')}`")

    if compra.get("observacoes"):
        with st.expander("Observações"):
            st.write(compra.get("observacoes"))

    if compra.get("url_qrcode"):
        with st.expander("URL / conteúdo do QR Code"):
            st.text_area("URL / QR Code", value=compra.get("url_qrcode") or "", height=90, label_visibility="collapsed")

    st.markdown('<div class="section-title">Itens desta compra</div>', unsafe_allow_html=True)
    if itens is not None and not itens.empty:
        render_itens_compra_modal(itens)
        total_itens = float(resumo.get("total_itens") or 0)
        diferenca = float(resumo.get("diferenca") or 0)
        if abs(diferenca) <= 0.05:
            st.caption(f"Conferência: soma dos itens {brl(total_itens)} x valor da nota {brl(float(compra.get('valor_total') or 0))}.")
        else:
            st.warning(f"Soma dos itens {brl(total_itens)} x valor da nota {brl(float(compra.get('valor_total') or 0))}. Diferença: {brl(diferenca)}.")
    else:
        st.info("Esta compra ainda não possui itens registrados.")


def _abrir_modal_detalhes(compra_id):
    if hasattr(st, "dialog"):
        @st.dialog("Detalhes da Compra", width="large")
        def _dialog():
            _render_detalhes_compra(compra_id)
            if st.button("Fechar", use_container_width=True):
                st.session_state.pop("detalhe_compra_id", None)
                rerun()
        _dialog()
    else:
        st.markdown('<div class="section-title">Detalhes da Compra</div>', unsafe_allow_html=True)
        _render_detalhes_compra(compra_id)
        if st.button("Fechar detalhes", use_container_width=True):
            st.session_state.pop("detalhe_compra_id", None)
            rerun()



def page_compras():
    header()
    st.markdown('<div class="section-title">Compras</div>', unsafe_allow_html=True)

    if st.session_state.get("compra_registrada_id"):
        render_compra_registrada(int(st.session_state.compra_registrada_id))
        st.divider()

    compras = db.get_compras()
    if compras.empty:
        st.info("Nenhuma compra registrada ainda. Use o botão **Adicionar Compra** para começar.")
        return

    st.caption("Compras registradas em ordem decrescente pela data da compra.")
    st.markdown('<div class="mobile-list-title">Lista de compras</div>', unsafe_allow_html=True)

    for _, row in compras.iterrows():
        compra_id = int(row["id"])
        mercado = _safe_html(row.get("mercado") or "Sem supermercado")
        data_br = _format_date_br(row.get("data_compra"))
        valor = brl(float(row.get("valor_total") or 0))
        origem = _safe_html(row.get("origem") or "-")
        forma = _safe_html(row.get("forma_pagamento") or "-")
        itens_info = ""
        try:
            resumo = db.get_resumo_itens_compra(compra_id)
            itens_info = f"{int(resumo.get('qtd_itens') or 0)} itens"
        except Exception:
            itens_info = ""

        st.markdown(f"""
<div class="purchase-card">
  <div class="purchase-card-header">
    <div>
      <div class="purchase-market">{mercado}</div>
      <div class="purchase-meta">{data_br} · {forma}</div>
    </div>
    <div class="purchase-value">{valor}</div>
  </div>
  <div class="purchase-card-footer">
    <span>ID {compra_id}</span>
    <span>{origem}</span>
    <span>{itens_info}</span>
  </div>
</div>
""", unsafe_allow_html=True)
        if st.button("Ver detalhes", key=f"detalhes_compra_{compra_id}", use_container_width=True):
            st.session_state.detalhe_compra_id = compra_id
            rerun()
        st.markdown("<div class='mobile-card-spacer'></div>", unsafe_allow_html=True)

    if st.session_state.get("detalhe_compra_id"):
        _abrir_modal_detalhes(int(st.session_state.detalhe_compra_id))

def page_itens():
    header()
    st.markdown('<div class="section-title">Itens da Compra</div>', unsafe_allow_html=True)
    compras = db.get_compras()
    produtos = db.get_produtos()
    if compras.empty:
        st.warning("Cadastre uma compra antes de adicionar itens.")
        return
    compras["label"] = compras.apply(lambda r: f"{r['data_compra']} • {r['mercado'] or 'Sem mercado'} • {brl(r['valor_total'])} • ID {r['id']}", axis=1)
    compra_opts = dict(zip(compras["label"], compras["id"]))
    prod_opts = options_from_df(produtos, "nome_padronizado", "id", "Produto não padronizado")

    compra_sel = st.selectbox("Compra selecionada", list(compra_opts.keys()))
    compra_id = compra_opts[compra_sel]

    with st.form("novo_item"):
        desc = st.text_input("Descrição original da nota", placeholder="Ex.: LEITE ITALAC INT 1L")
        c1, c2, c3, c4 = st.columns(4)
        prod_sel = c1.selectbox("Produto padronizado", list(prod_opts.keys()))
        qtd = c2.number_input("Quantidade", min_value=0.0, value=1.0, step=0.1)
        unidade = c3.selectbox("Unidade", ["un", "kg", "g", "L", "ml", "pct", "cx", "fardo"])
        valor_unit = c4.number_input("Valor unitário", min_value=0.0, value=0.0, step=0.1, format="%.2f")
        c5, c6 = st.columns(2)
        desconto = c5.number_input("Desconto", min_value=0.0, value=0.0, step=0.1, format="%.2f")
        valor_total = c6.number_input("Valor total", min_value=0.0, value=0.0, step=0.1, format="%.2f", help="Se deixar zero, será calculado por quantidade x valor unitário - desconto.")
        if st.form_submit_button("Adicionar item"):
            total = None if valor_total == 0 else valor_total
            db.add_item(compra_id, desc, prod_opts[prod_sel], qtd, unidade, valor_unit, total, desconto)
            st.success("Item adicionado.")
            rerun()

    itens = db.get_itens(compra_id)
    st.dataframe(itens, use_container_width=True, hide_index=True)
    if not itens.empty:
        item_opts = {f"ID {r['id']} • {r['descricao_original'] or r['produto'] or 'Item'} • {brl(r['valor_total'])}": int(r['id']) for _, r in itens.iterrows()}
        with st.expander("Excluir item"):
            item_sel = st.selectbox("Item", list(item_opts.keys()))
            if st.button("Excluir item selecionado"):
                db.delete_item(item_opts[item_sel])
                st.success("Item excluído.")
                rerun()




def page_historico():
    header()
    st.markdown('<div class="section-title">Histórico de Preços</div>', unsafe_allow_html=True)
    itens = db.get_itens()
    if itens.empty:
        st.info("Adicione compras pela leitura da NFC-e para formar o histórico de preços.")
        return

    itens = itens.copy()
    itens["data_compra"] = pd.to_datetime(itens["data_compra"], errors="coerce")
    itens["produto_exibicao"] = itens["produto"].fillna(itens["descricao_original"]).fillna("Produto não identificado")
    itens["mercado_exibicao"] = itens["mercado"].fillna("Sem supermercado")
    itens["categoria_exibicao"] = itens["categoria"].fillna("Sem categoria")

    # 1) Produtos com maior variação registrada
    st.markdown('<div class="section-title">Produtos com maior variação registrada</div>', unsafe_allow_html=True)
    rows = []
    for prod, g in itens.dropna(subset=["produto_exibicao"]).groupby("produto_exibicao"):
        g = g.sort_values("data_compra")
        precos_validos = g[g["valor_unitario"].fillna(0) > 0]
        if len(precos_validos) >= 2:
            first = float(precos_validos.iloc[0]["valor_unitario"] or 0)
            last = float(precos_validos.iloc[-1]["valor_unitario"] or 0)
            var = ((last - first) / first * 100) if first else 0
            rows.append({
                "produto": prod,
                "primeiro_preco": first,
                "ultimo_preco": last,
                "variacao": var,
                "registros": len(precos_validos),
            })

    if rows:
        var_df = pd.DataFrame(rows).sort_values("variacao", ascending=False).head(10)
        header_cols = st.columns([3.0, 1.2, 1.2, 1.2, 0.9])
        labels = ["Produto", "Primeiro Preço", "Último Preço", "Variação", "Registros"]
        for col, label in zip(header_cols, labels):
            col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)
        for _, row in var_df.iterrows():
            cols = st.columns([3.0, 1.2, 1.2, 1.2, 0.9])
            cols[0].markdown(f"<div class='table-cell'>{row['produto']}</div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div class='table-cell'>{brl(float(row['primeiro_preco'] or 0))}</div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div class='table-cell'>{brl(float(row['ultimo_preco'] or 0))}</div>", unsafe_allow_html=True)
            cols[3].markdown(f"<div class='table-cell'>{pct(float(row['variacao'] or 0))}</div>", unsafe_allow_html=True)
            cols[4].markdown(f"<div class='table-cell'>{int(row['registros'])}</div>", unsafe_allow_html=True)
    else:
        st.caption("Ainda não há produtos com dois ou mais registros para calcular variação.")

    st.divider()

    # 2) Filtro de produtos
    produtos = sorted([p for p in itens["produto_exibicao"].dropna().unique()])
    produto_sel = st.selectbox("Filtrar produto", ["Todos"] + produtos)
    df = itens.copy()
    if produto_sel != "Todos":
        df = df[df["produto_exibicao"] == produto_sel]

    # 3) Gráfico de linha do produto filtrado
    st.markdown('<div class="section-title">Evolução do preço unitário</div>', unsafe_allow_html=True)
    if produto_sel == "Todos":
        st.info("Selecione um produto no filtro acima para visualizar o gráfico de evolução de preço.")
    else:
        df_chart = df.sort_values("data_compra").copy()
        df_chart = df_chart[df_chart["valor_unitario"].fillna(0) > 0]
        if df_chart.empty:
            st.caption("Não há dados suficientes para gerar o gráfico.")
        else:
            df_chart["preco_formatado"] = df_chart["valor_unitario"].apply(brl)
            df_chart["total_formatado"] = df_chart["valor_total"].apply(brl)
            df_chart["data_formatada"] = df_chart["data_compra"].apply(_format_date_br)
            fig = px.line(
                df_chart,
                x="data_compra",
                y="valor_unitario",
                markers=True,
                title=f"Preço unitário — {produto_sel}",
            )
            fig.update_traces(
                name=produto_sel,
                showlegend=False,
                mode="lines+markers",
                line=dict(width=3),
                marker=dict(size=9),
                customdata=df_chart[["preco_formatado", "mercado_exibicao", "quantidade", "unidade", "total_formatado", "data_formatada"]].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[5]}</b><br>"
                    "Preço unitário: <b>%{customdata[0]}</b><br>"
                    "Supermercado: %{customdata[1]}<br>"
                    "Quantidade: %{customdata[2]:g} %{customdata[3]}<br>"
                    "Valor total do item: %{customdata[4]}"
                    "<extra></extra>"
                ),
            )
            fig.update_layout(
                height=390,
                title=dict(font=dict(size=18), x=0.02),
                xaxis_title="Data da compra",
                yaxis_title="Valor unitário (R$)",
                margin=dict(l=10, r=10, t=58, b=10),
                hovermode="x unified",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            fig.update_yaxes(tickprefix="R$ ", tickformat=",.2f", gridcolor="#E2E8F0")
            fig.update_xaxes(tickformat="%d/%m/%Y", gridcolor="#F1F5F9")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            if len(df_chart) >= 2:
                first = float(df_chart.iloc[0]["valor_unitario"] or 0)
                last = float(df_chart.iloc[-1]["valor_unitario"] or 0)
                var = ((last - first) / first * 100) if first else 0
                st.info(f"Variação do primeiro para o último registro: {brl(first)} → {brl(last)} ({pct(var)}).")

    # 4) Histórico de preços
    st.markdown('<div class="section-title">Histórico de Preços</div>', unsafe_allow_html=True)
    df = df.sort_values(["data_compra", "id"], ascending=[False, False])
    if df.empty:
        st.info("Nenhum registro encontrado para o filtro selecionado.")
        return

    header_cols = st.columns([1.05, 2.7, 0.75, 0.65, 1.15, 1.15, 1.7, 1.25])
    labels = ["Data", "Produto", "Qtd.", "Un.", "Valor Unit.", "Valor Total", "Supermercado", "Categoria"]
    for col, label in zip(header_cols, labels):
        col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)

    table_height = 380 if len(df) > 8 else None
    table_container = st.container(height=table_height, border=False) if table_height else st.container()
    with table_container:
        for _, row in df.iterrows():
            cols = st.columns([1.05, 2.7, 0.75, 0.65, 1.15, 1.15, 1.7, 1.25])
            cols[0].markdown(f"<div class='table-cell'>{_format_date_br(row['data_compra'])}</div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div class='table-cell'>{row['produto_exibicao']}</div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div class='table-cell'>{float(row['quantidade'] or 0):g}</div>", unsafe_allow_html=True)
            cols[3].markdown(f"<div class='table-cell'>{row['unidade'] or '-'}</div>", unsafe_allow_html=True)
            cols[4].markdown(f"<div class='table-cell'>{brl(float(row['valor_unitario'] or 0))}</div>", unsafe_allow_html=True)
            cols[5].markdown(f"<div class='table-cell'>{brl(float(row['valor_total'] or 0))}</div>", unsafe_allow_html=True)
            cols[6].markdown(f"<div class='table-cell'>{row['mercado_exibicao']}</div>", unsafe_allow_html=True)
            cols[7].markdown(f"<div class='table-cell'>{row['categoria_exibicao']}</div>", unsafe_allow_html=True)

def make_excel():
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        db.get_compras().to_excel(writer, sheet_name="Compras", index=False)
        db.get_itens().to_excel(writer, sheet_name="Itens", index=False)
        db.get_produtos(ativos=False).to_excel(writer, sheet_name="Produtos", index=False)
        db.get_mercados(ativos=False).to_excel(writer, sheet_name="Mercados", index=False)
        db.get_categorias(ativas=False).to_excel(writer, sheet_name="Categorias", index=False)
    output.seek(0)
    return output


def page_exportar():
    header()
    st.markdown('<div class="section-title">Exportar Excel</div>', unsafe_allow_html=True)
    st.write("Baixe uma planilha com compras, itens, produtos, mercados e categorias.")
    excel = make_excel()
    st.download_button(
        "Baixar Gestão de Compras.xlsx",
        data=excel,
        file_name=f"gestao_compras_export_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def main():
    sidebar()
    page = st.session_state.page
    if page == "Dashboard":
        page_dashboard()
    elif page == "Adicionar Compra":
        page_capturar_nf()
    elif page == "Compras":
        page_compras()
    elif page == "Produtos":
        page_produtos()
    elif page == "Mercados":
        page_mercados()
    elif page == "Categorias":
        page_categorias()
    elif page == "Histórico de Preços":
        page_historico()
    elif page == "Exportar Excel":
        page_exportar()


if __name__ == "__main__":
    main()
