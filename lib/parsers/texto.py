"""
Parser de texto livre — aceita o conteúdo de uma página de anúncio
copy-pasted pelo user (Ctrl+A + Ctrl+C no browser).

Funciona para qualquer site (Idealista, Remax, Imovirtual, Casa Sapo, Era,
Century 21...) porque trabalha sobre texto plano em vez de HTML.

Estratégia:
- Regex para preço (€), área (m²), tipologia (T1-T5+).
- Heurística para localização (procura padrões "em X" ou "X, Concelho").
- Heurística para tipo imóvel (apartamento/moradia/terreno/...).
- Heurística para estado de conservação (procura keywords).
"""

import re
from . import base


def parse(texto: str, url_origem: str = "") -> dict:
    """
    Recebe texto plano (output de Ctrl+A na página de um anúncio).
    Devolve dict com campos parciais.
    """
    out = {
        "fonte": "texto",
        "url": url_origem,
        "preco": None,
        "tipologia": None,
        "area_m2": None,
        "localizacao": None,
        "tipo_imovel": None,
        "estado_conservacao": None,
        "descricao": texto[:500] if texto else None,
        # Dados do agente / anunciante
        "agente_nome": None,
        "agente_apelido": None,
        "agente_agencia": None,
        "agente_tipo": None,  # "particular" ou "agente"
        "erros": [],
    }

    if not texto or len(texto) < 20:
        out["erros"].append("Texto vazio ou demasiado curto.")
        return out

    # ---- PREÇO ----
    # Tenta vários padrões PT: "250 000 €", "250.000€", "EUR 250000"
    candidatos_preco = []
    for m in re.finditer(
        r"(?:€\s*|EUR\s*)?([\d][\d\.\s,]{2,12}[\d])\s*(?:€|EUR|euros?)",
        texto, re.IGNORECASE,
    ):
        val = base.parse_numero(m.group(1))
        if val and 30_000 < val < 10_000_000:  # plausibility filter
            candidatos_preco.append(val)
    if candidatos_preco:
        # O preço de venda é geralmente o mais alto / o que aparece primeiro grande
        out["preco"] = max(candidatos_preco)

    # ---- ÁREA ----
    out["area_m2"] = base.detectar_area(texto)
    # Sanity check: 15-2000 m²
    if out["area_m2"] and not (15 <= out["area_m2"] <= 2000):
        # Pode ser área de terreno ou número irrelevante. Procurar outro.
        for m in re.finditer(r"([\d\.,]+)\s*(?:m²|m2|metros\s*quadrados)", texto, re.IGNORECASE):
            v = base.parse_numero(m.group(1))
            if v and 15 <= v <= 2000:
                out["area_m2"] = v
                break

    # ---- TIPOLOGIA ----
    out["tipologia"] = base.detectar_tipologia(texto)

    # ---- TIPO IMÓVEL ----
    tl = texto.lower()
    if "moradia" in tl or "vivenda" in tl:
        out["tipo_imovel"] = "Moradia"
    elif "apartamento" in tl or re.search(r"\bandar\b", tl):
        out["tipo_imovel"] = "Apartamento"
    elif "prédio" in tl or "predio" in tl:
        out["tipo_imovel"] = "Predio"
    elif "terreno" in tl:
        out["tipo_imovel"] = "Terreno"
    elif "loja" in tl or "comercial" in tl or "escritório" in tl:
        out["tipo_imovel"] = "Comercial"

    # ---- LOCALIZAÇÃO ----
    # Padrão típico de Idealista/Remax: "T2 em Olivais, Lisboa" ou
    # "Apartamento - Concelho - Freguesia".
    # Heurística: procurar "em X, Y" ou "X - Y - Z" no início.
    candidatos_loc = []
    for m in re.finditer(r"em\s+([A-ZÁÉÍÓÚÂÊÔÇ][\w\sáéíóúâêôç\-]+,\s*[A-ZÁÉÍÓÚÂÊÔÇ][\w\sáéíóúâêôç\-]+)", texto):
        candidatos_loc.append(m.group(1).strip())
    if candidatos_loc:
        out["localizacao"] = candidatos_loc[0]
    else:
        # Fallback: procurar concelho conhecido na primeira linha
        for concelho in ["Lisboa", "Almada", "Setúbal", "Setubal", "Amadora",
                         "Odivelas", "Seixal", "Barreiro", "Cascais", "Sintra",
                         "Oeiras", "Loures", "Mafra", "Vila Franca de Xira"]:
            if concelho in texto[:500]:
                out["localizacao"] = concelho
                break

    # ---- ESTADO CONSERVAÇÃO ----
    # Heurística por keywords
    if re.search(r"\b(ru[ií]na|para\s+demolir|estado\s+devoluto)\b", tl):
        out["estado_conservacao"] = "Ruina"
    elif re.search(r"\b(remodelação\s+profunda|reabilita[çc][aã]o\s+profunda|profunda\s+remodela)", tl):
        out["estado_conservacao"] = "Remodelacao profunda"
    elif re.search(r"\b(remodela[çc][aã]o|reabilita[çc][aã]o|para\s+obras)\b", tl):
        out["estado_conservacao"] = "Remodelacao moderada"
    elif re.search(r"\b(desatualizado|original|antigo|sem\s+obras)\b", tl):
        out["estado_conservacao"] = "Desatualizado"
    elif re.search(r"\b(novo|remodelado|impec[aá]vel|excelente\s+estado|bom\s+estado)\b", tl):
        out["estado_conservacao"] = "Bom"

    # ---- AGENTE / ANUNCIANTE ----
    # Detecção de "particular" vs "agente"
    if re.search(r"\banunciante\s+particular\b|\b(particular|proprietário)\b", tl):
        out["agente_tipo"] = "particular"
    elif re.search(r"\banunciante\s*:|\bagente\b|\bconsultor\b|\bag[eê]ncia\b|\bimobili[aá]ria\b", tl):
        out["agente_tipo"] = "agente"

    # Tentar extrair nome do anunciante / agência. Padrões comuns:
    #   "Anunciante: ABC Imobiliária"
    #   "Anuncio publicado por: João Silva"
    #   "Contacto: Maria Santos - Remax"
    for pat in [
        r"anunciante\s*[:\-]\s*([A-ZÁÉÍÓÚÂÊÔÇa-zà-ÿ][\w\s\-\&\.]{2,60})(?:\n|$|\s{2})",
        r"(?:agente|consultor|comercial)\s*[:\-]\s*([A-ZÁÉÍÓÚÂÊÔÇ][\w\s\-]{2,40})",
        r"publicado\s+por\s*[:\-]?\s*([A-ZÁÉÍÓÚÂÊÔÇ][\w\s\-]{2,40})",
    ]:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nome_full = m.group(1).strip()
            # Remover ruído tipo "ver telefone", quebras de linha
            nome_full = re.sub(r"\s+", " ", nome_full).strip()
            partes = nome_full.split()
            if len(partes) >= 2:
                out["agente_nome"] = partes[0]
                out["agente_apelido"] = " ".join(partes[1:])
            else:
                out["agente_agencia"] = nome_full
            break

    # Tentar agência conhecidas (Remax, Era, Century 21, etc.)
    for agencia in ["Remax", "RE/MAX", "ERA", "Century 21", "Decisões e Soluções",
                    "Maxfinance", "Realtv", "Belion", "Engel", "Sotheby"]:
        if re.search(r"\b" + re.escape(agencia) + r"\b", texto, re.IGNORECASE):
            if not out["agente_agencia"]:
                out["agente_agencia"] = agencia
            break

    # ---- VALIDAÇÃO ----
    faltam = [k for k in ("preco", "tipologia", "area_m2") if not out.get(k)]
    if faltam:
        out["erros"].append(
            f"Não detectei: {faltam}. "
            f"Cola mais contexto do anúncio (incluindo título, preço, características)."
        )

    return out
