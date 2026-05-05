"""
Persistência de análises — backend configurável.

Modo Núcleo OS (produção):
    - Cada "guardar" cria/actualiza Activo + cria Triagem I + cria/linka Contacto
    - Configurado via st.secrets:
        [airtable]
        token = "..."
        base_id = "..."
        table_activos = "Activos"
        table_triagem_i = "Triagem I"
        table_contactos = "Contactos"

Modo local (desenvolvimento):
    - Cada "guardar" gravar JSON em data/deals.json
    - Activo via secrets ausentes
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import airtable_io


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEALS_PATH = DATA_DIR / "deals.json"


def _config_airtable() -> Optional[dict]:
    try:
        import streamlit as st
        if "airtable" not in st.secrets:
            return None
        cfg = st.secrets["airtable"]
        if not cfg.get("token") or not cfg.get("base_id"):
            return None
        return {
            "token": cfg["token"],
            "base_id": cfg["base_id"],
            "table_activos": cfg.get("table_activos", "Activos"),
            "table_triagem_i": cfg.get("table_triagem_i", "Triagem I"),
            "table_contactos": cfg.get("table_contactos", "Contactos"),
        }
    except Exception:
        return None


def _criado_por() -> str:
    try:
        import streamlit as st
        return st.session_state.get("name", "") or st.session_state.get("username", "")
    except Exception:
        return ""


def backend_em_uso() -> str:
    """Devolve 'airtable' ou 'local'."""
    return "airtable" if _config_airtable() else "local"


# ---------------------------------------------------------------------------
# Local backend (dev)
# ---------------------------------------------------------------------------

def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DEALS_PATH.exists():
        DEALS_PATH.write_text("[]", encoding="utf-8")


def _listar_local() -> list[dict]:
    _ensure_dir()
    try:
        return json.loads(DEALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _guardar_local(payload: dict) -> str:
    _ensure_dir()
    deals = _listar_local()
    deal_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload_full = {
        "id": deal_id,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        **payload,
    }
    deals.append(payload_full)
    DEALS_PATH.write_text(
        json.dumps(deals, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return deal_id


def _eliminar_local(deal_id: str) -> bool:
    deals = _listar_local()
    novos = [d for d in deals if d["id"] != deal_id]
    if len(novos) == len(deals):
        return False
    DEALS_PATH.write_text(
        json.dumps(novos, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return True


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def listar_deals() -> list[dict]:
    """Para tab Histórico."""
    cfg = _config_airtable()
    if cfg:
        triagens = airtable_io.listar_triagens_recentes(
            cfg["token"], cfg["base_id"], cfg["table_triagem_i"]
        )
        # Normalizar para formato esperado pela UI
        out = []
        for t in triagens:
            f = t["fields"]
            out.append({
                "id": t["id"],
                "criado_em": f.get("Data triagem", ""),
                "fonte": "airtable",
                "veredicto": {
                    "cor": _recomendacao_para_cor(f.get("Recomendação", "")),
                    "rotulo": f.get("Recomendação", ""),
                    "mensagem": (f.get("Notas") or "")[:200],
                },
                "outputs": {
                    "lucro_liquido": (f.get("Margem bruta est.") or 0),
                    "roi_total": (f.get("Margem %") or 0),
                },
                "inputs": {
                    "nome_deal": f.get("Triagem ID") or t["id"],
                    "freguesia": "",
                    "ciclo_meses": 0,
                },
                "raw": f,
            })
        return out
    return _listar_local()


def _recomendacao_para_cor(rec: str) -> str:
    return {
        "Visitar": "verde",
        "Monitorizar": "amarelo",
        "Pedir info": "amarelo",
        "Excluir": "vermelho",
    }.get(rec, "amarelo")


def guardar_deal(payload: dict) -> str:
    """
    Em modo Airtable: cria/actualiza Activo + Triagem I + Contacto.
    Em modo local: grava JSON.

    payload deve conter:
        - inputs: dict (FFInputs serializado)
        - outputs: dict (FFOutputs serializado)
        - flags: list
        - veredicto: dict
        - agente_dados: dict (opcional, dados do agente do anúncio)
    """
    cfg = _config_airtable()
    if cfg:
        result = airtable_io.submeter_analise(
            token=cfg["token"],
            base_id=cfg["base_id"],
            table_activos=cfg["table_activos"],
            table_triagem=cfg["table_triagem_i"],
            table_contactos=cfg["table_contactos"],
            inp=payload.get("inputs", {}),
            out=payload.get("outputs", {}),
            ver=payload.get("veredicto", {}),
            flags=payload.get("flags", []),
            agente_dados=payload.get("agente_dados", {}),
            triado_por=_criado_por(),
        )
        return result["triagem_id"]
    return _guardar_local(payload)


def eliminar_deal(deal_id: str) -> bool:
    """Apenas modo local. Em Airtable, remove via UI Airtable."""
    cfg = _config_airtable()
    if cfg:
        return False
    return _eliminar_local(deal_id)


def carregar_deal(deal_id: str) -> Optional[dict]:
    for d in listar_deals():
        if d["id"] == deal_id:
            return d
    return None


def limpar_todos():
    cfg = _config_airtable()
    if cfg:
        raise NotImplementedError("Em modo Airtable, limpa via UI Airtable.")
    _ensure_dir()
    DEALS_PATH.write_text("[]", encoding="utf-8")
