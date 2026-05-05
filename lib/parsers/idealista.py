"""
Parser Idealista PT.

ATENÇÃO: Idealista tem Cloudflare anti-bot agressivo. Pedidos automatizados
sem residential IP/proxy/headers de browser real podem ser bloqueados com
403 ou desafio Cloudflare. Este parser tenta best-effort com headers de
browser, mas pode falhar — nesse caso o user vê uma mensagem clara e cola
os dados manualmente.

Estratégia:
1. Tenta fetch normal
2. Procura JSON-LD (Idealista publica schema.org/Product com dados estruturados)
3. Fallback para meta tags (og:title, og:description) e regex no HTML
"""

import re
from typing import Optional

from . import base


def parse(url: str) -> dict:
    out = {
        "fonte": "idealista",
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

    # 1. Tentar fetch
    try:
        html = base.get(url)
    except Exception as e:
        out["erros"].append(
            f"Idealista bloqueou o pedido ({type(e).__name__}). "
            f"Cola os dados manualmente."
        )
        return out

    # Detectar bloqueio Cloudflare
    if "Just a moment..." in html or "challenge-platform" in html or len(html) < 1000:
        out["erros"].append(
            "Cloudflare bloqueou o pedido. Cola os dados manualmente."
        )
        return out

    # 2. JSON-LD
    blocos = base.extrair_jsonld(html)
    for b in blocos:
        if isinstance(b, dict):
            tipo = b.get("@type", "")
            if tipo in ("Product", "Residence", "Apartment", "House", "RealEstateListing"):
                # Preço
                offers = b.get("offers", {})
                if isinstance(offers, dict):
                    p = offers.get("price")
                    if p:
                        out["preco"] = base.parse_numero(p)
                # Localização
                addr = b.get("address", {})
                if isinstance(addr, dict):
                    loc_parts = [
                        addr.get("addressLocality"),
                        addr.get("addressRegion"),
                    ]
                    out["localizacao"] = ", ".join(p for p in loc_parts if p)
                # Tipo
                if "Apartment" in tipo:
                    out["tipo_imovel"] = "Apartamento"
                elif "House" in tipo:
                    out["tipo_imovel"] = "Moradia"

    # 3. Meta tags + regex
    metas = base.extrair_meta(html)
    title = metas.get("og:title", "") or metas.get("title", "")
    desc = metas.get("og:description", "") or metas.get("description", "")

    # Tipologia: do título ou descrição
    if not out["tipologia"]:
        out["tipologia"] = base.detectar_tipologia(title) or base.detectar_tipologia(desc)

    # Área: do título ou descrição
    if not out["area_m2"]:
        out["area_m2"] = base.detectar_area(title) or base.detectar_area(desc)

    # Preço (fallback): regex no título
    if not out["preco"]:
        m = re.search(r"([\d\.\s]+)\s*€", title)
        if m:
            out["preco"] = base.parse_numero(m.group(1))

    # Tipo imóvel (fallback): heurística
    if not out["tipo_imovel"]:
        tl = (title + " " + desc).lower()
        if "moradia" in tl or "vivenda" in tl:
            out["tipo_imovel"] = "Moradia"
        elif "apartamento" in tl or "andar" in tl:
            out["tipo_imovel"] = "Apartamento"
        elif "terreno" in tl:
            out["tipo_imovel"] = "Terreno"
        elif "prédio" in tl or "predio" in tl:
            out["tipo_imovel"] = "Predio"

    # Localização (fallback): título tipicamente "Apartamento T2 em Olivais, Lisboa"
    if not out["localizacao"]:
        m = re.search(r"em\s+(.+?)\s*[,\-]", title)
        if m:
            out["localizacao"] = m.group(1).strip()

    out["descricao"] = desc[:500] if desc else None

    # Validação
    faltam = [k for k in ("preco", "tipologia", "area_m2") if not out.get(k)]
    if faltam:
        out["erros"].append(f"Campos não detectados: {faltam}. Preenche manualmente.")

    return out
