"""
Gestão de comparáveis para estimativa de preço de venda.

Cada comparável é um dict:
    {
        "url": "https://...",
        "preco": 300_000,
        "area_m2": 62,
        "tipologia": "T2",
        "comentario": "..."
    }

Função principal: dado uma lista de comparáveis, devolve preço/m² médio,
opcionalmente ajustado por um factor (comparáveis acima do nível do imóvel
real → factor < 1).
"""

from typing import Optional

from . import constants as C


def preco_m2(comp: dict) -> Optional[float]:
    """Calcula preço/m² de um comparável (devolve None se faltarem dados)."""
    p = comp.get("preco")
    a = comp.get("area_m2")
    if p is None or a is None or a <= 0:
        return None
    return p / a


def media_preco_m2(comparaveis: list[dict]) -> Optional[float]:
    """Média simples dos preços/m² dos comparáveis válidos."""
    valores = [preco_m2(c) for c in comparaveis]
    valores = [v for v in valores if v is not None]
    if not valores:
        return None
    return sum(valores) / len(valores)


def preco_m2_ajustado(
    comparaveis: list[dict],
    ajuste_label: str = "Iguais a revenda",
) -> Optional[float]:
    """
    Aplica o factor de ajuste à média dos comparáveis.

    ajuste_label deve ser uma das chaves de constants.COMPARAVEIS_FACTOR.
    """
    media = media_preco_m2(comparaveis)
    if media is None:
        return None
    factor = C.COMPARAVEIS_FACTOR.get(ajuste_label, 1.0)
    return media * factor


def estimar_preco_venda(
    comparaveis: list[dict],
    area_m2: float,
    ajuste_label: str = "Iguais a revenda",
) -> dict:
    """
    Estima o preço de venda total a partir dos comparáveis e da área.

    Retorna dict com:
        - preco_m2_medio: média não ajustada
        - factor_aplicado
        - preco_m2_ajustado
        - area_m2
        - preco_venda: ajustado × área
        - n_comparaveis_validos
    """
    n = sum(1 for c in comparaveis if preco_m2(c) is not None)
    media = media_preco_m2(comparaveis)
    factor = C.COMPARAVEIS_FACTOR.get(ajuste_label, 1.0)
    ajustado = media * factor if media is not None else None
    preco_venda = ajustado * area_m2 if ajustado is not None and area_m2 > 0 else None

    return {
        "preco_m2_medio": media,
        "factor_aplicado": factor,
        "preco_m2_ajustado": ajustado,
        "area_m2": area_m2,
        "preco_venda": preco_venda,
        "n_comparaveis_validos": n,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Exemplo do Excel: Olivais T1, 3 comparáveis T2
    comps = [
        {"url": "https://idealista.pt/...", "preco": 300_000, "area_m2": 62, "tipologia": "T2"},
        {"url": "https://idealista.pt/...", "preco": 299_000, "area_m2": 56, "tipologia": "T2"},
        {"url": "https://idealista.pt/...", "preco": 370_000, "area_m2": 77, "tipologia": "T2"},
    ]

    print("Média não ajustada:", media_preco_m2(comps))

    r = estimar_preco_venda(comps, area_m2=77, ajuste_label="Bastante acima da revenda")
    print("Estimativa preço venda (T1 77m², comparáveis T2):")
    for k, v in r.items():
        print(f"  {k}: {v}")
