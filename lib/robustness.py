"""
Análise de robustez (stress tests + veredicto).

Aplica deltas a:
  - Preço de venda (forçando venda_modo="manual" + override)
  - Ciclo (meses)
  - Custo obra (forçando obra_modo="manual" + override)

Devolve flags + veredicto VERDE/AMARELO/VERMELHO.
"""

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from . import engine as E
from . import constants as C


def _forcar_manual_venda(inputs: E.FFInputs, novo_preco: float) -> E.FFInputs:
    """Devolve cópia dos inputs com venda fixada em manual ao preço dado."""
    m = deepcopy(inputs)
    m.venda_modo = "manual"
    m.preco_venda_manual = novo_preco
    return m


def _forcar_manual_obra(inputs: E.FFInputs, novo_custo: float) -> E.FFInputs:
    """Devolve cópia com obra fixada em manual ao custo dado."""
    m = deepcopy(inputs)
    m.obra_modo = "manual"
    m.custo_obra_sem_iva_manual = novo_custo
    return m


# ---------------------------------------------------------------------------
# Stress tests
# ---------------------------------------------------------------------------

def stress_preco_venda(inputs: E.FFInputs) -> list[dict]:
    """Reduz o preço de venda em -5%, -10%, -15%."""
    base = E.calcular_ff(inputs)
    preco_base = base.preco_venda_usado
    rows = [{
        "cenario": "Base",
        "preco_venda": preco_base,
        "lucro_liquido": base.lucro_liquido,
        "roi_total": base.roi_total,
    }]
    for delta in C.STRESS_PRECO_VENDA:
        novo = preco_base * (1 + delta)
        out = E.calcular_ff(_forcar_manual_venda(inputs, novo))
        rows.append({
            "cenario": f"Venda {int(delta*100)}%",
            "preco_venda": novo,
            "lucro_liquido": out.lucro_liquido,
            "roi_total": out.roi_total,
        })
    return rows


def stress_ciclo(inputs: E.FFInputs) -> list[dict]:
    """Aumenta o ciclo em +3, +6 meses."""
    base = E.calcular_ff(inputs)
    rows = [{
        "cenario": "Base",
        "ciclo_meses": inputs.ciclo_meses,
        "lucro_liquido": base.lucro_liquido,
        "roi_total": base.roi_total,
        "cash_on_cash_anual": base.cash_on_cash_anual,
    }]
    for extra in C.STRESS_CICLO_MESES:
        m = deepcopy(inputs)
        m.ciclo_meses = inputs.ciclo_meses + extra
        out = E.calcular_ff(m)
        rows.append({
            "cenario": f"Ciclo +{extra}m",
            "ciclo_meses": m.ciclo_meses,
            "lucro_liquido": out.lucro_liquido,
            "roi_total": out.roi_total,
            "cash_on_cash_anual": out.cash_on_cash_anual,
        })
    return rows


def stress_obra(inputs: E.FFInputs) -> list[dict]:
    """Aumenta o custo de obra em +20%, +40%."""
    base = E.calcular_ff(inputs)
    obra_base = base.obra_sem_iva
    rows = [{
        "cenario": "Base",
        "obra_sem_iva": obra_base,
        "lucro_liquido": base.lucro_liquido,
        "roi_total": base.roi_total,
    }]
    for delta in C.STRESS_OBRA_PCT:
        novo = obra_base * (1 + delta)
        out = E.calcular_ff(_forcar_manual_obra(inputs, novo))
        rows.append({
            "cenario": f"Obra +{int(delta*100)}%",
            "obra_sem_iva": novo,
            "lucro_liquido": out.lucro_liquido,
            "roi_total": out.roi_total,
        })
    return rows


def stress_combinado_pessimista(inputs: E.FFInputs) -> dict:
    """V−10% + ciclo+6m + obra+40%."""
    base = E.calcular_ff(inputs)
    m = deepcopy(inputs)
    m.venda_modo = "manual"
    m.preco_venda_manual = base.preco_venda_usado * 0.90
    m.ciclo_meses = inputs.ciclo_meses + 6
    m.obra_modo = "manual"
    m.custo_obra_sem_iva_manual = base.obra_sem_iva * 1.40

    out = E.calcular_ff(m)
    return {
        "cenario": "Pessimista combinado (V-10% / Ciclo+6m / Obra+40%)",
        "lucro_liquido": out.lucro_liquido,
        "roi_total": out.roi_total,
        "equity_total": out.equity_total,
        "perda_pct_equity": (
            -out.lucro_liquido / out.equity_total
            if out.lucro_liquido < 0 and out.equity_total > 0 else 0
        ),
    }


# ---------------------------------------------------------------------------
# Flags + veredicto
# ---------------------------------------------------------------------------

def _fmt(v):
    return f"{v:,.0f}€".replace(",", " ")


def avaliar_flags(out: E.FFOutputs, inputs: E.FFInputs) -> list[dict]:
    flags = []

    # ROI
    if out.roi_total >= C.TARGET_ROI_FIXANDFLIP:
        flags.append({"id": "roi", "nivel": "ok",
                      "mensagem": f"ROI total {out.roi_total*100:.1f}% acima do target {C.TARGET_ROI_FIXANDFLIP*100:.0f}%."})
    elif out.roi_total >= C.TARGET_ROI_FIXANDFLIP * 0.75:
        flags.append({"id": "roi", "nivel": "amarelo",
                      "mensagem": f"ROI total {out.roi_total*100:.1f}% abaixo do target ({C.TARGET_ROI_FIXANDFLIP*100:.0f}%) mas acima de 75%."})
    else:
        flags.append({"id": "roi", "nivel": "vermelho",
                      "mensagem": f"ROI total {out.roi_total*100:.1f}% bem abaixo do target ({C.TARGET_ROI_FIXANDFLIP*100:.0f}%)."})

    # Margem absoluta
    if out.margem_absoluta >= C.TARGET_MARGEM_ABS_MIN:
        flags.append({"id": "margem", "nivel": "ok",
                      "mensagem": f"Margem absoluta {_fmt(out.margem_absoluta)} acima do mínimo {_fmt(C.TARGET_MARGEM_ABS_MIN)}."})
    elif out.margem_absoluta > 0:
        flags.append({"id": "margem", "nivel": "amarelo",
                      "mensagem": f"Margem absoluta {_fmt(out.margem_absoluta)} abaixo do mínimo. Margem fina protege mal contra surpresas."})
    else:
        flags.append({"id": "margem", "nivel": "vermelho",
                      "mensagem": f"Margem negativa: {_fmt(out.margem_absoluta)}."})

    # Ciclo
    if inputs.ciclo_meses <= C.TARGET_CICLO_MAX_MESES:
        flags.append({"id": "ciclo", "nivel": "ok",
                      "mensagem": f"Ciclo {inputs.ciclo_meses} meses dentro do limite {C.TARGET_CICLO_MAX_MESES}m."})
    elif inputs.ciclo_meses <= C.TARGET_CICLO_MAX_MESES + 6:
        flags.append({"id": "ciclo", "nivel": "amarelo",
                      "mensagem": f"Ciclo {inputs.ciclo_meses}m acima do alvo. Custo de oportunidade do equity sobe."})
    else:
        flags.append({"id": "ciclo", "nivel": "vermelho",
                      "mensagem": f"Ciclo {inputs.ciclo_meses}m demasiado longo."})

    # Stress combinado
    pess = stress_combinado_pessimista(inputs)
    if pess["lucro_liquido"] >= 0:
        flags.append({"id": "stress", "nivel": "ok",
                      "mensagem": f"Cenário pessimista combinado ainda dá positivo ({_fmt(pess['lucro_liquido'])})."})
    elif pess["perda_pct_equity"] < 0.20:
        flags.append({"id": "stress", "nivel": "amarelo",
                      "mensagem": f"Cenário pessimista perde {_fmt(pess['lucro_liquido'])} ({pess['perda_pct_equity']*100:.1f}% do equity)."})
    else:
        flags.append({"id": "stress", "nivel": "vermelho",
                      "mensagem": f"Cenário pessimista destrói {pess['perda_pct_equity']*100:.1f}% do equity ({_fmt(pess['lucro_liquido'])})."})

    # VPT vs preço
    if inputs.vpt > inputs.preco_aquisicao * 1.05 and inputs.preco_aquisicao > 0:
        flags.append({"id": "vpt", "nivel": "amarelo",
                      "mensagem": f"VPT ({_fmt(inputs.vpt)}) acima do preço ({_fmt(inputs.preco_aquisicao)}). IMT/IS calculados sobre VPT."})

    # Comissão imobiliária
    if inputs.comissao_imobiliaria_pct > 0.06:
        flags.append({"id": "comissao", "nivel": "amarelo",
                      "mensagem": f"Comissão {inputs.comissao_imobiliaria_pct*100:.1f}% acima do mercado típico (5%)."})

    # Preço/m² compra vs INE (se freguesia conhecida)
    if inputs.area_m2 > 0 and inputs.freguesia:
        from . import ine as INE
        info = INE.get_preco_m2(inputs.freguesia, inputs.ine_trimestre)
        if info:
            preco_m2_compra = inputs.preco_aquisicao / inputs.area_m2
            ratio = preco_m2_compra / info["preco_m2"]
            if ratio > 0.95:
                flags.append({"id": "compra_ine", "nivel": "amarelo",
                              "mensagem": f"Preço/m² compra ({preco_m2_compra:.0f}) está {(ratio-1)*100:+.0f}% vs INE ({info['preco_m2']}). Pouco desconto sobre mercado."})
            elif ratio < 0.65:
                flags.append({"id": "compra_ine", "nivel": "ok",
                              "mensagem": f"Preço/m² compra ({preco_m2_compra:.0f}) é {(ratio-1)*100:+.0f}% vs INE ({info['preco_m2']}). Desconto significativo."})

    return flags


def veredicto_global(flags: list[dict]) -> dict:
    if any(f["nivel"] == "vermelho" for f in flags):
        return {"cor": "vermelho", "rotulo": "REJEITAR ou renegociar",
                "mensagem": "Pelo menos uma métrica falha de forma material. Não avançar sem renegociar termos.",
                "n_flags_vermelhos": sum(1 for f in flags if f["nivel"] == "vermelho"),
                "n_flags_amarelos": sum(1 for f in flags if f["nivel"] == "amarelo"),
                "n_flags_ok": sum(1 for f in flags if f["nivel"] == "ok")}
    if any(f["nivel"] == "amarelo" for f in flags):
        return {"cor": "amarelo", "rotulo": "Cautela — analisar trade-offs",
                "mensagem": "Há sinais que pedem segunda análise. Pode passar, mas com olho aberto.",
                "n_flags_vermelhos": 0,
                "n_flags_amarelos": sum(1 for f in flags if f["nivel"] == "amarelo"),
                "n_flags_ok": sum(1 for f in flags if f["nivel"] == "ok")}
    return {"cor": "verde", "rotulo": "Avançar (sem complacência)",
            "mensagem": "Métricas alinham com o playbook. Stress test sobrevive. Avançar com diligência normal.",
            "n_flags_vermelhos": 0, "n_flags_amarelos": 0,
            "n_flags_ok": sum(1 for f in flags if f["nivel"] == "ok")}


def analise_completa(inputs: E.FFInputs) -> dict:
    out = E.calcular_ff(inputs)
    flags = avaliar_flags(out, inputs)
    return {
        "inputs": asdict(inputs),
        "outputs": asdict(out),
        "stress_preco": stress_preco_venda(inputs),
        "stress_ciclo": stress_ciclo(inputs),
        "stress_obra": stress_obra(inputs),
        "stress_pessimista": stress_combinado_pessimista(inputs),
        "flags": flags,
        "veredicto": veredicto_global(flags),
    }
