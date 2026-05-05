"""
Engine de análise Fix-and-Flip.

Inputs enriquecidos (v2):
- Identificação (nome, freguesia, link, tipo, tipologia, área m², estado, vendedor)
- Aquisição (preço, VPT, custos transação)
- Financiamento (LTV, prazo, taxa, comissões)
- Obra (calculada automaticamente a partir de área × estado, ou override manual)
- Holding (ciclo, IMI, custos mensais)
- Venda (calculada automaticamente a partir de comparáveis ou INE × área, ou manual)
- Saída fiscal (PJ Lda ou PF)

Outputs:
- Custos totais, equity, lucro bruto/líquido
- ROI total, Cash-on-Cash anualizado, IRR aproximado, margem
- Detalhe da estimativa de obra e venda
- Simulação preço máximo de aquisição para múltiplos ROIs alvo
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

from . import taxes as T
from . import constants as C
from . import comparables as Cmp
from . import ine as INE


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class FFInputs:
    # ---- Identificação
    nome_deal: str = "Sem nome"
    freguesia: str = ""
    link_anuncio: str = ""

    # ---- Caracterização do imóvel
    tipo_imovel: str = "Apartamento"   # Ver constants.TIPOS_IMOVEL
    tipologia: str = "T2"              # Ver constants.TIPOLOGIAS
    area_m2: float = 0.0               # Área útil/bruta (€/m² × area = obra/venda)
    estado_conservacao: str = "Desatualizado"  # Ver constants.ESTADOS_CONSERVACAO
    vendedor: str = "Particular"       # Ver constants.VENDEDORES

    # ---- Aquisição
    preco_aquisicao: float = 0.0
    vpt: float = 0.0
    tipo_imt: str = "secundaria"
    isencao_imt_revenda: bool = False
    custos_notario_registo: float = C.CUSTOS_NOTARIO_REGISTO_DEFAULT
    custos_due_diligence: float = 0.0

    # ---- Financiamento
    usa_financiamento: bool = True
    ltv: float = 0.70
    taxa_juro_anual: float = 0.055
    prazo_anos: int = 30
    comissoes_abertura: float = 1_500.0
    seguros_anuais: float = 350.0

    # ---- Obra: auto (calculada de área × estado) ou manual
    obra_modo: str = "auto"            # "auto" (área × €/m² estado) ou "manual"
    custo_obra_sem_iva_manual: float = 0.0  # Só usado se obra_modo == "manual"
    regime_iva_obra: str = "verba_2_23"
    contingencia_obra_pct: float = 0.10

    # ---- Holding
    ciclo_meses: int = 12
    taxa_imi: float = C.IMI_TAXA_DEFAULT
    custos_holding_mensais: float = 50.0

    # ---- Venda: auto (comparáveis ou INE) ou manual
    venda_modo: str = "manual"  # "manual" / "comparaveis" / "ine" / "max_comp_ine"
    preco_venda_manual: float = 0.0
    # Comparáveis: lista de dicts {url, preco, area_m2, tipologia, comentario}
    comparaveis: list = field(default_factory=list)
    factor_ajuste_comparaveis: str = "Iguais a revenda"  # Ver C.COMPARAVEIS_FACTOR
    # INE
    ine_trimestre: str = "Q1 2026"

    # ---- Custos venda
    comissao_imobiliaria_pct: float = C.COMISSAO_IMOBILIARIA_DEFAULT
    comissao_imobiliaria_iva: bool = True

    # ---- Saída fiscal
    estrutura: str = "lda"
    derrama_municipal: float = C.DERRAMA_MUNICIPAL_DEFAULT

    # ---- Núcleo OS
    canal_origem: str = "Outro"  # Idealista / Imovirtual / Agente / etc.
    # Dados do agente / anunciante (opcional, para popular Contactos)
    agente_primeiro_nome: str = ""
    agente_ultimo_nome: str = ""
    agente_telemovel: str = ""
    agente_email: str = ""
    agente_sou: str = "Agente Imobiliário"  # ou Proprietário


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

@dataclass
class FFOutputs:
    # Custos
    imt: float = 0.0
    is_transmissao: float = 0.0
    custos_compra_total: float = 0.0
    obra_sem_iva: float = 0.0
    obra_com_iva: float = 0.0
    obra_com_contingencia: float = 0.0
    juros_pagos_ciclo: float = 0.0
    imi_ciclo: float = 0.0
    custos_holding_total: float = 0.0
    seguros_ciclo: float = 0.0
    custos_venda: float = 0.0
    custo_total_operacao: float = 0.0

    # Financiamento
    valor_emprestimo: float = 0.0
    equity_aquisicao: float = 0.0
    equity_obra: float = 0.0
    equity_total: float = 0.0

    # Receita / venda
    preco_venda_usado: float = 0.0       # O valor final usado no cálculo
    preco_venda_origem: str = ""         # "manual" / "comparaveis" / "ine" / "max"
    preco_m2_venda: float = 0.0          # Preço/m² implícito na venda
    receita_venda_liquida: float = 0.0   # Após comissão

    # Resultado
    lucro_bruto: float = 0.0
    imposto_saida: float = 0.0
    lucro_liquido: float = 0.0

    # KPIs
    roi_total: float = 0.0
    margem_absoluta: float = 0.0
    margem_bruta_pct_venda: float = 0.0  # Lucro / Venda — indicador secundário
    cash_on_cash_anual: float = 0.0
    irr_aproximado: float = 0.0
    preco_m2_compra: float = 0.0

    # Detalhe (auditoria)
    breakdown: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Estimativa automática de obra
# ---------------------------------------------------------------------------

def estimar_custo_obra(area_m2: float, estado: str) -> dict:
    """
    Custo de obra sem IVA = área × €/m² do estado.
    Devolve dict com a fórmula explícita.
    """
    eur_m2 = C.OBRA_EUR_M2_POR_ESTADO.get(estado, 0)
    custo = area_m2 * eur_m2
    return {
        "estado": estado,
        "eur_m2": eur_m2,
        "area_m2": area_m2,
        "custo_sem_iva": custo,
    }


# ---------------------------------------------------------------------------
# Estimativa automática de preço de venda
# ---------------------------------------------------------------------------

def estimar_preco_venda(inputs: FFInputs) -> dict:
    """
    Calcula o preço de venda consoante o modo:
      - "manual": usa inputs.preco_venda_manual
      - "comparaveis": usa comparáveis × factor × área
      - "ine": usa preço INE (freguesia × trimestre) × área
      - "max_comp_ine": usa o maior dos dois (mais conservador para o vendedor)
    """
    modo = inputs.venda_modo
    detail = {"modo": modo}

    if modo == "manual":
        detail["preco_venda"] = inputs.preco_venda_manual
        detail["origem"] = "manual"
        return detail

    # Comparáveis
    venda_comp = None
    if inputs.comparaveis and inputs.area_m2 > 0:
        r = Cmp.estimar_preco_venda(
            inputs.comparaveis,
            inputs.area_m2,
            inputs.factor_ajuste_comparaveis,
        )
        venda_comp = r["preco_venda"]
        detail["comparaveis"] = r

    # INE
    venda_ine = None
    if inputs.freguesia and inputs.area_m2 > 0:
        r = INE.get_preco_m2(inputs.freguesia, inputs.ine_trimestre)
        if r is not None:
            venda_ine = r["preco_m2"] * inputs.area_m2
            detail["ine"] = {**r, "preco_venda": venda_ine}

    # Decisão
    if modo == "comparaveis" and venda_comp is not None:
        detail["preco_venda"] = venda_comp
        detail["origem"] = "comparaveis"
    elif modo == "ine" and venda_ine is not None:
        detail["preco_venda"] = venda_ine
        detail["origem"] = "ine"
    elif modo == "max_comp_ine":
        candidatos = [v for v in (venda_comp, venda_ine) if v is not None]
        if candidatos:
            detail["preco_venda"] = max(candidatos)
            detail["origem"] = "max(comp,ine)"
        else:
            detail["preco_venda"] = inputs.preco_venda_manual
            detail["origem"] = "fallback_manual"
    else:
        detail["preco_venda"] = inputs.preco_venda_manual
        detail["origem"] = "fallback_manual"

    return detail


# ---------------------------------------------------------------------------
# Amortização (sistema francês)
# ---------------------------------------------------------------------------

def amortizacao_juros_simplificada(
    capital: float,
    taxa_anual: float,
    prazo_anos: int,
    meses_pagos: int,
) -> tuple[float, float]:
    if capital <= 0 or taxa_anual <= 0:
        return 0.0, capital

    n_total = prazo_anos * 12
    i = taxa_anual / 12
    prestacao = capital * (i * (1 + i) ** n_total) / ((1 + i) ** n_total - 1)

    juros_total = 0.0
    saldo = capital
    for _ in range(min(meses_pagos, n_total)):
        juros_mes = saldo * i
        amort_mes = prestacao - juros_mes
        juros_total += juros_mes
        saldo -= amort_mes

    return juros_total, max(saldo, 0.0)


# ---------------------------------------------------------------------------
# Cálculo principal
# ---------------------------------------------------------------------------

def calcular_ff(inputs: FFInputs) -> FFOutputs:
    out = FFOutputs()
    bd = {}

    # ---- 1. CUSTOS DE AQUISIÇÃO
    imt_calc = T.calcular_imt(
        valor_aquisicao=inputs.preco_aquisicao,
        vpt=inputs.vpt,
        tipo=inputs.tipo_imt,
        isento_revenda=inputs.isencao_imt_revenda,
    )
    out.imt = imt_calc["imt"]
    bd["imt"] = imt_calc

    is_calc = T.calcular_is_transmissao(inputs.preco_aquisicao, inputs.vpt)
    out.is_transmissao = is_calc["is"]
    bd["is"] = is_calc

    out.custos_compra_total = (
        inputs.preco_aquisicao
        + out.imt
        + out.is_transmissao
        + inputs.custos_notario_registo
        + inputs.custos_due_diligence
    )

    # ---- 2. OBRA (auto ou manual)
    if inputs.obra_modo == "auto":
        obra_calc = estimar_custo_obra(inputs.area_m2, inputs.estado_conservacao)
        out.obra_sem_iva = obra_calc["custo_sem_iva"]
        bd["obra_estimativa"] = obra_calc
    else:
        out.obra_sem_iva = inputs.custo_obra_sem_iva_manual
        bd["obra_estimativa"] = {"modo": "manual", "custo_sem_iva": out.obra_sem_iva}

    iva_calc = T.iva_obra(out.obra_sem_iva, inputs.regime_iva_obra)
    out.obra_com_iva = iva_calc["obra_com_iva"]
    out.obra_com_contingencia = out.obra_com_iva * (1 + inputs.contingencia_obra_pct)
    bd["obra_iva"] = iva_calc

    # ---- 3. FINANCIAMENTO
    if inputs.usa_financiamento:
        out.valor_emprestimo = inputs.preco_aquisicao * inputs.ltv
        out.equity_aquisicao = out.custos_compra_total - out.valor_emprestimo
        juros, _ = amortizacao_juros_simplificada(
            out.valor_emprestimo, inputs.taxa_juro_anual,
            inputs.prazo_anos, inputs.ciclo_meses,
        )
        out.juros_pagos_ciclo = juros + inputs.comissoes_abertura
    else:
        out.valor_emprestimo = 0.0
        out.equity_aquisicao = out.custos_compra_total
        out.juros_pagos_ciclo = 0.0

    out.equity_obra = out.obra_com_contingencia
    out.equity_total = out.equity_aquisicao + out.equity_obra

    # ---- 4. HOLDING
    imi_calc = T.calcular_imi_ciclo(inputs.vpt, inputs.ciclo_meses, inputs.taxa_imi)
    out.imi_ciclo = imi_calc["imi_total_ciclo"]
    out.custos_holding_total = inputs.custos_holding_mensais * inputs.ciclo_meses
    out.seguros_ciclo = (
        inputs.seguros_anuais * (inputs.ciclo_meses / 12)
        if inputs.usa_financiamento else 0
    )

    # ---- 5. ESTIMATIVA DE VENDA
    venda_calc = estimar_preco_venda(inputs)
    out.preco_venda_usado = venda_calc.get("preco_venda", 0) or 0
    out.preco_venda_origem = venda_calc.get("origem", "")
    bd["venda_estimativa"] = venda_calc

    if inputs.area_m2 > 0:
        out.preco_m2_venda = out.preco_venda_usado / inputs.area_m2
        out.preco_m2_compra = inputs.preco_aquisicao / inputs.area_m2

    # ---- 6. CUSTOS VENDA
    comissao = out.preco_venda_usado * inputs.comissao_imobiliaria_pct
    if inputs.comissao_imobiliaria_iva:
        comissao *= (1 + C.IVA_NORMAL)
    out.custos_venda = comissao
    out.receita_venda_liquida = out.preco_venda_usado - out.custos_venda

    # ---- 7. LUCRO BRUTO (cash basis)
    cash_out = (
        out.equity_total
        + out.juros_pagos_ciclo
        + out.imi_ciclo
        + out.custos_holding_total
        + out.seguros_ciclo
    )
    cash_in = out.receita_venda_liquida - out.valor_emprestimo
    out.lucro_bruto = cash_in - cash_out

    # ---- 8. IMPOSTO SAÍDA
    if inputs.estrutura == "lda":
        imp = T.imposto_saida_lda(out.lucro_bruto, inputs.derrama_municipal)
        out.imposto_saida = imp["imposto_total"]
    else:
        encargos = (
            out.imt + out.is_transmissao + inputs.custos_notario_registo
            + out.obra_com_contingencia + out.custos_venda
        )
        imp = T.imposto_saida_pf(
            out.preco_venda_usado, inputs.preco_aquisicao, encargos
        )
        out.imposto_saida = imp["imposto"]
    bd["imposto_saida"] = imp

    out.lucro_liquido = out.lucro_bruto - out.imposto_saida

    # ---- 9. KPIs
    out.margem_absoluta = out.lucro_liquido
    out.roi_total = (
        out.lucro_liquido / out.equity_total if out.equity_total > 0 else 0.0
    )
    out.margem_bruta_pct_venda = (
        out.lucro_liquido / out.preco_venda_usado if out.preco_venda_usado > 0 else 0.0
    )
    out.cash_on_cash_anual = (
        out.roi_total * (12 / inputs.ciclo_meses) if inputs.ciclo_meses > 0 else 0.0
    )
    if out.equity_total > 0 and inputs.ciclo_meses > 0:
        anos = inputs.ciclo_meses / 12
        if out.lucro_liquido > -out.equity_total:
            mult = (out.equity_total + out.lucro_liquido) / out.equity_total
            out.irr_aproximado = mult ** (1 / anos) - 1
        else:
            out.irr_aproximado = -1.0

    out.custo_total_operacao = (
        out.custos_compra_total + out.obra_com_contingencia + out.juros_pagos_ciclo
        + out.imi_ciclo + out.custos_holding_total + out.seguros_ciclo + out.custos_venda
    )

    out.breakdown = bd
    return out


# ---------------------------------------------------------------------------
# Simulação: preço máximo de aquisição para atingir um ROI alvo
# ---------------------------------------------------------------------------

def preco_max_aquisicao(inputs: FFInputs, roi_alvo: float) -> dict:
    """
    Dado um ROI alvo e o resto dos parâmetros, devolve o preço máximo a pagar
    para atingir esse ROI. Faz busca binária porque os custos (IMT, etc.)
    dependem do próprio preço.
    """
    base_out = calcular_ff(inputs)
    venda = base_out.preco_venda_usado
    if venda <= 0:
        return {"erro": "Sem preço de venda estimado"}

    # Busca binária: preço entre 0 e venda
    lo, hi = 0.0, venda
    melhor = None
    for _ in range(40):
        meio = (lo + hi) / 2
        test = FFInputs(**{**asdict(inputs), "preco_aquisicao": meio,
                            "comparaveis": inputs.comparaveis})
        # Se o user usa modo manual de venda, o preço de venda não muda com aquisição.
        # Se usa comparáveis/INE, também não muda. OK.
        r = calcular_ff(test)
        if r.roi_total < roi_alvo:
            hi = meio
        else:
            lo = meio
            melhor = (meio, r)

    if melhor is None:
        return {
            "roi_alvo": roi_alvo,
            "preco_max": 0.0,
            "lucro_liquido": 0.0,
            "roi_obtido": 0.0,
            "erro": "Não atingível com estes parâmetros",
        }

    preco, r = melhor
    return {
        "roi_alvo": roi_alvo,
        "preco_max": preco,
        "lucro_liquido": r.lucro_liquido,
        "roi_obtido": r.roi_total,
        "custo_total": r.custo_total_operacao,
        "equity": r.equity_total,
    }


def tabela_preco_max_aquisicao(inputs: FFInputs) -> list[dict]:
    """Aplica preco_max_aquisicao para todos os ROIs alvo de SIMULACAO_ROI_ALVOS."""
    rows = []
    for roi in C.SIMULACAO_ROI_ALVOS:
        rows.append(preco_max_aquisicao(inputs, roi))
    return rows


# ---------------------------------------------------------------------------
# Helper para serialização (compatível com persistence)
# ---------------------------------------------------------------------------

def to_dict(inputs: FFInputs, outputs: FFOutputs) -> dict:
    return {
        "inputs": asdict(inputs),
        "outputs": asdict(outputs),
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Replicar o exemplo do Excel: Olivais T1, 77m², bom estado, isento IMT,
    # 250k pedido, comparáveis T2 a 4838/5339/4805 €/m².
    deal = FFInputs(
        nome_deal="T1 Olivais (Excel ref)",
        freguesia="Lisboa - Olivais",
        tipo_imovel="Apartamento",
        tipologia="T1",
        area_m2=77,
        estado_conservacao="Bom",
        vendedor="Particular",
        preco_aquisicao=250_000,
        vpt=200_000,
        tipo_imt="secundaria",
        isencao_imt_revenda=True,
        custos_notario_registo=800,
        usa_financiamento=False,
        obra_modo="auto",  # estado=Bom → 0 €/m²
        ciclo_meses=6,
        custos_holding_mensais=100,  # 600€ no Excel → 100/mês × 6
        venda_modo="comparaveis",
        comparaveis=[
            {"url": "...", "preco": 300_000, "area_m2": 62, "tipologia": "T2"},
            {"url": "...", "preco": 299_000, "area_m2": 56, "tipologia": "T2"},
            {"url": "...", "preco": 370_000, "area_m2": 77, "tipologia": "T2"},
        ],
        factor_ajuste_comparaveis="Bastante acima da revenda",  # 0.90
        estrutura="lda",
    )

    r = calcular_ff(deal)
    print(f"\n--- {deal.nome_deal} ---")
    print(f"Área: {deal.area_m2}m² | Tipologia: {deal.tipologia}")
    print(f"Preço/m² compra: {r.preco_m2_compra:.0f} €/m²")
    print(f"Preço/m² venda: {r.preco_m2_venda:.0f} €/m²")
    print(f"Preço venda usado: {r.preco_venda_usado:,.0f} € ({r.preco_venda_origem})")
    print(f"Custo total operação: {r.custo_total_operacao:,.0f} €")
    print(f"Lucro bruto: {r.lucro_bruto:,.0f} €")
    print(f"Imposto saída: {r.imposto_saida:,.0f} €")
    print(f"Lucro líquido: {r.lucro_liquido:,.0f} €")
    print(f"ROI total: {r.roi_total*100:.1f} %")
    print(f"Margem bruta (% venda): {r.margem_bruta_pct_venda*100:.1f} %")

    # Excel exemplo: Lucro 72.694, ROI 28.7%, ROI anual 57.4%
    print(f"\nExpected (Excel): Lucro ~72.694€, ROI ~28.7%")

    # Simulação preço máx
    print("\n--- Simulação preço máximo de aquisição ---")
    for r in tabela_preco_max_aquisicao(deal):
        if "erro" in r:
            print(f"  ROI {r['roi_alvo']*100:.0f}%: {r['erro']}")
        else:
            print(f"  ROI {r['roi_alvo']*100:.0f}%: max {r['preco_max']:,.0f} € → lucro {r['lucro_liquido']:,.0f} €")
