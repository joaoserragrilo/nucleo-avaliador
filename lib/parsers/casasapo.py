"""
Parser Casa Sapo.

Casa Sapo é menos estruturado. Faz best-effort via JSON-LD + meta + regex.
"""

import re
from . import base


def parse(url: str) -> dict:
    out = {
        "fonte": "casasapo",
        "url": url,
        "preco": None,
        "tipologia": None,
        "area_m2": None,
        "localizacao": None,
        "tipo_imovel": None,
        "estado_conservacao": None,
        "descricao": None,
        "erros": [],
    }

    try:
        html = base.get(url)
    except Exception as e:
        out["erros"].append(f"Erro fetch: {type(e).__name__}: {e}")
        return out

    for b in base.extrair_jsonld(html):
        if not isinstance(b, dict):
            continue
        tipo = str(b.get("@type", ""))
        if tipo in ("Product", "RealEstateListing", "Apartment", "House"):
            offers = b.get("offers", {})
            if isinstance(offers, dict):
                if (p := offers.get("price")):
                    out["preco"] = base.parse_numero(p)

    metas = base.extrair_meta(html)
    title = metas.get("og:title", "")
    desc = metas.get("og:description", "")

    if not out["tipologia"]:
        out["tipologia"] = base.detectar_tipologia(title + " " + desc)
    if not out["area_m2"]:
        out["area_m2"] = base.detectar_area(title + " " + desc)
    if not out["preco"]:
        m = re.search(r"([\d\.\s]+)\s*€", title + " " + desc)
        if m:
            out["preco"] = base.parse_numero(m.group(1))

    if not out["tipo_imovel"]:
        tl = (title + " " + desc).lower()
        if "moradia" in tl:
            out["tipo_imovel"] = "Moradia"
        elif "apartamento" in tl:
            out["tipo_imovel"] = "Apartamento"
        elif "terreno" in tl:
            out["tipo_imovel"] = "Terreno"

    out["descricao"] = desc[:500] if desc else None

    faltam = [k for k in ("preco", "tipologia", "area_m2") if not out.get(k)]
    if faltam:
        out["erros"].append(f"Campos não detectados: {faltam}.")

    return out
