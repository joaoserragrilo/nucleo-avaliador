"""
Parser genérico — funciona para qualquer site de imobiliária com SEO decente
(Era, Century 21, Decisões e Soluções, Realtv, Maxfinance, sites próprios
de agências, etc.).

Estratégia em camadas:
1. JSON-LD (schema.org/Product, RealEstateListing, Apartment, House) — standard
   de SEO, ~80% dos sites têm.
2. Open Graph meta tags (og:title, og:description, og:price:amount).
3. Microdata HTML (itemprop="price", "floorSize", etc.).
4. Heurísticas regex no HTML body.

Quando nenhuma camada extrai um campo, fica em None e aparece nos erros para
o user preencher manualmente.
"""

import re
import json
from typing import Optional

from . import base


def _extrair_de_jsonld(html: str, out: dict):
    """JSON-LD: schema.org/Product, RealEstateListing, etc."""
    for b in base.extrair_jsonld(html):
        if not isinstance(b, dict):
            continue
        # @type pode ser string ou lista
        tipo = b.get("@type", "")
        if isinstance(tipo, list):
            tipo_str = " ".join(str(t) for t in tipo)
        else:
            tipo_str = str(tipo)

        relevante = any(t in tipo_str for t in [
            "Product", "Residence", "Apartment", "House",
            "SingleFamilyResidence", "RealEstateListing", "Place", "Accommodation"
        ])
        if not relevante:
            continue

        # Preço (offers)
        if not out["preco"]:
            offers = b.get("offers", {})
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict):
                p = offers.get("price") or offers.get("priceSpecification", {}).get("price")
                if p:
                    out["preco"] = base.parse_numero(p)

        # Localização (address)
        if not out["localizacao"]:
            addr = b.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality"),
                    addr.get("addressRegion"),
                ]
                loc = ", ".join(p for p in parts if p)
                if loc:
                    out["localizacao"] = loc
            elif isinstance(addr, str):
                out["localizacao"] = addr

        # Tipo de imóvel
        if not out["tipo_imovel"]:
            if "Apartment" in tipo_str:
                out["tipo_imovel"] = "Apartamento"
            elif "House" in tipo_str or "SingleFamily" in tipo_str:
                out["tipo_imovel"] = "Moradia"

        # Área
        if not out["area_m2"]:
            fs = b.get("floorSize")
            if isinstance(fs, dict):
                out["area_m2"] = base.parse_numero(fs.get("value"))
            elif fs:
                out["area_m2"] = base.parse_numero(fs)

        # Tipologia (numberOfRooms)
        if not out["tipologia"]:
            n = b.get("numberOfRooms") or b.get("numberOfBedrooms")
            if isinstance(n, dict):
                n = n.get("value")
            if n:
                try:
                    n = int(float(n))
                    out["tipologia"] = f"T{n}" if n < 5 else "T5+"
                except (ValueError, TypeError):
                    pass

        # Descrição
        if not out["descricao"]:
            desc = b.get("description")
            if desc:
                out["descricao"] = str(desc)[:500]


def _extrair_de_meta(html: str, out: dict):
    """Open Graph + meta tags standard."""
    metas = base.extrair_meta(html)

    # OG title costuma ter "Apartamento T2 em Olivais por 250.000€"
    title = metas.get("og:title", "") or metas.get("title", "")
    desc = metas.get("og:description", "") or metas.get("description", "")
    full = f"{title} {desc}"

    if not out["preco"]:
        # og:price:amount é standard
        p = metas.get("og:price:amount") or metas.get("product:price:amount")
        if p:
            out["preco"] = base.parse_numero(p)
        else:
            m = re.search(r"([\d][\d\.\s,]{2,12}[\d])\s*(?:€|EUR|euros?)", full, re.IGNORECASE)
            if m:
                v = base.parse_numero(m.group(1))
                if v and 30_000 < v < 10_000_000:
                    out["preco"] = v

    if not out["tipologia"]:
        out["tipologia"] = base.detectar_tipologia(full)

    if not out["area_m2"]:
        out["area_m2"] = base.detectar_area(full)

    if not out["tipo_imovel"]:
        tl = full.lower()
        if "moradia" in tl or "vivenda" in tl:
            out["tipo_imovel"] = "Moradia"
        elif "apartamento" in tl or re.search(r"\bandar\b", tl):
            out["tipo_imovel"] = "Apartamento"
        elif "prédio" in tl or "predio" in tl:
            out["tipo_imovel"] = "Predio"
        elif "terreno" in tl:
            out["tipo_imovel"] = "Terreno"
        elif "loja" in tl or "comercial" in tl:
            out["tipo_imovel"] = "Comercial"

    if not out["descricao"]:
        out["descricao"] = (desc or title)[:500] or None


def _extrair_de_microdata(html: str, out: dict):
    """Microdata HTML: itemprop="price", "floorSize", etc."""
    s = base.soup(html)

    if not out["preco"]:
        for tag in s.find_all(attrs={"itemprop": "price"}):
            val = tag.get("content") or tag.get_text(strip=True)
            v = base.parse_numero(val)
            if v and 30_000 < v < 10_000_000:
                out["preco"] = v
                break

    if not out["area_m2"]:
        for tag in s.find_all(attrs={"itemprop": ["floorSize", "area"]}):
            val = tag.get("content") or tag.get_text(strip=True)
            v = base.parse_numero(val)
            if v and 15 <= v <= 2000:
                out["area_m2"] = v
                break


def _extrair_de_regex(html: str, out: dict):
    """Heurísticas regex no body. Última camada de fallback."""
    s = base.soup(html)
    body_text = s.get_text(" ", strip=True)

    if not out["preco"]:
        candidatos = []
        for m in re.finditer(
            r"([\d][\d\.\s,]{2,12}[\d])\s*(?:€|EUR|euros?)",
            body_text, re.IGNORECASE
        ):
            v = base.parse_numero(m.group(1))
            if v and 30_000 < v < 10_000_000:
                candidatos.append(v)
        if candidatos:
            out["preco"] = max(candidatos)

    if not out["area_m2"]:
        out["area_m2"] = base.detectar_area(body_text)

    if not out["tipologia"]:
        out["tipologia"] = base.detectar_tipologia(body_text[:2000])


def parse(url: str) -> dict:
    """
    Parser genérico para qualquer URL.

    Tenta camada por camada até preencher os campos. Devolve dict com
    erros se faltarem campos críticos.
    """
    out = {
        "fonte": "generico",
        "url": url,
        "preco": None,
        "tipologia": None,
        "area_m2": None,
        "localizacao": None,
        "tipo_imovel": None,
        "estado_conservacao": None,
        "descricao": None,
        "agente_nome": None,
        "agente_apelido": None,
        "agente_agencia": None,
        "agente_tipo": None,
        "erros": [],
    }

    try:
        html = base.get(url)
    except Exception as e:
        out["erros"].append(
            f"Não consegui descarregar a página ({type(e).__name__}). "
            f"Cola o texto do anúncio em vez do URL."
        )
        return out

    # Detectar bloqueio Cloudflare/captcha
    if "Just a moment" in html or "challenge-platform" in html or len(html) < 1000:
        out["erros"].append(
            "O site bloqueou o pedido (Cloudflare ou similar). Cola o texto manualmente."
        )
        return out

    # Camadas em ordem de preferência
    _extrair_de_jsonld(html, out)
    _extrair_de_meta(html, out)
    _extrair_de_microdata(html, out)
    _extrair_de_regex(html, out)

    faltam = [k for k in ("preco", "tipologia", "area_m2") if not out.get(k)]
    if faltam:
        out["erros"].append(
            f"Não detectei {faltam}. Preenche manualmente ou cola o texto do anúncio."
        )

    return out
