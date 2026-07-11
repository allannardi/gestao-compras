import re
from datetime import date, datetime
from urllib.parse import urlparse


def _br_money_to_float(texto):
    """Converte valores monetários brasileiros/decimais em float.

    Aceita exemplos comuns encontrados em NFC-e:
    - R$ 1.234,56
    - 125,90
    - 125,9
    - 7.45
    - 7
    """
    if texto is None:
        return 0.0
    s = str(texto).strip()
    m = re.search(r"-?\d{1,3}(?:\.\d{3})*,\d{1,2}|-?\d+,\d{1,2}|-?\d+\.\d{1,4}|-?\d+", s)
    if not m:
        return 0.0
    v = m.group(0)
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except Exception:
        return 0.0


def _br_qty_to_float(texto):
    if texto is None:
        return 0.0
    s = str(texto).strip().replace(".", "").replace(",", ".") if "," in str(texto) else str(texto).strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    try:
        return float(m.group(0))
    except Exception:
        return 0.0


def _clean_text(texto):
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def _parse_date_any(texto):
    if not texto:
        return ""
    for pattern in (r"(\d{2}/\d{2}/\d{4})", r"(\d{4}-\d{2}-\d{2})"):
        m = re.search(pattern, texto)
        if m:
            val = m.group(1)
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val, fmt).date().isoformat()
                except Exception:
                    pass
    return ""


def _url_valida(texto):
    try:
        u = urlparse(texto)
        return u.scheme in ("http", "https") and bool(u.netloc)
    except Exception:
        return False


def consultar_nfce_por_qrcode(qr_texto: str, timeout: int = 8) -> dict:
    """Tenta consultar a página pública da NFC-e e extrair dados básicos.

    Funciona melhor quando o QR Code aponta para páginas que retornam HTML público
    com os itens, como muitos layouts de NFC-e. Se a SEFAZ exigir captcha, bloquear
    automação ou alterar o layout, retorna uma prévia parcial para cadastro pendente.
    """
    resultado = {
        "ok": False,
        "mensagem": "Ainda não consultei a NFC-e.",
        "mercado_nome": "",
        "cnpj": "",
        "data_compra": "",
        "valor_total": 0.0,
        "itens": [],
        "forma_pagamento": "",
        "valor_pago": 0.0,
        "html_obtido": False,
    }

    if not qr_texto or not _url_valida(qr_texto):
        resultado["mensagem"] = "QR Code/chave lido, mas não é uma URL pública de consulta. Vou criar a compra para conferência manual."
        return resultado

    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        resultado["mensagem"] = "Dependências de consulta não instaladas. Rode: pip install -r requirements.txt"
        return resultado

    try:
        resp = requests.get(
            qr_texto,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome Safari",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
        )
        resp.raise_for_status()
        # Alguns portais antigos vêm em latin-1/windows-1252.
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
        resultado["html_obtido"] = True
    except Exception as exc:
        resultado["mensagem"] = f"Não consegui consultar a página da NFC-e automaticamente ({exc}). Vou criar a compra para conferência manual."
        return resultado

    try:
        soup = BeautifulSoup(html, "html.parser")
        texto_total_pagina = _clean_text(soup.get_text(" "))

        # Mercado: em muitos layouts de NFC-e/SP fica em .txtTopo.
        topo = [_clean_text(x.get_text(" ")) for x in soup.select(".txtTopo")]
        topo = [t for t in topo if t]
        if topo:
            # Normalmente o primeiro txtTopo é a razão/nome do estabelecimento.
            resultado["mercado_nome"] = topo[0][:120]
        else:
            title = soup.find("title")
            if title:
                resultado["mercado_nome"] = _clean_text(title.get_text(" "))[:120]

        cnpj_match = re.search(r"CNPJ\s*:?\s*(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", texto_total_pagina, re.I)
        if cnpj_match:
            resultado["cnpj"] = cnpj_match.group(1)
        else:
            # fallback para CNPJ impresso sem rótulo
            cnpj_digits = re.search(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", texto_total_pagina)
            if cnpj_digits:
                resultado["cnpj"] = cnpj_digits.group(0)

        resultado["data_compra"] = _parse_date_any(texto_total_pagina)

        # Valor total: tenta primeiro pelos rótulos do rodapé da NFC-e.
        # No layout de SP o campo costuma aparecer como "Valor a pagar R$: 125,94".
        # O ":" após R$ era o motivo de cair no fallback por soma dos itens.
        money_re = r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{1,2}|[0-9]+,[0-9]{1,2}|[0-9]+\.[0-9]{1,4})"
        for pat in (
            rf"Valor\s+a\s+pagar\s*R?\$?\s*:?\s*{money_re}",
            rf"Valor\s+total\s*R?\$?\s*:?\s*{money_re}",
            rf"Valor\s+Pago\s*R?\$?\s*:?\s*{money_re}",
            rf"TOTAL\s*R?\$?\s*:?\s*{money_re}",
            rf"Total\s*R?\$?\s*:?\s*{money_re}",
        ):
            m = re.search(pat, texto_total_pagina, re.I)
            if m:
                resultado["valor_total"] = round(_br_money_to_float(m.group(1)), 2)
                break

        # Forma de pagamento e valor pago.
        # Exemplo do portal SP: "Forma de pagamento: Valor pago R$: Cartão de Crédito 125,94 Troco NaN".
        forma = ""
        valor_pago = 0.0
        m_pgto = re.search(
            rf"Forma\s+de\s+pagamento\s*:?\s*(?:Valor\s+pago\s*R?\$?\s*:?\s*)?(.+?)\s+{money_re}(?=\s+Troco|\s+Informação|\s+Informacao|$)",
            texto_total_pagina,
            re.I,
        )
        if m_pgto:
            forma = _clean_text(m_pgto.group(1))[:80]
            valor_pago = round(_br_money_to_float(m_pgto.group(2)), 2)
        else:
            # Fallback por HTML: procura textos próximos de "Forma de pagamento".
            for tag in soup.find_all(string=re.compile(r"Forma\s+de\s+pagamento", re.I)):
                parent = tag.parent
                bloco = _clean_text(parent.get_text(" ") if parent else str(tag))
                sib = parent.find_next_sibling() if parent else None
                if sib:
                    bloco = _clean_text(bloco + " " + sib.get_text(" "))
                m2 = re.search(rf"(Cartão de Crédito|Cartao de Credito|Cartão de Débito|Cartao de Debito|Dinheiro|PIX|Vale|Voucher|Crédito|Credito|Débito|Debito)\s+{money_re}", bloco, re.I)
                if m2:
                    forma = _clean_text(m2.group(1))[:80]
                    valor_pago = round(_br_money_to_float(m2.group(2)), 2)
                    break
        resultado["forma_pagamento"] = forma
        resultado["valor_pago"] = valor_pago
        if not resultado.get("valor_total") and valor_pago:
            resultado["valor_total"] = valor_pago

        itens = []
        blocos = soup.find_all(id=re.compile(r"^Item", re.I))
        if not blocos:
            # Alguns layouts usam li/div sem ID claro, mas com classes dos campos.
            possiveis = soup.select("div:has(.txtTit), li:has(.txtTit)")
            blocos = possiveis or []

        for bloco in blocos:
            desc_el = bloco.select_one(".txtTit") or bloco.select_one(".txtTit2")
            desc = _clean_text(desc_el.get_text(" ")) if desc_el else ""
            if not desc:
                continue
            qtd_txt = _clean_text((bloco.select_one(".Rqtd") or {}).get_text(" ") if bloco.select_one(".Rqtd") else "")
            un_txt = _clean_text((bloco.select_one(".RUN") or {}).get_text(" ") if bloco.select_one(".RUN") else "")
            unit_txt = _clean_text((bloco.select_one(".RvlUnit") or {}).get_text(" ") if bloco.select_one(".RvlUnit") else "")
            total_txt = _clean_text((bloco.select_one(".valor") or {}).get_text(" ") if bloco.select_one(".valor") else "")

            qtd = _br_qty_to_float(qtd_txt)
            unidade = "un"
            un_m = re.search(r"UN\s*:?\s*([A-ZÇ0-9]+)", un_txt, re.I)
            if un_m:
                unidade = un_m.group(1).lower()
            valor_unit = _br_money_to_float(unit_txt)
            valor_total = _br_money_to_float(total_txt)
            if not valor_unit and qtd and valor_total:
                valor_unit = valor_total / qtd
            if not valor_total and qtd and valor_unit:
                valor_total = qtd * valor_unit

            itens.append({
                "descricao_original": desc,
                "quantidade": qtd or 1.0,
                "unidade": unidade,
                "valor_unitario": round(valor_unit, 4),
                "valor_total": round(valor_total, 2),
            })

        resultado["itens"] = itens

        # Fallback importante: se a página retornou os itens, mas o campo de total
        # não veio em um padrão fácil de capturar, calcula o total pela soma dos itens.
        if not resultado.get("valor_total") and itens:
            total_itens = sum(float(item.get("valor_total") or 0) for item in itens)
            resultado["valor_total"] = round(total_itens, 2)

        if itens or resultado["valor_total"] or resultado["mercado_nome"]:
            resultado["ok"] = True
            resultado["mensagem"] = "Dados encontrados automaticamente. Confira e clique em registrar."
        else:
            resultado["mensagem"] = "Consegui abrir a página da NFC-e, mas não encontrei os dados no layout retornado. Pode haver captcha ou mudança de layout."

        return resultado
    except Exception as exc:
        resultado["mensagem"] = f"A página foi aberta, mas não consegui interpretar os dados ({exc})."
        return resultado
