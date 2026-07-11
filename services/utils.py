import re
import unicodedata
from datetime import datetime


def brl(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0
    return f"{valor:+.1f}%".replace(".", ",")


def normalizar_texto(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")
    texto = texto.upper()
    texto = re.sub(r"[^A-Z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def mes_atual():
    return datetime.today().strftime("%Y-%m")
