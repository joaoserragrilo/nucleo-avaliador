"""
Parsers de anúncios imobiliários.

Há três caminhos:

1. **parse_url(url)** — tenta extrair dados duma URL. Para sites conhecidos
   (Idealista, Remax, Imovirtual, Casa Sapo) usa parser dedicado. Para
   qualquer outro site, usa parser genérico (JSON-LD + meta + microdata +
   regex). Funciona em ~80% dos sites com SEO decente.

2. **parse_texto(texto, url_origem="")** — recebe texto plano (output de
   Ctrl+A na página dum anúncio) e extrai os mesmos campos. **Funciona em
   QUALQUER site** porque trabalha sobre texto, sem depender de scraping
   HTTP. É o caminho mais robusto contra anti-bot (Cloudflare).

3. Os parsers individuais ficam acessíveis para testes/debug.

Resultado: dict com campos parciais (None quando não foi possível extrair):
    {
        "fonte": "generico" | "idealista" | "remax" | "texto" | ...,
        "url": "...",
        "preco": 250000,
        "tipologia": "T2",
        "area_m2": 77,
        "localizacao": "Lisboa - Olivais",
        "tipo_imovel": "Apartamento",
        "estado_conservacao": "Bom",
        "descricao": "...",
        "erros": [],
    }
"""

from urllib.parse import urlparse
from typing import Optional

from . import idealista
from . import remax
from . import imovirtual
from . import casasapo
from . import generico
from . import texto


# Sites com parser dedicado (mais preciso quando funcionam)
SITES_DEDICADOS = {
    "idealista.pt": idealista,
    "idealista.com": idealista,
    "remax.pt": remax,
    "imovirtual.com": imovirtual,
    "casasapo.pt": casasapo,
}


def detectar_site(url: str) -> Optional[str]:
    """Devolve a chave de SITES_DEDICADOS ou None."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return None
    for chave in SITES_DEDICADOS:
        if chave in host:
            return chave
    return None


def parse_url(url: str) -> dict:
    """
    Parsa um URL de anúncio. Estratégia:
    1. Se for site conhecido, usa parser dedicado.
    2. Se falhar (campos críticos vazios) ou não for conhecido, usa genérico.

    Devolve sempre um dict (com 'erros' não vazio se nada funcionar).
    """
    site = detectar_site(url)
    if site:
        try:
            r = SITES_DEDICADOS[site].parse(url)
            # Se conseguiu extrair preço E tipologia E área, dá-se por bom
            if r.get("preco") and r.get("tipologia") and r.get("area_m2"):
                return r
            # Senão tenta genérico em paralelo e merge com o que o dedicado tem
            try:
                gen = generico.parse(url)
                # Merge: o dedicado ganha onde tem; preenche o resto com genérico
                merged = dict(r)
                for k, v in gen.items():
                    if k == "erros":
                        merged["erros"] = (merged.get("erros") or []) + (v or [])
                    elif not merged.get(k):
                        merged[k] = v
                return merged
            except Exception:
                return r
        except Exception as e:
            return {
                "fonte": site, "url": url,
                "erros": [f"Falha no parser dedicado: {type(e).__name__}: {e}"],
            }

    # Site desconhecido → parser genérico
    try:
        return generico.parse(url)
    except Exception as e:
        return {
            "fonte": "desconhecido", "url": url,
            "erros": [f"Parser genérico falhou: {type(e).__name__}: {e}"],
        }


def parse_texto(texto_anuncio: str, url_origem: str = "") -> dict:
    """
    Parsa texto livre dum anúncio (output de Ctrl+A na página).

    Funciona para QUALQUER site — não depende de scraping HTTP. É o caminho
    mais resiliente contra anti-bot.
    """
    return texto.parse(texto_anuncio, url_origem)
