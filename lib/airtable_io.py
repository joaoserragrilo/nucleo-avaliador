"""
Cliente Airtable — integração com Núcleo OS schema.

Quando o tool corre uma análise, fluxo:
1. Procurar (ou criar) Contacto do agente do anúncio
2. Procurar (ou criar) Activo (chave: Link anúncio)
3. Criar Triagem I com os outputs do tool, linkada ao Activo

Configuração via st.secrets:
    [airtable]
    token = "patxxxxxx..."
    base_id = "appnv3Q8pmFUzaxgx"
    # opcionais (defaults sensatos):
    table_activos = "Activos"
    table_triagem_i = "Triagem I"
    table_contactos = "Contactos"
"""

import json
import re
from datetime import date
from typing import Optional

from . import constants as C


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api(token: str):
    from pyairtable import Api
    return Api(token)


def _table(token: str, base_id: str, name: str):
    return _api(token).table(base_id, name)


def _detect_type(record: dict) -> dict:
    """Tira campos None ou string vazia (Airtable rejeita)."""
    return {k: v for k, v in record.items() if v not in (None, "")}


def calcular_confianca(inp: dict, out: dict) -> str:
    """
    Confiança da Triagem baseada em:
    - INE confidence (do trimestre usado)
    - Número de comparáveis válidos
    """
    n_comp = len(inp.get("comparaveis") or [])
    venda_breakdown = (out.get("breakdown") or {}).get("venda_estimativa", {})
    ine_info = venda_breakdown.get("ine", {})
    ine_conf = ine_info.get("confidence", "")

    if ine_conf == "High" and n_comp >= 3:
        return "Alta"
    if ine_conf == "High" or n_comp >= 2:
        return "Média"
    return "Baixa"


def detectar_sou(parser_dados: dict, texto: str = "") -> str:
    """
    Heurística: se anúncio menciona "particular" → Proprietário; senão Agente.
    """
    full = (parser_dados.get("descricao") or "") + " " + (texto or "")
    if re.search(r"\bparticular\b|\banunciante\s+particular\b", full, re.IGNORECASE):
        return "Proprietário"
    return "Agente Imobiliário"


# ---------------------------------------------------------------------------
# Contactos
# ---------------------------------------------------------------------------

def procurar_contacto(token, base_id, table_name, primeiro_nome, ultimo_nome) -> Optional[str]:
    """Devolve record id se encontrar contacto com mesmo nome (case-insensitive)."""
    if not primeiro_nome and not ultimo_nome:
        return None
    tbl = _table(token, base_id, table_name)
    pn = (primeiro_nome or "").strip().lower()
    un = (ultimo_nome or "").strip().lower()
    for r in tbl.iterate(page_size=100):
        for rec in r:
            f = rec.get("fields", {})
            if (f.get("Primeiro Nome", "").strip().lower() == pn
                and f.get("Último nome", "").strip().lower() == un
                and pn):
                return rec["id"]
    return None


def criar_contacto(token, base_id, table_name, dados: dict) -> str:
    """Cria contacto e devolve record id."""
    tbl = _table(token, base_id, table_name)
    rec = _detect_type({
        "Primeiro Nome": dados.get("primeiro_nome", ""),
        "Último nome": dados.get("ultimo_nome", ""),
        "Sou": dados.get("sou", "Agente Imobiliário"),
        "Telemóvel": dados.get("telemovel", ""),
        "Email": dados.get("email", ""),
        "Mensagem": dados.get("mensagem", ""),
    })
    r = tbl.create(rec)
    return r["id"]


def garantir_contacto(token, base_id, table_name, dados: dict) -> Optional[str]:
    """Procura por nome; se não existe, cria. Devolve record id (ou None se sem nome)."""
    pn = dados.get("primeiro_nome", "").strip()
    un = dados.get("ultimo_nome", "").strip()
    if not pn and not un:
        return None
    existing = procurar_contacto(token, base_id, table_name, pn, un)
    if existing:
        return existing
    return criar_contacto(token, base_id, table_name, dados)


# ---------------------------------------------------------------------------
# Activos
# ---------------------------------------------------------------------------

def procurar_activo_por_link(token, base_id, table_name, link: str) -> Optional[str]:
    """Devolve record id se já existe um Activo com o mesmo Link anúncio."""
    if not link:
        return None
    tbl = _table(token, base_id, table_name)
    for page in tbl.iterate(page_size=100, fields=["Link anúncio"]):
        for rec in page:
            if rec.get("fields", {}).get("Link anúncio") == link:
                return rec["id"]
    return None


def montar_activo_payload(inp: dict, contacto_id: Optional[str] = None) -> dict:
    """Mapeia FFInputs → fields do Activos."""
    payload = {
        "Tipo de imovel": C.TIPO_INTERNO_PARA_AIRTABLE.get(inp.get("tipo_imovel", ""), ""),
        "Tipologia": C.TIPOLOGIA_INTERNA_PARA_AIRTABLE.get(inp.get("tipologia", ""), ""),
        "Estado Conservação": C.ESTADO_INTERNO_PARA_AIRTABLE.get(inp.get("estado_conservacao", ""), ""),
        "Área (m2)": inp.get("area_m2") or 0,
        "Preço pedido": inp.get("preco_aquisicao") or 0,
        "Link anúncio": inp.get("link_anuncio") or "",
        "Freguesia": inp.get("freguesia") or "",
        "Estado": "Em triagem I",
        "Data entrada": str(date.today()),
        "Canal origem": inp.get("canal_origem") or "Outro",
    }
    if contacto_id:
        # O campo é "Contacto (linked)" segundo o schema lido
        payload["Contacto (linked)"] = [contacto_id]
    return _detect_type(payload)


def criar_ou_actualizar_activo(token, base_id, table_name, inp: dict, contacto_id=None) -> tuple[str, str]:
    """
    Cria novo Activo ou actualiza existente (matching por Link anúncio).
    Devolve (record_id, accao) onde accao é "criado" ou "actualizado".
    """
    link = inp.get("link_anuncio")
    existing = procurar_activo_por_link(token, base_id, table_name, link) if link else None
    payload = montar_activo_payload(inp, contacto_id)
    tbl = _table(token, base_id, table_name)
    if existing:
        tbl.update(existing, payload)
        return existing, "actualizado"
    rec = tbl.create(payload)
    return rec["id"], "criado"


# ---------------------------------------------------------------------------
# Triagem I
# ---------------------------------------------------------------------------

def montar_triagem_payload(activo_id: str, inp: dict, out: dict, ver: dict, flags: list, triado_por: str = "") -> dict:
    """Mapeia FFOutputs → fields da Triagem I."""
    cor = ver.get("cor", "")
    recomendacao = C.VEREDICTO_PARA_RECOMENDACAO.get(cor, "Pedir info")
    confianca = calcular_confianca(inp, out)

    # Notas: resumo + breakdown
    notas_partes = [
        f"Veredicto: {ver.get('rotulo', '')}",
        f"ROI: {(out.get('roi_total') or 0)*100:.1f}% | "
        f"Lucro líq.: {(out.get('lucro_liquido') or 0):,.0f}€ | "
        f"Margem (% venda): {(out.get('margem_bruta_pct_venda') or 0)*100:.1f}%",
        f"Preço/m² compra: {(out.get('preco_m2_compra') or 0):,.0f}€ | "
        f"Preço/m² venda: {(out.get('preco_m2_venda') or 0):,.0f}€",
        "",
        "Flags:",
    ]
    for f in flags or []:
        ic = {"ok": "🟢", "amarelo": "🟡", "vermelho": "🔴"}.get(f.get("nivel"), "")
        notas_partes.append(f"  {ic} {f.get('mensagem', '')}")
    notas = "\n".join(notas_partes)

    payload = {
        "Activo": [activo_id],
        "Data triagem": str(date.today()),
        "Recomendação": recomendacao,
        "Confiança": confianca,
        "Valor actual est.": inp.get("preco_aquisicao") or 0,
        "Valor após obra est.": out.get("preco_venda_usado") or 0,
        "Custo obra est.": out.get("obra_com_contingencia") or 0,
        "Notas": notas[:5000],  # Airtable limit ~100k mas mantém legível
    }
    return _detect_type(payload)


def criar_triagem_i(token, base_id, table_name, activo_id: str, inp: dict, out: dict,
                     ver: dict, flags: list, triado_por: str = "") -> str:
    """Cria record na Triagem I e devolve record id."""
    tbl = _table(token, base_id, table_name)
    payload = montar_triagem_payload(activo_id, inp, out, ver, flags, triado_por)
    r = tbl.create(payload)
    return r["id"]


# ---------------------------------------------------------------------------
# Orchestrator: submeter análise completa ao Núcleo OS
# ---------------------------------------------------------------------------

def submeter_analise(
    token: str,
    base_id: str,
    table_activos: str,
    table_triagem: str,
    table_contactos: str,
    inp: dict,
    out: dict,
    ver: dict,
    flags: list,
    agente_dados: dict,
    triado_por: str = "",
) -> dict:
    """
    Cria/actualiza Activo + cria Triagem I + cria/linka Contacto.

    agente_dados deve ter: {primeiro_nome, ultimo_nome, sou, telemovel, email, mensagem}

    Devolve: {activo_id, accao_activo, triagem_id, contacto_id}
    """
    # 1. Contacto (se houver dados)
    contacto_id = None
    if agente_dados:
        contacto_id = garantir_contacto(token, base_id, table_contactos, agente_dados)

    # 2. Activo
    activo_id, accao = criar_ou_actualizar_activo(token, base_id, table_activos, inp, contacto_id)

    # 3. Triagem I
    triagem_id = criar_triagem_i(token, base_id, table_triagem, activo_id, inp, out, ver, flags, triado_por)

    return {
        "activo_id": activo_id,
        "accao_activo": accao,
        "triagem_id": triagem_id,
        "contacto_id": contacto_id,
    }


# ---------------------------------------------------------------------------
# Listar (para tab Histórico)
# ---------------------------------------------------------------------------

def listar_triagens_recentes(token, base_id, table_name, limit: int = 20) -> list[dict]:
    """Lista triagens recentes para o tab Histórico."""
    tbl = _table(token, base_id, table_name)
    records = tbl.all(sort=["-Data triagem"], max_records=limit)
    return [{"id": r["id"], "fields": r.get("fields", {})} for r in records]


def testar_ligacao(token, base_id) -> dict:
    """Smoke test: tenta listar bases."""
    try:
        api = _api(token)
        bases = api.bases()
        return {"ok": True, "n_bases": len(list(bases))}
    except Exception as e:
        return {"ok": False, "erro": f"{type(e).__name__}: {e}"}
