"""
Cálculos fiscais portugueses para imobiliário residencial.

Funções puras (sem efeitos colaterais). Cada função recebe inputs e devolve
um dict com o detalhe do cálculo, para auditoria.

NOTA: As tabelas vivem em constants.py. Se as taxas oficiais mudarem,
basta actualizar lá.
"""

from typing import Optional

from . import constants as C


# ---------------------------------------------------------------------------
# IMT
# ---------------------------------------------------------------------------

def calcular_imt(
    valor_aquisicao: float,
    vpt: Optional[float] = None,
    tipo: str = "hpp",
    isento_revenda: bool = False,
) -> dict:
    """
    Calcula o IMT.

    valor_aquisicao: preço de escritura (€).
    vpt: Valor Patrimonial Tributário. Se None, usa-se preço.
         IMT incide sobre o MAIOR entre VPT e preço.
    tipo: "hpp" (habitação própria), "secundaria" (habitação não permanente),
          "outros_urbanos" (6,5% taxa única), "rustico" (5% taxa única).
    isento_revenda: se True (empresa com actividade de compra para revenda
                    declarada e revenda em <1 ano), IMT = 0. Conferir requisitos
                    no CIMT artigo 7º antes de assumir.
    """
    if isento_revenda:
        return {
            "imt": 0.0,
            "base_tributavel": 0.0,
            "taxa_efectiva": 0.0,
            "nota": "Isenção art. 7º CIMT (compra para revenda). Conferir requisitos.",
        }

    base = max(valor_aquisicao, vpt or 0)

    if tipo == "outros_urbanos":
        imt = base * C.IMT_OUTROS_PREDIOS_URBANOS
        return {
            "imt": imt,
            "base_tributavel": base,
            "taxa_efectiva": imt / base if base else 0,
            "nota": "Outros prédios urbanos / terreno construção (6,5% taxa única).",
        }

    if tipo == "rustico":
        imt = base * C.IMT_PREDIOS_RUSTICOS
        return {
            "imt": imt,
            "base_tributavel": base,
            "taxa_efectiva": imt / base if base else 0,
            "nota": "Prédio rústico (5% taxa única).",
        }

    tabela = C.IMT_HPP_2025 if tipo == "hpp" else C.IMT_HABITACAO_SECUNDARIA_2025

    for limite_sup, taxa, parcela_a_abater, modo in tabela:
        if base <= limite_sup:
            if modo == "marginal":
                imt = max(0.0, base * taxa - parcela_a_abater)
            else:  # taxa única
                imt = base * taxa
            return {
                "imt": imt,
                "base_tributavel": base,
                "taxa_marginal": taxa,
                "parcela_abater": parcela_a_abater,
                "taxa_efectiva": imt / base if base else 0,
                "tipo": tipo,
            }

    # Fallback (não deve chegar aqui dado float("inf") na última linha)
    return {"imt": 0, "base_tributavel": base, "erro": "tabela IMT incompleta"}


# ---------------------------------------------------------------------------
# Imposto do Selo (transmissão)
# ---------------------------------------------------------------------------

def calcular_is_transmissao(valor_aquisicao: float, vpt: Optional[float] = None) -> dict:
    """0,8% sobre o maior entre VPT e preço."""
    base = max(valor_aquisicao, vpt or 0)
    is_valor = base * C.IS_TRANSMISSAO
    return {
        "is": is_valor,
        "base": base,
        "taxa": C.IS_TRANSMISSAO,
    }


# ---------------------------------------------------------------------------
# IMI durante o ciclo
# ---------------------------------------------------------------------------

def calcular_imi_ciclo(
    vpt: float,
    ciclo_meses: int,
    taxa_imi: float = C.IMI_TAXA_DEFAULT,
) -> dict:
    """
    IMI anual = VPT × taxa. Aproximação linear durante o ciclo: pro-rata mensal.

    Em PT o IMI é cobrado em prestações (Maio, Aug, Nov consoante valor) com
    base no titular a 31 Dez. Na prática, num F&F de 12-18 meses, paga-se
    1-2 anos. Aqui usamos pro-rata como aproximação suficiente para análise.
    """
    imi_anual = vpt * taxa_imi
    imi_total = imi_anual * (ciclo_meses / 12)
    return {
        "imi_anual": imi_anual,
        "imi_total_ciclo": imi_total,
        "taxa": taxa_imi,
        "vpt": vpt,
    }


# ---------------------------------------------------------------------------
# IVA da obra
# ---------------------------------------------------------------------------

def iva_obra(custo_obra_sem_iva: float, regime: str = "verba_2_23") -> dict:
    """
    regime: "verba_2_23" (6%) ou "normal" (23%).

    Verba 2.23 (Lista I CIVA) — 6% — só se obra é em imóvel afecto a habitação
    em ARU ou que cumpra requisitos específicos. Conferir caso a caso.
    """
    taxa = C.IVA_VERBA_2_23 if regime == "verba_2_23" else C.IVA_NORMAL
    iva = custo_obra_sem_iva * taxa
    return {
        "obra_sem_iva": custo_obra_sem_iva,
        "iva": iva,
        "obra_com_iva": custo_obra_sem_iva + iva,
        "taxa": taxa,
        "regime": regime,
    }


# ---------------------------------------------------------------------------
# Tributação na saída
# ---------------------------------------------------------------------------

def imposto_saida_lda(
    lucro_bruto: float,
    derrama_municipal: float = C.DERRAMA_MUNICIPAL_DEFAULT,
) -> dict:
    """
    IRC + derrama municipal sobre lucro tributável (PJ).

    Simplificação: lucro_bruto é assumido como lucro tributável após dedução
    de todos os custos (incluindo financiamento, obra, transação). Em
    contabilidade real há ajustes (depreciações, encargos não dedutíveis,
    derrama estadual em escalões altos). Para análise de viabilidade serve.
    """
    if lucro_bruto <= 0:
        return {
            "irc": 0.0,
            "derrama": 0.0,
            "imposto_total": 0.0,
            "lucro_liquido": lucro_bruto,
        }

    irc = lucro_bruto * C.IRC_TAXA
    derrama = lucro_bruto * derrama_municipal
    total = irc + derrama
    return {
        "irc": irc,
        "derrama": derrama,
        "imposto_total": total,
        "lucro_liquido": lucro_bruto - total,
        "taxa_efectiva": total / lucro_bruto if lucro_bruto else 0,
    }


def imposto_saida_pf(
    valor_venda: float,
    valor_aquisicao_corrigido: float,
    encargos_dedutiveis: float = 0.0,
) -> dict:
    """
    Mais-valia imobiliária PF — modelo simplificado.

    Mais-valia = venda − (aquisição corrigida + encargos)
    Imposto = mais-valia × 28% (taxa autónoma simplificada).

    Em modo realista PT o IRS aplica 50% da mais-valia somada ao rendimento
    global e tributa pela tabela marginal. Para análise de viabilidade,
    28% sobre 100% serve como aproximação conservadora.
    """
    mais_valia = valor_venda - valor_aquisicao_corrigido - encargos_dedutiveis
    if mais_valia <= 0:
        return {
            "mais_valia": mais_valia,
            "imposto": 0.0,
            "lucro_liquido": mais_valia,
        }
    imposto = mais_valia * C.IRS_MV_TAXA_AUTONOMA
    return {
        "mais_valia": mais_valia,
        "imposto": imposto,
        "lucro_liquido": mais_valia - imposto,
        "taxa": C.IRS_MV_TAXA_AUTONOMA,
        "nota": "Simplificação: 28% sobre mais-valia total. Realidade PT: 50% × marginal IRS.",
    }


# ---------------------------------------------------------------------------
# Self-test rápido
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Teste IMT habitação secundária a 175k (típico T2 Almada margem sul)
    r = calcular_imt(175_000, tipo="secundaria")
    print(f"IMT secundária 175k: {r['imt']:.2f}€ ({r.get('taxa_efectiva', 0)*100:.2f}%)")

    # Teste IS
    r = calcular_is_transmissao(175_000)
    print(f"IS 175k: {r['is']:.2f}€")

    # IMI ciclo 14m, VPT 90k
    r = calcular_imi_ciclo(90_000, 14)
    print(f"IMI 14m sobre VPT 90k: {r['imi_total_ciclo']:.2f}€")

    # IVA obra 25k Verba 2.23
    r = iva_obra(25_000, "verba_2_23")
    print(f"Obra 25k IVA 6%: {r['obra_com_iva']:.2f}€ (IVA {r['iva']:.2f}€)")

    # IRC sobre 50k lucro
    r = imposto_saida_lda(50_000)
    print(f"IRC+derrama sobre 50k lucro: {r['imposto_total']:.2f}€ (líquido {r['lucro_liquido']:.2f}€)")
