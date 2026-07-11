import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from PIL import Image, ImageOps
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def extrair_chave_nfce(texto: str) -> str:
    """Extrai uma chave NFC-e/NF-e de 44 dígitos de URL ou texto lido do QR Code."""
    if not texto:
        return ""

    try:
        parsed = urlparse(texto)
        params = parse_qs(parsed.query)
        for key in ("chNFe", "chave", "chaveNFe", "chNFeSat"):
            if key in params and params[key]:
                digits = re.sub(r"\D", "", params[key][0])
                if len(digits) >= 44:
                    return digits[:44]
        if "p" in params and params["p"]:
            digits = re.sub(r"\D", "", params["p"][0].split("|")[0])
            if len(digits) >= 44:
                return digits[:44]
    except Exception:
        pass

    digits = re.sub(r"\D", "", texto)
    match = re.search(r"\d{44}", digits)
    return match.group(0) if match else ""


def _decode_with_opencv(arr):
    import cv2

    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(arr)
    if data:
        return data.strip()
    return ""


def _try_pyzbar(pil_image):
    """Fallback opcional. Só usa pyzbar se estiver instalado no ambiente."""
    try:
        from pyzbar.pyzbar import decode
    except Exception:
        return ""
    try:
        decoded = decode(pil_image)
        if decoded:
            return decoded[0].data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
    return ""


def _preprocess_variants(arr):
    import cv2

    variants = []
    rgb = arr
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    variants.append(rgb)
    variants.append(gray)

    # Aumenta a imagem para QR pequeno/foto distante
    h, w = gray.shape[:2]
    for scale in (1.5, 2.0, 3.0):
        if max(h, w) * scale <= 5000:
            up_rgb = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            up_gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            variants.extend([up_rgb, up_gray])

    # Contraste e binarização ajudam em papel térmico fraco
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    variants.append(eq)

    sharp = cv2.filter2D(eq, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))
    variants.append(sharp)

    for src in (gray, eq, sharp):
        try:
            variants.append(cv2.threshold(src, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])
            variants.append(cv2.adaptiveThreshold(src, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2))
        except Exception:
            pass

    # Rotações para fotos tiradas de lado
    rotated = []
    for v in variants:
        rotated.append(v)
        rotated.append(cv2.rotate(v, cv2.ROTATE_90_CLOCKWISE))
        rotated.append(cv2.rotate(v, cv2.ROTATE_180))
        rotated.append(cv2.rotate(v, cv2.ROTATE_90_COUNTERCLOCKWISE))
    return rotated


def detectar_qrcode_em_imagem(uploaded_file):
    """Retorna o texto do QR Code encontrado em uma imagem.

    v0.2.1: tenta várias estratégias leves de pré-processamento para notas
    com papel térmico, baixa luz, QR pequeno ou foto um pouco distante.
    """
    try:
        import cv2  # noqa: F401
    except Exception as exc:
        raise RuntimeError("Biblioteca opencv-python-headless não instalada. Rode: pip install -r requirements.txt") from exc

    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image).convert("RGB")

    # Fallback opcional com pyzbar, se o usuário instalar no futuro.
    data = _try_pyzbar(image)
    if data:
        return data

    arr = np.array(image)
    for variant in _preprocess_variants(arr):
        try:
            data = _decode_with_opencv(variant)
            if data:
                return data
        except Exception:
            continue

    return ""


def salvar_imagem_nf(uploaded_file, prefixo="nf") -> str:
    """Salva foto da nota/QR no diretório uploads e retorna o caminho relativo."""
    UPLOADS_DIR.mkdir(exist_ok=True)
    suffix = Path(getattr(uploaded_file, "name", "imagem.jpg")).suffix.lower() or ".jpg"
    if suffix not in [".jpg", ".jpeg", ".png", ".webp"]:
        suffix = ".jpg"
    nome = f"{prefixo}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
    caminho = UPLOADS_DIR / nome
    data = uploaded_file.getvalue()
    caminho.write_bytes(data)
    return str(caminho.relative_to(BASE_DIR))
