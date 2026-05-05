"""
Parser Imovirtual.

Imovirtual usa Next.js. Os dados estruturados estão em JSON-LD ou no
Next.js __NEXT_DATA__ (script id="__NEXT_DATA__").
"""

import json
import re
from . import base


def parse(url: str) -> dict:
    out = {
        "fonte": "imovirtual",
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

    # 1. JSON-LD
    for b in base.extrair_jsonld(html):
        if not isinstance(b, dict):
            continue
        if b.get("@type") in ("Product", "RealEstateListing", "Apartment", "House"):
            offers = b.get("offers", {})
            if isinstance(offers, dict):
                if (p := offers.get("price")):
                    out["preco"] = base.parse_numero(p)
            addr = b.get("address", {})
            if isinstance(addr, dict):
                parts = [addr.get("addressLocality"), addr.get("addressRegion")]
                out["localizacao"] = ", ".join(p for p in parts if p)

    # 2. __NEXT_DATA__
    s = base.soup(html)
    next_tag = s.find("script", id="__NEXT_DATA__")
    if next_tag and next_tag.string:
        try:
            data = json.loads(next_tag.string)
            # Procurar campos típicos
            ad = data.get("props", {}).get("pageProps", {}).get("ad", {})
            if ad:
                if not out["preco"]:
                    out["preco"] = base.parse_numero(ad.get("price", {}).get("value"))
                if not out["area_m2"]:
                    out["area_m2"] = base.parse_numero(ad.get("area"))
                if not out["tipologia"]:
                    rooms = ad.get("rooms_num") or ad.get("roomsCount")
                    if rooms:
                        out["tipologia"] = f"T{rooms}" if int(rooms) < 5 else "T5+"
                loc = ad.get("location", {})
                if isinstance(loc, dict) and not out["localizacao"]:
                    out["localizacao"] = loc.get("address") or loc.get("city")
                if not out["descricao"]:
                    out["descricao"] = (ad.get("description") or "")[:500]
        except Exception:
            pass

    # 3. Fallback via meta
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

    if not out["descricao"]:
        out["descricao"] = desc[:500] if desc else None

    faltam = [k for k in ("preco", "tipologia", "area_m2") if not out.get(k)]
    if faltam:
        out["erros"].append(f"Campos não detectados: {faltam}.")

    return out
