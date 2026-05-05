"""
Helpers comuns aos parsers.

Faz HTTP request com user-agent decente (importante para evitar 403),
parsa HTML, e tem helpers de regex/soup para extrair campos comuns.
"""

import re
import json
from typing import Optional

import requests
from bs4 import BeautifulSoup


HEADERS_DEFAULT = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
}


def get(url: str, headers: Optional[dict] = None, timeout: int = 15) -> str:
    """
    Fetch URL, devolve HTML como string.

    Estratégia em duas tentativas:
    1. requests normal (rápido, suficiente para Remax/Imovirtual/Casa Sapo)
    2. cloudscraper como fallback (tenta resolver desafios Cloudflare,
       importante para Idealista)

    Lança exceção se ambas falharem.
    """
    h = {**HEADERS_DEFAULT, **(headers or {})}

    # Tentativa 1: requests normal
    try:
        r = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        # Se conseguiu mas conteúdo é challenge Cloudflare, tenta cloudscraper
        if "Just a moment" in r.text or "challenge-platform" in r.text:
            raise requests.HTTPError("Cloudflare challenge detected")
        return r.text
    except (requests.HTTPError, requests.ConnectionError, requests.Timeout):
        pass

    # Tentativa 2: cloudscraper
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        r = scraper.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return r.text
    except ImportError:
        # cloudscraper não instalado: re-lança o erro original
        raise requests.HTTPError("Site exige resolução Cloudflare e cloudscraper não está instalado")
    except Exception as e:
        raise requests.HTTPError(f"Cloudflare bypass falhou: {type(e).__name__}: {e}")


def soup(html: str) -> BeautifulSoup:
    """Parsa HTML em BeautifulSoup com lxml."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def extrair_jsonld(html: str) -> list[dict]:
    """
    Extrai todos os blocos JSON-LD (script type=application/ld+json) do HTML.
    Útil porque muitos sites imobiliários usam schema.org/Product ou
    schema.org/RealEstateListing.
    """
    s = soup(html)
    blocos = []
    for tag in s.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            if isinstance(data, list):
                blocos.extend(data)
            else:
                blocos.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return blocos


def extrair_meta(html: str) -> dict:
    """Extrai meta tags relevantes (og:title, og:description, etc.)."""
    s = soup(html)
    out = {}
    for tag in s.find_all("meta"):
        prop = tag.get("property") or tag.get("name") or ""
        content = tag.get("content")
        if prop and content:
            out[prop.lower()] = content
    return out


# ---------------------------------------------------------------------------
# Helpers de extração
# ---------------------------------------------------------------------------

def parse_numero(texto: str) -> Optional[float]:
    """
    Extrai um número de uma string PT (vírgula como decimal, ponto como milhar).
    'EUR 250.000', '250 000', '250,00 m²' → 250000, 250000, 250
    """
    if not texto:
        return None
    # Tira tudo excepto dígitos, vírgulas, pontos e sinal
    s = re.sub(r"[^\d,.\-]", "", str(texto))
    if not s:
        return None
    # Em PT, vírgula é decimal, ponto é milhar. Mas em alguns sites é o inverso.
    # Estratégia: se tem ambos, o último é decimal.
    has_c = "," in s
    has_d = "." in s
    if has_c and has_d:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_c:
        # Se só tem vírgula: pode ser decimal ou milhar.
        # Heurística: se tem 3 dígitos depois → milhar; senão → decimal.
        partes = s.split(",")
        if len(partes) > 1 and len(partes[-1]) == 3:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif has_d:
        partes = s.split(".")
        if len(partes) > 1 and len(partes[-1]) == 3:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def detectar_tipologia(texto: str) -> Optional[str]:
    """T0, T1, T2... a partir de texto livre."""
    if not texto:
        return None
    m = re.search(r"\bT(\d+)\b", texto, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return f"T{n}" if n < 5 else "T5+"
    return None


def detectar_area(texto: str) -> Optional[float]:
    """Extrai m² de texto. '77 m²', '77,5 m2', '77 metros' → 77, 77.5, 77."""
    if not texto:
        return None
    m = re.search(r"([\d\.,]+)\s*(?:m²|m2|metros\s*quadrados)", texto, re.IGNORECASE)
    if m:
        return parse_numero(m.group(1))
    return None
