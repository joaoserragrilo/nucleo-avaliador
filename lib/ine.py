"""
Módulo INE — Preços medianos por concelho/freguesia.

Carrega data/ine_q3_2025.json (extraído do Excel original com 121 entradas:
freguesias e concelhos da Área Metropolitana de Lisboa).

Cada entrada tem séries históricas Q4 2022 → Q3 2025 e estimativas lineares
para Q1-Q4 2026, mais R², confidence ("High"/"Medium"/"Low") e growth %.
"""

import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ine_q3_2025.json"

_DATA: list[dict] = []


def _load():
    """Carrega o ficheiro JSON. Idempotente."""
    global _DATA
    if _DATA:
        return _DATA
    if not _DATA_PATH.exists():
        return []
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        _DATA = json.load(f)
    return _DATA


def listar_locais(level: Optional[str] = None) -> list[dict]:
    """
    Devolve lista de locais disponíveis. level pode ser "Municipality" ou
    "Parish" para filtrar.
    """
    data = _load()
    if level:
        return [d for d in data if d["level"] == level]
    return data


def listar_nomes(level: Optional[str] = None) -> list[str]:
    """Apenas os nomes (úteis para dropdowns)."""
    return [d["location"] for d in listar_locais(level)]


def get_preco_m2(
    location: str,
    trimestre: str = "Q1 2026",
) -> Optional[dict]:
    """
    Devolve dict com preço €/m² para um local específico no trimestre dado.

    trimestre pode ser histórico ("Q3 2025", "Q4 2024", ...) ou estimativa
    ("Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026").
    """
    data = _load()
    location_norm = location.strip().lower()

    for entry in data:
        if entry["location"].strip().lower() == location_norm:
            valor = (
                entry["historico"].get(trimestre)
                or entry["estimativas_2026"].get(trimestre)
            )
            if valor is None:
                return None
            return {
                "location": entry["location"],
                "nuts_code": entry["nuts_code"],
                "level": entry["level"],
                "trimestre": trimestre,
                "preco_m2": valor,
                "confidence": entry["confidence"],
                "r2": entry["r2"],
                "growth_pct": entry["growth_pct"],
                "estimativa": trimestre.startswith("Est.")
                              or trimestre.startswith("Q") and "2026" in trimestre,
            }
    return None


def trimestres_disponiveis() -> list[str]:
    """Lista de trimestres disponíveis (históricos + estimativas)."""
    data = _load()
    if not data:
        return []
    primeiro = data[0]
    return list(primeiro["historico"].keys()) + list(primeiro["estimativas_2026"].keys())


def trimestre_default() -> str:
    """O trimestre default a usar para cálculo de venda (Q1 2026 = primeiro futuro)."""
    return "Q1 2026"


# ---------------------------------------------------------------------------
# Helper: pesquisa fuzzy (encontra "Almada" mesmo se o user escreveu "almada")
# ---------------------------------------------------------------------------

def procurar(termo: str, level: Optional[str] = None) -> list[dict]:
    """
    Pesquisa case-insensitive partial match.
    Útil para autocomplete em UI.
    """
    data = listar_locais(level)
    termo_l = termo.strip().lower()
    if not termo_l:
        return data
    return [d for d in data if termo_l in d["location"].lower()]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Total locais: {len(_load())}")
    print(f"Trimestres: {trimestres_disponiveis()}")
    print()

    # Almada centro
    r = get_preco_m2("Almada", "Q1 2026")
    print(f"Almada Q1 2026: {r}")

    # Amadora - Venteira (uma das obras tuas)
    r = get_preco_m2("Amadora - Venteira", "Q1 2026")
    print(f"Amadora-Venteira Q1 2026: {r}")

    # Search
    print(f"\nPesquisa 'almada':")
    for r in procurar("almada"):
        print(f"  - {r['location']} ({r['level']})")
