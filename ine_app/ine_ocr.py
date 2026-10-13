# Lógica de OCR tomada de extraer_ine.py (sin base de datos ni archivos).
import os
import re

import pytesseract
from PIL import Image, ImageOps

IDIOMA_OCR = os.environ.get("OCR_LANG", "spa")  # "eng" si no tienes el idioma español instalado

A_LETRA = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}
A_NUMERO = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
            "Z": "2", "S": "5", "B": "8", "G": "6"}
REGEX_CURP = re.compile(r"[A-Z]{4}\d{6}[HMX][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d")


def preparar_imagen(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    if img.width < 1600:
        f = 1600 / img.width
        img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
    if img.width > 2000:
        f = 2000 / img.width
        img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
    return img


def ocr(img: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(preparar_imagen(img), lang=IDIOMA_OCR, config="--psm 6")
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError("Tesseract no está instalado en el servidor.")
    except pytesseract.TesseractError as e:
        raise RuntimeError(f"Falló el OCR (¿está instalado el idioma '{IDIOMA_OCR}'?): {e}")


def corregir_curp(c: str) -> str:
    if len(c) != 18:
        return c
    v = list(c)
    for i in range(18):
        pos = i + 1
        if pos <= 4 or 11 <= pos <= 16:
            v[i] = A_LETRA.get(v[i], v[i])
        elif 5 <= pos <= 10 or pos == 18:
            v[i] = A_NUMERO.get(v[i], v[i])
    return "".join(v)


def extraer_curp(texto: str) -> str:
    m = REGEX_CURP.search(texto)
    if m:
        return m.group(0)
    limpio = re.sub(r"[^A-Z0-9\n ]", "", texto)
    for tok in re.finditer(r"[A-Z0-9]{18}", limpio):
        c = corregir_curp(tok.group(0))
        if REGEX_CURP.fullmatch(c):
            return c
    m = re.search(r"CURP\s*[:\-]?\s*([A-Z0-9]{18})", texto)
    if m:
        return corregir_curp(m.group(1))
    return ""


def extraer_vigencia(texto: str) -> str:
    m = re.search(r"VIGENCIA\s*[:\-]?\s*((?:20\d{2}[\s\-]*)+)", texto)
    if m:
        anios = re.findall(r"20\d{2}", m.group(1))
        if anios:
            return anios[-1]
    m = re.search(r"VIGENCIA[^\d]{0,15}(20\d{2})", texto)
    return m.group(1) if m else ""


def extraer_nombre(lineas: list[str]) -> str:
    idx = next((i for i, l in enumerate(lineas) if re.match(r"^\s*NOMBRE\b", l)), None)
    if idx is None:
        return ""
    candidatas: list[str] = []
    resto = re.sub(r"^\s*NOMBRE\b[:\s]*", "", lineas[idx]).strip()
    if resto:
        candidatas.append(resto)
    for l in lineas[idx + 1:]:
        if re.search(r"DOMICILIO|CALLE|COL\.?\s|FRACC|CLAVE|CURP|SEXO|FECHA|NACIMIENTO", l):
            break
        limpia = re.sub(r"[^A-ZÁÉÍÓÚÜÑ ]", "", l).strip()
        if len(limpia) >= 2:
            candidatas.append(limpia)
        if len(candidatas) == 3:
            break
    if not candidatas:
        return ""
    if len(candidatas) >= 3:
        paterno, materno, nombres = candidatas[0], candidatas[1], " ".join(candidatas[2:])
        return " ".join(f"{nombres} {paterno} {materno}".split())
    return " ".join(" ".join(candidatas).split())


def extraer_datos(img: Image.Image) -> dict:
    texto = ocr(img).upper()
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    return {
        "nombre": extraer_nombre(lineas),
        "curp": extraer_curp(texto),
        "vigencia": extraer_vigencia(texto),
    }
